# SPU Student Portal - Documentation Index

## 📚 Welcome to the Documentation

This comprehensive documentation covers all aspects of the SPU Student Portal, a complete graduation project management system for Syrian Private University.

## 🗂️ Documentation Structure

### 📋 Core Documentation

#### [00 - Project Overview](00-PROJECT-OVERVIEW.md)
**Start here!** Executive summary, architecture overview, technology stack, and system modules.

**Topics Covered**:
- System architecture and design patterns
- Technology stack (Django, React, PostgreSQL)
- User roles and permissions
- Project structure
- Key workflows overview

---

### 🔐 Authentication & User Management

#### [01 - Authentication System](01-AUTHENTICATION.md)
Complete guide to user authentication, JWT tokens, and account management.

**Topics Covered**:
- JWT token-based authentication
- HttpOnly cookie implementation
- Student self-registration
- Bulk user import
- Password management
- Role assignment

**Key Features**:
- Secure JWT with automatic rotation
- Token blacklisting on logout
- Rate limiting on auth endpoints
- Encrypted token storage

---

### 🎓 Project Management Features

#### [02 - Project Lifecycle](02-PROJECT-LIFECYCLE.md)
End-to-end project lifecycle from idea submission to approval.

**Topics Covered**:
- UC-01: Doctor proposes idea → Student applies
- UC-02: Student proposes idea → Supervisor approval
- Team formation and invitations
- Multi-level approval workflows
- Project status transitions

**Key Workflows**:
- Doctor idea approval (HoD review)
- Student proposal approval (Supervisor → HoD)
- Application approval (Doctor → HoD)
- Team invitation flow

---

#### [03 - Workflow System](03-WORKFLOW-SYSTEM.md)
Customizable workflow templates with stages and recurring reports.

**Topics Covered**:
- Template creation and management
- Stage triggers (project_start, after_days, date, manual)
- Recurring stages (weekly/monthly reports)
- Dynamic form fields per stage
- Student submission and supervisor review
- Smart template updates

**Key Features**:
- Reusable workflow templates
- Automatic stage activation
- Celery-based recurring stage generation
- Progress tracking

---

#### [04 - Kanban Board Management](04-KANBAN-BOARDS.md)
Visual task management with drag-and-drop Kanban boards.

**Topics Covered**:
- Task creation and management
- Status pipeline (To Do → In Progress → In Review → Done)
- Task assignment and priority
- Comments and collaboration
- File attachments
- Activity logging

**Key Features**:
- Real-time task updates
- Drag-and-drop interface (@dnd-kit)
- File upload with validation
- Complete audit trail

---

#### [05 - Dynamic Forms System](05-DYNAMIC-FORMS.md)
HoD-configurable forms for proposals, applications, and reports.

**Topics Covered**:
- Form builder interface
- Field types (text, textarea, number, select, radio, checkbox, date, file)
- Form submission and validation
- Response viewing and management
- Data preservation when fields are deleted

**Use Cases**:
- Student proposal forms
- Application questionnaires
- Weekly/monthly progress reports
- Milestone reports

---

#### [06 - GitLab Integration](06-GITLAB-INTEGRATION.md)
Version control integration with GitLab CE.

**Topics Covered**:
- GitLab account linking
- Repository creation and management
- Team member access control
- Commit tracking via webhooks
- Contribution analytics
- Token encryption

**Key Features**:
- Personal access token linking
- Auto-repository creation
- Real-time commit synchronization
- Contributor statistics
- Webhook-based updates

---

#### [07 - Notification System](07-NOTIFICATIONS.md)
Real-time notification system for all stakeholders.

**Topics Covered**:
- Notification types and triggers
- Notification delivery
- Read/unread status
- Frontend bell integration

**Notification Categories**:
- Project idea events
- Proposal status changes
- Application updates
- Team invitations
- Workflow stage reminders

---

### 📖 Reference Documentation

#### [08 - API Reference](08-API-REFERENCE.md)
Complete REST API documentation with endpoints and examples.

