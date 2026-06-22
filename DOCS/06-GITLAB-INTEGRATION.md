# GitLab Integration System

## 📋 Overview

The GitLab Integration provides seamless version control integration for graduation projects. Students can link their GitLab accounts, supervisors can create repositories, manage team access, and track code commits in real-time. The system supports both self-hosted GitLab CE instances and GitLab.com.

## 🎯 Key Features

- **Account Linking**: Students link personal GitLab accounts with access tokens
- **Repository Management**: Auto-create repositories for projects
- **Member Management**: Add/remove team members with role-based access
- **Commit Tracking**: Real-time webhook integration for commit history
- **Contribution Analytics**: Track individual contributions and statistics
- **Security**: Encrypted token storage, webhook signature verification

## 🏗️ Architecture

### Entity Model

```
GitLabUser (user account linkage)
  ↓
GitLabProject (one per ProjectBoard)
├── GitLabCommit (multiple)
│   └── GitLabCommitFile (multiple)
└── Members (via GitLab API)
```

### Core Models

#### 1. GitLabUser

```python
class GitLabUser:
    user = OneToOneField(User)  # Portal user
    gitlab_user_id = PositiveIntegerField  # GitLab user ID
    gitlab_username = CharField(100)
    gitlab_name = CharField(200)
    gitlab_email = EmailField
    avatar_url = URLField
    access_token = EncryptedCharField(500)  # Personal Access Token
    linked_at = DateTimeField
    updated_at = DateTimeField
```

**Encryption**: Access tokens encrypted using Fernet (symmetric encryption)
- Key derived from Django `SECRET_KEY`
- Encrypted at rest, decrypted on read
- Prevents token exposure in database dumps

#### 2. GitLabProject

```python
class GitLabProject:
    board = OneToOneField(ProjectBoard)
    gitlab_project_id = PositiveIntegerField  # GitLab project ID
    gitlab_project_path = CharField(255)  # e.g., "group/project"
    project_name = CharField(200)
    web_url = URLField  # Browser URL
    ssh_url = URLField  # SSH clone URL
    http_url = URLField  # HTTPS clone URL
    visibility = CharField(20)  # private, internal, public
    default_branch = CharField(100)
    webhook_id = PositiveIntegerField  # Registered webhook ID
    is_orphaned = BooleanField  # True if deleted from GitLab
    created_at = DateTimeField
    updated_at = DateTimeField
```

**Relationship**: One-to-one with ProjectBoard (one repo per project)

#### 3. GitLabCommit

```python
class GitLabCommit:
    project = ForeignKey(GitLabProject)
    sha = CharField(40)  # Git commit SHA
    message = TextField
    author_name = CharField(200)
    author_email = EmailField
    author_username = CharField(100)
    ref = CharField(200)  # Branch name
    authored_date = DateTimeField
    committed_date = DateTimeField
    web_url = URLField
    added_lines = PositiveIntegerField
    removed_lines = PositiveIntegerField
    total_lines = PositiveIntegerField
    created_at = DateTimeField
```

**Unique Constraint**: (project, sha) to prevent duplicate commits

#### 4. GitLabCommitFile

```python
class GitLabCommitFile:
    commit = ForeignKey(GitLabCommit)
    file_path = CharField(500)
    status = CharField(20)  # added, modified, deleted, renamed
    additions = PositiveIntegerField
    deletions = PositiveIntegerField
```

## 🔄 Integration Workflows

### 1. Link GitLab Account

**Prerequisite**: Student must create Personal Access Token in GitLab
- Scopes required: `api` or `read_user + read_repository + write_repository`

**Step 1: Get GitLab URL**

**Endpoint**: `GET /api/gitlab/config/`

**Response**:
```json
{
  "success": true,
  "gitlab_url": "http://gitlab.spu.edu.sy"
}
```

**Step 2: Create Access Token** (Student does this in GitLab)
1. Go to GitLab → User Settings → Access Tokens
2. Create token with name "SPU Portal"
3. Select scopes: `api`
4. Copy generated token

**Step 3: Link Account**

**Endpoint**: `POST /api/gitlab/link/`

**Request**:
```json
{
  "gitlab_token": "glpat-xxxxxxxxxxxxxxxxxxxx",
  "gitlab_username": "john.doe"  // Optional
}
```

