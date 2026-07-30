from .token_views import CookieTokenObtainPairView, CookieTokenRefreshView, cookie_logout, current_user
from .views import (
    import_users, change_password, list_doctors, list_departments,
    assign_hod_view, student_self_register,
    change_username, username_suggestions,
    upload_reference,
    student_login_request, student_login_verify,
    request_password_reset, verify_password_reset_code, reset_password_with_code,
)
from .serializers import CustomTokenObtainPairView
from django.urls import path

urlpatterns = [
    path('api/token/', CookieTokenObtainPairView.as_view()),
    path('api/token/refresh/', CookieTokenRefreshView.as_view()),
    path('api/logout/', cookie_logout),
    path('api/auth/me/', current_user, name='current_user'),
    path('api/change-password/',   change_password,                      name='change_password'),
    path('api/change-username/',   change_username,                      name='change_username'),
    path('api/username-suggestions/', username_suggestions,               name='username_suggestions'),
    path('api/import-users/',      import_users,                         name='import_users'),
    path('api/doctors/',           list_doctors,                         name='list_doctors'),
    path('api/departments/',       list_departments,                     name='list_departments'),
    path('api/assign-hod/',        assign_hod_view,                      name='assign_hod'),
    path('api/register/',          student_self_register,                name='student_self_register'),
    path('api/upload-reference/',  upload_reference,                     name='upload_reference'),
    path('api/auth/password-reset/request/', request_password_reset, name='password_reset_request'),
    path('api/auth/password-reset/verify/', verify_password_reset_code, name='password_reset_verify'),
    path('api/auth/password-reset/confirm/', reset_password_with_code, name='password_reset_confirm'),
    path('api/auth/student-login-request/', student_login_request,       name='student_login_request'),
    path('api/auth/student-login-verify/',  student_login_verify,        name='student_login_verify'),
]