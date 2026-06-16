from rest_framework.permissions import BasePermission

class IsDeanOrAdmin(BasePermission):
    """Dean has all admin privileges (superuser)."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'dean'