**Process**:
1. Verify token with GitLab API (`/api/v4/user`)
2. Extract user info (ID, username, name, email, avatar)
3. Encrypt and store token
4. Create/update GitLabUser record

**Response**:
```json
{
  "success": true,
  "message": "تم ربط حسابك بنجاح: john.doe",
  "data": {
    "gitlab_user_id": 123,
    "gitlab_username": "john.doe",
    "gitlab_name": "John Doe",
    "gitlab_email": "john@example.com",
    "avatar_url": "https://gitlab.../avatar.jpg",
    "linked_at": "2026-06-22T10:00:00Z"
  }
}
```

### 2. Create GitLab Repository

**Endpoint**: `POST /api/gitlab/board/{board_id}/create-project/`

**Permission**: Project member or supervisor

**Request**:
```json
{
  "project_name": "smart-campus-app",  // Optional, auto-generated if omitted
  "visibility": "private",  // private, internal, public
  "initialize_with_readme": true
}
```

**Process**:
1. Validate user is board member
2. Check no existing GitLab project for this board
3. Generate project name if not provided:
   ```python
   name = board.title.lower().replace(' ', '-')
   name = re.sub(r'[^a-z0-9-]', '', name)
   ```
4. Create repository via GitLab API:
   ```python
   POST /api/v4/projects
   {
     "name": "Smart Campus App",
     "path": "smart-campus-app",
     "namespace_id": creator_namespace_id,
     "visibility": "private",
     "initialize_with_readme": true
   }
   ```
5. Add supervisor as Maintainer (access level 40)
6. Create GitLabProject record
7. Register webhook for push events

**Response**:
```json
{
  "success": true,
  "message": "تم إنشاء المستودع: smart-campus-app",
  "data": {
    "id": 50,
    "gitlab_project_id": 456,
    "project_name": "Smart Campus App",
    "gitlab_project_path": "john.doe/smart-campus-app",
    "web_url": "http://gitlab.spu.edu.sy/john.doe/smart-campus-app",
    "ssh_url": "git@gitlab.spu.edu.sy:john.doe/smart-campus-app.git",
    "http_url": "http://gitlab.spu.edu.sy/john.doe/smart-campus-app.git",
    "visibility": "private",
    "default_branch": "main",
    "webhook_registered": true
  }
}
```

### 3. Manage Team Members

#### Add Member

**Endpoint**: `POST /api/gitlab/board/{board_id}/members/add/`

**Permission**: Supervisor or admin

**Request**:
```json
{
  "gitlab_username": "jane.smith",
  "access_level": 30  // 10=Guest, 20=Reporter, 30=Developer, 40=Maintainer
}
```

**GitLab Access Levels**:
- **10 (Guest)**: View repository only
- **20 (Reporter)**: Pull code, view issues
- **30 (Developer)**: Push code, create branches
- **40 (Maintainer)**: Manage repository settings, members

**Process**:
1. Lookup GitLab user by username
2. Add member via API:
   ```python
   POST /api/v4/projects/{id}/members
   {
     "user_id": gitlab_user_id,
     "access_level": 30
   }
   ```

**Response**:
```json
{
  "success": true,
  "message": "تمت إضافة Jane Smith (Developer)",
  "data": {
    "gitlab_user_id": 789,
    "name": "Jane Smith",
    "username": "jane.smith",
    "access_level": 30,
    "access_level_name": "Developer"
  }
}
```

#### Remove Member

**Endpoint**: `POST /api/gitlab/board/{board_id}/members/remove/`

**Request**:
```json
{
  "gitlab_user_id": 789
}
```

**Process**:
```python
DELETE /api/v4/projects/{id}/members/{user_id}
```

#### List Members

**Endpoint**: `GET /api/gitlab/board/{board_id}/members/`

**Response**:
```json
{
  "success": true,
  "data": [
    {
      "id": 123,
      "username": "john.doe",
      "name": "John Doe",
      "email": "john@example.com",
      "avatar_url": "https://...",
      "access_level": 30,
      "access_level_name": "Developer"
    },
    {
      "id": 456,
      "username": "dr.smith",
      "name": "Dr. Smith",
      "access_level": 40,
      "access_level_name": "Maintainer"
    }
  ]
}
```

