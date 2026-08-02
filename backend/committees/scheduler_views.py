"""
Scheduling API views — CRUD endpoints for rooms, doctor availability,
solver settings, and scheduling runs.

Endpoints (all require Dean role except my-availability which requires Doctor):

  Rooms:
    GET    /api/committees/rooms/
    POST   /api/committees/rooms/
    GET    /api/committees/rooms/{id}/
    PATCH  /api/committees/rooms/{id}/
    DELETE /api/committees/rooms/{id}/

  Doctor availability (Dean manages any doctor):
    GET    /api/committees/availability/?doctor_id=
    POST   /api/committees/availability/
    DELETE /api/committees/availability/{id}/

    GET    /api/committees/availability/exceptions/?doctor_id=
    POST   /api/committees/availability/exceptions/
    DELETE /api/committees/availability/exceptions/{id}/

  Doctor availability (Doctor manages own):
    GET    /api/committees/my-availability/
    POST   /api/committees/my-availability/
    DELETE /api/committees/my-availability/{id}/

    GET    /api/committees/my-availability/exceptions/
    POST   /api/committees/my-availability/exceptions/
    DELETE /api/committees/my-availability/exceptions/{id}/

  Solver settings:
    GET    /api/committees/solver-settings/?committee_type=&semester=
    POST   /api/committees/solver-settings/
    GET    /api/committees/solver-settings/{id}/
    PATCH  /api/committees/solver-settings/{id}/
    DELETE /api/committees/solver-settings/{id}/

  Scheduling runs (list/retrieve):
    GET    /api/committees/schedule/runs/?committee_type=&semester=
    GET    /api/committees/schedule/runs/{id}/
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from django.utils import timezone

from .models import (
    Room, DoctorWeeklyAvailability, DoctorDateException,
    SolverSettings, SchedulingRun,
    COMMITTEE_TYPE_AR,
)
from .serializers import (
    RoomSerializer, DoctorWeeklyAvailabilitySerializer,
    DoctorDateExceptionSerializer,
    SolverSettingsSerializer, SchedulingRunSerializer,
)


# ── Permissions ──────────────────────────────────────────────────────────────

class IsDean(permissions.BasePermission):
    """Only Dean role can access these endpoints."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'role', None) == 'dean'
        )


class IsDoctorOrDean(permissions.BasePermission):
    """Doctor or Dean can access doctor-availability endpoints."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, 'role', None) in ('doctor', 'dean', 'hod')
        )


# ── 1. Room ViewSet ──────────────────────────────────────────────────────────

class RoomViewSet(viewsets.ModelViewSet):
    """CRUD for rooms."""
    queryset = Room.objects.all().order_by('name')
    serializer_class   = RoomSerializer
    permission_classes = [IsDean]

    def get_queryset(self):
        qs = super().get_queryset()
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ('true', '1', 'yes'))
        return qs

    def destroy(self, request, *args, **kwargs):
        """Override destroy — PROTECT prevents deletion if any committee
        is using this room. Return a clear error message in Arabic."""
        instance = self.get_object()
        if instance.committees.exists():
            count = instance.committees.count()
            return Response(
                {
                    'detail': f'لا يمكن حذف القاعة "{instance.name}" لأنها مستخدمة في {count} لجنة. '
                              f'قم بإزالة اللجان من هذه القاعة أولاً أو عطّل القاعة (is_active=False).',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


# ── 2. Doctor weekly availability (Dean manages) ─────────────────────────────

class DoctorAvailabilityView(APIView):
    """Dean-side endpoint for managing any doctor's weekly availability."""
    permission_classes = [IsDean]

    def get(self, request):
        doctor_id = request.query_params.get('doctor_id')
        qs = DoctorWeeklyAvailability.objects.select_related('doctor').all()
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)
        serializer = DoctorWeeklyAvailabilitySerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = DoctorWeeklyAvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, pk):
        try:
            obj = DoctorWeeklyAvailability.objects.get(pk=pk)
        except DoctorWeeklyAvailability.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DoctorDateExceptionView(APIView):
    """Dean-side endpoint for managing any doctor's date exceptions."""
    permission_classes = [IsDean]

    def get(self, request):
        doctor_id = request.query_params.get('doctor_id')
        qs = DoctorDateException.objects.select_related('doctor').all()
        if doctor_id:
            qs = qs.filter(doctor_id=doctor_id)
        serializer = DoctorDateExceptionSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = DoctorDateExceptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, pk):
        try:
            obj = DoctorDateException.objects.get(pk=pk)
        except DoctorDateException.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── 3. Doctor self-availability endpoints ────────────────────────────────────

