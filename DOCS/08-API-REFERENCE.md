# API Reference Guide

## 📋 Overview

Complete REST API documentation for the SPU Student Portal backend. All endpoints use JSON format and require JWT authentication unless otherwise specified.

## 🔑 Base URL

```
Development: http://localhost:8000
Production: https://portal.spu.edu.sy
```

## 🔐 Authentication

### Headers

```http
Authorization: Bearer <access_token>
Cookie: access_token=<jwt>; refresh_token=<jwt>
```

### Auth Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/login/` | Login with credentials | No |
| POST | `/api/register/` | Student self-registration | No |
| POST | `/api/logout/` | Logout and blacklist token | Yes |
| POST | `/api/token/refresh/` | Refresh access token | Yes |
| POST | `/api/change-password/` | Change password | Yes |

## 👤 User Management

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| POST | `/api/import-users/` | Bulk import users | Dean |
| GET | `/api/list-doctors/` | List all doctors | Dean |
| GET | `/api/list-departments/` | List departments with HoDs | Dean |
| POST | `/api/assign-hod/` | Assign HoD to department | Dean |
| GET | `/api/list-students/` | Search students for team | Student |

## 💡 Project Ideas (Doctor)

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| POST | `/api/submit-idea/` | Submit project idea | Doctor/HoD |
| GET | `/api/my-ideas/` | List my ideas | Doctor/HoD |
| GET | `/api/browse-ideas/` | List approved ideas | Student |
| GET | `/api/hod/pending-ideas/` | Pending idea reviews | HoD |
| POST | `/api/hod/review-idea/{id}/` | Approve/reject idea | HoD |

## 📝 Student Proposals

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| POST | `/api/propose-idea/` | Submit proposal | Student |
| GET | `/api/my-proposal/` | Get my active proposal | Student |
| POST | `/api/cancel-proposal/{id}/` | Cancel proposal | Student (owner) |
| GET | `/api/supervisor/pending-proposals/` | Pending for review | Supervisor |
| POST | `/api/supervisor/review-proposal/{id}/` | Approve/reject | Supervisor |
| GET | `/api/hod/pending-proposals/` | Pending for HoD | HoD |
| POST | `/api/hod/review-proposal/{id}/` | Approve/reject | HoD |

## 🎯 Applications (Student → Doctor Idea)

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| POST | `/api/apply-idea/{id}/` | Apply to idea | Student |
| GET | `/api/my-application/` | Get my application | Student |
| GET | `/api/doctor/pending-applications/` | Pending for review | Doctor |
| POST | `/api/doctor/review-application/{id}/` | Approve/reject | Doctor |
| GET | `/api/hod/pending-applications/` | Pending for HoD | HoD |
| POST | `/api/hod/review-application/{id}/` | Approve/reject | HoD |

## 🤝 Team Invitations

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/api/my-invitations/` | List my invitations | Student |
| POST | `/api/respond-invitation/{id}/` | Accept/reject | Student (invitee) |
| GET | `/api/my-proposal-invitations/` | Proposal invites | Student |
| POST | `/api/respond-proposal-invitation/{id}/` | Accept/reject | Student (invitee) |
| POST | `/api/proposal/{id}/replace-member/` | Replace member | Student (leader) |
| POST | `/api/application/{id}/replace-member/` | Replace member | Student (leader) |

## 📋 Kanban Boards

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/api/boards/my-board/` | Get my project board | Student |
| GET | `/api/boards/supervisor/` | List supervised boards | Doctor |
| GET | `/api/boards/hod/` | List department boards | HoD |
| GET | `/api/boards/hod/stats/` | Department statistics | HoD |
| POST | `/api/boards/{id}/tasks/` | Create task | Team member |
| PATCH | `/api/boards/{id}/tasks/{task_id}/` | Update task | Team member |
| DELETE | `/api/boards/{id}/tasks/{task_id}/` | Delete task | Team member |
| GET | `/api/boards/{id}/tasks/{task_id}/comments/` | List comments | Team member |
| POST | `/api/boards/{id}/tasks/{task_id}/comments/` | Add comment | Team member |
| DELETE | `/api/boards/{id}/tasks/{task_id}/comments/{comment_id}/` | Delete comment | Author/Supervisor |
| POST | `/api/boards/{id}/tasks/{task_id}/attachments/` | Upload file | Team member |
| DELETE | `/api/boards/{id}/tasks/{task_id}/attachments/{att_id}/` | Delete file | Uploader/Supervisor |
| GET | `/api/boards/{id}/activity/` | View activity log | Team member |

