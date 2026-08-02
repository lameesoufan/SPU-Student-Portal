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



class StudentLoginRequestThrottle(SimpleRateThrottle):
    """Rate limit for OTP generation: 3 requests per 15 minutes per IP."""
    scope = 'student_login_request'

    def get_cache_key(self, request, view):
        # Throttle by IP address
        ident = self.get_ident(request)
        return self.cache_format % {'scope': self.scope, 'ident': ident}


class StudentLoginVerifyThrottle(SimpleRateThrottle):
    """Rate limit for OTP verification: 5 failed attempts per 30 minutes per session_token."""
    scope = 'student_login_verify'

    def get_cache_key(self, request, view):
        # Throttle by session_token instead of IP
        session_token = str(request.data.get('session_token', '')).strip()
        if not session_token:
            # Fallback to IP if no session_token provided
            return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}
        return self.cache_format % {'scope': self.scope, 'ident': f'session_{session_token}'}
