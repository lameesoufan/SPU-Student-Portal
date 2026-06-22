# Workflow & Stage Management System

## 📋 Overview

The Workflow System provides a flexible, template-based approach to managing project milestones, deliverables, and recurring reports. HoDs and Doctors can create reusable workflow templates with multiple stages, then apply them to registered projects. Students submit required materials for each stage, and supervisors review and approve submissions.

## 🎯 Key Features

- **Template-Based Workflows**: Create reusable workflows for consistent project management
- **Flexible Triggers**: Stages activate based on project start, specific dates, or manual triggers
- **Recurring Stages**: Weekly/monthly reports with automatic generation
- **Dynamic Fields**: Each stage can have custom form fields
- **Progress Tracking**: Monitor completion status of all workflow stages
- **Smart Updates**: Modify templates without losing student submissions

## 🏗️ Architecture

### Entity Hierarchy

```
WorkflowTemplate
├── WorkflowStage (multiple)
│   └── WorkflowStageField (multiple)
│
ProjectWorkflow (instance of template applied to project)
├── WorkflowStageInstance (one per stage)
    └── WorkflowFieldResponse (one per field)
```

### Core Models

#### 1. WorkflowTemplate

```python
class WorkflowTemplate:
    name = CharField(255)
    description = TextField
    department = CharField(50)
    created_by = ForeignKey(User)  # HoD or Doctor
    status = CharField  # active, inactive, archived
    created_at = DateTimeField
    updated_at = DateTimeField
```

**Purpose**: Blueprint for project workflows  
**Scope**: Department-specific  
**Lifecycle**: Can be active, inactive, or archived

#### 2. WorkflowStage

```python
class WorkflowStage:
    template = ForeignKey(WorkflowTemplate)
    name = CharField(255)
    description = TextField
    order = PositiveIntegerField
    
    # Trigger Configuration
    trigger_type = CharField  # project_start, after_days, date, milestone, manual
    trigger_days = PositiveIntegerField  # For after_days trigger
    trigger_date = DateField  # For date trigger
    
    # Requirements
    is_required = BooleanField
    notify_before_days = PositiveIntegerField  # Reminder notification
    
    # Recurring Configuration
    is_recurring = BooleanField
    recurrence_unit = CharField  # daily, weekly, biweekly, monthly
    recurrence_interval = PositiveIntegerField  # Every N units
    recurrence_day_of_week = IntegerField  # For weekly (0=Mon, 6=Sun)
    recurrence_end_date = DateField
    max_occurrences = PositiveIntegerField
```

**Trigger Types**:
- `project_start`: Due immediately when workflow applied
- `after_days`: Due X days after project start
- `date`: Due on specific calendar date
- `milestone`: Manual activation by supervisor
- `manual`: Student or supervisor triggers

#### 3. WorkflowStageField

```python
class WorkflowStageField:
    stage = ForeignKey(WorkflowStage)
    label = CharField(255)
    field_type = CharField  # text, textarea, number, select, radio, checkbox, date, file
    required = BooleanField
    options = JSONField  # For select/radio/checkbox
    order = PositiveIntegerField
```

**Supported Field Types**:
- `text`: Short text input
- `textarea`: Long text (multiline)
- `number`: Numeric input
- `select`: Dropdown (single choice)
- `radio`: Radio buttons (single choice)
- `checkbox`: Multiple checkboxes (multi-choice)
- `date`: Date picker
- `file`: File upload

#### 4. ProjectWorkflow

```python
class ProjectWorkflow:
    project_board = ForeignKey(ProjectBoard)
    template = ForeignKey(WorkflowTemplate)
    started_at = DateTimeField
    completed_at = DateTimeField
    is_active = BooleanField
```

**Constraint**: One active workflow per project board

#### 5. WorkflowStageInstance

```python
class WorkflowStageInstance:
    project_workflow = ForeignKey(ProjectWorkflow)
    stage = ForeignKey(WorkflowStage)
    due_date = DateField
    status = CharField  # scheduled, pending, in_progress, submitted, approved, rejected, overdue
    
    # Submission Tracking
    submitted_at = DateTimeField
    reviewed_at = DateTimeField
    reviewed_by = ForeignKey(User)
    feedback = TextField
    
    # Recurrence Tracking
    occurrence_number = PositiveIntegerField
    parent_recurrence = ForeignKey('self')  # Links recurring instances
```

**Status Flow**:
```
scheduled → pending → in_progress → submitted → approved/rejected
                                       ↓
                                   overdue (if past due_date)
```

## 🔄 Workflow Creation Process

### Step 1: Create Template (HoD/Doctor)

**Endpoint**: `POST /api/workflow/templates/`

