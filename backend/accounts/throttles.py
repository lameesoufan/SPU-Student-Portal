from rest_framework.throttling import SimpleRateThrottle


class LoginRateThrottle(SimpleRateThrottle):
    scope = 'accounts_login'

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        username = str(request.data.get('username', '')).strip().lower()
        key = f"{ident}:{username}" if username else ident
        return self.cache_format % {'scope': self.scope, 'ident': key}


class RegisterRateThrottle(SimpleRateThrottle):
    scope = 'accounts_register'

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        university_id = str(request.data.get('university_id', '')).strip().lower()
        key = f"{ident}:{university_id}" if university_id else ident
        return self.cache_format % {'scope': self.scope, 'ident': key}


class ProposeIdeaThrottle(SimpleRateThrottle):
    scope = 'propose_idea'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return self.cache_format % {'scope': self.scope, 'ident': request.user.pk}
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class WorkflowSubmitThrottle(SimpleRateThrottle):
    scope = 'workflow_submit'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return self.cache_format % {'scope': self.scope, 'ident': request.user.pk}
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class FileUploadThrottle(SimpleRateThrottle):
    scope = 'file_upload'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return self.cache_format % {'scope': self.scope, 'ident': request.user.pk}
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}
class PasswordResetThrottle(SimpleRateThrottle):
    """Rate limit for password change/reset: 3 per hour per user."""
    scope = 'password_reset'

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return self.cache_format % {'scope': self.scope, 'ident': request.user.pk}
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}