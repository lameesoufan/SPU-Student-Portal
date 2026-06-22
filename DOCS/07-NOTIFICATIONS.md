# Notification System

## 📋 Overview

The Notification System provides real-time alerts to users about important events, status changes, and required actions. Notifications keep all stakeholders informed throughout the project lifecycle.

## 🎯 Notification Types

### Project Ideas
- `idea_submitted`: Doctor submits project idea
- `idea_approved`: HoD approves idea
- `idea_rejected`: HoD rejects idea

### Student Proposals
- `proposal_submitted`: Student submits proposal
- `proposal_approved_sup`: Supervisor approves proposal
- `proposal_approved_hod`: HoD approves proposal
- `proposal_rejected`: Proposal rejected
- `proposal_assigned`: Project board created

### Applications
- `application_submitted`: Student applies to idea
- `application_approved_doc`: Doctor approves application
- `application_approved_hod`: HoD approves application
- `application_rejected`: Application rejected
- `application_registered`: Project registered

### Invitations
- `invitation_received`: Team invitation received
- `invitation_accepted`: Member accepts invitation
- `invitation_rejected`: Member rejects invitation

## 📊 Notification Model

```python
class Notification:
    recipient = ForeignKey(User)
    notif_type = CharField(40)
    title = CharField(255)
    message = TextField
    is_read = BooleanField(default=False)
    created_at = DateTimeField
```

## 🔔 Notification Triggers

### Example: Student Submits Proposal

```python
from notifications.models import Notification

def create_student_proposal(...):
    proposal = StudentIdeaProposal.objects.create(...)
    
    # Notify supervisor
    Notification.objects.create(
        recipient=proposal.supervisor,
        notif_type='proposal_submitted',
        title='New Proposal Submitted',
        message=f'{proposal.student.get_full_name()} submitted "{proposal.title}"'
    )
    
    # Notify team members
    for invitation in proposal.invitations.all():
        Notification.objects.create(
            recipient=invitation.invitee,
            notif_type='invitation_received',
            title='Team Invitation',
            message=f'{proposal.student.get_full_name()} invited you to "{proposal.title}"'
        )
```

## 📡 API Endpoints

### List Notifications

**Endpoint**: `GET /api/notifications/`

**Query Params**:
- `unread_only`: Boolean (default: false)
- `page`: Page number
- `per_page`: Items per page

**Response**:
```json
{
  "total": 15,
  "unread_count": 3,
  "notifications": [
    {
      "id": 100,
      "notif_type": "proposal_approved_hod",
      "title": "Proposal Approved",
      "message": "Your proposal 'Smart Campus App' has been approved by HoD.",
      "is_read": false,
      "created_at": "2026-06-22T10:00:00Z"
    }
  ]
}
```

### Mark as Read

**Endpoint**: `POST /api/notifications/{id}/read/`

### Mark All as Read

**Endpoint**: `POST /api/notifications/mark-all-read/`

### Delete Notification

**Endpoint**: `DELETE /api/notifications/{id}/`

## 🎨 Frontend Integration

### Notification Bell Component

```javascript
function NotificationBell() {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  
  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, []);
  
  const fetchNotifications = async () => {
    const res = await api.get('/api/notifications/');
    setNotifications(res.data.notifications);
    setUnreadCount(res.data.unread_count);
  };
  
  return (
    <div className="notification-bell">
      <Bell />
      {unreadCount > 0 && <span className="badge">{unreadCount}</span>}
      <NotificationDropdown notifications={notifications} />
    </div>
  );
}
```

---

**Related Documentation**:
- [Project Lifecycle](02-PROJECT-LIFECYCLE.md)
- [Workflow System](03-WORKFLOW-SYSTEM.md)

**Code References**:
- Models: `backend/notifications/models.py`
- Views: `backend/notifications/views.py`
- Frontend: `frontend/src/components/NotificationBell.jsx`

**Last Updated**: June 22, 2026