**Request**:
```json
{
  "name": "Software Engineering Project Workflow",
  "description": "Standard workflow for SE capstone projects",
  "status": "active",
  "stages": [
    {
      "name": "Initial Proposal",
      "description": "Submit detailed project proposal",
      "order": 1,
      "trigger_type": "project_start",
      "notify_before_days": 3,
      "is_required": true,
      "is_recurring": false,
      "fields": [
        {
          "label": "Project Objectives",
          "field_type": "textarea",
          "required": true,
          "order": 1
        },
        {
          "label": "Technology Stack",
          "field_type": "select",
          "required": true,
          "options": ["Python/Django", "Node.js/React", "Java/Spring"],
          "order": 2
        },
        {
          "label": "Project Timeline",
          "field_type": "file",
          "required": true,
          "order": 3
        }
      ]
    },
    {
      "name": "Weekly Progress Report",
      "description": "Submit weekly progress updates",
      "order": 2,
      "trigger_type": "after_days",
      "trigger_days": 7,
      "is_required": true,
      "is_recurring": true,
      "recurrence_unit": "weekly",
      "recurrence_interval": 1,
      "recurrence_day_of_week": 4,  // Friday
      "max_occurrences": 10,
      "fields": [
        {
          "label": "Completed Tasks",
          "field_type": "textarea",
          "required": true
        },
        {
          "label": "Challenges Faced",
          "field_type": "textarea",
          "required": false
        },
        {
          "label": "Next Week Goals",
          "field_type": "textarea",
          "required": true
        }
      ]
    },
    {
      "name": "Mid-Term Presentation",
      "description": "Present project progress to evaluation committee",
      "order": 3,
      "trigger_type": "date",
      "trigger_date": "2026-07-15",
      "is_required": true,
      "fields": [
        {
          "label": "Presentation Slides",
          "field_type": "file",
          "required": true
        },
        {
          "label": "Demo Video",
          "field_type": "file",
          "required": false
        }
      ]
    }
  ]
}
```

**Response**:
```json
{
  "id": 5,
  "name": "Software Engineering Project Workflow",
  "description": "Standard workflow for SE capstone projects",
  "department": "software_engineering",
  "created_by": {
    "id": 10,
    "username": "hod.se",
    "name": "Dr. John Smith"
  },
  "status": "active",
  "stages": [...],  // Full stage details
  "created_at": "2026-06-22T10:00:00Z"
}
```

### Step 2: Apply Template to Project

**Endpoint**: `POST /api/workflow/apply/`

**Permission**: HoD or assigned supervisor

**Request**:
```json
{
  "project_board_id": 42,
  "template_id": 5
}
```

**Process**:
1. Validates user has permission for this project
2. Checks no active workflow exists on this board
3. Creates `ProjectWorkflow` instance
4. Generates `WorkflowStageInstance` for each stage:
   - Calculates `due_date` based on trigger
   - Sets initial status (`scheduled` or `pending`)
   - Creates empty `WorkflowFieldResponse` records
5. Sends notifications to team members

**Auto-Generated Due Dates**:
- `project_start`: Today
- `after_days`: Today + trigger_days
- `date`: trigger_date value
- `milestone`/`manual`: null (activated later)

**Status Logic**:
- If `due_date > today` and trigger is `after_days`/`date` → `scheduled`
- Otherwise → `pending`

### Step 3: Auto-Activation of Scheduled Stages

**Celery Task**: `workflow.tasks.activate_scheduled_stages`

**Schedule**: Daily at 00:10

**Process**:
```python
def activate_scheduled_stages():
    today = datetime.now().date()
    scheduled = WorkflowStageInstance.objects.filter(
        status='scheduled',
        due_date__lte=today
    )
    for instance in scheduled:
        instance.status = 'pending'
        instance.save()
        # Send notification to team
```

## 📝 Student Submission Process

### Step 1: View Workflow Stages

**Endpoint**: `GET /api/workflow/project/{project_board_id}/`

**Permission**: Project member or supervisor

**Response**:
```json
{
  "id": 15,
  "template": {
    "id": 5,
    "name": "Software Engineering Project Workflow"
  },
  "project_board": 42,
  "started_at": "2026-06-01T10:00:00Z",
  "stage_instances": [
    {
      "id": 100,
      "stage": {
        "name": "Initial Proposal",
        "description": "Submit detailed project proposal",
        "is_required": true,
        "fields": [...]
      },
      "due_date": "2026-06-01",
      "status": "pending",
      "occurrence_number": 1,
      "field_responses": [
        {
          "id": 500,
          "field": {
            "id": 20,
            "label": "Project Objectives",
            "field_type": "textarea",
            "required": true
          },
          "value": ""
        }
      ]
    },
    {
      "id": 101,
      "stage": {
        "name": "Weekly Progress Report",
        "description": "Submit weekly progress updates",
        "is_recurring": true
      },
      "due_date": "2026-06-08",
      "status": "scheduled",  // Not yet active
      "occurrence_number": 1
    }
  ]
}
```

