import logging

from django.http import HttpResponse
from django.core.cache import cache
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ImportRow, ImportSession

logger = logging.getLogger('project_imports')

from .permissions import IsSuperAdmin
from .serializers import ImportRowSerializer, ImportSessionSerializer
from .services import ImportService
from .templates import TemplateGenerator
from .throttles import ImportRateThrottle
from .validators import ImportValidationError


class ImportProjectsView(APIView):
    permission_classes = [IsSuperAdmin]
    throttle_classes = [ImportRateThrottle]
    parser_classes = [MultiPartParser, FormParser]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        # Successful imports may contain one-time plaintext credentials for newly
        # created accounts. Never allow browsers or intermediary caches to retain
        # the response.
        response['Cache-Control'] = 'no-store, private'
        response['Pragma'] = 'no-cache'
        return response

    def post(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response({'error': 'File is required.'}, status=status.HTTP_400_BAD_REQUEST)

        dry_run = str(request.query_params.get('dry_run', request.data.get('dry_run', 'false'))).lower() == 'true'
        preview_result_id = request.data.get('preview_result_id') or request.query_params.get('preview_result_id')
        lock_key = f'project_import_in_progress_{request.user.id}'
        if not cache.add(lock_key, True, timeout=3600):
            return Response(
                {'error': 'Import already in progress. Please wait for completion.'},
                status=status.HTTP_409_CONFLICT,
            )

        service = ImportService(request.user)
        try:
            result = service.execute_import(
                upload,
                dry_run=dry_run,
                preview_result_id=preview_result_id,
            )
        except ImportValidationError as exc:
            return Response(
                {'error': exc.message, 'details': exc.details},
                status=exc.status_code,
            )
        except Exception as exc:
            logger.exception('Import failed for user %s', request.user.username)
            return Response(
                {'error': 'Import failed. No changes were saved.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            cache.delete(lock_key)

        has_errors = bool(result.get('validation_errors'))
        has_valid_rows = result.get('valid_rows_count', 0) > 0
        if has_errors and not has_valid_rows:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result, status=status.HTTP_200_OK if dry_run else status.HTTP_201_CREATED)


class DownloadTemplateView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        content = TemplateGenerator().generate_template()
        response = HttpResponse(
            content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="project_import_template.xlsx"'
        return response


class ImportHistoryView(ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = ImportSessionSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = ImportSession.objects.filter(super_admin=self.request.user)
        status_filter = self.request.query_params.get('status')
        from_date = parse_date(self.request.query_params.get('from_date') or '')
        to_date = parse_date(self.request.query_params.get('to_date') or '')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if from_date:
            queryset = queryset.filter(started_at__date__gte=from_date)
        if to_date:
            queryset = queryset.filter(started_at__date__lte=to_date)
        return queryset


class ImportRowsView(ListAPIView):
    permission_classes = [IsSuperAdmin]
    serializer_class = ImportRowSerializer
    pagination_class = None

    def get_queryset(self):
        session_id = self.kwargs['session_id']
        return ImportRow.objects.filter(
            session_id=session_id,
            session__super_admin=self.request.user,
        ).select_related('created_student', 'created_project')