class MyAvailabilityView(APIView):
    """Doctor manages their own weekly availability."""
    permission_classes = [IsDoctorOrDean]

    def get(self, request):
        qs = DoctorWeeklyAvailability.objects.filter(doctor=request.user)
        serializer = DoctorWeeklyAvailabilitySerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        # Bulk mode: if 'weekdays' is a list, replace all
        if 'weekdays' in request.data and isinstance(request.data['weekdays'], list):
            weekdays = set(request.data['weekdays'])
            # Validate
            for w in weekdays:
                if not isinstance(w, int) or w < 0 or w > 6:
                    return Response(
                        {'detail': f'Invalid weekday {w}. Must be int 0-6.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            # Replace all
            DoctorWeeklyAvailability.objects.filter(doctor=request.user).delete()
            objs = [
                DoctorWeeklyAvailability(doctor=request.user, weekday=w)
                for w in weekdays
            ]
            DoctorWeeklyAvailability.objects.bulk_create(objs)
            qs = DoctorWeeklyAvailability.objects.filter(doctor=request.user)
            return Response(DoctorWeeklyAvailabilitySerializer(qs, many=True).data)

        # Single mode
        data = dict(request.data)
        data['doctor'] = request.user.id
        serializer = DoctorWeeklyAvailabilitySerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, pk):
        try:
            obj = DoctorWeeklyAvailability.objects.get(pk=pk, doctor=request.user)
        except DoctorWeeklyAvailability.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MyDateExceptionView(APIView):
    """Doctor manages their own date exceptions."""
    permission_classes = [IsDoctorOrDean]

    def get(self, request):
        qs = DoctorDateException.objects.filter(doctor=request.user)
        serializer = DoctorDateExceptionSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = dict(request.data)
        data['doctor'] = request.user.id
        serializer = DoctorDateExceptionSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, pk):
        try:
            obj = DoctorDateException.objects.get(pk=pk, doctor=request.user)
        except DoctorDateException.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── 4. Solver settings ViewSet ───────────────────────────────────────────────

class SolverSettingsViewSet(viewsets.ModelViewSet):
    """CRUD for solver settings (per committee_type × semester)."""
    queryset = SolverSettings.objects.all().order_by('-created_at')
    serializer_class   = SolverSettingsSerializer
    permission_classes = [IsDean]

    def get_queryset(self):
        qs = super().get_queryset()
        committee_type = self.request.query_params.get('committee_type')
        semester       = self.request.query_params.get('semester')
        is_active      = self.request.query_params.get('is_active')
        if committee_type:
            qs = qs.filter(committee_type=committee_type)
        if semester:
            qs = qs.filter(semester=semester)
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ('true', '1', 'yes'))
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


# ── 5. Scheduling runs (read-only) ───────────────────────────────────────────

class SchedulingRunListView(APIView):
    """List all scheduling runs for a given committee_type × semester."""
    permission_classes = [IsDean]

    def get(self, request):
        committee_type = request.query_params.get('committee_type')
        semester       = request.query_params.get('semester')
        status_filter  = request.query_params.get('status')

        qs = SchedulingRun.objects.select_related('solver_settings', 'requested_by').all()
        if committee_type:
            qs = qs.filter(committee_type=committee_type)
        if semester:
            qs = qs.filter(semester=semester)
        if status_filter:
            qs = qs.filter(status=status_filter)
        qs = qs.order_by('-requested_at')

        serializer = SchedulingRunSerializer(qs, many=True)
        return Response(serializer.data)


