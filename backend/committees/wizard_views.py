"""
Wizard endpoints for the committees app — unified semester setup + scheduling.

These endpoints dramatically reduce the dean's effort by combining multiple
steps into single API calls:

  POST /api/committees/semester-setup/
    → Creates 4 SolverSettings (consecutive weeks)
    → Validates rooms, doctors, templates
    → Runs project distribution (single + multi modes)
    → Returns a complete summary ready for scheduling

  POST /api/committees/schedule-all/
    → Runs CP-SAT for all 4 committee types in sequence
    → Returns 4 plans + a unified Gantt-friendly data structure
    → Does NOT apply — leaves Apply All decision to the dean

  POST /api/committees/schedule-apply-all/
    → Applies all preview-status runs for the given semester
    → Returns a summary of what was applied

  POST /api/committees/schedule-reject-all/
    → Rejects all preview-status runs for the given semester
"""
from __future__ import annotations

from datetime import date, timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    CommitteeTemplate, Committee, Room,
    SolverSettings, SchedulingRun,
    COMMITTEE_TYPE_AR, ALL_COMMITTEE_TYPES,
)
from .serializers import SolverSettingsSerializer
from .services import distribute_projects_to_committees
from .solver import run_solver, apply_scheduling_run, reject_scheduling_run
from .scheduler_views import IsDean


# ── 1. Semester Setup Wizard ─────────────────────────────────────────────────

