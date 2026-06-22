# Project Lifecycle Management

## 📋 Overview

The Project Lifecycle module manages the complete journey of graduation projects from initial idea submission to final approval and team formation. It supports two primary pathways: **Doctor-Proposed Ideas** (UC-01) and **Student-Proposed Ideas** (UC-02), each with distinct approval workflows.

## 🎯 Core Concepts

### Project Origin Types

1. **Doctor Idea** → **Student Application** → **Registered Project**
2. **Student Proposal** → **HoD Approval** → **Assigned Project**

### Key Entities

- **ProjectIdea**: Doctor-proposed project idea
- **StudentIdeaProposal**: Student-proposed project idea
- **IdeaApplication**: Student application to a doctor's idea
- **ProjectApplication**: Auto-created wrapper for approved student proposals
- **TeamInvitation**: Invitation to join an application team
- **ProposalInvitation**: Invitation to join a proposal team

## 📊 UC-01: Doctor Proposes Idea

### Status Flow Diagram

```
┌─────────────────┐
│ Doctor Submits  │
│      Idea       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│ pending_review  ├────►│   rejected   │
└────────┬────────┘     └──────────────┘
         │
         │ HoD Approval
         ▼
┌─────────────────┐
│    approved     │ ◄─── Students can browse
└────────┬────────┘
         │
         │ Student Applies
         ▼
┌─────────────────────────────────┐
│    IdeaApplication Created      │
└────────┬────────────────────────┘
         │
         ▼
┌────────────────────┐
│ awaiting_members   │ ◄─── Waiting for team confirmations
└────────┬───────────┘
         │
         │ All Members Accept
         ▼
┌────────────────────┐
│  pending_doctor    │ ◄─── Doctor reviews application
└────────┬───────────┘
         │
         │ Doctor Approves
         ▼
┌────────────────────┐
│   pending_hod      │ ◄─── HoD final review
└────────┬───────────┘
         │
         │ HoD Approves
         ▼
┌────────────────────┐
│    registered      │ ◄─── ProjectBoard Created
└────────────────────┘
```

### Workflow Steps

#### Step 1: Doctor Submits Idea

**Endpoint**: `POST /api/submit-idea/`

**Request**:
```json
{
  "title": "AI-Powered Medical Diagnosis System",
  "description": "Develop a machine learning system...",
  "department": "artificial_intelligence",
  "required_skills": "Python, TensorFlow, Medical Knowledge",
  "max_team_size": 3
}
```

**Model**:
```python
class ProjectIdea:
    doctor = ForeignKey(User)
    title = CharField(255)
    description = TextField
    department = CharField(50)
    required_skills = CharField(500)
    max_team_size = PositiveSmallIntegerField
    status = CharField  # pending_review, approved, rejected
    rejection_reason = TextField
```

**Business Rules**:
- Only doctors and HoDs can submit ideas
- Max team size: 1-4 students
- Department must match doctor's department
- Auto-notification sent to HoD

#### Step 2: HoD Reviews Idea

**Endpoint**: `POST /api/hod/review-idea/{idea_id}/`

**Permission**: HoD of same department

**Request**:
```json
{
  "action": "approve",  // or "reject"
  "rejection_reason": "Optional reason if rejected"
}
```

**Business Rules**:
- Only HoD of idea's department can review
- Approved ideas appear in student browse list
- Rejected ideas can be resubmitted (new submission required)
- Notification sent to doctor

#### Step 3: Student Browses & Applies

**Browse Endpoint**: `GET /api/browse-ideas/`

**Response**:
```json
[
  {
    "id": 42,
    "title": "AI-Powered Medical Diagnosis System",
    "description": "Develop a machine learning system...",
    "doctor": {
      "id": 10,
      "name": "Dr. Sarah Johnson",
      "username": "dr.johnson"
    },
    "department": "artificial_intelligence",
    "required_skills": "Python, TensorFlow, Medical Knowledge",
    "max_team_size": 3,
    "created_at": "2026-06-01T10:00:00Z"
  }
]
```