### 4. Webhook Integration

#### Register Webhook

**Auto-registered** when repository is created

**Webhook Configuration**:
```python
POST /api/v4/projects/{id}/hooks
{
  "url": "https://portal.spu.edu.sy/api/gitlab/webhook/",
  "push_events": true,
  "token": GITLAB_WEBHOOK_SECRET,
  "enable_ssl_verification": true
}
```

#### Webhook Handler

**Endpoint**: `POST /api/gitlab/webhook/`

**Headers**:
- `X-Gitlab-Event`: Event type (e.g., "Push Hook")
- `X-Gitlab-Token`: Signature for verification

**Process**:
1. Verify webhook signature
2. Extract event type from header
3. Process push events:
   ```python
   def process_push_event(payload):
       project_id = payload['project_id']
       commits = payload['commits']
       ref = payload['ref']  # Branch
       
       for commit_data in commits:
           create_or_update_commit(
               project_id=project_id,
               sha=commit_data['id'],
               message=commit_data['message'],
               author=commit_data['author'],
               timestamp=commit_data['timestamp'],
               added=commit_data['added'],
               modified=commit_data['modified'],
               removed=commit_data['removed']
           )
   ```

**Webhook Payload Example**:
```json
{
  "object_kind": "push",
  "event_name": "push",
  "ref": "refs/heads/main",
  "project_id": 456,
  "commits": [
    {
      "id": "abc123...",
      "message": "Implement user authentication",
      "timestamp": "2026-06-22T10:00:00Z",
      "author": {
        "name": "John Doe",
        "email": "john@example.com"
      },
      "added": ["src/auth.py"],
      "modified": ["src/models.py"],
      "removed": []
    }
  ]
}
```

## 📊 Commit Analytics

### View Commits

**Endpoint**: `GET /api/gitlab/board/{board_id}/commits/`

**Query Params**:
- `author`: Filter by GitLab username
- `branch`: Filter by branch name
- `since`: Date filter (ISO format)
- `until`: Date filter
- `page`: Pagination
- `per_page`: Items per page (default 20)

**Response**:
```json
{
  "success": true,
  "total": 45,
  "page": 1,
  "per_page": 20,
  "data": [
    {
      "id": 1001,
      "sha": "abc123def456...",
      "short_sha": "abc123d",
      "message": "Implement user authentication",
      "author_name": "John Doe",
      "author_email": "john@example.com",
      "author_username": "john.doe",
      "ref": "main",
      "authored_date": "2026-06-22T10:00:00Z",
      "committed_date": "2026-06-22T10:00:00Z",
      "web_url": "http://gitlab.../commit/abc123...",
      "added_lines": 120,
      "removed_lines": 15,
      "total_lines": 135,
      "files": [
        {
          "file_path": "src/auth.py",
          "status": "added",
          "additions": 80,
          "deletions": 0
        },
        {
          "file_path": "src/models.py",
          "status": "modified",
          "additions": 40,
          "deletions": 15
        }
      ]
    }
  ]
}
```

### Commit Statistics

**Endpoint**: `GET /api/gitlab/board/{board_id}/commits/stats/`

**Response**:
```json
{
  "success": true,
  "data": {
    "total_commits": 45,
    "total_lines_added": 3250,
    "total_lines_removed": 890,
    "total_lines_changed": 4140,
    "contributors": [
      {
        "username": "john.doe",
        "name": "John Doe",
        "commits": 25,
        "lines_added": 1850,
        "lines_removed": 420,
        "percentage": 55.6
      },
      {
        "username": "jane.smith",
        "name": "Jane Smith",
        "commits": 20,
        "lines_added": 1400,
        "lines_removed": 470,
        "percentage": 44.4
      }
    ],
    "activity_timeline": [
      {
        "date": "2026-06-22",
        "commits": 5,
        "lines_changed": 320
      },
      {
        "date": "2026-06-21",
        "commits": 3,
        "lines_changed": 180
      }
    ]
  }
}
```

### Sync Commits (Manual)

**Endpoint**: `POST /api/gitlab/board/{board_id}/commits/sync/`