## 🔄 Workflow System

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/api/workflow/templates/` | List templates | HoD/Doctor |
| GET | `/api/workflow/templates/{id}/` | Get template | HoD/Doctor |
| POST | `/api/workflow/templates/` | Create template | HoD/Doctor |
| PUT | `/api/workflow/templates/{id}/` | Update template | HoD/Doctor |
| DELETE | `/api/workflow/templates/{id}/` | Delete template | HoD/Doctor |
| POST | `/api/workflow/apply/` | Apply to project | HoD/Supervisor |
| GET | `/api/workflow/project/{board_id}/` | Get project workflow | Team/Supervisor |
| POST | `/api/workflow/stage/{instance_id}/submit/` | Submit stage | Student (member) |
| POST | `/api/workflow/stage/{instance_id}/review/` | Review stage | Supervisor |

## 📄 Dynamic Forms

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/api/forms/{context}/` | Get HoD's form | HoD |
| POST | `/api/forms/{context}/` | Save form | HoD |
| GET | `/api/forms/{dept}/{context}/` | Get form template | Any user |
| POST | `/api/forms/submit/` | Submit response | Student |
| GET | `/api/forms/{context}/responses/` | List responses | HoD |
| GET | `/api/forms/response/proposal/{id}/` | Get proposal form | Student/Supervisor |
| GET | `/api/forms/response/application/{id}/` | Get application form | Student/Doctor |

## 🦊 GitLab Integration

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/api/gitlab/config/` | Get GitLab URL | Authenticated |
| POST | `/api/gitlab/link/` | Link account | Student |
| POST | `/api/gitlab/unlink/` | Unlink account | Student |
| GET | `/api/gitlab/status/` | Check link status | Authenticated |
| POST | `/api/gitlab/verify-token/` | Verify token | Authenticated |
| POST | `/api/gitlab/board/{id}/create-project/` | Create repository | Team/Supervisor |
| GET | `/api/gitlab/board/{id}/info/` | Get project info | Team/Supervisor |
| POST | `/api/gitlab/board/{id}/info/` | Refresh info | Team/Supervisor |
| GET | `/api/gitlab/board/{id}/members/` | List members | Team/Supervisor |
| POST | `/api/gitlab/board/{id}/members/add/` | Add member | Supervisor |
| POST | `/api/gitlab/board/{id}/members/remove/` | Remove member | Supervisor |
| GET | `/api/gitlab/board/{id}/commits/` | List commits | Team/Supervisor |
| GET | `/api/gitlab/board/{id}/commits/stats/` | Commit statistics | Team/Supervisor |
| POST | `/api/gitlab/board/{id}/commits/sync/` | Sync commits | Team/Supervisor |
| POST | `/api/gitlab/webhook/` | Webhook handler | Public (verified) |

## 🔔 Notifications

| Method | Endpoint | Description | Permission |
|--------|----------|-------------|------------|
| GET | `/api/notifications/` | List notifications | Authenticated |
| POST | `/api/notifications/{id}/read/` | Mark as read | Owner |
| POST | `/api/notifications/mark-all-read/` | Mark all read | Authenticated |
| DELETE | `/api/notifications/{id}/` | Delete notification | Owner |

## 📊 Response Formats

### Success Response

```json
{
  "message": "Operation successful",
  "data": {...}
}
```

### Error Response

```json
{
  "error": "Error message",
  "details": {
    "field": ["Error detail"]
  }
}
```

### Paginated Response

```json
{
  "count": 100,
  "next": "http://api/endpoint/?page=2",
  "previous": null,
  "results": [...]
}
```

## 🔒 HTTP Status Codes

- **200 OK**: Successful GET/PATCH
- **201 Created**: Successful POST
- **204 No Content**: Successful DELETE
- **400 Bad Request**: Validation error
- **401 Unauthorized**: Not authenticated
- **403 Forbidden**: Not permitted
- **404 Not Found**: Resource not found
- **409 Conflict**: Duplicate or constraint violation
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server error

## 🚀 Rate Limits

```python
THROTTLE_RATES = {
    'accounts_login': '10/minute',
    'accounts_register': '5/minute',
    'propose_idea': '10/hour',
    'workflow_submit': '30/hour',
    'file_upload': '20/hour',
    'anon': '60/minute',
    'user': '600/minute',
}
```

---

**Related Documentation**:
- [Authentication](01-AUTHENTICATION.md)
- [Project Lifecycle](02-PROJECT-LIFECYCLE.md)
- [All Feature Docs](00-PROJECT-OVERVIEW.md)

**Last Updated**: June 22, 2026
