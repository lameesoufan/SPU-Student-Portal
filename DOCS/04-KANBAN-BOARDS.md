# Kanban Board & Task Management System

## 📋 Overview

The Kanban Board system provides a visual, collaborative task management interface for graduation projects. Once a project is approved and a board is created, team members and supervisors can create tasks, track progress, collaborate through comments, and manage attachments.

## 🎯 Key Features

- **Visual Task Management**: Drag-and-drop Kanban interface
- **Task Assignment**: Assign tasks to specific team members
- **Priority Management**: Low, Medium, High priority levels
- **Due Date Tracking**: Set and monitor task deadlines
- **Collaboration**: Comments and discussions on tasks
- **File Attachments**: Upload supporting documents
- **Activity Log**: Complete audit trail of all changes
- **Real-time Updates**: See team activity as it happens

## 🏗️ Entity Model

### Core Entities

```
ProjectBoard
├── Task (multiple)
│   ├── TaskComment (multiple)
│   └── TaskAttachment (multiple)
└── ActivityLog (multiple)
```

### 1. ProjectBoard

```python
class ProjectBoard:
    proposal = OneToOneField(StudentIdeaProposal)  # For UC-02
    application = OneToOneField(IdeaApplication)   # For UC-01
    title = CharField(255)
    created_at = DateTimeField
```

**Creation Trigger**:
- **Student Proposal**: Created when HoD approves proposal (status → `assigned`)
- **Doctor Idea Application**: Created when HoD approves application (status → `registered`)

**Auto-Creation**: Uses `get_or_create()` to ensure board exists on first access

**Members Property**:
```python
@property
def members(self):
    # Returns all team members (leader + accepted invitations)
    if self.proposal:
        return [proposal.student] + accepted_proposal_invitations
    elif self.application:
        return [application.student] + accepted_team_invitations
```

### 2. Task

```python
class Task:
    board = ForeignKey(ProjectBoard)
    title = CharField(255)
    description = TextField
    status = CharField  # todo, in_progress, in_review, done
    priority = CharField  # low, medium, high
    assignee = ForeignKey(User)  # Team member
    due_date = DateField
    created_by = ForeignKey(User)
    created_at = DateTimeField
    updated_at = DateTimeField
```

**Status Pipeline**:
```
┌─────────┐    ┌──────────────┐    ┌───────────┐    ┌──────┐
│  To Do  │───►│ In Progress  │───►│ In Review │───►│ Done │
└─────────┘    └──────────────┘    └───────────┘    └──────┘
```

**Priority Levels**:
- **High**: Critical path items, blockers
- **Medium**: Standard priority
- **Low**: Nice-to-have, future enhancements

### 3. TaskComment

```python
class TaskComment:
    task = ForeignKey(Task)
    author = ForeignKey(User)
    body = TextField
    created_at = DateTimeField
    updated_at = DateTimeField
```

**Use Cases**:
- Progress updates
- Questions and discussions
- Supervisor feedback
- Design decisions

### 4. TaskAttachment

```python
class TaskAttachment:
    task = ForeignKey(Task)
    uploaded_by = ForeignKey(User)
    file = FileField(upload_to='task_attachments/{board_id}/{task_id}/')
    filename = CharField(255)  # Original name
    file_size = PositiveIntegerField  # Bytes
    created_at = DateTimeField
```

**Supported File Types**:
- Documents: `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`
- Images: `.png`, `.jpg`, `.jpeg`, `.gif`
- Text: `.txt`

**Constraints**:
- Max file size: **10 MB**
- MIME type validation enforced
- Virus scanning recommended (not implemented)

### 5. ActivityLog

```python
class ActivityLog:
    board = ForeignKey(ProjectBoard)
    task = ForeignKey(Task)  # Nullable
    actor = ForeignKey(User)
    verb = CharField  # Action performed
    detail = CharField(500)  # Additional context
    created_at = DateTimeField
```

