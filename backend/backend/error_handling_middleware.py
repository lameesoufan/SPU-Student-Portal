"""
Custom error handling middleware for better user-facing error messages.

This middleware catches common exceptions and returns user-friendly error messages
in Arabic, instead of exposing technical stack traces to end users.
"""
from django.http import JsonResponse
from django.db import IntegrityError
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler as drf_exception_handler
import logging

logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware:
    """
    Middleware to catch unhandled exceptions and return user-friendly error messages.
    
    This prevents technical stack traces from being shown to users while still
    logging the full error details for developers.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        """
        Handle exceptions that occur during request processing.
        """
        # Log the full exception details for debugging
        logger.error(
            f"Exception in {request.path}: {str(exception)}",
            exc_info=True,
            extra={'request': request}
        )
        
        # Check if this is an API request (starts with /api/)
        if not request.path.startswith('/api/'):
            return None  # Let Django handle non-API errors normally
        
        # Handle IntegrityError (database constraint violations)
        if isinstance(exception, IntegrityError):
            error_message = "حدث خطأ في قاعدة البيانات. يرجى التأكد من صحة البيانات المدخلة."
            
            # Try to extract more specific error info
            error_str = str(exception).lower()
            if 'null value' in error_str and 'not-null constraint' in error_str:
                error_message = "حقل مطلوب مفقود. يرجى ملء جميع الحقول المطلوبة."
            elif 'duplicate key' in error_str or 'unique constraint' in error_str:
                error_message = "هذا السجل موجود بالفعل. يرجى استخدام قيم مختلفة."
            elif 'foreign key' in error_str:
                error_message = "العنصر المرجعي غير موجود أو تم حذفه."
            
            return JsonResponse(
                {
                    'error': error_message,
                    'detail': 'حدث خطأ أثناء حفظ البيانات. يرجى المحاولة مرة أخرى أو الاتصال بالدعم الفني.',
                    'type': 'IntegrityError'
                },
                status=400
            )
        
        # Handle other database errors
        if 'django.db' in str(type(exception)):
            return JsonResponse(
                {
                    'error': 'حدث خطأ في قاعدة البيانات',
                    'detail': 'يرجى المحاولة مرة أخرى. إذا استمرت المشكلة، اتصل بالدعم الفني.',
                    'type': 'DatabaseError'
                },
                status=500
            )
        
        # Handle permission errors
        if 'PermissionDenied' in str(type(exception)):
            return JsonResponse(
                {
                    'error': 'ليس لديك صلاحية للقيام بهذا الإجراء',
                    'detail': 'يرجى التواصل مع المسؤول للحصول على الصلاحيات المطلوبة.',
                    'type': 'PermissionDenied'
                },
                status=403
            )
        
        # Handle generic errors
        return JsonResponse(
            {
                'error': 'حدث خطأ غير متوقع',
                'detail': 'يرجى المحاولة مرة أخرى. إذا استمرت المشكلة، اتصل بالدعم الفني.',
                'type': 'UnexpectedError'
            },
            status=500
        )


def custom_exception_handler(exc, context):
    """
    Custom exception handler for Django REST Framework.
    
    This provides user-friendly error messages for DRF exceptions.
    """
    # Call DRF's default exception handler first
    response = drf_exception_handler(exc, context)
    
    if response is not None:
        # Customize the error response
        error_data = response.data
        
        # If it's a simple error message, wrap it properly
        if isinstance(error_data, str):
            response.data = {
                'error': error_data,
                'detail': error_data
            }
        elif isinstance(error_data, dict):
            # Add Arabic translations for common error messages
            if 'detail' in error_data:
                detail = str(error_data['detail']).lower()
                if 'not found' in detail:
                    error_data['error'] = 'العنصر غير موجود'
                elif 'permission denied' in detail or 'not authorized' in detail:
                    error_data['error'] = 'ليس لديك صلاحية للقيام بهذا الإجراء'
                elif 'authentication' in detail:
                    error_data['error'] = 'يرجى تسجيل الدخول للمتابعة'
                elif 'required' in detail or 'this field' in detail:
                    error_data['error'] = 'يرجى ملء جميع الحقول المطلوبة'
                else:
                    error_data['error'] = 'حدث خطأ في الطلب'
            
            response.data = error_data
    
    return response