### Step 2: Submit Stage

**Endpoint**: `POST /api/workflow/stage/{stage_instance_id}/submit/`

**Permission**: Project team member

**Request**:
```json
{
  "field_responses": {
    "20": "Our project aims to develop...",  // field_id: value
    "21": "Python/Django",
    "22": "<file_upload_handled_separately>"
  }
}
```

**Validation**:
- All required fields must be filled
- Field types validated (number, date format, etc.)
- Select/radio options must be from predefined list
- Status must be `pending` (not `scheduled` or `submitted`)

**On Success**:
1. Updates or creates `WorkflowFieldResponse` records
2. Changes status: `pending` → `submitted`
3. Sets `submitted_at` timestamp
4. Sends notification to supervisor

### Step 3: Supervisor Review

**Endpoint**: `POST /api/workflow/stage/{stage_instance_id}/review/`

**Permission**: Project supervisor, HoD, or Dean

**Request**:
```json
{
  "action": "approve",  // or "reject"
  "feedback": "Great work! The objectives are clear and achievable."
}
```

**On Approval**:
- Status: `submitted` → `approved`
- Sets `reviewed_at` and `reviewed_by`
- Saves `feedback`
- Notification sent to team

**On Rejection**:
- Status: `submitted` → `in_progress`
- Clears `submitted_at`
- Student can revise and resubmit

## 🔁 Recurring Stages

### Configuration Options

```python
is_recurring = True
recurrence_unit = 'weekly'  # daily, weekly, biweekly, monthly
recurrence_interval = 1  # Every 1 week
recurrence_day_of_week = 4  # Friday (for weekly)
recurrence_end_date = '2026-08-31'  # Stop date
max_occurrences = 10  # Max 10 instances
```

### Generation Process

**Celery Task**: `workflow.tasks.generate_recurring_stages`

**Schedule**: Daily at 00:05

**Logic**:
```python
def generate_recurring_stages():
    # Find stages that need new instances
    active_stages = WorkflowStageInstance.objects.filter(
        stage__is_recurring=True,
        project_workflow__is_active=True,
        status='approved'  # Previous occurrence approved
    )
    
    for instance in active_stages:
        # Check if we should create next occurrence
        if should_create_next(instance):
            create_next_occurrence(instance)

def should_create_next(instance):
    # Check max_occurrences
    if instance.stage.max_occurrences:
        current_count = get_occurrence_count(instance)
        if current_count >= instance.stage.max_occurrences:
            return False
    
    # Check end_date
    if instance.stage.recurrence_end_date:
        next_due = calculate_next_due_date(instance)
        if next_due > instance.stage.recurrence_end_date:
            return False
    
    return True

def calculate_next_due_date(instance):
    last_due = instance.due_date
    unit = instance.stage.recurrence_unit
    interval = instance.stage.recurrence_interval
    
    if unit == 'daily':
        return last_due + timedelta(days=interval)
    elif unit == 'weekly':
        return last_due + timedelta(weeks=interval)
    elif unit == 'biweekly':
        return last_due + timedelta(weeks=2 * interval)
    elif unit == 'monthly':
        return last_due + relativedelta(months=interval)
```

### Recurrence Tracking

**Parent-Child Linking**:
```python
# First occurrence
instance1 = WorkflowStageInstance(
    occurrence_number=1,
    parent_recurrence=None
)

# Second occurrence (auto-generated)
instance2 = WorkflowStageInstance(
    occurrence_number=2,
    parent_recurrence=instance1  # Links to first
)
```

**Query All Occurrences**:
```python
# Get all instances of a recurring stage
recurring_instances = WorkflowStageInstance.objects.filter(
    Q(id=first_instance.id) | Q(parent_recurrence=first_instance)
).order_by('occurrence_number')
```

## 🔧 Template Management

### Update Template (Smart Diff)

**Endpoint**: `PUT /api/workflow/templates/{template_id}/`

**Permission**: HoD or original creator

**Request**: Same structure as create, but with IDs

**Smart Update Logic**:

1. **Stage Matching**:
   - First try match by `id`
   - Then try match by `name` + `order`
   - Then try match by `name` only
   - If no match → create new stage

2. **Field Matching**:
   - First try match by `id`
   - Then try match by `label`
   - If no match → create new field

3. **Deletion Handling**:
   - **Stages**: Only delete if no submitted instances exist
   - **Fields**: Only delete if no responses exist
   - Protected items kept with warnings

4. **New Field Propagation**:
   - New fields added to all existing instances
   - Auto-creates empty `WorkflowFieldResponse`
   - If field is required → instances moved back to `in_progress`

