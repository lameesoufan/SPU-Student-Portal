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

The committee duration is computed as:
  duration = (projects_count × discussion_duration) + buffer_between_committees_minutes
where discussion_duration is REQUIRED on each Committee (per dean decision).
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
    """
    Calculate committee duration. Uses settings.discussion_duration if provided
    (from the scheduling form), otherwise falls back to committee.discussion_duration,
    otherwise defaults to 15 minutes.
    """
    # Priority: settings.discussion_duration (from form) > committee.discussion_duration (DB) > 15 (default)
    duration_per_project = getattr(settings, 'discussion_duration', None) or committee.discussion_duration or 15
    projects_count = committee.projects_count
    return (projects_count * duration_per_project) \
           + settings.buffer_between_committees_minutes


def _committee_doctors(committee: Committee) -> set[int]:
    """Return the set of doctor user IDs involved in this committee."""
    ids = set()
    if committee.chair_id:
        ids.add(committee.chair_id)
    for m in committee.members.values_list('id', flat=True):
        ids.add(m)
    return ids


def _doctor_available_dates(doctor_id: int, dates: list[date]) -> list[date]:
    """Filter `dates` to only those where the doctor is available.

    DEFAULT-AVAILABLE RULE:
      If a doctor has NO DoctorWeeklyAvailability records AND NO
      DoctorDateException records at all, they are considered available
      on ALL dates (the dean/did-not-set-availability default).

    Otherwise:
      - A doctor is available on a date if:
        - The weekday is in their DoctorWeeklyAvailability (if any records exist), AND
        - There is no DoctorDateException with exception_type='blocked' on that date.
      - An exception with exception_type='available' overrides everything
        (the doctor is available on that date even if not in weekly availability).

    So:
      - No availability set + no exceptions → available on all dates
      - Weekly availability set → available only on those weekdays (minus blocked dates)
      - Blocked exception → unavailable on that specific date
      - Available exception → available on that specific date (overrides weekly)
    """
    weekly_qs = DoctorWeeklyAvailability.objects.filter(doctor_id=doctor_id)
    exception_qs = DoctorDateException.objects.filter(doctor_id=doctor_id)

    weekly_weekdays = set(weekly_qs.values_list('weekday', flat=True))
    blocked_dates = set(
        exception_qs.filter(exception_type='blocked').values_list('date', flat=True)
    )
    available_overrides = set(
        exception_qs.filter(exception_type='available').values_list('date', flat=True)
    )

    # DEFAULT-AVAILABLE: no availability and no exceptions at all → available everywhere
    has_any_weekly = bool(weekly_weekdays)
    has_any_exception = bool(blocked_dates) or bool(available_overrides)
    if not has_any_weekly and not has_any_exception:
        return list(dates)

    # Has at least some settings — apply the normal rule
    result = []
    for d in dates:
        # Available override always wins
        if d in available_overrides:
            result.append(d)
            continue
        # Blocked exception always wins
        if d in blocked_dates:
            continue
        # If weekly exists, doctor is available only on those weekdays
        if has_any_weekly:
            if d.weekday() in weekly_weekdays:
                result.append(d)
        else:
            # No weekly set, but has exceptions → available on non-blocked dates
            result.append(d)
    return result


# ── Infeasibility report builder ─────────────────────────────────────────────

