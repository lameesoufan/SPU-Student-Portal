from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    message = 'Insufficient permissions for bulk import operations'

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, 'role', None) == 'dean'
            and bool(getattr(user, 'is_superuser', False))
        )
