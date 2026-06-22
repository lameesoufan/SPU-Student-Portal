# Database Schema Documentation

## 📋 Overview

Complete database schema for the SPU Student Portal. The system uses PostgreSQL in production with SQLite support for development.

## 🗄️ Schema Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        AUTHENTICATION                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                           accounts_user
                     ┌─────────┼─────────┐
                     │         │         │
┌────────────────────┴───┐     │     ┌───┴─────────────────────┐
│   PROJECTS MODULE      │     │     │   GITLAB INTEGRATION   │
├────────────────────────┤     │     ├────────────────────────┤
│ projects_projectidea   │     │     │ gitlab_gitlabuser      │
│ projects_studentidea.. │     │     │ gitlab_gitlabproject   │
│ projects_ideaappli...  │     │     │ gitlab_gitlabcommit    │
│ projects_teaminvit...  │     │     │ gitlab_gitlabcommit... │
│ projects_proposalinv.. │     │     └────────────────────────┘
│ projects_projectapp... │     │
└────────────────────────┘     │
                               │
┌──────────────────────────────┴──────────────────────────────┐
│                    PROJECT MANAGEMENT                        │
├──────────────────────────────────────────────────────────────┤
│ project_management_projectboard                              │
│ project_management_task                                      │
│ project_management_taskcomment                               │
│ project_management_taskattachment                            │
│ project_management_activitylog                               │
└──────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────┴──────────────────────────────┐
│                      WORKFLOW SYSTEM                         │
├──────────────────────────────────────────────────────────────┤
│ workflow_workflowtemplate                                    │
│ workflow_workflowstage                                       │
│ workflow_workflowstagefield                                  │
│ workflow_projectworkflow                                     │
│ workflow_workflowstageinstance                               │
│ workflow_workflowfieldresponse                               │
└──────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────┴──────────────────────────────┐
│                    DYNAMIC FORMS                             │
├──────────────────────────────────────────────────────────────┤
│ dy_forms_dynamicform                                         │
│ dy_forms_formfield                                           │
│ dy_forms_formresponse                                        │
│ dy_forms_fieldresponse                                       │
└──────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────┴──────────────────────────────┐
│                     NOTIFICATIONS                            │
├──────────────────────────────────────────────────────────────┤
│ notifications_notification                                   │
└──────────────────────────────────────────────────────────────┘
```

## 📊 Table Details

### accounts_user

**Extends**: Django AbstractUser

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BigInteger | PK, Auto | Primary key |
| username | VARCHAR(150) | UNIQUE, NOT NULL | Login username |
| first_name | VARCHAR(150) | | User's first name |
| last_name | VARCHAR(150) | | User's last name |
| email | VARCHAR(254) | | Email address |
| password | VARCHAR(128) | NOT NULL | Hashed password |
| is_staff | Boolean | DEFAULT FALSE | Django admin access |
| is_superuser | Boolean | DEFAULT FALSE | Full permissions |
| is_active | Boolean | DEFAULT TRUE | Account enabled |
| date_joined | Timestamp | | Registration date |
| role | VARCHAR(20) | NOT NULL | dean, hod, doctor, student |
| department | VARCHAR(50) | | Department code |
| must_change_password | Boolean | DEFAULT FALSE | Force password change |

**Indexes**:
- `username_idx` (UNIQUE)
- `email_idx`
- `role_idx`
- `department_idx`

**Constraints**:
- `unique_hod_per_department`: Only one HoD per department

### projects_projectidea

Doctor-proposed project ideas

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BigInteger | PK | Primary key |
| doctor_id | BigInteger | FK → accounts_user | Idea creator |
| title | VARCHAR(255) | NOT NULL | Idea title |
| description | Text | NOT NULL | Detailed description |
| department | VARCHAR(50) | NOT NULL | Department code |
| required_skills | VARCHAR(500) | | Comma-separated skills |
| max_team_size | SmallInteger | NOT NULL | Maximum team size |
| status | VARCHAR(35) | NOT NULL | pending_review, approved, rejected |
| rejection_reason | Text | | Reason if rejected |
| created_at | Timestamp | NOT NULL | Creation time |
| updated_at | Timestamp | NOT NULL | Last update time |

**Indexes**:
- `doctor_status_idx` (doctor_id, status)
- `department_status_created_idx` (department, status, created_at DESC)

### projects_studentideaproposal

Student-proposed project ideas

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BigInteger | PK | Primary key |
| student_id | BigInteger | FK → accounts_user | Proposal leader |
| supervisor_id | BigInteger | FK → accounts_user | Assigned supervisor |
| title | VARCHAR(255) | NOT NULL | Proposal title |
| description | Text | NOT NULL | Detailed description |
| department | VARCHAR(50) | NOT NULL | Department code |
| team_size | SmallInteger | NOT NULL | Planned team size |
| team_size_reason | Text | | Justification if size ≠ 2-3 |
| status | VARCHAR(25) | NOT NULL | awaiting_members, pending_supervisor, etc. |
| rejection_reason | Text | | Reason if rejected |
| created_at | Timestamp | NOT NULL | Creation time |
| updated_at | Timestamp | NOT NULL | Last update time |

**Indexes**:
- `student_status_idx` (student_id, status)
- `supervisor_status_created_idx` (supervisor_id, status, created_at DESC)

**Constraints**:
- `unique_active_proposal_per_student`: One active proposal per student

### project_management_projectboard

Kanban board for approved projects

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BigInteger | PK | Primary key |
| proposal_id | BigInteger | FK → StudentIdeaProposal, UNIQUE | Link to proposal (nullable) |
| application_id | BigInteger | FK → IdeaApplication, UNIQUE | Link to application (nullable) |
| title | VARCHAR(255) | NOT NULL | Board title |
| created_at | Timestamp | NOT NULL | Creation time |

**Indexes**:
- `created_at_idx`

### project_management_task

Individual tasks on boards

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BigInteger | PK | Primary key |
| board_id | BigInteger | FK → ProjectBoard | Parent board |
| title | VARCHAR(255) | NOT NULL | Task title |
| description | Text | | Detailed description |
| status | VARCHAR(20) | NOT NULL | todo, in_progress, in_review, done |
| priority | VARCHAR(10) | NOT NULL | low, medium, high |
| assignee_id | BigInteger | FK → accounts_user | Assigned member |
| due_date | Date | | Deadline |
| created_by_id | BigInteger | FK → accounts_user | Creator |
| created_at | Timestamp | NOT NULL | Creation time |
| updated_at | Timestamp | NOT NULL | Last update time |

**Indexes**:
- `board_status_idx` (board_id, status)
- `assignee_status_idx` (assignee_id, status)
- `board_updated_idx` (board_id, updated_at DESC)

### workflow_workflowtemplate

Reusable workflow templates

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BigInteger | PK | Primary key |
| name | VARCHAR(255) | NOT NULL | Template name |
| description | Text | | Template description |
| department | VARCHAR(50) | NOT NULL | Department code |
| created_by_id | BigInteger | FK → accounts_user | Template creator |
| status | VARCHAR(20) | NOT NULL | active, inactive, archived |
| created_at | Timestamp | NOT NULL | Creation time |
| updated_at | Timestamp | NOT NULL | Last update time |

**Indexes**:
- `department_status_created_idx` (department, status, created_at DESC)

### workflow_workflowstageinstance

Active workflow stage for a project

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BigInteger | PK | Primary key |
| project_workflow_id | BigInteger | FK → ProjectWorkflow | Parent workflow |
| stage_id | BigInteger | FK → WorkflowStage | Stage template |
| due_date | Date | | Due date |
| status | VARCHAR(20) | NOT NULL | scheduled, pending, submitted, approved, etc. |
| submitted_at | Timestamp | | Submission time |
| reviewed_at | Timestamp | | Review time |
| reviewed_by_id | BigInteger | FK → accounts_user | Reviewer |
| feedback | Text | | Reviewer feedback |
| occurrence_number | Integer | NOT NULL | For recurring stages |
| parent_recurrence_id | BigInteger | FK → self | First instance in series |
| created_at | Timestamp | NOT NULL | Creation time |
| updated_at | Timestamp | NOT NULL | Last update time |

**Indexes**:
- `workflow_status_idx` (project_workflow_id, status)

**Constraints**:
- `unique_stage_occurrence_per_workflow` (project_workflow_id, stage_id, occurrence_number)

### dy_forms_dynamicform

HoD-created custom forms

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BigInteger | PK | Primary key |
| hod_id | BigInteger | FK → accounts_user | Form creator |
| department | VARCHAR(50) | NOT NULL | Department code |
| context | VARCHAR(20) | NOT NULL | propose, browse, weekly_report, etc. |
| title | VARCHAR(255) | | Form title |
| description | Text | | Form description |
| is_recurring | Boolean | DEFAULT FALSE | Is recurring report |
| frequency | VARCHAR(20) | | once, weekly, monthly, etc. |
| created_at | Timestamp | NOT NULL | Creation time |
| updated_at | Timestamp | NOT NULL | Last update time |

**Constraints**:
- `unique_dynamic_form_department_context` (department, context)

### gitlab_gitlabproject

GitLab repository per project

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BigInteger | PK | Primary key |
| board_id | BigInteger | FK → ProjectBoard, UNIQUE | Linked project board |
| gitlab_project_id | Integer | NOT NULL | GitLab project ID |
| gitlab_project_path | VARCHAR(255) | NOT NULL | e.g., user/repo |
| project_name | VARCHAR(200) | | Repository name |
| web_url | URLField | NOT NULL | Browser URL |
| ssh_url | URLField | | SSH clone URL |
| http_url | URLField | | HTTPS clone URL |
| visibility | VARCHAR(20) | NOT NULL | private, internal, public |
| default_branch | VARCHAR(100) | | Main branch name |
| webhook_id | Integer | | Registered webhook ID |
| is_orphaned | Boolean | DEFAULT FALSE | True if deleted from GitLab |
| created_at | Timestamp | NOT NULL | Creation time |
| updated_at | Timestamp | NOT NULL | Last update time |

**Indexes**:
- `gitlab_project_id_idx`

### gitlab_gitlabcommit

Tracked Git commits

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | BigInteger | PK | Primary key |
| project_id | BigInteger | FK → GitLabProject | Parent repository |
| sha | VARCHAR(40) | NOT NULL | Git commit SHA |
| message | Text | NOT NULL | Commit message |
| author_name | VARCHAR(200) | NOT NULL | Committer name |
| author_email | EmailField | NOT NULL | Committer email |
| author_username | VARCHAR(100) | | GitLab username |
| ref | VARCHAR(200) | | Branch name |
| authored_date | Timestamp | NOT NULL | Author date |
| committed_date | Timestamp | NOT NULL | Commit date |
| web_url | URLField | | Commit URL |
| added_lines | Integer | DEFAULT 0 | Lines added |
| removed_lines | Integer | DEFAULT 0 | Lines removed |
| total_lines | Integer | DEFAULT 0 | Total changes |
| created_at | Timestamp | NOT NULL | Tracked time |

**Indexes**:
- `sha_idx`
- `project_committed_idx` (project_id, committed_date DESC)
- `author_project_idx` (author_username, project_id)

**Constraints**:
- `unique_commit_per_project` (project_id, sha)

## 🔗 Key Relationships

### One-to-One
- `GitLabUser ↔ User`
- `GitLabProject ↔ ProjectBoard`
- `ProjectBoard ↔ StudentIdeaProposal`
- `ProjectBoard ↔ IdeaApplication`

### One-to-Many
- `User → ProjectIdea` (doctor's ideas)
- `User → StudentIdeaProposal` (student's proposals)
- `ProjectIdea → IdeaApplication` (applications to idea)
- `ProjectBoard → Task` (tasks on board)
- `Task → TaskComment` (comments on task)
- `WorkflowTemplate → WorkflowStage` (stages in template)
- `GitLabProject → GitLabCommit` (commits in repo)

### Many-to-Many (via through models)
- `StudentIdeaProposal ↔ User` (via ProposalInvitation)
- `IdeaApplication ↔ User` (via TeamInvitation)

## 📏 Size Estimates (for planning)

**Small Department (100 students, 20 projects/year)**:
- accounts_user: ~120 rows
- projects_projectidea: ~30 rows/year
- projects_studentideaproposal: ~50 rows/year
- project_management_task: ~500 rows/year
- gitlab_gitlabcommit: ~2,000 rows/year

**Large Department (500 students, 100 projects/year)**:
- accounts_user: ~600 rows
- projects_projectidea: ~150 rows/year
- projects_studentideaproposal: ~250 rows/year
- project_management_task: ~2,500 rows/year
- gitlab_gitlabcommit: ~10,000 rows/year

## 🔧 Maintenance

### Cleanup Tasks

**Archive Old Projects** (annually):
```sql
-- Archive completed projects older than 2 years
UPDATE project_management_projectboard
SET archived = TRUE
WHERE created_at < NOW() - INTERVAL '2 years'
AND status = 'completed';
```

**Purge Old Notifications** (monthly):
```sql
-- Delete read notifications older than 90 days
DELETE FROM notifications_notification
WHERE is_read = TRUE
AND created_at < NOW() - INTERVAL '90 days';
```

### Backup Strategy

1. **Full Backup**: Daily at 2:00 AM
2. **Incremental**: Every 6 hours
3. **Retention**: 30 days
4. **Test Restore**: Monthly

---

**Related Documentation**:
- [All Feature Modules](00-PROJECT-OVERVIEW.md)
- [API Reference](08-API-REFERENCE.md)

**Last Updated**: June 22, 2026
