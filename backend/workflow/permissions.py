from rest_framework.permissions import BasePermission


class IsHodOrDoctor(BasePermission):
    """Allow only HoD or Doctor users."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['hod', 'doctor']


class IsHod(BasePermission):
    """Allow only HoD users."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'hod'


class IsStudent(BasePermission):
    """Allow only Student users."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'student'