**Tracked Activities**:
- `created`: Task created
- `status_changed`: Status updated
- `priority_changed`: Priority modified
- `assigned`: Task assigned to member
- `unassigned`: Task unassigned
- `due_date_set`: Due date added/changed
- `commented`: Comment added
- `attachment_added`: File uploaded
- `attachment_removed`: File deleted
- `deleted`: Task deleted

## 🔄 Task Management Workflows

### 1. Create Task

**Endpoint**: `POST /api/boards/{board_id}/tasks/`

**Permission**: Team member or supervisor

**Request**:
```json
{
  "title": "Design database schema",
  "description": "Create ER diagram and SQL schema for user management module",
  "status": "todo",
  "priority": "high",
  "assignee": 123,  // User ID (optional)
  "due_date": "2026-07-01"
}
```

**Validation**:
- Title required (max 255 chars)
- Status must be valid enum value
- Priority must be valid enum value
- Assignee must be board member
- Due date must be future date (optional)

**Response**:
```json
{
  "id": 500,
  "title": "Design database schema",
  "description": "Create ER diagram and SQL schema...",
  "status": "todo",
  "priority": "high",
  "assignee": {
    "id": 123,
    "username": "student002",
    "name": "Jane Smith"
  },
  "due_date": "2026-07-01",
  "created_by": {
    "id": 122,
    "username": "student001",
    "name": "John Doe"
  },
  "created_at": "2026-06-22T10:00:00Z",
  "updated_at": "2026-06-22T10:00:00Z",
  "comments_count": 0,
  "attachments_count": 0
}
```

**Activity Log Created**:
```
John Doe created the task "Design database schema"
```

### 2. Update Task

**Endpoint**: `PATCH /api/boards/{board_id}/tasks/{task_id}/`

**Permission**: Team member or supervisor

**Request** (Partial Update):
```json
{
  "status": "in_progress",
  "assignee": 124
}
```

**Activity Logging**:
```python
# Example logs generated:
if status_changed:
    log("status_changed", "todo → in_progress")
if assignee_changed:
    log("assigned", "Alice Johnson")
if priority_changed:
    log("priority_changed", "medium → high")
if due_date_changed:
    log("due_date_set", "2026-07-01")
```

**Response**: Updated task object

### 3. Delete Task

**Endpoint**: `DELETE /api/boards/{board_id}/tasks/{task_id}/`

**Permission**: Team member or supervisor

**Process**:
1. Log activity: `deleted`, `"Task title"`
2. Delete all comments (cascade)
3. Delete all attachments (cascade + files)
4. Delete task

**Response**: `204 No Content`

### 4. Drag & Drop (Frontend)

**Frontend Implementation** (React + @dnd-kit):
```javascript
import { DndContext, DragOverlay } from '@dnd-kit/core';

function KanbanBoard({ boardId }) {
  const handleDragEnd = async (event) => {
    const { active, over } = event;
    const taskId = active.id;
    const newStatus = over.id;  // 'todo', 'in_progress', etc.
    
    await api.patch(`/api/boards/${boardId}/tasks/${taskId}/`, {
      status: newStatus
    });
  };
  
  return (
    <DndContext onDragEnd={handleDragEnd}>
      <div className="kanban-columns">
        <Column status="todo" tasks={todoTasks} />
        <Column status="in_progress" tasks={inProgressTasks} />
        <Column status="in_review" tasks={inReviewTasks} />
        <Column status="done" tasks={doneTasks} />
      </div>
    </DndContext>
  );
}
```

## 💬 Comments System

### Add Comment

**Endpoint**: `POST /api/boards/{board_id}/tasks/{task_id}/comments/`

**Permission**: Team member or supervisor

**Request**:
```json
{
  "body": "I've completed the ER diagram. Please review and provide feedback."
}
```

