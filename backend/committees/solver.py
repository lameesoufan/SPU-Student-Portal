"""
CP-SAT based committee scheduler using Google OR-Tools.

This module exposes a single entry point `run_solver()` that takes a
committee_type, semester, and SolverSettings, builds a CP-SAT model,
solves it, and returns either:
  - {success: True, plan, summary_stats, solver_status, wall_time}
  - {success: False, infeasibility_report: [...]}

The model handles ONE committee_type at a time (per the dean's requirement:
seminar_1, seminar_2, technical, final_discussion are scheduled in
independent weeks so they never conflict with each other).

Constraints (hard):
  1. Each committee must be scheduled within workdays and daily work window.
  2. No two committees in the same room at overlapping times (NoOverlap per room).
  3. No two committees with the same doctor at overlapping times (NoOverlap per doctor).
  4. Doctor availability: a committee with doctor X must be on a date whose
     weekday is in X's weekly availability, AND not in X's blocked exceptions.
  5. Each committee must be scheduled entirely within one workday.

Soft constraints (objective):
  - Minimize doctor load imbalance (max_load - min_load) with weight 50.
  - Minimize number of distinct days used with weight 10.

The committee's actual discussion duration is computed as:
  duration = projects_count × discussion_duration

The configured buffer is modeled separately as resource-occupancy time. It
prevents back-to-back committees that share a room or doctor, without extending
the committee's displayed/saved end time.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from typing import Optional

from django.db import transaction
from django.utils import timezone

from ortools.sat.python import cp_model

from .models import (
    Committee, Room, DoctorWeeklyAvailability, DoctorDateException,
    SolverSettings, SchedulingRun,
    COMMITTEE_TYPE_AR, WEEKDAYS_AR,
)

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _time_to_minutes(t: time) -> int:
    """Convert a time object to minutes since midnight."""
    return t.hour * 60 + t.minute


def _date_range(start: date, end: date):
    """Yield each date from start to end inclusive."""
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def _committee_duration_minutes(committee: Committee, settings: SolverSettings) -> Optional[int]:
    """Return the committee's actual discussion duration in minutes.

    The inter-committee buffer is deliberately excluded. It is represented by
    separate occupancy intervals in the CP-SAT model, so it creates a gap
    between conflicting committees without changing their displayed end time.
    """
    # Priority: settings.discussion_duration (from form) > committee.discussion_duration (DB) > 15 (default)
    duration_per_project = getattr(settings, 'discussion_duration', None) or committee.discussion_duration or 15
    projects_count = committee.projects_count
    return projects_count * duration_per_project


def _committee_occupancy_minutes(committee: Committee, settings: SolverSettings) -> Optional[int]:
    """Return resource occupancy duration: discussion time plus trailing buffer."""
    duration = _committee_duration_minutes(committee, settings)
    if duration is None:
        return None
    return duration + max(0, settings.buffer_between_committees_minutes or 0)



def _build_solver_caches(
    committees: list[Committee],
    dates: list[date],
) -> tuple[
    dict[int, set[int]],
    set[int],
    dict[int, list[date]],
    dict[int, str],
    set[int],
]:
    """Build database-backed lookup tables once before creating constraints.

    `members.all()` uses Django's prefetch cache, unlike repeated
    `values_list()` calls. Weekly availability and date exceptions are loaded
    with two bulk queries, then converted to per-doctor available-date lists in
    memory.
    """
    committee_doctors: dict[int, set[int]] = {}
    doctor_names: dict[int, str] = {}

    for committee in committees:
        doctor_ids: set[int] = set()

        if committee.chair_id:
            doctor_ids.add(committee.chair_id)
            if committee.chair is not None:
                doctor_names[committee.chair_id] = (
                    committee.chair.get_full_name() or committee.chair.username
                )

        # This uses the prefetch_related('members') result already in memory.
        for member in committee.members.all():
            doctor_ids.add(member.id)
            doctor_names[member.id] = member.get_full_name() or member.username

        committee_doctors[committee.id] = doctor_ids

    all_doctors: set[int] = set().union(*committee_doctors.values()) if committee_doctors else set()

    weekly_by_doctor: dict[int, set[int]] = {doctor_id: set() for doctor_id in all_doctors}
    for doctor_id, weekday in DoctorWeeklyAvailability.objects.filter(
        doctor_id__in=all_doctors
    ).values_list('doctor_id', 'weekday'):
        weekly_by_doctor[doctor_id].add(weekday)

    blocked_by_doctor: dict[int, set[date]] = {doctor_id: set() for doctor_id in all_doctors}
    override_by_doctor: dict[int, set[date]] = {doctor_id: set() for doctor_id in all_doctors}
    doctors_with_exceptions: set[int] = set()

    for doctor_id, exception_date, exception_type in DoctorDateException.objects.filter(
        doctor_id__in=all_doctors
    ).values_list('doctor_id', 'date', 'exception_type'):
        doctors_with_exceptions.add(doctor_id)
        if exception_type == 'blocked':
            blocked_by_doctor[doctor_id].add(exception_date)
        elif exception_type == 'available':
            override_by_doctor[doctor_id].add(exception_date)

    doctors_with_rules = {
        doctor_id
        for doctor_id in all_doctors
        if weekly_by_doctor[doctor_id] or doctor_id in doctors_with_exceptions
    }

    doctor_available_dates: dict[int, list[date]] = {}
    for doctor_id in all_doctors:
        weekly_weekdays = weekly_by_doctor[doctor_id]
        blocked_dates = blocked_by_doctor[doctor_id]
        available_overrides = override_by_doctor[doctor_id]

        if doctor_id not in doctors_with_rules:
            doctor_available_dates[doctor_id] = list(dates)
            continue

        available: list[date] = []
        for current_date in dates:
            if current_date in available_overrides:
                available.append(current_date)
            elif current_date in blocked_dates:
                continue
            elif weekly_weekdays:
                if current_date.weekday() in weekly_weekdays:
                    available.append(current_date)
            else:
                available.append(current_date)

        doctor_available_dates[doctor_id] = available

    return (
        committee_doctors,
        all_doctors,
        doctor_available_dates,
        doctor_names,
        doctors_with_rules,
    )


# ── Infeasibility report builder ─────────────────────────────────────────────

def _build_infeasibility_report(
    committees: list[Committee],
    rooms: list[Room],
    dates: list[date],
    settings: SolverSettings,
    *,
    committee_doctors: Optional[dict[int, set[int]]] = None,
    doctor_names: Optional[dict[int, str]] = None,
    doctors_with_rules: Optional[set[int]] = None,
) -> list[dict]:
    """Return a list of Arabic-language infeasibility reason dicts."""
    report: list[dict] = []
    committee_type_ar = COMMITTEE_TYPE_AR.get(settings.committee_type, settings.committee_type)

    # 1) Committees without discussion_duration — NOT an error anymore
    # The Solver will default to 15 minutes if missing.
    missing_duration = [c for c in committees if not c.discussion_duration]
    if missing_duration:
        report.append({
            'code': 'defaulting_discussion_duration',
            'level': 'info',  # info — not blocking
            'message_ar': (
                f'{len(missing_duration)} لجنة من نوع "{committee_type_ar}" ليس لها مدة مناقشة محددة. '
                f'سيتم استخدام المدة الافتراضية (15 دقيقة).'
            ),
            'committee_ids': [c.id for c in missing_duration],
            'suggestions_ar': [
                'يمكنك تحديد مدة مختلفة من صفحة التشكيلات',
            ],
        })

    # 2) No rooms available
    if not rooms:
        report.append({
            'code': 'no_rooms',
            'level': 'error',
            'message_ar': 'لا توجد قاعات فعّالة. أضف قاعات من صفحة القاعات أولاً.',
            'suggestions_ar': ['أضف قاعة واحدة على الأقل'],
        })

    # 3) No dates in range matching workdays
    if not dates:
        report.append({
            'code': 'no_workdays',
            'level': 'error',
            'message_ar': (
                f'لا توجد أيام عمل ضمن النطاق {settings.date_range_start} - {settings.date_range_end} '
                f'تطابق أيام الأسبوع المختارة.'
            ),
            'suggestions_ar': [
                'وسّع نطاق التواريخ',
                'أضف أيام عمل أخرى في إعدادات الـ Solver',
            ],
        })

    # 4) Capacity check (rough estimate)
    if committees and rooms and dates:
        # Capacity includes the required gap between committees, while the
        # committee's saved/displayed duration does not.
        total_minutes_needed = sum(
            _committee_occupancy_minutes(c, settings) or 0
            for c in committees
        )
        daily_minutes = _time_to_minutes(settings.daily_end) - _time_to_minutes(settings.daily_start)
        total_minutes_available = len(rooms) * len(dates) * daily_minutes
        if total_minutes_needed > total_minutes_available:
            report.append({
                'code': 'insufficient_capacity',
                'level': 'error',
                'message_ar': (
                    f'السعة غير كافية. مطلوب {total_minutes_needed} دقيقة جدولة، '
                    f'متاح {total_minutes_available} دقيقة نظرياً '
                    f'({len(rooms)} قاعة × {len(dates)} يوم × {daily_minutes} دقيقة/يوم).'
                ),
                'suggestions_ar': [
                    'إضافة قاعات',
                    'توسيع نطاق التواريخ',
                    'زيادة ساعات العمل اليومية',
                ],
            })

    # 5) Doctors without any weekly availability — NOT an error anymore.
    # The normal solver path supplies caches, so this block performs no queries.
    committee_doctors = committee_doctors or {
        committee.id: ({committee.chair_id} if committee.chair_id else set())
        | {member.id for member in committee.members.all()}
        for committee in committees
    }
    doctor_names = doctor_names or {}
    all_doctors = set().union(*committee_doctors.values()) if committee_doctors else set()

    if doctors_with_rules is None:
        weekly_doctors = set(
            DoctorWeeklyAvailability.objects.filter(
                doctor_id__in=all_doctors
            ).values_list('doctor_id', flat=True)
        )
        exception_doctors = set(
            DoctorDateException.objects.filter(
                doctor_id__in=all_doctors
            ).values_list('doctor_id', flat=True)
        )
        doctors_with_rules = weekly_doctors | exception_doctors

    doctors_no_availability = [
        {
            'doctor_id': doctor_id,
            'doctor_name': doctor_names.get(doctor_id, f'#{doctor_id}'),
        }
        for doctor_id in sorted(all_doctors - doctors_with_rules)
    ]

    if doctors_no_availability:
        report.append({
            'code': 'doctor_default_available',
            'level': 'info',
            'message_ar': (
                f'{len(doctors_no_availability)} دكتور بدون توفر أسبوعي مسجّل '
                f'({", ".join(d["doctor_name"] for d in doctors_no_availability)}). '
                f'سيُعتبرون متاحين في كل أيام الأسبوع افتراضياً.'
            ),
            'doctors': doctors_no_availability,
            'suggestions_ar': [
                'يمكنك تحديد التوفر الأسبوعي لهؤلاء الدكاترة لتقييد الجدولة',
                'أو تركهم كما هم — سيتوفرون في كل الأيام',
            ],
        })

    # NOTE: doctor_overload check was REMOVED per dean decision —
    # the dean does NOT want a hard max-committees-per-doctor limit.
    # The Solver will distribute committees freely across available days
    # and rooms, and doctors will be scheduled as needed.

    return report


# ── Main solver entry point ──────────────────────────────────────────────────

def run_solver(
    *,
    committee_type: str,
    semester: str,
    settings: SolverSettings,
    requested_by=None,
) -> dict:
    """Run CP-SAT solver for the given committee_type × semester.

    Returns:
        {
            success: True,
            solver_status: 'OPTIMAL' | 'FEASIBLE',
            wall_time: float,
            plan: {committee_type, semester, assignments: [...]},
            summary_stats: {...},
        }
    OR
        {
            success: False,
            infeasibility_report: [...],
        }
    """
    # ── 1. Collect data ────────────────────────────────────────────────────
    committees = list(
        Committee.objects
        .filter(committee_type=committee_type)
        .select_related('chair', 'template')
        .prefetch_related('members', 'applications', 'proposals')
    )

    # ── Early exit if no committees ──
    # If there are no committees of this type, return a clear error
    if not committees:
        return {
            'success': False,
            'infeasibility_report': [{
                'code': 'no_committees',
                'level': 'error',
                'message_ar': (
                    f'لا توجد لجان من نوع "{COMMITTEE_TYPE_AR.get(committee_type, committee_type)}" '
                    'تأكد من تشغيل التوزيع (Distribute) أولاً لكل المشاريع الحالية.'
                ),
                'suggestions_ar': [
                    'اذهب إلى صفحة Committees Dashboard واضغط Distribute Projects',
                    'تأكد من وجود تشكيلات (Templates) للنوع المطلوب',
                ],
            }],
        }

    rooms = list(Room.objects.filter(is_active=True))

    workday_ints = set(settings.workdays or [])
    dates = [
        d for d in _date_range(settings.date_range_start, settings.date_range_end)
        if d.weekday() in workday_ints
    ]
    date_to_index = {current_date: index for index, current_date in enumerate(dates)}

    (
        committee_doctors,
        all_doctors,
        doctor_available_dates,
        doctor_name_cache,
        doctors_with_rules,
    ) = _build_solver_caches(committees, dates)

    # ── 2. Pre-flight infeasibility checks ─────────────────────────────────
    # Only `error`-level items block scheduling. `warn` and `info` are
    # non-blocking — they're surfaced to the dean as warnings/tips.
    pre_report = _build_infeasibility_report(
        committees,
        rooms,
        dates,
        settings,
        committee_doctors=committee_doctors,
        doctor_names=doctor_name_cache,
        doctors_with_rules=doctors_with_rules,
    )
    blocking_report = [r for r in pre_report if r.get('level') == 'error']
    if blocking_report:
        return {
            'success': False,
            'infeasibility_report': blocking_report,
            'warnings': [r for r in pre_report if r.get('level') != 'error'],
        }

    # ── 3. Compute per-committee durations ────────────────────────────────
    durations = {}
    occupancy_durations = {}
    for c in committees:
        d = _committee_duration_minutes(c, settings)
        if d is None:
            # Already reported above; defensive check
            return {
                'success': False,
                'infeasibility_report': [{
                    'code': 'missing_discussion_duration',
                    'level': 'error',
                    'message_ar': f'اللجنة #{c.id} لا تملك discussion_duration.',
                }],
            }
        durations[c.id] = d
        occupancy_durations[c.id] = _committee_occupancy_minutes(c, settings)

    # ── 4. Build CP-SAT model ──────────────────────────────────────────────
    model = cp_model.CpModel()

    daily_start_min = _time_to_minutes(settings.daily_start)
    daily_end_min   = _time_to_minutes(settings.daily_end)
    horizon         = len(dates) * 1440  # minutes

    # Per-committee decision variables
    committee_vars: dict[int, dict] = {}
    for c in committees:
        dur = durations[c.id]
        occupancy_dur = occupancy_durations[c.id]
        # Start in global minutes (date_idx * 1440 + minute_in_day).
        # `end_var` is the real committee end. `occupancy_end_var` includes
        # the trailing buffer and is used only for resource conflicts.
        start_var = model.NewIntVar(0, horizon - occupancy_dur, f'start_{c.id}')
        end_var = model.NewIntVar(dur, horizon, f'end_{c.id}')
        occupancy_end_var = model.NewIntVar(occupancy_dur, horizon, f'occupancy_end_{c.id}')
        interval_var = model.NewIntervalVar(
            start_var, occupancy_dur, occupancy_end_var, f'occupancy_interval_{c.id}'
        )
        # Room choice (index into rooms list)
        room_var = model.NewIntVar(0, len(rooms) - 1, f'room_{c.id}')
        # Day index (which date)
        day_var = model.NewIntVar(0, len(dates) - 1, f'day_{c.id}')

        committee_vars[c.id] = {
            'committee': c,
            'start': start_var,
            'end': end_var,
            'occupancy_end': occupancy_end_var,
            'interval': interval_var,
            'room_idx': room_var,
            'day_idx': day_var,
            'duration': dur,
            'occupancy_duration': occupancy_dur,
        }

    # ── 5. Hard constraints ────────────────────────────────────────────────

    # 5a) Day extraction and work-window
    for c_id, v in committee_vars.items():
        # minute_in_day = start % 1440
        minute_in_day = model.NewIntVar(0, 1439, f'min_{c_id}')
        model.AddModuloEquality(minute_in_day, v['start'], 1440)
        
        # day_idx = (start - minute_in_day) / 1440
        # Expressed as a standard linear constraint: start = day_idx * 1440 + minute_in_day
        model.Add(v['start'] == v['day_idx'] * 1440 + minute_in_day)
        model.Add(v['end'] == v['start'] + v['duration'])
        model.Add(v['occupancy_end'] == v['start'] + v['occupancy_duration'])
        # Must start at/after daily_start and the real discussion must end
        # at/before daily_end. The buffer is not part of the committee time.
        model.Add(minute_in_day >= daily_start_min)
        model.Add(minute_in_day + v['duration'] <= daily_end_min)
        # End must be in the same day (no overflow to next day)
        model.Add(v['end'] <= (v['day_idx'] + 1) * 1440)
        model.Add(v['start'] >= v['day_idx'] * 1440)

    # 5b) NoOverlap per room (using optional intervals)
    for r_idx, room in enumerate(rooms):
        room_intervals = []
        for c_id, v in committee_vars.items():
            in_room = model.NewBoolVar(f'in_room_{c_id}_{r_idx}')
            # in_room == 1 IFF room_idx == r_idx
            model.Add(v['room_idx'] == r_idx).OnlyEnforceIf(in_room)
            model.Add(v['room_idx'] != r_idx).OnlyEnforceIf(in_room.Not())
            opt_interval = model.NewOptionalIntervalVar(
                v['start'], v['occupancy_duration'], v['occupancy_end'],
                in_room, f'opt_int_{c_id}_{r_idx}',
            )
            room_intervals.append(opt_interval)
        if len(room_intervals) > 1:
            model.AddNoOverlap(room_intervals)

    # 5c) NoOverlap per doctor
    for doc_id in all_doctors:
        doc_intervals = []
        for c in committees:
            if doc_id not in committee_doctors[c.id]:
                continue
            doc_intervals.append(committee_vars[c.id]['interval'])
        if len(doc_intervals) > 1:
            model.AddNoOverlap(doc_intervals)

    # 5d) Doctor availability (weekly + exceptions)
    for doc_id in all_doctors:
        available_dates = doctor_available_dates[doc_id]
        if not available_dates:
            # Should have been caught in pre-flight; defensive
            continue
        available_day_indices = [date_to_index[d] for d in available_dates]
        # For each committee with this doctor: day_idx must be in available_day_indices
        for c in committees:
            if doc_id not in committee_doctors[c.id]:
                continue
            v = committee_vars[c.id]
            # day_idx ∈ available_day_indices
            # Use a boolean for each available day, exactly one must be true
            day_bools = []
            for di in available_day_indices:
                b = model.NewBoolVar(f'avail_{doc_id}_{c.id}_d{di}')
                model.Add(v['day_idx'] == di).OnlyEnforceIf(b)
                model.Add(v['day_idx'] != di).OnlyEnforceIf(b.Not())
                day_bools.append(b)
            if day_bools:
                model.AddExactlyOne(day_bools)
            else:
                # Should never happen (already filtered), but defensive
                model.Add(v['day_idx'] == -1)  # forces infeasibility

    # ── 6. Soft constraints (objective) ────────────────────────────────────
    penalties = []

    # 6a) Doctor load imbalance
    if all_doctors:
        load_vars = {}
        for doc_id in all_doctors:
            # Number of committees assigned to this doctor (all of them — they're all
            # scheduled since we have to schedule every committee)
            load_vars[doc_id] = sum(
                1 for c in committees if doc_id in committee_doctors[c.id]
            )
        # Since every committee MUST be scheduled, the load is fixed per doctor.
        # The imbalance is determined by the input data, not by solver decisions.
        # We can't optimize it here — but we still report it in summary_stats.
        pass

    # 6b) Minimize number of distinct days used AND prioritize restricted doctors
    used_days: list[cp_model.IntVar] = []
    for di, d in enumerate(dates):
        ud = model.NewBoolVar(f'used_day_{di}')
        any_in_day = []
        for c_id, v in committee_vars.items():
            in_day = model.NewBoolVar(f'in_day_{c_id}_{di}')
            model.Add(v['day_idx'] == di).OnlyEnforceIf(in_day)
            model.Add(v['day_idx'] != di).OnlyEnforceIf(in_day.Not())
            any_in_day.append(in_day)
            
            # NEW: Prioritize restricted doctors (rarity bonus)
            # If this committee has a doctor available on <= 3 days,
            # give a BONUS (negative penalty) for scheduling on those days.
            # This forces the solver to schedule restricted doctors first,
            # and leave flexible doctors for other days.
            c = v['committee']
            doc_ids = committee_doctors[c.id]
            rarity_bonus = 0
            for doc_id in doc_ids:
                avail_dates = doctor_available_dates[doc_id]
                num_avail = len(avail_dates)
                if 0 < num_avail <= 3:  # restricted doctor
                    if dates[di] in avail_dates:
                        rarity_bonus += (4 - num_avail) * 500
            if rarity_bonus > 0:
                penalties.append(in_day * -rarity_bonus)

        if any_in_day:
            model.AddMaxEquality(ud, any_in_day)
        used_days.append(ud)
    penalties.append(cp_model.LinearExpr.Sum(used_days) * 10)

    # 6c) Minimize number of rooms used (group committees into fewer rooms)
    used_rooms: list[cp_model.IntVar] = []
    for r_idx, room in enumerate(rooms):
        ur = model.NewBoolVar(f'used_room_{r_idx}')
        any_in_room = []
        for c_id, v in committee_vars.items():
            in_r = model.NewBoolVar(f'in_room_var_{c_id}_{r_idx}')
            model.Add(v['room_idx'] == r_idx).OnlyEnforceIf(in_r)
            model.Add(v['room_idx'] != r_idx).OnlyEnforceIf(in_r.Not())
            any_in_room.append(in_r)
        if any_in_room:
            model.AddMaxEquality(ur, any_in_room)
        used_rooms.append(ur)
    # Heavy weight on minimizing rooms — dean wants committees grouped
    # into as few rooms as possible (e.g., 5 committees → 5 rooms, not 10).
    # 6d) DAILY LOAD BALANCING — distribute committees evenly across days
    # Instead of packing everything into the first day (Makespan),
    # we minimize the maximum number of committees on any single day.
    # This forces the solver to spread committees evenly:
    #   76 committees / 3 days = ~25 per day (balanced)
    #   instead of 45 + 17 + 14 (packed into first day)
    daily_loads = []
    for di, d in enumerate(dates):
        # Count committees on this day
        load = model.NewIntVar(0, len(committees), f'daily_load_{di}')
        day_committees = []
        for c_id, v in committee_vars.items():
            in_day = model.NewBoolVar(f'load_check_{c_id}_{di}')
            model.Add(v['day_idx'] == di).OnlyEnforceIf(in_day)
            model.Add(v['day_idx'] != di).OnlyEnforceIf(in_day.Not())
            day_committees.append(in_day)
        model.Add(load == sum(day_committees))
        daily_loads.append(load)

    # Minimize the MAXIMUM daily load (forces even distribution)
    max_daily_load = model.NewIntVar(0, len(committees), 'max_daily_load')
    for load in daily_loads:
        model.Add(max_daily_load >= load)
    penalties.append(max_daily_load * 1000)

    # Small Makespan weight (prefer earlier days when load is equal)
    latest_end = model.NewIntVar(0, horizon, 'latest_end')
    for c_id, v in committee_vars.items():
        model.Add(latest_end >= v['end'])
    penalties.append(latest_end * 10)

    # 6e) HARD CONSTRAINT: same doctor group stays in one room per day.
    # Committees with the same chair+members must share a room only when they
    # are scheduled on the SAME day. On another day, the group may use a
    # different room.
    from collections import defaultdict
    groups = defaultdict(list)
    for c_id, v in committee_vars.items():
        c = v['committee']
        doc_ids = tuple(sorted(committee_doctors[c.id]))
        groups[doc_ids].append(v)

    for doc_ids, group_vars in groups.items():
        for i in range(len(group_vars)):
            for j in range(i + 1, len(group_vars)):
                left = group_vars[i]
                right = group_vars[j]
                same_day = model.NewBoolVar(
                    f'same_day_group_{left["committee"].id}_{right["committee"].id}'
                )
                model.Add(left['day_idx'] == right['day_idx']).OnlyEnforceIf(same_day)
                model.Add(left['day_idx'] != right['day_idx']).OnlyEnforceIf(same_day.Not())
                model.Add(left['room_idx'] == right['room_idx']).OnlyEnforceIf(same_day)

    # Remove the old used_rooms penalty (replaced by 6e)
    # penalties.append(cp_model.LinearExpr.Sum(used_rooms) * 1)  # commented out

    if penalties:
        model.Minimize(cp_model.LinearExpr.Sum(penalties))

    # ── 7. Solve ───────────────────────────────────────────────────────────
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(settings.solver_timeout_seconds)
    solver.parameters.num_search_workers = 8
    solver.parameters.log_search_progress = False

    status = solver.Solve(model)
    wall_time = float(solver.WallTime())

    if status == cp_model.INFEASIBLE:
        # Detailed infeasibility analysis
        from collections import defaultdict
        # Check doctor availability per day for each committee
        doctor_availability = defaultdict(set)
        for doc_id in all_doctors:
            available_dates = doctor_available_dates[doc_id]
            for d in available_dates:
                doctor_availability[doc_id].add(d.isoformat())
        
        conflict_details = []
        for c in committees:
            docs_in_committee = committee_doctors[c.id]
            common_days = None
            for doc_id in docs_in_committee:
                doc_days = doctor_availability.get(doc_id, set(d.isoformat() for d in dates))
                if common_days is None:
                    common_days = set(doc_days)
                else:
                    common_days = common_days.intersection(doc_days)
            
            if not common_days:
                # Find the doctors who are causing the conflict
                doc_names = []
                for doc_id in docs_in_committee:
                    name = doctor_name_cache.get(doc_id, f'#{doc_id}')
                    doc_days = doctor_availability.get(doc_id, set(d.isoformat() for d in dates))
                    doc_names.append(f'{name} (متاح: {', '.join(sorted(doc_days)) if doc_days else 'لا يوجد'})')
                
                conflict_details.append({
                    'committee_id': c.id,
                    'doctors': doc_names,
                    'reason': 'لا يوجد يوم مشترك متاح لجميع أعضاء اللجنة'
                })
        
        if conflict_details:
            msg = 'تعارض في توفر الدكاترة! اللجان التالية لا يوجد يوم مشترك متاح لجميع أعضائها:\n'
            for cd in conflict_details:
                msg += f'\n- لجنة #{cd["committee_id"]}: {', '.join(cd["doctors"])}\n'
            report = [{
                'code': 'doctor_availability_conflict',
                'level': 'error',
                'message_ar': msg,
                'suggestions_ar': [
                    'عدل توفر الدكاترة ليكون هناك يوم مشترك',
                    'أو غير أعضاء اللجنة',
                    'أو وسع نطاق التواريخ',
                ],
                'conflict_details': conflict_details,
            }]
        else:
            msg = 'تعذّر إيجاد حل ممكن. القيود متعارضة تماماً. راجع التوفر، القاعات، وأيام العمل.'
            report = [{
                'code': 'solver_infeasible',
                'level': 'error',
                'message_ar': msg,
                'suggestions_ar': [
                    'زد عدد القاعات',
                    'وسّع نطاق التواريخ',
                    'تأكد من توفر الدكاترة في أيام العمل',
                ],
            }]
        
        return {
            'success': False,
            'infeasibility_report': report,
        }

    if status == cp_model.UNKNOWN:
        return {
            'success': False,
            'infeasibility_report': [{
                'code': 'solver_timeout',
                'level': 'error',
                'message_ar': (
                    f'انتهت مهلة الـ Solver ({settings.solver_timeout_seconds} ثانية) '
                    f'دون إيجاد حل كامل. حاول زيادة المهلة أو تبسيط القيود.'
                ),
                'suggestions_ar': [
                    f'زد solver_timeout_seconds (الحالي: {settings.solver_timeout_seconds})',
                    'قلّل عدد اللجان',
                    'زد القاعات أو الأيام',
                ],
            }],
        }

    # status is OPTIMAL or FEASIBLE
    solver_status_str = 'OPTIMAL' if status == cp_model.OPTIMAL else 'FEASIBLE'

    # ── 8. Extract plan ────────────────────────────────────────────────────
    assignments = []
    used_days_set = set()
    used_rooms_set = set()
    doctor_scheduled_count: dict[int, int] = {doc_id: 0 for doc_id in all_doctors}

    for c_id, v in committee_vars.items():
        c = v['committee']
        start_global = solver.Value(v['start'])
        room_idx = solver.Value(v['room_idx'])
        day_idx = solver.Value(v['day_idx'])

        minute_in_day = start_global % 1440
        d = dates[day_idx]
        room = rooms[room_idx]

        # Build datetime (naive — Django will treat as UTC; committee scheduling is
        # in Damascus local time. The dean will see formatted strings.)
        scheduled_start_dt = datetime.combine(d, time(
            hour=(minute_in_day // 60),
            minute=(minute_in_day % 60),
        ))
        scheduled_end_dt = scheduled_start_dt + timedelta(minutes=v['duration'])

        used_days_set.add(d.isoformat())
        used_rooms_set.add(room.id)
        for doc_id in committee_doctors[c.id]:
            doctor_scheduled_count[doc_id] = doctor_scheduled_count.get(doc_id, 0) + 1

        # Get project info for the plan
        project_ids = []
        for app in c.applications.all():
            project_ids.append({'source': 'IdeaApplication', 'id': app.id})
        for prop in c.proposals.all():
            project_ids.append({'source': 'StudentIdeaProposal', 'id': prop.id})

        # Get doctor info
        doctor_names = []
        if c.chair_id:
            doctor_names.append({
                'id': c.chair_id,
                'name': c.chair.get_full_name() or c.chair.username,
                'role': 'chair',
            })
        for m in c.members.all():
            doctor_names.append({
                'id': m.id,
                'name': m.get_full_name() or m.username,
                'role': 'member',
            })

        assignments.append({
            'committee_id': c.id,
            'committee_type': c.committee_type,
            'committee_type_ar': COMMITTEE_TYPE_AR.get(c.committee_type, c.committee_type),
            'department': c.department,
            'project_ids': project_ids,
            'doctors': doctor_names,
            'date': d.isoformat(),
            'weekday': WEEKDAYS_AR.get(d.weekday(), str(d.weekday())),
            'start_time': scheduled_start_dt.strftime('%H:%M'),
            'end_time': scheduled_end_dt.strftime('%H:%M'),
            'scheduled_start': scheduled_start_dt.isoformat(),
            'scheduled_end': scheduled_end_dt.isoformat(),
            'room_id': room.id,
            'room_name': room.name,
            'duration_minutes': v['duration'],
            'buffer_minutes': max(0, settings.buffer_between_committees_minutes or 0),
            'discussion_duration': (
                getattr(settings, 'discussion_duration', None)
                or c.discussion_duration
                or 15
            ),
            'projects_count': c.projects_count,
            # Snapshot used to detect stale previews before Apply.
            'committee_snapshot': {
                'updated_at': c.updated_at.isoformat() if c.updated_at else None,
                'committee_type': c.committee_type,
                'department': c.department,
                'project_type': c.project_type,
                'semester': c.semester,
                'chair_id': c.chair_id,
                'member_ids': sorted(member.id for member in c.members.all()),
                'application_ids': sorted(application.id for application in c.applications.all()),
                'proposal_ids': sorted(proposal.id for proposal in c.proposals.all()),
                'discussion_duration': c.discussion_duration,
            },
        })

    # Sort assignments by date, then start_time, then room
    assignments.sort(key=lambda a: (a['date'], a['start_time'], a['room_name']))

    # ── 9. Summary stats ───────────────────────────────────────────────────
    doctor_workload = []
    for doc_id, count in sorted(doctor_scheduled_count.items(),
                                  key=lambda x: -x[1]):
        name = doctor_name_cache.get(doc_id, f'#{doc_id}')
        doctor_workload.append({
            'doctor_id': doc_id,
            'doctor_name': name,
            'committees_count': count,
        })

    summary_stats = {
        'total_committees': len(committees),
        'scheduled_committees': len(assignments),
        'days_used': len(used_days_set),
        'rooms_used': len(used_rooms_set),
        'total_days_available': len(dates),
        'total_rooms_available': len(rooms),
        'doctor_workload': doctor_workload,
        'max_load': max(doctor_scheduled_count.values()) if doctor_scheduled_count else 0,
        'min_load': min(doctor_scheduled_count.values()) if doctor_scheduled_count else 0,
    }

    plan = {
        'committee_type': committee_type,
        'committee_type_ar': COMMITTEE_TYPE_AR.get(committee_type, committee_type),
        'semester': semester,
        'assignments': assignments,
    }

    return {
        'success': True,
        'solver_status': solver_status_str,
        'wall_time': wall_time,
        'plan': plan,
        'summary_stats': summary_stats,
        'infeasibility_report': [],
        # Non-blocking warnings (e.g. doctors with default-availability)
        'warnings': [r for r in pre_report if r.get('level') != 'error'],
    }


# ── Apply / Reject helpers ───────────────────────────────────────────────────

@transaction.atomic
def apply_scheduling_run(run: SchedulingRun) -> dict:
    """Apply a preview SchedulingRun only when its source data is unchanged.

    The preview contains a snapshot of each committee. Apply validates the
    complete scope before clearing or writing any scheduling fields. Because
    this function is atomic, any validation/update failure rolls back all work.
    """
    if run.status != 'preview':
        raise ValueError(
            f"Cannot apply run with status '{run.status}' — must be 'preview'"
        )

    plan = run.plan_json or {}
    assignments = plan.get('assignments', [])
    if not assignments:
        raise ValueError('الخطة لا تحتوي على أي لجان قابلة للتطبيق.')

    assignment_ids = [a.get('committee_id') for a in assignments]
    if any(committee_id is None for committee_id in assignment_ids):
        raise ValueError('الخطة غير صالحة: يوجد assignment بدون committee_id.')
    if len(assignment_ids) != len(set(assignment_ids)):
        raise ValueError('الخطة غير صالحة: يوجد committee_id مكرر.')

    # Lock the whole scheduling scope so it cannot change during validation/apply.
    scope_qs = (
        Committee.objects.select_for_update()
        .filter(committee_type=run.committee_type)
        .prefetch_related('members', 'applications', 'proposals')
    )
    scope_committees = list(scope_qs)
    current_ids = {committee.id for committee in scope_committees}
    planned_ids = set(assignment_ids)

    # The solver previews every committee in this committee-type scope. A changed
    # count means a committee was added, removed, or moved after Preview.
    if current_ids != planned_ids:
        missing = sorted(planned_ids - current_ids)
        added = sorted(current_ids - planned_ids)
        raise ValueError(
            'خطة الجدولة قديمة ولا يمكن تطبيقها. '
            f'لجان محذوفة/منقولة: {missing or "لا يوجد"}، '
            f'لجان جديدة: {added or "لا يوجد"}. أعد تنفيذ Preview.'
        )

    committee_by_id = {committee.id: committee for committee in scope_committees}

    # Validate every committee against the snapshot saved at Preview time.
    stale_details = []
    for assignment in assignments:
        committee_id = assignment['committee_id']
        committee = committee_by_id[committee_id]
        snapshot = assignment.get('committee_snapshot')

        # Old plans created before snapshot support are rejected intentionally.
        if not snapshot:
            stale_details.append(
                f'اللجنة #{committee_id}: الخطة لا تحتوي fingerprint؛ أعد Preview.'
            )
            continue

        current_snapshot = {
            'updated_at': committee.updated_at.isoformat() if committee.updated_at else None,
            'committee_type': committee.committee_type,
            'department': committee.department,
            'project_type': committee.project_type,
            'semester': committee.semester,
            'chair_id': committee.chair_id,
            'member_ids': sorted(committee.members.values_list('id', flat=True)),
            'application_ids': sorted(committee.applications.values_list('id', flat=True)),
            'proposal_ids': sorted(committee.proposals.values_list('id', flat=True)),
            'discussion_duration': committee.discussion_duration,
        }

        changed_fields = [
            field
            for field, current_value in current_snapshot.items()
            if current_value != snapshot.get(field)
        ]
        if changed_fields:
            stale_details.append(
                f'اللجنة #{committee_id}: تغيّرت الحقول {", ".join(changed_fields)}.'
            )

    if stale_details:
        raise ValueError(
            'خطة الجدولة أصبحت قديمة بسبب تغييرات حدثت بعد Preview. '
            'أعد إنشاء Preview جديد. التفاصيل: ' + ' '.join(stale_details)
        )

    # Clear every legacy and CP-SAT scheduling field in the validated scope.
    cleared = Committee.objects.filter(id__in=planned_ids).update(
        room=None,
        scheduled_start=None,
        scheduled_end=None,
        date=None,
        time=None,
        start_time=None,
        end_time=None,
        location='',
        status='draft',
        manually_scheduled=False,
        last_scheduling_run=None,
    )
    if cleared != len(planned_ids):
        raise ValueError(
            'فشل مسح الجدولة القديمة لكل اللجان؛ لم يتم تطبيق أي تغيير.'
        )

    updated = 0
    for assignment in assignments:
        duration_used = assignment.get('discussion_duration') or 15
        affected = Committee.objects.filter(
            id=assignment['committee_id'],
            committee_type=run.committee_type,
        ).update(
            room_id=assignment['room_id'],
            scheduled_start=assignment['scheduled_start'],
            scheduled_end=assignment['scheduled_end'],
            last_scheduling_run=run,
            discussion_duration=duration_used,
            date=assignment['date'],
            time=assignment['start_time'],
            start_time=assignment['start_time'],
            end_time=assignment['end_time'],
            location=assignment.get('room_name', ''),
            status='scheduled',
            manually_scheduled=False,
        )
        if affected != 1:
            raise ValueError(
                f'فشل تحديث اللجنة #{assignment["committee_id"]}. '
                'تم إلغاء العملية كاملة؛ أعد Preview.'
            )
        updated += affected

    # Post-condition: every committee in this exact scheduling scope must now
    # be scheduled. Any mismatch aborts the atomic transaction.
    scheduled_ids = set(
        Committee.objects.filter(
            id__in=planned_ids,
            status='scheduled',
            room__isnull=False,
            scheduled_start__isnull=False,
            scheduled_end__isnull=False,
        ).values_list('id', flat=True)
    )
    if scheduled_ids != planned_ids:
        failed_ids = sorted(planned_ids - scheduled_ids)
        raise ValueError(
            'لم تُطبّق الجدولة على كامل نطاق الخطة. ' 
            f'اللجان غير المجدولة: {failed_ids}. تم التراجع عن العملية كاملة.'
        )

    run.status = 'applied'
    run.applied_at = timezone.now()
    run.save(update_fields=['status', 'applied_at'])

    project_count = sum(committee.projects_count for committee in scope_committees)
    return {
        'applied': True,
        'committees_updated': updated,
        'projects_covered': project_count,
        'run_id': run.id,
        'committee_type': run.committee_type,
        'semester': run.semester,
    }


def reject_scheduling_run(run: SchedulingRun) -> dict:
    """Mark a preview SchedulingRun as rejected."""
    if run.status != 'preview':
        raise ValueError(f"Cannot reject run with status '{run.status}' — must be 'preview'")
    run.status = 'rejected'
    run.save(update_fields=['status'])
    return {'rejected': True, 'run_id': run.id}
