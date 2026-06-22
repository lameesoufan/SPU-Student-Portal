# Security Guidelines & Best Practices

## 📋 Overview

Comprehensive security documentation covering authentication, authorization, data protection, and security best practices implemented in the SPU Student Portal.

## 🔐 Authentication Security

### JWT Token Management

**Token Lifecycle**:
- Access Token: 30 minutes (short-lived)
- Refresh Token: 1 day (medium-lived)
- Automatic rotation on refresh
- Blacklisting on logout

**Storage**:
```javascript
// ✅ CORRECT: HttpOnly cookies (backend sets)
response.set_cookie(
    'access_token',
    token,
    httponly=True,      // Prevents JavaScript access
    secure=True,        // HTTPS only in production
    samesite='Lax',     // CSRF protection
)

// ❌ WRONG: localStorage or sessionStorage
localStorage.setItem('token', token);  // Vulnerable to XSS
```

### Password Security

**Hashing**: Django's PBKDF2 with SHA256
- 260,000 iterations (Django 5.2 default)
- Automatic work factor increases in future versions

**Validation Rules**:
- Minimum 8 characters
- Cannot be too similar to username/email
- Cannot be entirely numeric
- Cannot be a common password

**Password Change Flow**:
```python
# Force password change on first login
if user.must_change_password:
    # Redirect to change password page
    # Disable other functionality until changed
```

## 🛡️ Authorization & Access Control

### Role-Based Permissions

**Permission Hierarchy**:
```
Dean (Superuser)
└─ Full system access
   ├─ HoD (Department Admin)
   │  └─ Department-level management
   │     ├─ Doctor (Supervisor)
   │     │  └─ Project supervision
   │     └─ Student
   │        └─ Own project access
```

**Permission Checks**:
```python
# ✅ CORRECT: Explicit permission checks
from rest_framework.permissions import IsAuthenticated
from .permissions import IsHod, IsBoardMember

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsHod])
def create_form(request):
    # HoD-only function
    pass

# ❌ WRONG: Trusting frontend
if request.user.role == 'hod':  # Client can manipulate this
    # Dangerous!
```

### Resource-Level Authorization

**Board Access**:
```python
def _get_board_for_member(user, board_id):
    board = ProjectBoard.objects.get(pk=board_id)
    
    # Students: must be team member
    if user.role == 'student':
        if not board.members.filter(pk=user.pk).exists():
            return None
    
    # Doctors: must be supervisor
    if user.role == 'doctor':
        if not is_supervisor(board, user):
            return None
    
    return board
```

## 🔒 Data Protection

### Sensitive Data Encryption

**GitLab Access Tokens**:
```python
from cryptography.fernet import Fernet
import base64, hashlib

def _get_fernet():
    # Derive key from SECRET_KEY
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    )
    return Fernet(key)

class EncryptedCharField(models.CharField):
    def get_prep_value(self, value):
        if value:
            return _get_fernet().encrypt(value.encode()).decode()
        return value
    
    def from_db_value(self, value, expression, connection):
        if value:
            return _get_fernet().decrypt(value.encode()).decode()
        return value
```

**⚠️ WARNING**: Changing `SECRET_KEY` will break all encrypted data

### SQL Injection Prevention

**✅ SAFE: Django ORM**:
```python
# Parameterized queries (automatic)
User.objects.filter(username=user_input)
Task.objects.filter(title__icontains=search_query)
```

**❌ DANGEROUS: Raw SQL**:
```python
# Never do this!
cursor.execute(f"SELECT * FROM users WHERE username = '{username}'")
```

### XSS Prevention

**Backend**:
- All output escaped by default in Django templates
- DRF serializers sanitize JSON output

**Frontend**:
```javascript
// ✅ SAFE: React escapes by default
<div>{user.name}</div>

// ❌ DANGEROUS: dangerouslySetInnerHTML
<div dangerouslySetInnerHTML={{__html: userInput}} />
```

### CSRF Protection

**Enabled by Default**:
```python
MIDDLEWARE = [
    'django.middleware.csrf.CsrfViewMiddleware',
]
```

**Cookie-Based Auth**:
- `SameSite=Lax` prevents CSRF attacks
- CORS configured for specific origins only

### File Upload Security

**Validation Layers**:
```python
# 1. Size check
if file.size > MAX_FILE_SIZE:
    raise ValidationError("File too large")

# 2. Extension check
ext = os.path.splitext(file.name)[1].lower()
if ext not in ALLOWED_EXTENSIONS:
    raise ValidationError("Invalid file type")

# 3. MIME type check
mime_type = mimetypes.guess_type(file.name)[0]
if mime_type not in MIME_WHITELIST:
    raise ValidationError("Invalid MIME type")
```

**⚠️ RECOMMENDED**: Add virus scanning (e.g., ClamAV)

## 🌐 Network Security

### HTTPS/TLS

**Production Requirements**:
```python
# settings.py (production)
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
```

### CORS Configuration

**Whitelist Approach**:
```python
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    'https://portal.spu.edu.sy',
    'https://admin.spu.edu.sy',
]

# ❌ NEVER do this in production:
# CORS_ALLOW_ALL_ORIGINS = True
```

### Rate Limiting

**Throttle Configuration**:
```python
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/minute',
        'user': '600/minute',
        'accounts_login': '10/minute',      # Brute-force protection
        'accounts_register': '5/minute',     # Spam protection
        'file_upload': '20/hour',            # Resource protection
    }
}
```

### Webhook Security