**Apply Endpoint**: `POST /api/apply-idea/{idea_id}/`

**Request**:
```json
{
  "team_size": 3,
  "team_size_reason": "Complex project requires diverse skills",
  "member_ids": ["student002", "student003"],
  "form_id": 5,  // Optional dynamic form
  "field_responses": [
    {
      "field_id": 1,
      "value": "We have experience in..."
    }
  ]
}
```

**Business Rules**:
- Student can only have ONE active application at a time
- Idea can only have ONE registered application
- Team size must be 1-3 (or match idea's max_team_size)
- Team size reason required if size = 1 or > 3
- Members must accept invitations before proceeding

#### Step 4: Team Invitation Flow

**Model**:
```python
class TeamInvitation:
    application = ForeignKey(IdeaApplication)
    invitee = ForeignKey(User)
    status = CharField  # pending, accepted, rejected
```

**Check Invitations**: `GET /api/my-invitations/`

**Respond to Invitation**: `POST /api/respond-invitation/{inv_id}/`

```json
{
  "action": "accept"  // or "reject"
}
```

**Business Rules**:
- All invited members must accept before moving to next stage
- If any member rejects → application status = `rejected_insufficient_members`
- Leader can replace rejected members
- Each member can only accept ONE invitation at a time

#### Step 5: Doctor Reviews Application

**Endpoint**: `POST /api/doctor/review-application/{app_id}/`

**Request**:
```json
{
  "action": "approve",
  "rejection_reason": ""
}
```

**Business Rules**:
- Only idea's doctor can review
- Can view submitted dynamic form responses
- Rejection moves application to `rejected` status
- Approval moves to `pending_hod`

#### Step 6: HoD Final Approval

**Endpoint**: `POST /api/hod/review-application/{app_id}/`

**Request**:
```json
{
  "action": "approve"
}
```

**On Approval**:
1. Application status → `registered`
2. **ProjectBoard** auto-created
3. All team members linked to board
4. Notifications sent to all members
5. Idea becomes unavailable for other students

## 📊 UC-02: Student Proposes Own Idea

### Status Flow Diagram

```
┌─────────────────────┐
│  Student Submits    │
│     Proposal        │
└──────────┬──────────┘
           │
           ▼
┌───────────────────────┐
│  awaiting_members     │ ◄─── Waiting for team invitations
└──────────┬────────────┘
           │
           │ All Members Accept
           ▼
┌───────────────────────┐
│  pending_supervisor   │ ◄─── Supervisor reviews
└──────────┬────────────┘
           │
           │ Supervisor Approves
           ▼
┌───────────────────────┐
│    pending_hod        │ ◄─── HoD final review
└──────────┬────────────┘
           │
           │ HoD Approves
           ▼
┌───────────────────────┐
│      assigned         │ ◄─── ProjectBoard Created
└───────────────────────┘
```

### Workflow Steps

#### Step 1: Student Submits Proposal

**Endpoint**: `POST /api/propose-idea/`

**Request**:
```json
{
  "title": "Smart Campus Navigation App",
  "description": "Mobile app with AR features...",
  "department": "software_engineering",
  "supervisor": 15,  // Doctor ID
  "team_size": 2,
  "team_size_reason": "",  // Required if team_size = 1 or 4
  "member_ids": ["student002"],
  "form_id": 3,
  "field_responses": [
    {
      "field_id": 10,
      "value": "Project motivation..."
    }
  ]
}
```

**Model**:
```python
class StudentIdeaProposal:
    student = ForeignKey(User)  # Leader
    supervisor = ForeignKey(User)  # Must be doctor
    title = CharField(255)
    description = TextField
    department = CharField(50)
    team_size = PositiveSmallIntegerField
    team_size_reason = TextField
    status = CharField
    rejection_reason = TextField
```

**Business Rules**:
- Student can only have ONE active proposal
- Team size: 1-4 students
- Must select supervisor (doctor)
- Department must match student's department
- Dynamic form submission optional (if HoD created one)

#### Step 2: Team Formation (Proposal Invitations)

**Model**:
```python
class ProposalInvitation:
    proposal = ForeignKey(StudentIdeaProposal)
    invitee = ForeignKey(User)
    status = CharField  # pending, accepted, rejected
```

**Flow**:
1. System auto-creates invitations for all `member_ids`
2. Invited students receive notifications
3. Each student accepts/rejects via: `POST /api/respond-proposal-invitation/{inv_id}/`
4. If all accept → status moves to `pending_supervisor`
5. If any reject → leader can replace member

**Replace Member**: `POST /api/proposal/{proposal_id}/replace-member/`

```json
{
  "old_member_id": "student002",
  "new_member_id": "student004"
}
```

#### Step 3: Supervisor Reviews Proposal

**Endpoint**: `POST /api/supervisor/review-proposal/{proposal_id}/`

**Permission**: Assigned supervisor only

**Request**:
```json
{
  "action": "approve",
  "rejection_reason": ""
}
```

**Business Rules**:
- Can view dynamic form responses
- Can request modifications (rejection → student resubmits)
- Approval moves to `pending_hod`

#### Step 4: HoD Reviews Proposal

**Endpoint**: `POST /api/hod/review-proposal/{proposal_id}/`

**Permission**: HoD of proposal's department

**Request**:
```json
{
  "action": "approve"
}
```

**On Approval**:
1. Proposal status → `assigned`
2. **ProjectApplication** wrapper created
3. **ProjectBoard** auto-created
4. All team members linked to board
5. Notifications sent
6. Student can begin project work

#### Step 5: Project Assignment

**Auto-Created Entities**:
```python
# Wrapper for board linking
ProjectApplication(
    proposal=proposal,
    student=student,
    status='accepted'
)

# Kanban board for task management
ProjectBoard(
    proposal=proposal,
    title=proposal.title
)
```

## 🔄 Team Management Features

### 1. Replace Team Member

**Scenarios**:
- Member rejects invitation
- Member becomes inactive
- Team dynamics require change

**Constraints**:
- Only leader can replace members
- Can only replace BEFORE final approval
- New member must accept invitation
- Cannot replace yourself (leader)

### 2. Cancel Proposal/Application

**Student Endpoint**: `POST /api/cancel-proposal/{proposal_id}/`

**Allowed States**:
- `awaiting_members`
- `pending_supervisor`

**Not Allowed**:
- After HoD approval (`assigned`)
- After any supervisor/HoD rejection

**Effect**:
- Proposal/Application deleted
- All invitations cancelled
- Team members notified

### 3. Check My Project Status

**Student Endpoint**: `GET /api/my-proposal/`

**Response**:
```json
{
  "id": 42,
  "title": "Smart Campus Navigation App",
  "status": "pending_supervisor",
  "supervisor": {
    "id": 15,
    "name": "Dr. Smith"
  },
  "team_members": [
    {
      "username": "student001",
      "name": "John Doe",
      "invitation_status": "accepted"
    }
  ],
  "created_at": "2026-06-15T10:00:00Z"
}
```

## 🔍 Search & Browse Features

### 1. Browse Approved Ideas

**Endpoint**: `GET /api/browse-ideas/`

**Filters** (Query Params):
- `department`: Filter by department
- `search`: Text search in title/description
- `doctor_id`: Ideas by specific doctor

**Example**:
```
GET /api/browse-ideas/?department=software_engineering&search=mobile
```

### 2. Search Students for Team

**Endpoint**: `GET /api/list-students/?q=john`

**Response**:
```json
[
  {
    "username": "student123",
    "name": "John Smith",
    "display": "John Smith (student123)"
  }
]
```

**Business Rules**:
- Minimum 2 characters in search query
- Excludes current user
- Returns max 20 results
- Search in username, first_name, last_name

### 3. List Available Supervisors

**Endpoint**: `GET /api/list-doctors/`

**Response**:
```json
[
  {
    "id": 15,
    "name": "Dr. Sarah Johnson",
    "department": "software_engineering"
  }
]
```

## 🔒 Access Control

### Permission Matrix

| Action | Dean | HoD | Doctor | Student |
|--------|------|-----|--------|---------|
| Submit doctor idea | ✅ | ✅ | ✅ | ❌ |
| Review doctor idea | ✅ | ✅ (own dept) | ❌ | ❌ |
| Browse ideas | ✅ | ✅ | ✅ | ✅ |
| Apply to idea | ❌ | ❌ | ❌ | ✅ |
| Review application (doctor) | ❌ | ❌ | ✅ (own idea) | ❌ |
| Review application (HoD) | ✅ | ✅ (own dept) | ❌ | ❌ |
| Propose own idea | ❌ | ❌ | ❌ | ✅ |
| Review proposal (supervisor) | ❌ | ❌ | ✅ (assigned) | ❌ |
| Review proposal (HoD) | ✅ | ✅ (own dept) | ❌ | ❌ |

## 🐛 Error Handling

### Common Errors

**Validation Errors**:
```json
{
  "error": "Validation failed.",
  "details": {
    "title": ["This field is required."],
    "team_size": ["Ensure this value is less than or equal to 4."]
  }
}
```

**Business Logic Errors**:
```json
{
  "error": "You already have an active proposal. Complete or cancel it first."
}
```

**Permission Errors**:
```json
{
  "error": "You cannot review this proposal."
}
```

## 🔍 Database Constraints

### Unique Constraints

1. **One Active Proposal per Student**:
```python
UniqueConstraint(
    fields=['student'],
    condition=Q(status__in=['awaiting_members', 'pending_supervisor', 
                            'pending_hod', 'assigned']),
    name='unique_active_proposal_per_student'
)
```

2. **One Active Application per Student**:
```python
UniqueConstraint(
    fields=['student'],
    condition=Q(status__in=['awaiting_members', 'pending_doctor', 
                            'pending_hod', 'registered']),
    name='unique_active_application_per_student'
)
```

3. **One Registered Application per Idea**:
```python
UniqueConstraint(
    fields=['idea'],
    condition=Q(status='registered'),
    name='unique_registered_application_per_idea'
)
```

### Indexes

```python
# Performance optimization indexes
indexes = [
    Index(fields=['doctor', 'status']),
    Index(fields=['department', 'status', '-created_at']),
    Index(fields=['status', '-created_at']),
    Index(fields=['student', 'status']),
    Index(fields=['supervisor', 'status', '-created_at']),
]
```

## 📊 Key Service Functions

### projects/services.py

```python
# Doctor Idea Management
create_project_idea(doctor, title, description, department, 
                   required_skills, max_team_size)
hod_review_doctor_idea(idea, action, rejection_reason)

# Student Proposal Management
create_student_proposal(student, supervisor, title, description,
                       department, team_size, team_size_reason,
                       member_ids)
supervisor_review_proposal(proposal, action, rejection_reason)
hod_review_proposal(proposal, action, rejection_reason)
cancel_proposal(proposal, student)

# Application Management
apply_on_idea(student, idea, team_size, team_size_reason, member_ids)
doctor_review_application(application, action, rejection_reason)
hod_review_application(application, action, rejection_reason)

# Team Management
respond_to_invitation(invitation, action)
respond_to_proposal_invitation(invitation, action)
replace_proposal_member(proposal, old_member_id, new_member_id)
replace_application_member(application, old_member_id, new_member_id)
```

---

**Related Documentation**:
- [Dynamic Forms](05-DYNAMIC-FORMS.md) - Form integration in proposals
- [Workflow System](03-WORKFLOW-SYSTEM.md) - Post-approval workflow stages
- [Kanban Boards](04-KANBAN-BOARDS.md) - Project execution phase
- [Notifications](07-NOTIFICATIONS.md) - Status change alerts

**Last Updated**: June 22, 2026