**Process**:
1. Fetch commits from GitLab API:
   ```python
   GET /api/v4/projects/{id}/repository/commits
   ```
2. For each commit, fetch diff:
   ```python
   GET /api/v4/projects/{id}/repository/commits/{sha}/diff
   ```
3. Calculate line changes
4. Create/update GitLabCommit and GitLabCommitFile records

## 🔒 Security Features

### 1. Token Encryption

```python
from cryptography.fernet import Fernet
import hashlib
import base64

def _get_fernet():
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
            try:
                return _get_fernet().decrypt(value.encode()).decode()
            except Exception:
                return value
        return value
```

### 2. Webhook Signature Verification

```python
def verify_webhook_signature(request):
    token = request.headers.get('X-Gitlab-Token')
    if not token:
        raise ValueError('Missing webhook token')
    
    if token != settings.GITLAB_WEBHOOK_SECRET:
        raise ValueError('Invalid webhook signature')
```

### 3. Access Control

**Permission Helper**:
```python
def _assert_board_member(user, board):
    if user.is_staff or user.is_superuser:
        return board
    
    if user.role in ['admin', 'hod', 'dean']:
        return board
    
    if user.role == 'doctor':
        if board.proposal and board.proposal.supervisor_id == user.id:
            return board
        if board.application and board.application.idea.doctor_id == user.id:
            return board
        return None
    
    if user.role == 'student':
        if board.members.filter(pk=user.pk).exists():
            return board
    
    return None
```

## 🔧 Configuration

### Environment Variables

```python
# settings.py
GITLAB_URL = os.getenv('GITLAB_URL', 'http://localhost:8080')
GITLAB_TOKEN = os.getenv('GITLAB_TOKEN', '')  # Admin token
GITLAB_WEBHOOK_SECRET = os.getenv('GITLAB_WEBHOOK_SECRET', '')
GITLAB_WEBHOOK_BASE_URL = os.getenv('GITLAB_WEBHOOK_BASE_URL', 'http://localhost:8000')
GITLAB_EXTERNAL_URL = os.getenv('GITLAB_EXTERNAL_URL', 'http://localhost:8080')
```

### Celery Tasks

**Cleanup Orphaned Projects**:
```python
@shared_task
def cleanup_deleted_projects():
    """Check if GitLab projects still exist, mark orphaned"""
    projects = GitLabProject.objects.filter(is_orphaned=False)
    
    for project in projects:
        try:
            gitlab_api_get(f'/api/v4/projects/{project.gitlab_project_id}')
        except GitLabAPIError as e:
            if e.status_code == 404:
                project.is_orphaned = True
                project.save()
                # Notify team
```

**Schedule**: Daily at 01:00

## 🐛 Troubleshooting

### Issue: "خطأ في GitLab: 401 Unauthorized"
**Cause**: Invalid or expired access token  
**Solution**: Re-link GitLab account with new token

### Issue: "المستودع محذوف من GitLab"
**Cause**: Repository manually deleted from GitLab  
**Solution**: Create new repository or contact admin

### Issue: Webhook not receiving events
**Cause**: Webhook not registered or network issue  
**Solution**: Check webhook ID exists, verify WEBHOOK_BASE_URL accessible

### Issue: Commits not syncing
**Cause**: Webhook failed or admin token expired  
**Solution**: Manually sync via API or check admin token

### Issue: "غير مصرح — لست عضواً في هذا المشروع"
**Cause**: User not in project team  
**Solution**: Verify board membership

---

**Related Documentation**:
- [Project Lifecycle](02-PROJECT-LIFECYCLE.md) - When repositories are created
- [Kanban Boards](04-KANBAN-BOARDS.md) - Project context
- [API Reference](08-API-REFERENCE.md) - Complete endpoint specs
- [Security Guidelines](10-SECURITY.md) - Token handling best practices

**Code References**:
- Models: `backend/gitlab_integration/models.py`
- Views: `backend/gitlab_integration/views.py`
- Services: `backend/gitlab_integration/services.py`
- Webhook Handler: `backend/gitlab_integration/webhook_views.py`
- Tasks: `backend/gitlab_integration/tasks.py`
- Frontend: `frontend/src/components/GitLabPanel.jsx`

**Last Updated**: June 22, 2026