class SemesterSetupView(APIView):
    """POST /api/committees/semester-setup/

    Payload:
        {
            "semester": "Spring 2026",
            "start_date": "2026-02-01",        # بداية الأسبوع الأول
            "weeks_per_type": 1,                # كل نوع يأخذ أسبوعاً (افتراضي 1)
            "workdays": [5, 6],                 # أيام العمل الأسبوعية (Sat, Sun)
            "daily_start": "09:00",
            "daily_end": "17:00",
            "buffer_minutes": 10,
            "max_committees_per_doctor": 5,
            "solver_timeout_seconds": 30,
            "room_ids": [1, 2, 3],              # قاعات مختارة (يجب أن تكون موجودة)
            "run_distribution": true            # هل نشغّل Distribute بعد الإعداد؟
        }

    Returns:
        - 200 with summary if everything succeeded
        - 400 with detailed errors if validation failed
    """
    permission_classes = [IsDean]

    def post(self, request):
        semester       = request.data.get('semester')
        start_date_str = request.data.get('start_date')
        weeks_per_type = int(request.data.get('weeks_per_type', 1))
        workdays       = request.data.get('workdays', [5, 6])
        daily_start    = request.data.get('daily_start', '09:00')
        daily_end      = request.data.get('daily_end', '17:00')
        buffer_minutes = int(request.data.get('buffer_minutes', 10))
        max_per_doctor = int(request.data.get('max_committees_per_doctor', 5))
        timeout        = int(request.data.get('solver_timeout_seconds', 30))
        room_ids       = request.data.get('room_ids', [])
        run_distribution = request.data.get('run_distribution', True)
        scheduling_mode  = request.data.get('scheduling_mode', 'multi')

        # ── Validation ──
        errors = []
        if not semester:
            errors.append('semester مطلوب')
        if not start_date_str:
            errors.append('start_date مطلوب')
        else:
            try:
                start_date = date.fromisoformat(start_date_str)
            except ValueError:
                errors.append(f'start_date ليس بصيغة صحيحة (expected YYYY-MM-DD): {start_date_str}')
        if not workdays or not isinstance(workdays, list):
            errors.append('workdays يجب أن تكون قائمة (مثال: [5, 6] للسبت والأحد)')
        if errors:
            return Response({'detail': 'أخطاء في التحقق', 'errors': errors},
                            status=status.HTTP_400_BAD_REQUEST)

        # ── Validate rooms ──
        rooms = []
        if room_ids:
            rooms = list(Room.objects.filter(id__in=room_ids, is_active=True))
            if len(rooms) != len(room_ids):
                missing = set(room_ids) - {r.id for r in rooms}
                errors.append(f'بعض القاعات غير موجودة أو غير فعّالة: {missing}')

        # ── 1. Create 4 SolverSettings with consecutive weeks ──
        created_settings = []
        updated_settings = []
        for idx, ctype in enumerate(ALL_COMMITTEE_TYPES):
            week_start = start_date + timedelta(weeks=idx * weeks_per_type)
            week_end   = week_start + timedelta(days=7 * weeks_per_type - 1)

            # Check if settings exist for this (type × semester)
            existing = SolverSettings.objects.filter(
                committee_type=ctype, semester=semester,
            ).first()

            data = {
                'name': f'{COMMITTEE_TYPE_AR[ctype]} - {semester}',
                'committee_type': ctype,
                'semester': semester,
                'date_range_start': week_start.isoformat(),
                'date_range_end': week_end.isoformat(),
                'workdays': workdays,
                'daily_start': daily_start,
                'daily_end': daily_end,
                'buffer_between_committees_minutes': buffer_minutes,
                'max_committees_per_doctor': max_per_doctor,
                'solver_timeout_seconds': timeout,
                'is_active': True,
            }

            if existing:
                # Update existing
                for k, v in data.items():
                    setattr(existing, k, v)
                existing.save()
                updated_settings.append(existing)
            else:
                # Create new
                s = SolverSettings.objects.create(
                    created_by=request.user, **data,
                )
                created_settings.append(s)

        all_settings = created_settings + updated_settings

        # ── 2. Count templates and projects ready for distribution ──
        single_templates = CommitteeTemplate.objects.filter(
            scheduling_mode='single', semester=semester,
        ).count()
        multi_templates = CommitteeTemplate.objects.filter(
            scheduling_mode='multi', semester=semester,
        ).count()

        # ── 3. Run distribution if requested ──
        distribution_result = None
        distribution_error = None
        if run_distribution:
            try:
                distribution_result = distribute_projects_to_committees(
                    semester=semester,
                    dry_run=False,
                    scheduling_mode=scheduling_mode,
                )
            except Exception as e:
                distribution_error = str(e)

        # ── 4. Count committees per type after distribution ──
        committees_per_type = {}
        for ctype in ALL_COMMITTEE_TYPES:
            committees_per_type[ctype] = Committee.objects.filter(
                committee_type=ctype, semester=semester,
            ).count()

        return Response({
            'success': True,
            'semester': semester,
            'start_date': start_date_str,
            'weeks_per_type': weeks_per_type,
            'settings_created': len(created_settings),
            'settings_updated': len(updated_settings),
            'settings': SolverSettingsSerializer(all_settings, many=True).data,
            'rooms_selected': len(rooms),
            'rooms': [{'id': r.id, 'name': r.name, 'capacity': r.capacity} for r in rooms],
            'templates_count': {
                'single': single_templates,
                'multi': multi_templates,
                'total': single_templates + multi_templates,
            },
            'committees_per_type': committees_per_type,
            'committees_total': sum(committees_per_type.values()),
            'distribution': distribution_result,
            'distribution_error': distribution_error,
            'scheduling_mode': scheduling_mode,
            'ready_for_scheduling': sum(committees_per_type.values()) > 0,
            'executed_at': timezone.now().isoformat(),
        }, status=status.HTTP_200_OK)


# ── 2. Schedule All (CP-SAT for 4 types) ─────────────────────────────────────

