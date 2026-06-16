# Workflow App - Dynamic Project Workflows

## Overview
This app provides a dynamic workflow system for managing project stages and forms after a project is assigned.

## Features

### 1. Workflow Templates
- HoD or Doctor can create workflow templates for their department
- Each template contains multiple stages
- Stages can be triggered by:
  - **Project Start**: Immediately when project starts
  - **After X Days**: X days after project start
  - **Specific Date**: On a specific calendar date
  - **Milestone**: At project milestones
  - **Manual**: Manually triggered by supervisor

### 2. Workflow Stages
Each stage includes:
- Name and description
- Trigger configuration
- Associated dynamic form (from dy_forms app)
- Due date calculation
- Notification settings
- Required/Optional flag

### 3. Project Workflows
- Apply a template to a project when it's assigned
- Automatically creates stage instances with calculated due dates
- Track progress and completion

### 4. Stage Instances
- Students submit forms for each stage
- Supervisors review and approve/reject submissions
- Track status: pending, in_progress, submitted, approved, rejected, overdue
- Provide feedback on submissions

## API Endpoints

### Workflow Templates Management
```
GET    /api/workflow/templates/                    - List all templates
GET    /api/workflow/templates/{id}/               - Get specific template
POST   /api/workflow/templates/create/             - Create new template
PUT    /api/workflow/templates/{id}/update/        - Update template
DELETE /api/workflow/templates/{id}/delete/        - Delete template
```

### Apply Workflow
```
POST   /api/workflow/apply/                        - Apply template to project
```

### Student Views
```
GET    /api/workflow/project/{project_board_id}/   - Get project workflow
GET    /api/workflow/pending/                      - Get pending stages
POST   /api/workflow/stage/{id}/submit/            - Submit stage form
```

### Review Submissions
```
POST   /api/workflow/stage/{id}/review/            - Review stage submission
```

## Usage Example

### 1. Create Workflow Template (HoD/Doctor)
```json
POST /api/workflow/templates/create/
{
  "name": "Software Engineering Project Workflow",
  "description": "Standard workflow for SE projects",
  "stages": [
    {
      "name": "Initial Requirements",
      "description": "Submit initial requirements document",
      "order": 1,
      "trigger_type": "project_start",
      "form_id": 5,
      "notify_before_days": 3,
      "is_required": true
    },
    {
      "name": "Weekly Progress Report",
      "description": "Weekly progress update",
      "order": 2,
      "trigger_type": "after_days",
      "trigger_days": 7,
      "form_id": 6,
      "notify_before_days": 1,
      "is_required": true
    },
    {
      "name": "Mid-term Presentation",
      "description": "Mid-term project presentation",
      "order": 3,
      "trigger_type": "date",
      "trigger_date": "2026-06-15",
      "form_id": 7,
      "notify_before_days": 7,
      "is_required": true
    }
  ]
}
```

### 2. Apply Workflow to Project
```json
POST /api/workflow/apply/
{
  "project_board_id": 123,
  "template_id": 1
}
```

### 3. Student Submits Stage
```json
POST /api/workflow/stage/45/submit/
{
  "form_response_id": 789
}
```

### 4. Supervisor Reviews
```json
POST /api/workflow/stage/45/review/
{
  "action": "approve",
  "feedback": "Good work! Requirements are clear."
}
```

## Models

### WorkflowTemplate
- Template for reusable workflows
- Department-specific
- Contains multiple stages

### WorkflowStage
- Individual stage in a template
- Trigger configuration
- Linked to DynamicForm

### ProjectWorkflow
- Instance of template applied to project
- Tracks overall workflow progress

### WorkflowStageInstance
- Instance of stage for specific project
- Tracks submission and review status
- Links to FormResponse

## Integration Points

### With dy_forms App
- Each stage uses a DynamicForm
- Students fill forms for each stage
- Form responses are linked to stage instances

### With project_management App
- Workflows are applied when project is assigned
- Track workflow progress on project board
- Notify students of upcoming deadlines

### With notifications App
- Notify students before stage due dates
- Notify supervisors of new submissions
- Alert on overdue stages

## Future Enhancements
- Recurring stages (weekly/monthly reports)
- Conditional stages (if milestone reached)
- Parallel stages (multiple forms at once)
- Stage dependencies (stage B after stage A approved)
- Automatic workflow application on project assignment
- Dashboard for workflow analytics
