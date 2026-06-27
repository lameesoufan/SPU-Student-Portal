from .token_views import CookieTokenObtainPairView, CookieTokenRefreshView, cookie_logout
from .views import (
    import_users, change_password, list_doctors, list_departments,
    assign_hod_view, logout, student_self_register,
    change_username, username_suggestions,
)
from .serializers import CustomTokenObtainPairView
from django.urls import path

urlpatterns = [
    path('api/token/', CookieTokenObtainPairView.as_view()),
    path('api/token/refresh/', CookieTokenRefreshView.as_view()),
    path('api/logout/', cookie_logout),
    path('api/change-password/',   change_password,                      name='change_password'),
    path('api/change-username/',   change_username,                      name='change_username'),
    path('api/username-suggestions/', username_suggestions,               name='username_suggestions'),
    path('api/import-users/',      import_users,                         name='import_users'),
    path('api/doctors/',           list_doctors,                         name='list_doctors'),
    path('api/departments/',       list_departments,                     name='list_departments'),
    path('api/assign-hod/',        assign_hod_view,                      name='assign_hod'),
    path('api/register/',          student_self_register,                name='student_self_register'),
]