class ScheduleAllView(APIView):
    """POST /api/committees/schedule-all/

    Payload:
        {
            "semester": "Spring 2026",
            "committee_types": ["seminar_1", "seminar_2", "technical", "final_discussion"],
            "settings_overrides": {  # optional per-type overrides
                "seminar_1": {"settings_id": 1},
                ...
            }
        }

    Runs CP-SAT for each committee_type in sequence, creates a SchedulingRun
    for each, and returns all plans + a unified assignments list for Gantt.

    Does NOT apply — the dean reviews and uses schedule-apply-all.
    """
    permission_classes = [IsDean]

    def post(self, request):
        semester = request.data.get('semester')
        committee_types = request.data.get('committee_types', ALL_COMMITTEE_TYPES)
        settings_overrides = request.data.get('settings_overrides', {})

        if not semester:
            return Response({'detail': 'semester مطلوب'},
                            status=status.HTTP_400_BAD_REQUEST)

        if not committee_types:
            committee_types = list(ALL_COMMITTEE_TYPES)

        results = []
        unified_assignments = []
        unified_warnings = []
        total_wall_time = 0
        any_success = False

        for ctype in committee_types:
            # Pick settings: override or active for this type × semester
            settings_obj = None
            if ctype in settings_overrides and settings_overrides[ctype].get('settings_id'):
                settings_obj = SolverSettings.objects.filter(
                    id=settings_overrides[ctype]['settings_id'],
                ).first()
            if not settings_obj:
                settings_obj = SolverSettings.objects.filter(
                    committee_type=ctype, semester=semester, is_active=True,
                ).first()

            if not settings_obj:
                results.append({
                    'committee_type': ctype,
                    'committee_type_ar': COMMITTEE_TYPE_AR.get(ctype, ctype),
                    'success': False,
                    'error': 'لا توجد إعدادات Solver فعّالة لهذا النوع والفصل',
                })
                continue

            # Count committees of this type
            committees_count = Committee.objects.filter(
                committee_type=ctype, semester=semester,
            ).count()
            if committees_count == 0:
                results.append({
                    'committee_type': ctype,
                    'committee_type_ar': COMMITTEE_TYPE_AR.get(ctype, ctype),
                    'success': False,
                    'error': 'لا توجد لجان من هذا النوع — شغّل Distribute أولاً',
                    'committees_count': 0,
                })
                continue

            # Create a SchedulingRun with status='pending'
            run = SchedulingRun.objects.create(
                committee_type=ctype,
                semester=semester,
                solver_settings=settings_obj,
                status='pending',
                requested_by=request.user,
            )

            # Run the solver
            solver_result = run_solver(
                committee_type=ctype,
                semester=semester,
                settings=settings_obj,
                requested_by=request.user,
            )

            if not solver_result.get('success'):
                run.status = 'failed'
                run.infeasibility_report = solver_result.get('infeasibility_report', [])
                run.solver_status = 'INFEASIBLE'
                run.solver_wall_time_sec = solver_result.get('wall_time', 0)
                run.save(update_fields=['status', 'infeasibility_report',
                                         'solver_status', 'solver_wall_time_sec'])

                results.append({
                    'committee_type': ctype,
                    'committee_type_ar': COMMITTEE_TYPE_AR.get(ctype, ctype),
                    'success': False,
                    'run_id': run.id,
                    'infeasibility_report': run.infeasibility_report,
                    'warnings': solver_result.get('warnings', []),
                    'committees_count': committees_count,
                })
                unified_warnings.extend(solver_result.get('warnings', []))
            else:
                # Success — save plan and mark as preview
                run.plan_json = solver_result['plan']
                run.summary_stats = solver_result['summary_stats']
                run.solver_status = solver_result['solver_status']
                run.solver_wall_time_sec = solver_result['wall_time']
                run.status = 'preview'
                run.save(update_fields=['plan_json', 'summary_stats', 'solver_status',
                                         'solver_wall_time_sec', 'status'])

                results.append({
                    'committee_type': ctype,
                    'committee_type_ar': COMMITTEE_TYPE_AR.get(ctype, ctype),
                    'success': True,
                    'run_id': run.id,
                    'solver_status': run.solver_status,
                    'wall_time': run.solver_wall_time_sec,
                    'plan': run.plan_json,
                    'summary_stats': run.summary_stats,
                    'warnings': solver_result.get('warnings', []),
                    'committees_count': committees_count,
                })
                any_success = True
                total_wall_time += run.solver_wall_time_sec

                # Add to unified assignments (for Gantt)
                for a in run.plan_json.get('assignments', []):
                    unified_assignments.append(a)

                unified_warnings.extend(solver_result.get('warnings', []))

        # Build unified summary stats
        unified_summary = {
            'total_committees': sum(r.get('summary_stats', {}).get('total_committees', 0)
                                     for r in results if r.get('success')),
            'scheduled_committees': sum(r.get('summary_stats', {}).get('scheduled_committees', 0)
                                          for r in results if r.get('success')),
            'types_succeeded': sum(1 for r in results if r.get('success')),
            'types_failed': sum(1 for r in results if not r.get('success')),
            'total_wall_time': total_wall_time,
            'days_used': sum(r.get('summary_stats', {}).get('days_used', 0)
                              for r in results if r.get('success')),
            'rooms_used': sum(r.get('summary_stats', {}).get('rooms_used', 0)
                               for r in results if r.get('success')),
        }

        return Response({
            'success': any_success,
            'semester': semester,
            'results': results,
            'unified_assignments': unified_assignments,
            'unified_summary': unified_summary,
            'warnings': unified_warnings,
            'runs_for_apply': [r['run_id'] for r in results if r.get('success')],
            'executed_at': timezone.now().isoformat(),
        }, status=status.HTTP_200_OK)


