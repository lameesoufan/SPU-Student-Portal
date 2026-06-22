# SPU Student Portal - Project Overview

## 📋 Executive Summary

The **SPU Student Portal** is a comprehensive web-based platform designed for Syrian Private University (SPU) to manage graduation projects throughout their entire lifecycle. The system facilitates collaboration between students, doctors (faculty), and department heads (HoD) with role-based access control and end-to-end project tracking.

## 🎯 Project Goals

- **Streamline Project Management**: Digitize and automate the graduation project submission, approval, and tracking process
- **Enhance Collaboration**: Provide real-time collaboration tools for teams and supervisors
- **Improve Transparency**: Create visibility into project progress for all stakeholders
- **Integrate Development Tools**: Connect with GitLab for version control and code review
- **Enable Workflow Automation**: Support customizable workflows and recurring reports

## 🏗️ System Architecture

### Technology Stack

#### Backend
- **Framework**: Django 5.2.6 (Python)
- **API**: Django REST Framework (DRF)
- **Database**: PostgreSQL (production) / SQLite (development)
- **Authentication**: JWT (JSON Web Tokens) with HttpOnly cookies
- **Task Queue**: Celery + Redis (for async tasks)
- **File Storage**: Django File Storage with configurable backends

#### Frontend
- **Framework**: React 19.2.4
- **Build Tool**: Vite 8.0.16
- **UI Library**: Tailwind CSS 3.4.19
- **State Management**: React Hooks + Context API
- **HTTP Client**: Axios 1.13.6
- **Drag & Drop**: @dnd-kit for Kanban boards

#### Integration & DevOps
- **Version Control**: GitLab CE Integration
- **Load Testing**: Locust + K6
- **Security**: Cryptography (Fernet) for sensitive data encryption

### Architecture Patterns

1. **Service-Oriented Backend**: Business logic separated into service layers (`services.py`)
2. **Repository Pattern**: Data access through selectors (`selectors.py`)
3. **RESTful API Design**: Clear endpoint structure with proper HTTP methods
4. **Role-Based Access Control (RBAC)**: Granular permissions per user role
5. **Webhook Integration**: Real-time GitLab event processing

## 👥 User Roles

### 1. **Dean (Admin)**
- Full system access
- User management (import students/doctors)
- Assign HoDs to departments
- View all projects across departments
- System-wide analytics

### 2. **Head of Department (HoD)**
- Review and approve doctor-proposed ideas
- Review and approve student proposals
- Create and manage dynamic forms
- Build and apply workflow templates
- Department-level project oversight
- View department statistics

### 3. **Doctor (Faculty/Supervisor)**
- Propose project ideas for students
- Supervise student-proposed projects
- Review and approve applications to their ideas
- Access supervised project boards
- View project progress and commits

### 4. **Student**
- Propose own project ideas
- Browse and apply to doctor ideas
- Form teams and invite members
- Submit workflow stages and reports
- Manage project tasks via Kanban board
- Link GitLab account for version control
- Track commits and contributions

## 📊 System Modules

### Core Modules

| Module | Description | Key Features |
|--------|-------------|--------------|
| **Accounts** | User authentication & management | JWT auth, role management, password handling |
| **Projects** | Project lifecycle management | Ideas, proposals, applications, team formation |
| **Workflow** | Customizable project workflows | Stage templates, recurring reports, approvals |
| **Project Management** | Task & board management | Kanban boards, tasks, comments, attachments |
| **Dynamic Forms** | Configurable forms | HoD-created forms, field validation, file uploads |
| **Notifications** | Real-time alerts | Activity notifications, status updates |
| **GitLab Integration** | Version control sync | Repository creation, commit tracking, member management |

## 🔄 Key Workflows

### UC-01: Doctor Proposes Idea
1. Doctor submits project idea
2. HoD reviews and approves/rejects
3. Approved ideas appear in student browse list
4. Students can apply to idea
5. Doctor reviews applications
6. HoD gives final approval
7. Project registered → board created

