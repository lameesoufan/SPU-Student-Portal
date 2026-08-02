"""
Workflow App — API Views (Thin Layer)

كل view هون بيعمل 3 أشياء بس: يتحقق من الصلاحية الأساسية، يفكّ الطلب،
ويستدعي الدالة المناسبة من services.py. كل منطق العمل موجود حصراً هناك.
"""
import json

from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.decorators import parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .serializers import (
    WorkflowTemplateSerializer, ProjectWorkflowSerializer, WorkflowStageInstanceSerializer,
)
from .permissions import IsHodOrDoctor, IsHod, IsStudent
from accounts.throttles import WorkflowSubmitThrottle
from . import services as svc


def _error_response(result):
    """يبني Response موحّد من أي dict خطأ راجع من services.py، مع الحفاظ على أي مفاتيح إضافية (missing_fields, active_count...)."""
    payload = {k: v for k, v in result.items() if k not in ('ok', 'status')}
    if 'error' not in payload:
        payload['error'] = 'حدث خطأ.'
    return Response(payload, status=result.get('status', 400))


# ── HoD/Doctor: Manage Workflow Templates ────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def list_workflow_templates(request):
    result = svc.list_templates_for_user(request.user)
    return Response(WorkflowTemplateSerializer(result['templates'], many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def get_workflow_template(request, template_id):
    result = svc.get_template_detail(request.user, template_id)
    if not result['ok']:
        return _error_response(result)
    return Response(WorkflowTemplateSerializer(result['template']).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def create_workflow_template(request):
    result = svc.create_template(request.user, request.data)
    if not result['ok']:
        return _error_response(result)
    return Response(WorkflowTemplateSerializer(result['template']).data, status=result.get('status', 201))


@api_view(['PUT'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def update_workflow_template(request, template_id):
    result = svc.update_template(request.user, template_id, request.data)
    if not result['ok']:
        return _error_response(result)

    data = WorkflowTemplateSerializer(result['template']).data
    if result.get('warnings'):
        return Response({**data, 'data': data, 'warnings': result['warnings']})
    return Response(data)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def delete_workflow_template(request, template_id):
    result = svc.delete_template(request.user, template_id)
    if not result['ok']:
        return _error_response(result)
    return Response({'message': 'Template deleted successfully'})


# ── Apply Workflow to Project ─────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def apply_workflow_to_project(request):
    result = svc.apply_workflow_to_project(
        request.user,
        request.data.get('project_board_id'),
        request.data.get('template_id'),
    )
    if not result['ok']:
        return _error_response(result)
    return Response(ProjectWorkflowSerializer(result['workflow']).data, status=result.get('status', 201))


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def apply_workflow_bulk(request):
    result = svc.apply_workflow_bulk(
        request.user,
        request.data.get('template_id'),
        request.data.get('project_ids', []),
        request.data.get('replace_existing', True),
    )
    if not result['ok']:
        return _error_response(result)

    r = result['results']
    return Response({
        'message': result['message'],
        'applied_count': len(r['applied']),
        'replaced_count': len(r['replaced']),
        'skipped_count': len(r['skipped']),
        'error_count': len(r['errors']),
        'results': r,
    }, status=result.get('status', 201))


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def get_available_projects(request):
    result = svc.list_available_projects(request.user)
    return Response(result['projects'])


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def get_projects_workflow_status(request):
    result = svc.get_projects_workflow_status(request.user)
    return Response(result['projects'])


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def get_reviewable_projects(request):
    result = svc.get_reviewable_projects(request.user)
    return Response(result['projects'])


# ── Student: View and Submit Workflow Stages ──────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_project_workflow(request, project_board_id):
    result = svc.get_project_workflow_data(request.user, project_board_id)
    if not result['ok']:
        return _error_response(result)
    return Response(ProjectWorkflowSerializer(
        result['workflows'], many=True, context={'request': request}
    ).data)


@api_view(['PUT'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def replace_workflow_for_project(request, project_board_id):
    result = svc.replace_workflow_for_project(
        request.user,
        project_board_id,
        request.data.get('new_template_id'),
        request.data.get('keep_completed_stages', True),
    )
    if not result['ok']:
        return _error_response(result)
    return Response({
        'message': 'Workflow replaced successfully',
        'old_workflow_id': result['old_workflow_id'],
        'new_workflow_id': result['new_workflow_id'],
        'preserved_completed_stages': result['preserved_completed_stages'],
        'new_stages_count': result['new_stages_count'],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsStudent])
def get_pending_stages(request):
    result = svc.get_pending_stages_for_student(request.user)
    return Response(WorkflowStageInstanceSerializer(
        result['stages'], many=True, context={'request': request}
    ).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
@throttle_classes([WorkflowSubmitThrottle])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def submit_workflow_stage(request, stage_instance_id):
    field_responses = request.data.get('field_responses', {})
    if isinstance(field_responses, str):
        try:
            field_responses = json.loads(field_responses)
        except (json.JSONDecodeError, TypeError, ValueError):
            return Response({'error': 'field_responses must contain valid JSON.'}, status=400)

    result = svc.submit_workflow_stage(
        request.user,
        stage_instance_id,
        field_responses,
        request.FILES,
    )
    if not result['ok']:
        return _error_response(result)
    return Response(WorkflowStageInstanceSerializer(
        result['stage_instance'], context={'request': request}
    ).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def cleanup_duplicate_stages(request):
    result = svc.cleanup_duplicate_stages(request.user)
    return Response({'message': 'Cleanup completed', 'results': result['results']})


# ── HoD/Doctor: Review Workflow Stage Submissions ─────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsHodOrDoctor])
def review_workflow_stage(request, stage_instance_id):
    result = svc.review_workflow_stage(
        request.user,
        stage_instance_id,
        request.data.get('action'),
        request.data.get('feedback', ''),
    )
    if not result['ok']:
        return _error_response(result)
    return Response(WorkflowStageInstanceSerializer(result['stage_instance']).data)