# ── 3. Apply All / Reject All ────────────────────────────────────────────────

class ScheduleApplyAllView(APIView):
    """POST /api/committees/schedule-apply-all/

    Payload: { "semester": "Spring 2026" }

    Applies all preview-status SchedulingRuns for the given semester.
    """
    permission_classes = [IsDean]

    def post(self, request):
        semester = request.data.get('semester')
        if not semester:
            return Response({'detail': 'semester مطلوب'},
                            status=status.HTTP_400_BAD_REQUEST)

        runs = SchedulingRun.objects.filter(
            semester=semester, status='preview',
        )
        if not runs.exists():
            return Response({'detail': 'لا توجد معاينات جاهزة للتطبيق'},
                            status=status.HTTP_400_BAD_REQUEST)

        applied = []
        errors = []
        for run in runs:
            try:
                result = apply_scheduling_run(run)
                applied.append({
                    'run_id': run.id,
                    'committee_type': run.committee_type,
                    'committee_type_ar': COMMITTEE_TYPE_AR.get(run.committee_type, run.committee_type),
                    **result,
                })
            except ValueError as e:
                errors.append({
                    'run_id': run.id,
                    'committee_type': run.committee_type,
                    'error': str(e),
                })

        return Response({
            'applied_count': len(applied),
            'errors_count': len(errors),
            'applied': applied,
            'errors': errors,
            'executed_at': timezone.now().isoformat(),
        }, status=status.HTTP_200_OK)


class ScheduleRejectAllView(APIView):
    """POST /api/committees/schedule-reject-all/

    Payload: { "semester": "Spring 2026" }

    Rejects all preview-status SchedulingRuns for the given semester.
    """
    permission_classes = [IsDean]

    def post(self, request):
        semester = request.data.get('semester')
        if not semester:
            return Response({'detail': 'semester مطلوب'},
                            status=status.HTTP_400_BAD_REQUEST)

        runs = SchedulingRun.objects.filter(
            semester=semester, status='preview',
        )
        rejected_count = 0
        for run in runs:
            try:
                reject_scheduling_run(run)
                rejected_count += 1
            except ValueError:
                pass  # already not in preview status

        return Response({
            'rejected_count': rejected_count,
            'executed_at': timezone.now().isoformat(),
        }, status=status.HTTP_200_OK)