**Response with Warnings**:
```json
{
  "data": {...},  // Updated template
  "warnings": [
    "New field 'Budget Justification' added. Applied to 15 instance(s).",
    "Stage 'Final Report' kept (has 3 submission(s)).",
    "Field 'Old Question' kept (has 10 response(s))."
  ]
}
```

### Delete Template

**Endpoint**: `DELETE /api/workflow/templates/{template_id}/`

**Constraint**: Cannot delete if any active workflows exist

**Response (if active workflows)**:
```json
{
  "error": "Cannot delete template with active workflows",
  "detail": "This template is currently in use by active workflows.",
  "active_count": 5,
  "projects": [
    "Smart Campus App",
    "Medical Diagnosis System",
    ...
  ]
}
```

## 📊 Progress Tracking

### Get Workflow Progress

**Calculated Metrics**:
```python
def get_workflow_progress(project_workflow):
    total_stages = project_workflow.stage_instances.count()
    completed = project_workflow.stage_instances.filter(
        status='approved'
    ).count()
    
    return {
        'total': total_stages,
        'completed': completed,
        'percentage': (completed / total_stages * 100) if total_stages > 0 else 0,
        'pending': project_workflow.stage_instances.filter(
            status__in=['pending', 'in_progress']
        ).count(),
        'overdue': project_workflow.stage_instances.filter(
            status='overdue'
        ).count()
    }
```

### Mark Overdue Stages

**Process** (can be Celery task):
```python
def mark_overdue_stages():
    today = datetime.now().date()
    overdue = WorkflowStageInstance.objects.filter(
        status__in=['pending', 'in_progress'],
        due_date__lt=today,
        stage__is_required=True
    )
    
    for instance in overdue:
        instance.status = 'overdue'
        instance.save()
        # Send notification
```

## 🔍 HoD/Supervisor Views

### List All Workflows for Department

**Endpoint**: `GET /api/workflow/department-overview/`

**Permission**: HoD (own dept) or Dean (all)

**Response**:
```json
{
  "templates": [
    {
      "id": 5,
      "name": "SE Project Workflow",
      "active_projects": 12,
      "stages_count": 8
    }
  ],
  "active_workflows": [
    {
      "project": "Smart Campus App",
      "template": "SE Project Workflow",
      "progress": 65,
      "overdue_stages": 1
    }
  ]
}
```

### Review Pending Submissions

**Endpoint**: `GET /api/workflow/pending-reviews/`

**Permission**: Doctor (supervised projects only)

**Response**:
```json
[
  {
    "stage_instance_id": 100,
    "project": "Smart Campus App",
    "stage": "Weekly Progress Report #3",
    "student": "John Doe",
    "submitted_at": "2026-06-22T09:00:00Z",
    "due_date": "2026-06-22"
  }
]
```

## 🔒 Access Control

### Permission Matrix

| Action | Dean | HoD | Doctor | Student |
|--------|------|-----|--------|---------|
| Create template | ✅ | ✅ (own dept) | ✅ (own dept) | ❌ |
| Update template | ✅ | ✅ (own) | ✅ (own) | ❌ |
| Delete template | ✅ | ✅ (own, no active) | ✅ (own, no active) | ❌ |
| Apply workflow | ✅ | ✅ (dept projects) | ✅ (supervised) | ❌ |
| View workflow | ✅ | ✅ (dept projects) | ✅ (supervised) | ✅ (own project) |
| Submit stage | ❌ | ❌ | ❌ | ✅ (team member) |
| Review stage | ✅ | ✅ (dept projects) | ✅ (supervised) | ❌ |

## 🐛 Troubleshooting

### Issue: "This stage is not yet active"
**Cause**: Status is `scheduled`, due date hasn't arrived  
**Solution**: Wait for auto-activation or manually change due date

### Issue: New field not appearing in instances
**Cause**: Template update didn't propagate  
**Solution**: Re-save template or manually run migration script

### Issue: Cannot delete template
**Cause**: Active workflows still using it  
**Solution**: Complete or archive workflows first

### Issue: Recurring stage not generating
**Cause**: Previous occurrence not approved or reached max  
**Solution**: Approve previous occurrence or check limits

---

**Related Documentation**:
- [Dynamic Forms](05-DYNAMIC-FORMS.md) - Similar field system
- [Project Lifecycle](02-PROJECT-LIFECYCLE.md) - When workflows are applied
- [API Reference](08-API-REFERENCE.md) - Complete endpoint specs

**Code References**:
- Models: `backend/workflow/models.py`
- Views: `backend/workflow/views.py`
- Services: `backend/workflow/services.py`
- Tasks: `backend/workflow/tasks.py`

**Last Updated**: June 22, 2026