### UC-02: Student Proposes Own Idea
1. Student submits proposal + fills dynamic form
2. Student invites team members
3. Supervisor reviews and approves/rejects
4. HoD reviews and approves/rejects
5. HoD assigns project → board created
6. Team can begin work

### UC-03: Project Execution
1. HoD applies workflow template to project
2. Workflow stages auto-activate based on triggers
3. Students submit required reports per stage
4. Supervisors review and provide feedback
5. Students manage tasks on Kanban board
6. Commits tracked from GitLab

## 🔒 Security Features

- **HttpOnly JWT Cookies**: Prevents XSS attacks
- **Token Blacklisting**: Secure logout mechanism
- **CORS Protection**: Configured allowed origins
- **Field-Level Encryption**: Sensitive data (GitLab tokens) encrypted at rest
- **CSRF Protection**: Django middleware enabled
- **Rate Limiting**: Throttling on sensitive endpoints
- **SQL Injection Protection**: Parameterized queries via ORM
- **File Upload Validation**: Extension and MIME type whitelisting

## 📈 Performance Optimizations

- **Database Indexing**: Strategic indexes on frequently queried fields
- **Query Optimization**: `select_related()` and `prefetch_related()` usage
- **Connection Pooling**: Persistent database connections
- **Pagination**: All list endpoints paginated (default 50 items)
- **Caching Ready**: Redis configuration for Celery + potential view caching

## 🚀 Deployment Considerations

### Environment Variables
- `SECRET_KEY`: Django secret (required)
- `DEBUG`: Development mode flag
- `DATABASE_ENGINE`: Database type (postgres/sqlite)
- `GITLAB_URL`: GitLab instance URL
- `GITLAB_TOKEN`: Admin token for API access
- `CORS_ALLOWED_ORIGINS`: Frontend URLs

### Database Migrations
```bash
python manage.py migrate
```

### Static Files
```bash
python manage.py collectstatic
```

### Celery Workers (Optional)
```bash
celery -A backend worker -l INFO
celery -A backend beat -l INFO
```

## 📦 Project Structure

```
SPU-Student-Portal/
├── backend/
│   ├── accounts/           # User auth & management
│   ├── projects/           # Ideas, proposals, applications
│   ├── workflow/           # Workflow templates & instances
│   ├── project_management/ # Kanban boards & tasks
│   ├── dy_forms/          # Dynamic forms
│   ├── notifications/      # Notification system
│   ├── gitlab_integration/ # GitLab API integration
│   └── backend/           # Django settings & config
├── frontend/
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── hooks/         # Custom hooks
│   │   ├── lib/           # Utilities
│   │   └── api.jsx        # API client
│   └── public/            # Static assets
├── load-tests/            # Performance testing
└── DOCS/                  # Documentation (this folder)
```

## 🔗 Related Documentation

- [Authentication System](01-AUTHENTICATION.md)
- [Project Lifecycle](02-PROJECT-LIFECYCLE.md)
- [Workflow System](03-WORKFLOW-SYSTEM.md)
- [Kanban Board Management](04-KANBAN-BOARDS.md)
- [Dynamic Forms](05-DYNAMIC-FORMS.md)
- [GitLab Integration](06-GITLAB-INTEGRATION.md)
- [Notification System](07-NOTIFICATIONS.md)
- [API Reference](08-API-REFERENCE.md)
- [Database Schema](09-DATABASE-SCHEMA.md)
- [Security Guidelines](10-SECURITY.md)

## 📞 Support & Maintenance

### Key Points for Future Development
1. All business logic in `services.py` for easy testing
2. Permissions handled via DRF permission classes
3. Serializers validate all input data
4. Activity logging for audit trails
5. Webhook handlers for external integrations

### Common Modification Scenarios
- **Add new role**: Update `ROLE_CHOICES` in `accounts/models.py`
- **Add workflow trigger**: Update `TRIGGER_TYPES` in `workflow/models.py`
- **Add form field type**: Update `FIELD_TYPES` in `dy_forms/models.py`
- **Add department**: Update `DEPARTMENTS` in `accounts/models.py`

---

**Document Version**: 1.0  
**Last Updated**: June 22, 2026  
**Maintained By**: Development Team
