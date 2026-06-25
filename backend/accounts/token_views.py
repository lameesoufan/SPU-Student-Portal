import base64
import json as json_module
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.conf import settings

from .serializers import CustomTokenObtainPairView


def _set_cookie(response, key, value, max_age):
    response.set_cookie(
        key, value,
        max_age=max_age,
        httponly=settings.JWT_COOKIE_HTTPONLY,
        secure=settings.JWT_COOKIE_SECURE,
        samesite=settings.JWT_COOKIE_SAMESITE,
        path='/',
    )


def _clear_cookie(response, key):
    response.delete_cookie(key, path='/', samesite=settings.JWT_COOKIE_SAMESITE)


class CookieTokenObtainPairView(CustomTokenObtainPairView):
    """Login — returns tokens as HttpOnly cookies + access token + user info in body."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            access = response.data.get('access')
            refresh = response.data.get('refresh')

            if access:
                _set_cookie(response, 'access_token', access, settings.JWT_COOKIE_ACCESS_MAX_AGE)
            if refresh:
                _set_cookie(response, 'refresh_token', refresh, settings.JWT_COOKIE_REFRESH_MAX_AGE)

            payload = {}
            if access:
                try:
                    payload_b64 = access.split('.')[1]
                    payload_b64 += '=' * (4 - len(payload_b64) % 4)
                    payload = json_module.loads(base64.urlsafe_b64decode(payload_b64))
                except Exception:
                    payload = {}

            response.data = {
                'message': 'Login successful',
                'access': access,   # ← أضفناه عشان الـ frontend يقدر يرسلو بـ Authorization header
                'username': payload.get('username', request.data.get('username', '')),
                'role': payload.get('role', ''),
                'must_change_password': payload.get('must_change_password', False),
                'department': payload.get('department', ''),
            }

        return response


class CookieTokenRefreshView(TokenRefreshView):
    """Refresh — reads refresh token from cookie, sets new cookies + returns access in body."""

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')
        if refresh_token:
            request.data['refresh'] = refresh_token

        response = super().post(request, *args, **kwargs)

        if response.status_code == 200:
            access = response.data.get('access')
            refresh = response.data.get('refresh')

            if access:
                _set_cookie(response, 'access_token', access, settings.JWT_COOKIE_ACCESS_MAX_AGE)
            if refresh:
                _set_cookie(response, 'refresh_token', refresh, settings.JWT_COOKIE_REFRESH_MAX_AGE)

            # ← أضفنا الـ access token بالـ response عشان الـ frontend يحفظو
            response.data = {
                'message': 'Token refreshed',
                'access': access,
            }

        return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cookie_logout(request):
    """Logout — clear cookies and blacklist the refresh token."""
    response = Response({'message': 'Logged out'}, status=status.HTTP_200_OK)

    _clear_cookie(response, 'access_token')
    _clear_cookie(response, 'refresh_token')

    refresh_token = request.COOKIES.get('refresh_token')
    if refresh_token:
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            pass

    return response