**Response**:
```json
{
  "id": 1001,
  "author": {
    "id": 123,
    "username": "student002",
    "name": "Jane Smith"
  },
  "body": "I've completed the ER diagram...",
  "created_at": "2026-06-22T14:30:00Z",
  "updated_at": "2026-06-22T14:30:00Z"
}
```

**Activity Log**: `commented`, `"I've completed the ER diagram..."`

### List Comments

**Endpoint**: `GET /api/boards/{board_id}/tasks/{task_id}/comments/`

**Permission**: Team member or supervisor

**Response**:
```json
[
  {
    "id": 1001,
    "author": {...},
    "body": "I've completed the ER diagram...",
    "created_at": "2026-06-22T14:30:00Z"
  },
  {
    "id": 1002,
    "author": {...},
    "body": "Great work! Just a few suggestions...",
    "created_at": "2026-06-22T15:00:00Z"
  }
]
```

**Pagination**: Max 100 comments returned

### Delete Comment

**Endpoint**: `DELETE /api/boards/{board_id}/tasks/{task_id}/comments/{comment_id}/`

**Permission**: Comment author or supervisor

**Response**: `204 No Content`

## 📎 Attachments System

### Upload Attachment

**Endpoint**: `POST /api/boards/{board_id}/tasks/{task_id}/attachments/`

**Permission**: Team member or supervisor

**Content-Type**: `multipart/form-data`

**Request**:
```http
POST /api/boards/42/tasks/500/attachments/
Content-Type: multipart/form-data

------WebKitFormBoundary
Content-Disposition: form-data; name="file"; filename="database-schema.pdf"
Content-Type: application/pdf

<binary data>
------WebKitFormBoundary--
```

**Validation**:
```python
# File size check
if file.size > 10 * 1024 * 1024:
    return error("File too large. Max 10 MB.")

# Extension check
extension = os.path.splitext(file.name)[1].lower()
if extension not in ALLOWED_EXTENSIONS:
    return error("Unsupported file type.")

# MIME type check
if content_type not in MIME_WHITELIST:
    return error("Unsupported file type (MIME mismatch).")
```

**File Storage Path**:
```
media/task_attachments/{board_id}/{task_id}/{safe_filename}
```

**Response**:
```json
{
  "id": 2001,
  "filename": "database-schema.pdf",
  "file_size": 524288,  // Bytes
  "file_url": "/media/task_attachments/42/500/database-schema.pdf",
  "extension": "pdf",
  "uploaded_by": {
    "id": 123,
    "username": "student002",
    "name": "Jane Smith"
  },
  "created_at": "2026-06-22T16:00:00Z"
}
```

**Activity Log**: `attachment_added`, `"database-schema.pdf"`

### List Attachments

**Endpoint**: `GET /api/boards/{board_id}/tasks/{task_id}/attachments/`

**Included in Task Object**:
```json
{
  "id": 500,
  "title": "Design database schema",
  "attachments": [
    {
      "id": 2001,
      "filename": "database-schema.pdf",
      "file_url": "/media/...",
      "file_size": 524288,
      "uploaded_by": {...}
    }
  ]
}
```

### Delete Attachment

**Endpoint**: `DELETE /api/boards/{board_id}/tasks/{task_id}/attachments/{attachment_id}/`

**Permission**: Uploader (if student) or supervisor

**Process**:
1. Delete physical file from storage
2. Delete database record
3. Log activity

**Activity Log**: `attachment_removed`, `"database-schema.pdf"`

## 📊 Board Access Patterns

### Student: My Board

**Endpoint**: `GET /api/boards/my-board/`

**Permission**: Student only

