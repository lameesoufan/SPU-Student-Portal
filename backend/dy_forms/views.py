from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from django.db import transaction
import json

from .models import DynamicForm, FormField, FormResponse
from .serializers import DynamicFormSerializer, FormResponseSerializer
from .permissions import IsHod, IsStudent
from .validators import validate_context, validate_form_fields


import os
import mimetypes

MAX_FORM_FILE_SIZE = 10 * 1024 * 1024   # 10 MB
ALLOWED_FORM_FILE_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    '.ppt', '.pptx', '.txt', '.csv',
    '.jpg', '.jpeg', '.png', '.gif',
    '.zip', '.rar',
}
FORM_MIME_WHITELIST = {
    'application/pdf', 'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain', 'text/csv',
    'image/jpeg', 'image/png', 'image/gif',
    'application/zip', 'application/x-rar-compressed',
}


def _validate_form_file(file):
    """فحص حجم ونوع ملف النموذج الديناميكي."""
    if file.size > MAX_FORM_FILE_SIZE:
        raise ValueError(f'File too large. Max {MAX_FORM_FILE_SIZE // (1024*1024)} MB.')
    extension = os.path.splitext(file.name or '')[1].lower()
    if extension not in ALLOWED_FORM_FILE_EXTENSIONS:
        raise ValueError(f'Unsupported file type: {extension}')
    mime_type, _ = mimetypes.guess_type(file.name or '')
    content_type = getattr(file, 'content_type', None) or mime_type
    if content_type and content_type not in FORM_MIME_WHITELIST:
        raise ValueError('Unsupported file type (MIME mismatch).')


def _validation_error(error):
    return Response({'error': 'Validation failed.', 'details': error}, status=400)


def _empty_form_response():
    return Response({'id': None, 'title': '', 'description': '', 'fields': []})


def _can_access_response(user, response):
    if user.role == 'hod' and response.form.department == user.department:
        return True
    if user.role == 'student' and response.student_id == user.id:
        return True
    if user.role == 'doctor':
        try:
            from projects.models import StudentIdeaProposal, IdeaApplication
            if response.proposal_id and StudentIdeaProposal.objects.filter(
                pk=response.proposal_id, supervisor=user
            ).exists():
                return True
            if response.application_id and IdeaApplication.objects.filter(
                pk=response.application_id, idea__doctor=user
            ).exists():
                return True
        except Exception:
            return False
    return False


# ── HoD: save/update form for their department ───────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHod])
def hod_get_form(request, context):
    """GET the HoD's form for a given context (propose / browse)."""
    try:
        validate_context(context)
    except Exception as exc:
        return _validation_error({'context': exc.detail if hasattr(exc, 'detail') else str(exc)})

    form = DynamicForm.objects.filter(
        department=request.user.department, context=context
    ).prefetch_related('fields').first()
    if not form:
        return _empty_form_response()
    return Response(DynamicFormSerializer(form).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsHod])
def hod_save_form(request, context):
    """POST to create/replace the HoD's form fields for a given context."""
    try:
        validate_context(context)
        fields_data = validate_form_fields(request.data.get('fields', []))
    except Exception as exc:
        return _validation_error(exc.detail if hasattr(exc, 'detail') else str(exc))

    title       = request.data.get('title', '')
    description = request.data.get('description', '')

    with transaction.atomic():
        form, _ = DynamicForm.objects.get_or_create(
            department=request.user.department,
            context=context,
            defaults={
                'hod': request.user, 
                'title': title,
                'description': description,
            },
        )
        form.title = title
        form.description = description
        form.hod   = request.user
        form.save()

        form.fields.all().delete()
        for idx, f in enumerate(fields_data):
            FormField.objects.create(
                form       = form,
                label      = f['label'],
                field_type = f['field_type'],
                required   = f['required'],
                options    = f['options'],
                order      = idx,
            )

    return Response(DynamicFormSerializer(
        DynamicForm.objects.prefetch_related('fields').get(pk=form.pk)
    ).data)


# ── Student: fetch form for a department + context ───────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_get_form(request, department, context):
    """GET the dynamic form for a department+context (visible to students)."""
    try:
        validate_context(context)
    except Exception as exc:
        return _validation_error({'context': exc.detail if hasattr(exc, 'detail') else str(exc)})

    form = DynamicForm.objects.filter(
        department=department, context=context
    ).prefetch_related('fields').first()
    if not form:
        return _empty_form_response()
    return Response(DynamicFormSerializer(form).data)


# ── Student: submit form response ────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsStudent])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def submit_form_response(request):
    """POST a student's filled form response."""
    for key, file in request.FILES.items():
        try:
            _validate_form_file(file)
        except ValueError as e:
            return _validation_error({key: str(e)})
    data = request.data
    # When sent as multipart/form-data, field_responses arrives as a JSON string
    if isinstance(data.get('field_responses'), str):
        try:
            data = dict(data)
            data['field_responses'] = json.loads(data['field_responses'])
        except (json.JSONDecodeError, ValueError):
            return _validation_error({'field_responses': 'Invalid JSON.'})

    serializer = FormResponseSerializer(data=data, context={'request': request})
    if not serializer.is_valid():
        return _validation_error(serializer.errors)
    response = serializer.save(student=request.user)
    return Response(FormResponseSerializer(response, context={'request': request}).data, status=201)


# ── Retrieve responses (HoD / admin) ─────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsHod])
def hod_list_responses(request, context):
    """GET all form responses for the HoD's department + context."""
    responses = FormResponse.objects.filter(
        form__department=request.user.department,
        form__context=context,
    ).select_related('student', 'form').prefetch_related('field_responses__field')[:MAX_RESPONSE_LIST_SIZE]
    return Response(FormResponseSerializer(responses, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_response_by_proposal(request, proposal_id):
    """GET the form response linked to a specific proposal."""
    resp = FormResponse.objects.select_related('form', 'student').prefetch_related(
        'field_responses__field'
    ).filter(proposal_id=proposal_id).order_by('-submitted_at').first()
    if not resp or not _can_access_response(request.user, resp):
        return Response({'detail': 'Not found.'}, status=404)
    return Response(FormResponseSerializer(resp, context={'request': request}).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_response_by_application(request, application_id):
    """GET the form response linked to a specific idea application."""
    resp = FormResponse.objects.select_related('form', 'student').prefetch_related(
        'field_responses__field'
    ).filter(application_id=application_id).order_by('-submitted_at').first()
    if not resp or not _can_access_response(request.user, resp):
        return Response({'detail': 'Not found.'}, status=404)
    return Response(FormResponseSerializer(resp, context={'request': request}).data)