**Sections**:
- Authentication endpoints
- User management
- Project ideas and proposals
- Applications and team invitations
- Kanban boards and tasks
- Workflow stages
- Dynamic forms
- GitLab integration
- Notifications

**For Each Endpoint**:
- HTTP method and URL
- Required permissions
- Request/response formats
- Status codes
- Rate limits

---

#### [09 - Database Schema](09-DATABASE-SCHEMA.md)
Complete database structure and relationships.

**Topics Covered**:
- Entity-relationship diagrams
- Table definitions with columns
- Indexes and constraints
- Key relationships
- Size estimates
- Maintenance procedures

**Schema Modules**:
- Authentication (accounts_user)
- Projects (ideas, proposals, applications)
- Project Management (boards, tasks)
- Workflow (templates, stages, instances)
- Dynamic Forms
- GitLab Integration
- Notifications

---

#### [10 - Security Guidelines](10-SECURITY.md)
Security best practices and implementation details.

**Topics Covered**:
- Authentication security (JWT, passwords)
- Authorization and access control
- Data protection (encryption, validation)
- SQL injection prevention
- XSS/CSRF protection
- File upload security
- Network security (HTTPS, CORS)
- Security headers
- Common vulnerabilities and mitigations

**Security Features**:
- HttpOnly JWT cookies
- Token encryption (Fernet)
- Rate limiting
- CORS whitelist
- HSTS enforcement
- Webhook signature verification

---

## 🚀 Quick Start Guide

### For Developers

1. **Read**: [00-PROJECT-OVERVIEW.md](00-PROJECT-OVERVIEW.md)
2. **Setup Authentication**: [01-AUTHENTICATION.md](01-AUTHENTICATION.md)
3. **Understand Core Flow**: [02-PROJECT-LIFECYCLE.md](02-PROJECT-LIFECYCLE.md)
4. **API Integration**: [08-API-REFERENCE.md](08-API-REFERENCE.md)

### For System Administrators

1. **Architecture**: [00-PROJECT-OVERVIEW.md](00-PROJECT-OVERVIEW.md)
2. **Database Setup**: [09-DATABASE-SCHEMA.md](09-DATABASE-SCHEMA.md)
3. **Security Hardening**: [10-SECURITY.md](10-SECURITY.md)

### For HoDs/Department Heads