**Response**:
```json
{
  "has_project": true,
  "board": {
    "id": 42,
    "title": "Smart Campus Navigation App",
    "created_at": "2026-06-01T10:00:00Z",
    "members": [
      {
        "id": 122,
        "username": "student001",
        "name": "John Doe"
      },
      {
        "id": 123,
        "username": "student002",
        "name": "Jane Smith"
      }
    ],
    "supervisor": {
      "id": 15,
      "username": "dr.smith",
      "name": "Dr. John Smith"
    },
    "tasks": [
      {
        "id": 500,
        "title": "Design database schema",
        "status": "in_progress",
        "priority": "high",
        "assignee": {...},
        "due_date": "2026-07-01",
        "comments_count": 3,
        "attachments_count": 1
      }
    ]
  }
}
```

**If No Project**:
```json
{
  "has_project": false
}
```

### Supervisor: My Supervised Boards

**Endpoint**: `GET /api/boards/supervisor/`

**Permission**: Doctor only

**Response**:
```json
[
  {
    "id": 42,
    "title": "Smart Campus Navigation App",
    "members": [...],
    "tasks_summary": {
      "total": 15,
      "todo": 5,
      "in_progress": 6,
      "in_review": 2,
      "done": 2
    },
    "progress": 13  // Percentage
  },
  {
    "id": 43,
    "title": "AI Medical Diagnosis",
    "members": [...],
    "tasks_summary": {...},
    "progress": 45
  }
]
```

### HoD/Dean: Department Overview

**Endpoint**: `GET /api/boards/hod/`

**Permission**: HoD (own dept) or Dean (all)

**Response**: List of all boards in department with statistics

**Statistics Endpoint**: `GET /api/boards/hod/stats/`

```json
{
  "total_projects": 25,
  "proposals_count": 12,
  "applications_count": 13,
  "avg_progress": 52,  // Average completion percentage
  "department": "software_engineering"
}
```

## 📈 Activity Log

### View Board Activity

**Endpoint**: `GET /api/boards/{board_id}/activity/`

**Permission**: Team member or supervisor

**Response**:
```json
[
  {
    "id": 5001,
    "actor": {
      "id": 123,
      "username": "student002",
      "name": "Jane Smith"
    },
    "verb": "attachment_added",
    "detail": "database-schema.pdf",
    "task": {
      "id": 500,
      "title": "Design database schema"
    },
    "created_at": "2026-06-22T16:00:00Z"
  },
  {
    "id": 5000,
    "actor": {
      "id": 122,
      "username": "student001",
      "name": "John Doe"
    },
    "verb": "status_changed",
    "detail": "todo → in_progress",
    "task": {
      "id": 500,
      "title": "Design database schema"
    },
    "created_at": "2026-06-22T11:00:00Z"
  }
]
```

**Pagination**: Max 50 activities returned

**Ordering**: Newest first (`-created_at`)

## 🔒 Access Control

### Permission Helper

```python
def _is_board_member(board, user):
    """Check if user is a team member"""
    from projects.models import ProposalInvitation, TeamInvitation
    
    if board.proposal:
        if board.proposal.student_id == user.id:
            return True
        return ProposalInvitation.objects.filter(
            proposal=board.proposal, 
            status='accepted', 
            invitee_id=user.id
        ).exists()
    
    elif board.application:
        if board.application.student_id == user.id:
            return True
        return TeamInvitation.objects.filter(
            application=board.application,
            status='accepted',
            invitee_id=user.id
        ).exists()
    
    return False

def _get_board_for_member(user, board_id):
    """Get board if user has access"""
    board = ProjectBoard.objects.get(pk=board_id)
    
    # Students: must be team member
    if user.role == 'student' and _is_board_member(board, user):
        return board
    
    # Doctors: must be supervisor
    if user.role == 'doctor':
        if board.proposal and board.proposal.supervisor_id == user.id:
            return board
        if board.application and board.application.idea.doctor_id == user.id:
            return board
    
    # HoD/Dean: department access
    if user.role in ['hod', 'dean']:
        return board
    
    return None  # Access denied
```

### Permission Matrix