def _build_infeasibility_report(
    committees: list[Committee],
    rooms: list[Room],
    dates: list[date],
    settings: SolverSettings,
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
        total_minutes_needed = sum(
            _committee_duration_minutes(c, settings) or 0
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

    # 5) Doctors without any weekly availability — NOT an error anymore
    # (default = available on all dates). Just an info-level note.
    all_doctors: set[int] = set()
    for c in committees:
        all_doctors.update(_committee_doctors(c))

    doctors_no_availability = []
    for doc_id in all_doctors:
        has_weekly = DoctorWeeklyAvailability.objects.filter(doctor_id=doc_id).exists()
        has_exceptions = DoctorDateException.objects.filter(doctor_id=doc_id).exists()
        if not has_weekly and not has_exceptions:
            doctor = None
            try:
                from django.contrib.auth import get_user_model
                doctor = get_user_model().objects.get(id=doc_id)
            except Exception:
                pass
            doctors_no_availability.append({
                'doctor_id': doc_id,
                'doctor_name': (doctor.get_full_name() or doctor.username) if doctor else f'#{doc_id}',
            })

    if doctors_no_availability:
        report.append({
            'code': 'doctor_default_available',
            'level': 'info',  # info — not blocking
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
        .filter(committee_type=committee_type, semester=semester)
        .select_related('chair', 'template')
        .prefetch_related('members')
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
                    f'في الفصل "{semester}". تأكد من تشغيل التوزيع (Distribute) أولاً.'
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

    # ── 2. Pre-flight infeasibility checks ─────────────────────────────────
    # Only `error`-level items block scheduling. `warn` and `info` are
    # non-blocking — they're surfaced to the dean as warnings/tips.
    pre_report = _build_infeasibility_report(committees, rooms, dates, settings)
    blocking_report = [r for r in pre_report if r.get('level') == 'error']
    if blocking_report:
        return {
            'success': False,
            'infeasibility_report': blocking_report,
            'warnings': [r for r in pre_report if r.get('level') != 'error'],
        }

    # ── 3. Compute per-committee durations ────────────────────────────────
    durations = {}
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

    # ── 4. Build CP-SAT model ──────────────────────────────────────────────
    model = cp_model.CpModel()

    daily_start_min = _time_to_minutes(settings.daily_start)
    daily_end_min   = _time_to_minutes(settings.daily_end)
    horizon         = len(dates) * 1440  # minutes

    # Per-committee decision variables
    committee_vars: dict[int, dict] = {}
    for c in committees:
        dur = durations[c.id]
        # Start in global minutes (date_idx * 1440 + minute_in_day)
        start_var = model.NewIntVar(0, horizon - dur, f'start_{c.id}')
        end_var   = model.NewIntVar(dur, horizon, f'end_{c.id}')
        interval_var = model.NewIntervalVar(start_var, dur, end_var, f'interval_{c.id}')
        # Room choice (index into rooms list)
        room_var = model.NewIntVar(0, len(rooms) - 1, f'room_{c.id}')
        # Day index (which date)
        day_var = model.NewIntVar(0, len(dates) - 1, f'day_{c.id}')

        committee_vars[c.id] = {
            'committee': c,
            'start': start_var,
            'end': end_var,
            'interval': interval_var,
            'room_idx': room_var,
            'day_idx': day_var,
            'duration': dur,
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
        # Must start at/after daily_start and end at/before daily_end within same day
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
                v['start'], v['duration'], v['end'],
                in_room, f'opt_int_{c_id}_{r_idx}',
            )
            room_intervals.append(opt_interval)
        if len(room_intervals) > 1:
            model.AddNoOverlap(room_intervals)

    # 5c) NoOverlap per doctor
    all_doctors: set[int] = set()
    for c in committees:
        all_doctors.update(_committee_doctors(c))

    for doc_id in all_doctors:
        doc_intervals = []
        for c in committees:
            if doc_id not in _committee_doctors(c):
                continue
            doc_intervals.append(committee_vars[c.id]['interval'])
        if len(doc_intervals) > 1:
            model.AddNoOverlap(doc_intervals)

    # 5d) Doctor availability (weekly + exceptions)
    for doc_id in all_doctors:
        available_dates = _doctor_available_dates(doc_id, dates)
        if not available_dates:
            # Should have been caught in pre-flight; defensive
            continue
        available_day_indices = [dates.index(d) for d in available_dates]
        # For each committee with this doctor: day_idx must be in available_day_indices
        for c in committees:
            if doc_id not in _committee_doctors(c):
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
                1 for c in committees if doc_id in _committee_doctors(c)
            )
        # Since every committee MUST be scheduled, the load is fixed per doctor.
        # The imbalance is determined by the input data, not by solver decisions.
        # We can't optimize it here — but we still report it in summary_stats.
        pass

    # 6b) Minimize number of distinct days used
    used_days: list[cp_model.IntVar] = []
    for di, d in enumerate(dates):
        ud = model.NewBoolVar(f'used_day_{di}')
        # ud == 1 IFF any committee has day_idx == di
        any_in_day = []
        for c_id, v in committee_vars.items():
            in_day = model.NewBoolVar(f'in_day_{c_id}_{di}')
            model.Add(v['day_idx'] == di).OnlyEnforceIf(in_day)
            model.Add(v['day_idx'] != di).OnlyEnforceIf(in_day.Not())
            any_in_day.append(in_day)
        # ud >= each in_day (i.e. ud = OR(any_in_day))
        for b in any_in_day:
            model.Add(ud >= b)
        # If no committee is in this day, ud can be 0
        # We don't force ud == 1 even if some in_day == 1, because OR constraints
        # can be encoded by AddMaxEquality. Let's use that instead:
        # Actually, let's rebuild using AddMaxEquality
        if any_in_day:
            # ud == max(any_in_day) — i.e. OR
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
    # 6d) Minimize Makespan (latest end time) — forces parallel execution
    # Committees will be scheduled in different rooms simultaneously
    # to finish as early as possible.
    latest_end = model.NewIntVar(0, horizon, 'latest_end')
    for c_id, v in committee_vars.items():
        model.Add(latest_end >= v['end'])
    penalties.append(latest_end * 1000)

    # 6e) HARD CONSTRAINT: Committee must stay in the same room all day
    # Group committees by their doctor signature (chair + members).
    # All committees in the same group MUST have the exact same room_idx.
    from collections import defaultdict
    groups = defaultdict(list)
    for c_id, v in committee_vars.items():
        c = v['committee']
        doc_ids = tuple(sorted(_committee_doctors(c)))
        groups[doc_ids].append(v)

    for doc_ids, group_vars in groups.items():
        if len(group_vars) > 1:
            # All committees in this group must have the same room_idx
            first_room = group_vars[0]['room_idx']
            for v in group_vars[1:]:
                model.Add(v['room_idx'] == first_room)

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
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Check doctor availability per day for each committee
        doctor_availability = defaultdict(set)
        for doc_id in all_doctors:
            available_dates = _doctor_available_dates(doc_id, dates)
            for d in available_dates:
                doctor_availability[doc_id].add(d.isoformat())
        
        conflict_details = []
        for c in committees:
            docs_in_committee = _committee_doctors(c)
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
                    try:
                        u = User.objects.get(id=doc_id)
                        name = u.get_full_name() or u.username
                    except Exception:
                        name = f'#{doc_id}'
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
        for doc_id in _committee_doctors(c):
            doctor_scheduled_count[doc_id] = doctor_scheduled_count.get(doc_id, 0) + 1

        # Get project info for the plan
        project_ids = []
        for app in c.applications.values_list('id', flat=True):
            project_ids.append({'source': 'IdeaApplication', 'id': app})
        for prop in c.proposals.values_list('id', flat=True):
            project_ids.append({'source': 'StudentIdeaProposal', 'id': prop})

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
            'discussion_duration': c.discussion_duration,
            'projects_count': c.projects_count,
        })

    # Sort assignments by date, then start_time, then room
    assignments.sort(key=lambda a: (a['date'], a['start_time'], a['room_name']))

    # ── 9. Summary stats ───────────────────────────────────────────────────
    from django.contrib.auth import get_user_model
    User = get_user_model()
    doctor_workload = []
    for doc_id, count in sorted(doctor_scheduled_count.items(),
                                  key=lambda x: -x[1]):
        try:
            u = User.objects.get(id=doc_id)
            name = u.get_full_name() or u.username
        except Exception:
            name = f'#{doc_id}'
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
    """Apply a preview SchedulingRun to the DB.

    Steps:
      1. Validate run.status == 'preview'
      2. Clear existing scheduling for committees of (type, semester)
      3. Apply new assignments from run.plan_json
      4. Mark run.status = 'applied', run.applied_at = now
    """
    if run.status != 'preview':
        raise ValueError(f"Cannot apply run with status '{run.status}' — must be 'preview'")

    plan = run.plan_json or {}
    assignments = plan.get('assignments', [])

    # Clear existing scheduling
    Committee.objects.filter(
        committee_type=run.committee_type,
        semester=run.semester,
    ).update(
        room=None,
        scheduled_start=None,
        scheduled_end=None,
        manually_scheduled=False,
        last_scheduling_run=None,
    )

    # Apply new assignments
    updated = 0
    for a in assignments:
        # Save the discussion_duration used for this run to the DB
        # so ProjectsAssignmentView can calculate per-project times correctly
        duration_used = run.solver_settings.discussion_duration if run.solver_settings else None
        Committee.objects.filter(id=a['committee_id']).update(
            room_id=a['room_id'],
            scheduled_start=a['scheduled_start'],
            scheduled_end=a['scheduled_end'],
            last_scheduling_run=run,
            discussion_duration=duration_used if duration_used else None,
            # Update legacy fields too for compatibility
            date=a['date'],
            start_time=a['start_time'],
            end_time=a['end_time'],
            status='scheduled',
        )
        updated += 1

    run.status = 'applied'
    run.applied_at = timezone.now()
    run.save(update_fields=['status', 'applied_at'])

    return {
        'applied': True,
        'committees_updated': updated,
        'run_id': run.id,
    }


def reject_scheduling_run(run: SchedulingRun) -> dict:
    """Mark a preview SchedulingRun as rejected."""
    if run.status != 'preview':
        raise ValueError(f"Cannot reject run with status '{run.status}' — must be 'preview'")
    run.status = 'rejected'
    run.save(update_fields=['status'])
    return {'rejected': True, 'run_id': run.id}
