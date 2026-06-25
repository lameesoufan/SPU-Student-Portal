from rest_framework.permissions import BasePermission


class IsDoctor(BasePermission):
    """Allow doctors AND HoDs (who are also doctors) to submit ideas."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in ('doctor', 'hod'))


class IsDoctorOrHod(BasePermission):
    """Allow doctors or HoDs."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role in ('doctor', 'hod'))


class IsStudent(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'student')


class IsHod(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'hod')