| Action | Team Member | Supervisor | HoD | Dean |
|--------|-------------|------------|-----|------|
| View board | ✅ (own) | ✅ (supervised) | ✅ (dept) | ✅ (all) |
| Create task | ✅ | ✅ | ❌ | ❌ |
| Update task | ✅ | ✅ | ❌ | ❌ |
| Delete task | ✅ | ✅ | ❌ | ❌ |
| Add comment | ✅ | ✅ | ❌ | ❌ |
| Delete comment | ✅ (own) | ✅ (any) | ❌ | ❌ |
| Upload attachment | ✅ | ✅ | ❌ | ❌ |
| Delete attachment | ✅ (own) | ✅ (any) | ❌ | ❌ |
| View activity | ✅ | ✅ | ✅ | ✅ |

## 🎨 Frontend Integration

### React Component Structure

```
KanbanBoard
├── BoardHeader (title, members, stats)
├── TaskFilters (search, assignee, priority)
├── KanbanColumns
│   ├── Column (To Do)
│   │   └── TaskCard[]
│   ├── Column (In Progress)
│   │   └── TaskCard[]
│   ├── Column (In Review)
│   │   └── TaskCard[]
│   └── Column (Done)
│       └── TaskCard[]
└── TaskModal (details, comments, attachments)
```

### Key Features

**Drag & Drop**:
```javascript
// Using @dnd-kit
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

function TaskCard({ task }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
  } = useSortable({ id: task.id });
  
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };
  
  return (
    <div ref={setNodeRef} style={style} {...attributes} {...listeners}>
      <h3>{task.title}</h3>
      <p>{task.description}</p>
    </div>
  );
}
```

**Real-time Updates** (Polling):
```javascript
import { usePolling } from '../hooks/usePolling';

function KanbanBoard({ boardId }) {
  const [tasks, setTasks] = useState([]);
  
  usePolling(async () => {
    const board = await api.get(`/api/boards/${boardId}/`);
    setTasks(board.data.board.tasks);
  }, 30000);  // Poll every 30 seconds
}
```

## 🔍 Performance Optimizations

### Database Indexes

```python
class Task:
    class Meta:
        indexes = [
            Index(fields=['board', 'status']),
            Index(fields=['assignee', 'status']),
            Index(fields=['board', '-updated_at']),
        ]

class ActivityLog:
    class Meta:
        indexes = [
            Index(fields=['board', '-created_at']),
            Index(fields=['actor', '-created_at']),
        ]
```

### Query Optimization

```python
# Board detail with all relations
board = ProjectBoard.objects.select_related(
    'proposal__supervisor',
    'proposal__student',
    'application__idea__doctor',
    'application__student',
).prefetch_related(
    'tasks__assignee',
    'tasks__created_by',
    'tasks__comments__author',
    'tasks__attachments__uploaded_by',
).get(pk=board_id)
```

## 🐛 Troubleshooting

### Issue: "Not found or not a member"
**Cause**: User trying to access board they don't belong to  
**Solution**: Verify membership in proposal/application invitations

### Issue: File upload fails silently
**Cause**: File size or type validation failed  
**Check**: Response error message, file size < 10 MB, extension in whitelist

### Issue: Drag & drop not working
**Cause**: Frontend state not updating properly  
**Solution**: Check DndContext configuration, verify task IDs unique

### Issue: Activity log empty
**Cause**: Activities not being logged in views  
**Solution**: Check `_log()` calls in task CRUD operations

---

**Related Documentation**:
- [Project Lifecycle](02-PROJECT-LIFECYCLE.md) - How boards are created
- [GitLab Integration](06-GITLAB-INTEGRATION.md) - Link commits to tasks
- [API Reference](08-API-REFERENCE.md) - Complete endpoint specs

**Code References**:
- Models: `backend/project_management/models.py`
- Views: `backend/project_management/views.py`
- Serializers: `backend/project_management/serializers.py`
- Frontend: `frontend/src/components/KanbanBoard.jsx`

**Last Updated**: June 22, 2026