**Signature Verification**:
```python
def verify_webhook_signature(request):
    provided_token = request.headers.get('X-Gitlab-Token')
    expected_token = settings.GITLAB_WEBHOOK_SECRET
    
    if not provided_token:
        raise ValueError("Missing webhook signature")
    
    if not secrets.compare_digest(provided_token, expected_token):
        raise ValueError("Invalid webhook signature")
```

## 🔍 Security Headers

**Configured Headers**:
```python
# Django security middleware
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Permissions Policy
PERMISSIONS_POLICY = {
    'camera': [],
    'microphone': [],
    'geolocation': [],
}
```

**Expected Response Headers**:
```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Strict-Transport-Security: max-age=31536000; includeSubDomains
Referrer-Policy: strict-origin-when-cross-origin
```

## 🚨 Common Vulnerabilities & Mitigations

### 1. Broken Authentication

**Vulnerability**: Weak password policies, session fixation

**Mitigation**:
- ✅ Strong password validation
- ✅ Token rotation on refresh
- ✅ Token blacklisting on logout
- ✅ HttpOnly secure cookies

### 2. Broken Authorization

**Vulnerability**: Insecure direct object references (IDOR)

**Mitigation**:
```python
# ❌ BAD: No authorization check
def get_proposal(request, proposal_id):
    proposal = StudentIdeaProposal.objects.get(pk=proposal_id)
    return Response(ProposalSerializer(proposal).data)

# ✅ GOOD: Verify ownership/permissions
def get_proposal(request, proposal_id):
    proposal = StudentIdeaProposal.objects.get(
        pk=proposal_id,
        student=request.user  # Only owner can access
    )
    return Response(ProposalSerializer(proposal).data)
```

### 3. Sensitive Data Exposure

**Vulnerability**: Passwords, tokens in logs/responses

**Mitigation**:
```python
# ✅ Never log sensitive data
logger.info(f"User login: {username}")  # OK
logger.debug(f"Token: {token}")         # NEVER!

# ✅ Exclude from serializers
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        exclude = ['password', 'access_token']
```

### 4. XXE (XML External Entity)

**Vulnerability**: XML parsing attacks

**Mitigation**: Not applicable (system uses JSON only)

### 5. Security Misconfiguration

**Vulnerability**: Debug mode in production, default passwords

**Checklist**:
- ✅ `DEBUG = False` in production
- ✅ Strong `SECRET_KEY` (64+ random chars)
- ✅ Change default admin password
- ✅ Disable unnecessary services
- ✅ Keep dependencies updated

### 6. Insufficient Logging

**Mitigation**:
```python
# Log security events
logger.warning(f"Failed login attempt: {username} from {ip}")
logger.info(f"User {user.id} accessed board {board_id}")
logger.error(f"Unauthorized access attempt to {url} by {user.id}")
```

## 🔐 Secrets Management

### Environment Variables

**✅ REQUIRED**:
```bash
SECRET_KEY=<64-char-random-string>
DB_PASSWORD=<strong-password>
GITLAB_TOKEN=<gitlab-admin-token>
GITLAB_WEBHOOK_SECRET=<webhook-secret>
```

**Generation**:
```python
# Generate SECRET_KEY
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())

# Generate webhook secret
import secrets
print(secrets.token_urlsafe(32))
```

### .env File Security

**✅ DO**:
- Add `.env` to `.gitignore`
- Use `.env.example` with placeholder values
- Restrict file permissions: `chmod 600 .env`
- Use separate `.env` per environment

**❌ DON'T**:
- Commit `.env` to version control
- Share `.env` via email/chat
- Use production secrets in development

## 🛡️ Deployment Security Checklist

### Pre-Deployment

- [ ] `DEBUG = False`
- [ ] Strong `SECRET_KEY` generated
- [ ] Database credentials secured
- [ ] HTTPS configured (TLS certificate)
- [ ] CORS whitelist configured
- [ ] Rate limiting enabled
- [ ] Security headers configured
- [ ] Admin password changed from default
- [ ] All dependencies updated
- [ ] Security scan completed

### Post-Deployment

- [ ] Monitor error logs for security events
- [ ] Regular security updates
- [ ] Periodic penetration testing
- [ ] Backup verification
- [ ] SSL certificate renewal tracking

## 📝 Incident Response

### Security Incident Procedure

1. **Detect**: Monitor logs, alerts, user reports
2. **Contain**: Disable affected accounts/features
3. **Investigate**: Analyze logs, identify scope
4. **Remediate**: Patch vulnerability, restore service
5. **Document**: Write incident report
6. **Review**: Update security measures

### Contact Information

**Security Team**: security@spu.edu.sy  
**Emergency**: +963-XXX-XXXXXX

## 🔄 Security Updates

### Dependency Updates

```bash
# Check for vulnerabilities
pip-audit

# Update dependencies
pip install --upgrade -r requirements.txt

# Test thoroughly after updates
python manage.py test
```

### Django Security Updates

Subscribe to: https://www.djangoproject.com/weblog/

## 📚 Additional Resources

- [OWASP Top 10](https://owasp.org/Top10/)
- [Django Security](https://docs.djangoproject.com/en/5.2/topics/security/)
- [Mozilla Web Security](https://infosec.mozilla.org/guidelines/web_security)

---

**Related Documentation**:
- [Authentication](01-AUTHENTICATION.md)
- [API Reference](08-API-REFERENCE.md)
- [Database Schema](09-DATABASE-SCHEMA.md)

**Last Updated**: June 22, 2026