1. **User Roles**: [00-PROJECT-OVERVIEW.md](00-PROJECT-OVERVIEW.md#-user-roles)
2. **Workflow Management**: [03-WORKFLOW-SYSTEM.md](03-WORKFLOW-SYSTEM.md)
3. **Form Creation**: [05-DYNAMIC-FORMS.md](05-DYNAMIC-FORMS.md)

### For Faculty/Supervisors

1. **Project Oversight**: [02-PROJECT-LIFECYCLE.md](02-PROJECT-LIFECYCLE.md)
2. **Workflow Review**: [03-WORKFLOW-SYSTEM.md](03-WORKFLOW-SYSTEM.md)
3. **Board Monitoring**: [04-KANBAN-BOARDS.md](04-KANBAN-BOARDS.md)
4. **GitLab Integration**: [06-GITLAB-INTEGRATION.md](06-GITLAB-INTEGRATION.md)

### For Students

1. **Getting Started**: [01-AUTHENTICATION.md](01-AUTHENTICATION.md#-student-self-registration)
2. **Submitting Proposals**: [02-PROJECT-LIFECYCLE.md](02-PROJECT-LIFECYCLE.md#-uc-02-student-proposes-own-idea)
3. **Applying to Ideas**: [02-PROJECT-LIFECYCLE.md](02-PROJECT-LIFECYCLE.md#-uc-01-doctor-proposes-idea)
4. **Managing Tasks**: [04-KANBAN-BOARDS.md](04-KANBAN-BOARDS.md)
5. **GitLab Setup**: [06-GITLAB-INTEGRATION.md](06-GITLAB-INTEGRATION.md#1-link-gitlab-account)

---

## 📊 Documentation by Feature

### Project Submission
- [02-PROJECT-LIFECYCLE.md](02-PROJECT-LIFECYCLE.md) - Full lifecycle
- [05-DYNAMIC-FORMS.md](05-DYNAMIC-FORMS.md) - Custom forms
- [07-NOTIFICATIONS.md](07-NOTIFICATIONS.md) - Status updates

### Project Execution
- [04-KANBAN-BOARDS.md](04-KANBAN-BOARDS.md) - Task management
- [03-WORKFLOW-SYSTEM.md](03-WORKFLOW-SYSTEM.md) - Milestone tracking
- [06-GITLAB-INTEGRATION.md](06-GITLAB-INTEGRATION.md) - Code tracking

### Administration
- [01-AUTHENTICATION.md](01-AUTHENTICATION.md) - User management
- [03-WORKFLOW-SYSTEM.md](03-WORKFLOW-SYSTEM.md) - Template creation
- [05-DYNAMIC-FORMS.md](05-DYNAMIC-FORMS.md) - Form builder

### Integration
- [06-GITLAB-INTEGRATION.md](06-GITLAB-INTEGRATION.md) - GitLab API
- [08-API-REFERENCE.md](08-API-REFERENCE.md) - REST API
- [07-NOTIFICATIONS.md](07-NOTIFICATIONS.md) - Event system

---

## 🔍 Finding Information

### By Topic

**Authentication & Security**
→ [01-AUTHENTICATION.md](01-AUTHENTICATION.md) + [10-SECURITY.md](10-SECURITY.md)

**Project Workflows**
→ [02-PROJECT-LIFECYCLE.md](02-PROJECT-LIFECYCLE.md) + [03-WORKFLOW-SYSTEM.md](03-WORKFLOW-SYSTEM.md)

**Task Management**
→ [04-KANBAN-BOARDS.md](04-KANBAN-BOARDS.md)

**Custom Forms**
→ [05-DYNAMIC-FORMS.md](05-DYNAMIC-FORMS.md)

**Version Control**
→ [06-GITLAB-INTEGRATION.md](06-GITLAB-INTEGRATION.md)

**API Development**
→ [08-API-REFERENCE.md](08-API-REFERENCE.md)

**Database Work**
→ [09-DATABASE-SCHEMA.md](09-DATABASE-SCHEMA.md)

### By Role

**Dean/Admin**
- All documentation applies
- Focus: [01](01-AUTHENTICATION.md), [10](10-SECURITY.md), [09](09-DATABASE-SCHEMA.md)

**HoD**
- [03-WORKFLOW-SYSTEM.md](03-WORKFLOW-SYSTEM.md)
- [05-DYNAMIC-FORMS.md](05-DYNAMIC-FORMS.md)
- [02-PROJECT-LIFECYCLE.md](02-PROJECT-LIFECYCLE.md)

**Doctor/Supervisor**
- [02-PROJECT-LIFECYCLE.md](02-PROJECT-LIFECYCLE.md)
- [03-WORKFLOW-SYSTEM.md](03-WORKFLOW-SYSTEM.md)
- [04-KANBAN-BOARDS.md](04-KANBAN-BOARDS.md)
- [06-GITLAB-INTEGRATION.md](06-GITLAB-INTEGRATION.md)

**Student**
- [01-AUTHENTICATION.md](01-AUTHENTICATION.md) (Self-registration)
- [02-PROJECT-LIFECYCLE.md](02-PROJECT-LIFECYCLE.md)
- [04-KANBAN-BOARDS.md](04-KANBAN-BOARDS.md)
- [06-GITLAB-INTEGRATION.md](06-GITLAB-INTEGRATION.md)

---

## 🛠️ Common Tasks

### Setting Up the System
1. Read [00-PROJECT-OVERVIEW.md](00-PROJECT-OVERVIEW.md#-deployment-considerations)
2. Configure authentication ([01-AUTHENTICATION.md](01-AUTHENTICATION.md))
3. Set up database ([09-DATABASE-SCHEMA.md](09-DATABASE-SCHEMA.md))
4. Apply security settings ([10-SECURITY.md](10-SECURITY.md))

### Adding a New Feature
1. Review architecture ([00-PROJECT-OVERVIEW.md](00-PROJECT-OVERVIEW.md))
2. Design database changes ([09-DATABASE-SCHEMA.md](09-DATABASE-SCHEMA.md))
3. Implement API endpoints ([08-API-REFERENCE.md](08-API-REFERENCE.md))
4. Update permissions ([10-SECURITY.md](10-SECURITY.md))
5. Add notifications ([07-NOTIFICATIONS.md](07-NOTIFICATIONS.md))

### Troubleshooting
Each documentation file has a "🐛 Troubleshooting" section at the end.

---

## 📞 Support

### Documentation Issues
If you find errors or need clarification, please:
1. Check the troubleshooting section in the relevant doc
2. Search across all documentation files
3. Contact: dev-team@spu.edu.sy

### Code Issues
- Check the code references in each documentation file
- Review the API reference for endpoint details
- Verify security guidelines are followed

---

## 📝 Documentation Standards

### File Naming
- `XX-FEATURE-NAME.md` where XX is a number (00-10)
- Use hyphens for spaces
- All caps for main files (README.md)

### Section Structure
Each documentation file follows this structure:
1. **📋 Overview**: Summary of the feature
2. **🎯 Key Features**: Bullet points
3. **🏗️ Architecture**: Models and design
4. **🔄 Workflows**: Step-by-step processes
5. **📡 API Endpoints**: Integration details
6. **🎨 Frontend Integration**: UI components
7. **🔒 Access Control**: Permissions
8. **🐛 Troubleshooting**: Common issues
9. **Related Documentation**: Links to other docs
10. **Code References**: File locations

### Markdown Conventions
- `📋 📊 🎯 🏗️ 🔄 📡 🎨 🔒 🐛 📞` for section headers
- Code blocks with language tags
- Tables for structured data
- Mermaid diagrams for workflows
- **Bold** for emphasis
- `Code` for technical terms

---

## 🔄 Keeping Documentation Updated

### When to Update
- New feature added
- API endpoint changed
- Security practice updated
- Bug fix affecting documented behavior
- Configuration option added

### Update Checklist
- [ ] Update relevant feature documentation
- [ ] Update API reference if endpoints changed
- [ ] Update database schema if models changed
- [ ] Update security docs if auth/permissions changed
- [ ] Update this README if new doc file added
- [ ] Update "Last Updated" date

---

## 📈 Document Versions

| File | Last Updated | Version |
|------|--------------|---------|
| 00-PROJECT-OVERVIEW.md | June 22, 2026 | 1.0 |
| 01-AUTHENTICATION.md | June 22, 2026 | 1.0 |
| 02-PROJECT-LIFECYCLE.md | June 22, 2026 | 1.0 |
| 03-WORKFLOW-SYSTEM.md | June 22, 2026 | 1.0 |
| 04-KANBAN-BOARDS.md | June 22, 2026 | 1.0 |
| 05-DYNAMIC-FORMS.md | June 22, 2026 | 1.0 |
| 06-GITLAB-INTEGRATION.md | June 22, 2026 | 1.0 |
| 07-NOTIFICATIONS.md | June 22, 2026 | 1.0 |
| 08-API-REFERENCE.md | June 22, 2026 | 1.0 |
| 09-DATABASE-SCHEMA.md | June 22, 2026 | 1.0 |
| 10-SECURITY.md | June 22, 2026 | 1.0 |

---

**Total Documentation**: 11 comprehensive files covering all aspects of the SPU Student Portal system.

**Documentation maintained by**: Development Team  
**Contact**: dev-team@spu.edu.sy  
**Repository**: [SPU-Student-Portal](https://github.com/spu/student-portal)