class SchedulingRunDetailView(APIView):
    """Retrieve a single scheduling run with full plan."""
    permission_classes = [IsDean]

    def get(self, request, pk):
        try:
            run = SchedulingRun.objects.get(pk=pk)
        except SchedulingRun.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = SchedulingRunSerializer(run)
        return Response(serializer.data)


# ── 6. Preview / Apply / Reject endpoints ────────────────────────────────────

from .solver import run_solver, apply_scheduling_run, reject_scheduling_run
from .models import SolverSettings, SchedulingRun, COMMITTEE_TYPE_AR


class SchedulePreviewView(APIView):
    """POST /api/committees/schedule/preview/

    Payload:
        {
            "committee_type": "seminar_1",
            "semester": "Spring 2026",
            "settings_id": 1,        # optional — auto-pick active if omitted
            "timeout_seconds": 30    # optional override
        }

    Returns:
        - 200 with the preview plan if solving succeeds
        - 200 with infeasibility_report if solving fails (still HTTP 200)
        - 400 on validation errors
    """
    permission_classes = [IsDean]

    def post(self, request):
        committee_type = request.data.get('committee_type')
        semester       = request.data.get('semester')
        settings_id    = request.data.get('settings_id')
        timeout_override = request.data.get('timeout_seconds')

        if not committee_type or not semester:
            return Response(
                {'detail': 'committee_type and semester are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Build SolverSettings (inline from request OR from DB) ──
        # The dean can pass all params directly in the request (simplified flow):
        #   date_range_start, date_range_end, daily_start, daily_end,
        #   buffer_minutes, workdays
        # If not provided, fall back to DB SolverSettings.
        inline_params = {
            'date_range_start': request.data.get('date_range_start'),
            'date_range_end': request.data.get('date_range_end'),
            'daily_start': request.data.get('daily_start'),
            'daily_end': request.data.get('daily_end'),
            'buffer_between_committees_minutes': request.data.get('buffer_minutes', 10),
            'discussion_duration': request.data.get('discussion_duration', 15),
            'workdays': request.data.get('workdays'),
        }
        has_inline = any(v is not None for v in inline_params.values())

        if has_inline:
            # Build an in-memory SolverSettings (not saved to DB)
            # Convert strings to proper date/time objects
            from datetime import date as dt_date, time as dt_time
            def _parse_date(s):
                if not s: return None
                if isinstance(s, dt_date): return s
                return dt_date.fromisoformat(str(s))
            def _parse_time(s):
                if not s: return dt_time(9, 0)
                if isinstance(s, dt_time): return s
                parts = str(s).split(':')
                return dt_time(int(parts[0]), int(parts[1]))
            settings_obj = SolverSettings(
                committee_type=committee_type,
                semester=semester,
                date_range_start=_parse_date(inline_params['date_range_start']),
                date_range_end=_parse_date(inline_params['date_range_end']),
                daily_start=_parse_time(inline_params['daily_start'] or '09:00'),
                daily_end=_parse_time(inline_params['daily_end'] or '17:00'),
                buffer_between_committees_minutes=int(inline_params['buffer_between_committees_minutes'] or 10),
                workdays=inline_params['workdays'] or [5, 6],  # default Sat+Sun
                solver_timeout_seconds=int(timeout_override or 30),
                is_active=True,
            )
            # Set discussion_duration as a temporary attribute (not a DB field)
            settings_obj.discussion_duration = int(inline_params['discussion_duration'] or 15)
        elif settings_id:
            try:
                settings_obj = SolverSettings.objects.get(
                    pk=settings_id,
                    committee_type=committee_type,
                    semester=semester,
                )
            except SolverSettings.DoesNotExist:
                return Response(
                    {
                        'detail': (
                            f'إعدادات Solver #{settings_id} غير موجودة أو لا تتبع '
                            f'نوع اللجنة والفصل الدراسي المطلوبين.'
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            settings_obj = (
                SolverSettings.objects
                .filter(committee_type=committee_type, semester=semester, is_active=True)
                .first()
            )
            if not settings_obj:
                return Response({
                    'detail': (
                        f'لا توجد إعدادات Solver فعّالة لـ '
                        f'"{COMMITTEE_TYPE_AR.get(committee_type, committee_type)}" '
                        f'في الفصل "{semester}". مرر المعطيات مباشرة أو أنشئ الإعدادات أولاً.'
                    ),
                }, status=status.HTTP_400_BAD_REQUEST)

        # Optional timeout override (cloned settings in memory)
        if timeout_override:
            try:
                # Clone to avoid mutating DB object
                from copy import copy
                settings_obj = copy(settings_obj)
                settings_obj.solver_timeout_seconds = int(timeout_override)
            except (ValueError, TypeError):
                pass

        # Create a SchedulingRun with status='pending'
        # If settings_obj is an inline (unsaved) object, we can't link it
        # via FK — so we set solver_settings=None.
        run = SchedulingRun.objects.create(
            committee_type=committee_type,
            semester=semester,
            solver_settings=settings_obj if settings_obj.pk else None,
            status='pending',
            requested_by=request.user,
        )

        # Run the solver
        try:
            result = run_solver(
                committee_type=committee_type,
                semester=semester,
                settings=settings_obj,
                requested_by=request.user,
            )
        except Exception as e:
            import traceback
            return Response({
                'detail': f'فشل الـ Solver: {str(e)}',
                'traceback': traceback.format_exc().split('\n'),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not result.get('success'):
            # Mark run as failed
            run.status = 'failed'
            run.infeasibility_report = result.get('infeasibility_report', [])
            run.solver_status = 'INFEASIBLE'
            run.solver_wall_time_sec = result.get('wall_time', 0)
            run.save(update_fields=['status', 'infeasibility_report',
                                     'solver_status', 'solver_wall_time_sec'])
            return Response({
                'success': False,
                'run_id': run.id,
                'status': 'failed',
                'infeasibility_report': run.infeasibility_report,
                'wall_time': run.solver_wall_time_sec,
            }, status=status.HTTP_200_OK)

        # Success — save plan and mark as preview
        run.plan_json = result['plan']
        run.summary_stats = result['summary_stats']
        run.solver_status = result['solver_status']
        run.solver_wall_time_sec = result['wall_time']
        run.status = 'preview'
        run.save(update_fields=['plan_json', 'summary_stats', 'solver_status',
                                 'solver_wall_time_sec', 'status'])

        return Response({
            'success': True,
            'run_id': run.id,
            'status': 'preview',
            'solver_status': run.solver_status,
            'wall_time': run.solver_wall_time_sec,
            'plan': run.plan_json,
            'summary_stats': run.summary_stats,
            # Non-blocking warnings (info/warn level — e.g. doctors
            # without explicit availability who are treated as default-available)
            'warnings': result.get('warnings', []),
        }, status=status.HTTP_200_OK)


class ScheduleApplyView(APIView):
    """POST /api/committees/schedule/{run_id}/apply/

    Applies a preview SchedulingRun to the DB.
    Clears existing scheduling for the same (committee_type × semester) first.
    """
    permission_classes = [IsDean]

    def post(self, request, run_id):
        try:
            run = SchedulingRun.objects.get(pk=run_id)
        except SchedulingRun.DoesNotExist:
            return Response({'detail': 'Run not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = apply_scheduling_run(run)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)


class ScheduleRejectView(APIView):
    """POST /api/committees/schedule/{run_id}/reject/

    Marks a preview SchedulingRun as rejected. Does not affect the DB.
    """
    permission_classes = [IsDean]

    def post(self, request, run_id):
        try:
            run = SchedulingRun.objects.get(pk=run_id)
        except SchedulingRun.DoesNotExist:
            return Response({'detail': 'Run not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = reject_scheduling_run(run)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)
