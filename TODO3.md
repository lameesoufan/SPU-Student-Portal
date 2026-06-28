# TODO: Managing Failed and Withdrawn Students in Graduation Projects

## 1. Executive Summary

The current system has no durable student-level participation status for graduation projects. Project membership is inferred from two separate project sources:

- `IdeaApplication.student` plus accepted `TeamInvitation` rows for doctor-proposed ideas that become `registered`.
- `StudentIdeaProposal.student` plus accepted `ProposalInvitation` rows for student-proposed ideas that become `assigned`.

That design works while every accepted team member remains active, but it cannot represent a student who failed, withdrew, or was administratively removed while the rest of the project continues. The correct implementation is to introduce a first-class participation table in the `projects` app and make all operational logic ask that table whether a student is active.

Recommended architecture:

- Add `ProjectParticipation` records for each student in each registered or assigned graduation project.
- Store `status = active | failed | withdrawn` on that participation record, not on the global student account.
- Add a project-level `operational_status` to both `IdeaApplication` and `StudentIdeaProposal`, because those are the current project source models.
- Keep existing lifecycle statuses such as `registered` and `assigned`; do not overload them with failure or withdrawal semantics.
- Add a transactional `StudentProjectStatusService` used by Dean-only API endpoints.
- Add a dedicated audit log table because the existing `project_management.ActivityLog` is scoped to boards/tasks and is not suitable for academic participation decisions.
- Update committees, reports, project boards, workflow, imports, dynamic forms, exports, GitLab membership synchronization, and frontend pages to use active participations.

No grades should be created or modified by this feature. The feature only controls project participation and future operational eligibility.

## 2. Current Codebase Findings

### 2.1 Relevant Modules

Backend modules inspected:

- `backend/accounts`: custom user model, role definitions, Dean permission helpers, user imports, HoD assignment.
- `backend/projects`: graduation-project domain models, student proposal flow, doctor idea application flow, invitation handling, selectors, serializers, routes, and core services.
- `backend/committees`: committee templates, generated committees, project distribution, dashboard warnings, assignment exports, committee exports.
- `backend/project_management`: project boards, board member derivation, tasks, comments, attachments, board activity log, HoD/Dean board visibility.
- `backend/workflow`: workflow templates, workflow application to projects, pending/reviewable stages, student access to workflow stages.
- `backend/project_imports`: bulk project import, imported project creation, import validation, import history.
- `backend/dy_forms`: form responses linked to proposals, applications, boards, and students.
- `backend/gitlab_integration`: project repository membership and synchronization logic that uses project board members.
- `backend/notifications`: notification delivery available for status-change notifications if product wants them.

Frontend modules inspected:

- `frontend/src/api.jsx`: central API wrapper used by dashboards and feature pages.
- `frontend/src/App.jsx`: role-based dashboard routing.
- `frontend/src/components/DeanDashboard.jsx`: Dean navigation and module routing.
- `frontend/src/components/committees/CommitteesDashboard.jsx`: Dean committee dashboard, distribution trigger, warnings, committee statistics.
- `frontend/src/components/committees/DistributionTable.jsx`: committee distribution table, export buttons, distribute action.
- `frontend/src/components/committees/CommitteeDetail.jsx`: committee detail, assigned projects, doctors, schedule.
- `frontend/src/components/committees/ProjectsAssignment.jsx`: project-to-committee assignment report and swap UI.
- `frontend/src/components/StudentDashboard.jsx`: student project/application/proposal status cards.
- `frontend/src/components/MyProject.jsx`: student project board and workflow entry point.
- `frontend/src/components/SupervisorProjects.jsx`: supervisor project list and board entry.
- `frontend/src/components/HodProjects.jsx`: HoD/Dean project overview.
- `frontend/src/components/KanbanBoard.jsx`: board member and task assignee UI.
- `frontend/src/components/workflow/*`: workflow assignment, review, status, and student/supervisor project views.
- `frontend/src/components/ImportProjects.jsx`: project import history and related frontend flows.

Test modules present:

- `backend/projects/tests.py`, `backend/projects/test_api.py`, `backend/test_projects.py`
- `backend/committees` currently has no dedicated test file in the inspected file list and should receive one.
- `backend/project_management/tests.py`
- `backend/workflow/tests.py`, `backend/test_workflow_scenarios.py`
- `backend/project_imports/tests.py`
- `backend/accounts/tests.py`, `backend/accounts/test_api.py`
- `backend/dy_forms/tests.py`
- `backend/notifications/tests.py`
- `backend/gitlab_integration/tests.py`, `backend/gitlab_integration/test_api.py`

Build and validation entry points:

- Backend dependencies are declared in root `requirements.txt`.
- Frontend dependencies and scripts are in `frontend/package.json`.
- Frontend validation commands available: `npm run lint`, `npm run build`.
- Backend validation should use `cd backend && python manage.py test`.

### 2.2 Relevant Models / Tables

`accounts.User`

- Custom Django user model.
- Roles are `dean`, `hod`, `doctor`, and `student`.
- `username` is used throughout student-facing flows and appears to function as the university ID in many serializers and UI displays.
- `department` is stored on the user.
- Dean users are automatically marked staff/superuser in `User.save()`.

`projects.ProjectIdea`

- Doctor-proposed idea.
- Has `doctor`, `department`, `project_type`, `status`, and `max_team_size`.
- Registered teams are reached through related `IdeaApplication` records.

`projects.IdeaApplication`

- Represents a student/team applying to a doctor idea.
- The leader is stored in `student`.
- Accepted team members are stored in `TeamInvitation`.
- Important statuses: `awaiting_members`, `pending_doctor`, `pending_hod`, `registered`, `rejected`, `rejected_insufficient_members`.
- `registered` is the current signal that the project is an active graduation project.
- No per-student participation status exists.

`projects.TeamInvitation`

- Links an `IdeaApplication` to invited student users.
- `status` is invitation state, not project participation state.
- Accepted invitations are currently treated as active members forever.

`projects.StudentIdeaProposal`

- Represents a student-proposed project.
- The leader is stored in `student`.
- Accepted team members are stored in `ProposalInvitation`.
- Important statuses: `awaiting_members`, `pending_supervisor`, `pending_hod`, `assigned`, `rejected`.
- `assigned` is the current signal that the project is an active graduation project.
- No per-student participation status exists.

`projects.ProposalInvitation`

- Links a `StudentIdeaProposal` to invited student users.
- `status` is invitation state, not project participation state.
- Accepted invitations are currently treated as active members forever.

`projects.ProjectApplication`

- Created when HoD approves a `StudentIdeaProposal`.
- One-to-one with `StudentIdeaProposal`.
- Points to the proposal leader in `student`.
- Does not represent all team members.

`committees.CommitteeTemplate`

- Dean-created committee template for one committee type, department, project type, and semester.
- Stores chair, members, and created_by.

`committees.Committee`

- Generated from a template.
- Stores chair, members, schedule, status, and project assignments.
- Project assignments are many-to-many to whole `IdeaApplication` and `StudentIdeaProposal` records.
- Committee assignments are project-level, not student-level.

`project_management.ProjectBoard`

- One-to-one to either `StudentIdeaProposal` or `IdeaApplication`.
- `members` property derives users from project leader plus accepted invitations.
- No student-level active/inactive filtering exists.

`project_management.ActivityLog`

- Board/task activity log with verbs such as `created`, `status_changed`, `assigned`, and related task actions.
- Scoped to board/task activity and not suitable as the audit trail for Dean participation decisions.

`workflow.ProjectWorkflow` and related workflow models

- Workflow instances are tied to `ProjectBoard`.
- Student access and pending stages depend on project board membership.
- Because board membership is derived from leader/invitations, inactive students would continue to see workflow operations unless membership helpers change.

`project_imports.ImportSession` and `ImportRow`

- Import audit/history tables.
- Bulk import creates `StudentIdeaProposal`, `ProposalInvitation`, `ProjectApplication`, and `ProjectBoard` records directly.
- Import validators currently treat accepted/assigned/registered membership as an active conflict.

`dy_forms.FormResponse`

- Form response can link to a proposal, idea application, project board, and student.
- Form submission/access rules need to respect active participation when a form is an active project workflow/progress artifact.

Current relationship storage:

- There is no project-member pivot table.
- Membership is duplicated as implicit leader fields plus invitation tables.
- Project-level lifecycle status exists on `IdeaApplication.status` and `StudentIdeaProposal.status`.
- Student-level project status does not exist.
- Historical membership is not soft-deleted; it is preserved by keeping the original leader/invitation rows.
- Some rejected application records can be deleted in existing application reuse logic, but registered/assigned project records are retained.

### 2.3 Current Project Membership Flow

Student-proposed project flow:

1. `create_student_proposal()` validates the student and selected members with `_student_is_active()`.
2. The leader is stored on `StudentIdeaProposal.student`.
3. Additional members are stored as `ProposalInvitation` rows.
4. Accepted invitations move a proposal toward `pending_supervisor`.
5. Supervisor approval moves it to `pending_hod`.
6. HoD approval moves it to `assigned`, creates a `ProjectApplication`, and notifies the leader and accepted invitees.
7. From that point, every leader and accepted invitee is assumed active.

Doctor idea application flow:

1. `apply_on_idea()` validates the applicant and selected members with `_student_is_active()`.
2. The leader is stored on `IdeaApplication.student`.
3. Additional members are stored as `TeamInvitation` rows.
4. Accepted invitations move the application toward `pending_doctor`.
5. Doctor approval moves it to `pending_hod`.
6. HoD approval moves it to `registered`.
7. From that point, every leader and accepted invitee is assumed active.

Bulk import flow:

1. `project_imports.services.ImportService` creates `StudentIdeaProposal(status='assigned')`.
2. It creates accepted `ProposalInvitation` rows for team members.
3. It creates `ProjectApplication(status='accepted')`.
4. It creates `ProjectBoard`.
5. No project participation table is created because none exists yet.

Current active-project checks:

- `projects.services.student_has_registered_project(student)` checks registered `IdeaApplication`, accepted `ProjectApplication`, accepted `TeamInvitation`, and accepted `ProposalInvitation`.
- `projects.services._student_is_active(student)` checks registered projects plus active/pending applications, proposals, and invitations.
- These helpers do not distinguish active, failed, or withdrawn participation.

### 2.4 Current Committee Distribution Flow

Committee distribution is implemented in `backend/committees/services.py`.

Current behavior:

- `_collect_projects(department, project_type)` queries:
  - `IdeaApplication.objects.filter(status='registered', idea__department=department)`
  - `StudentIdeaProposal.objects.filter(status='assigned', department=department)`
- It creates one `CollectedProject` per source project.
- `CollectedProject.student_id` and `student_name` are currently populated from the project leader only.
- Accepted team members are not part of the distribution data model.
- `build_distribution_plan()` and `build_distribution_plan_for_combo()` distribute whole projects across committees.
- `apply_distribution_plan()` clears and rewrites affected committee project assignments.
- `Committee.get_all_projects()` later expands students from leader plus accepted invitations for display and exports.

Current assumptions that must change:

- A project remains eligible if its source lifecycle status is `registered` or `assigned`.
- The project leader is enough to represent the project in distribution.
- Every accepted invitation member is active.
- A project with no active members cannot currently be detected.
- A project whose leader is failed/withdrawn but members remain active would still be collected incorrectly unless collection uses active participations.

### 2.5 Current Reports Flow

Reports and exports currently live mainly in `backend/committees/services.py` and `backend/committees/views.py`.

Current report surfaces:

- Committee dashboard statistics in `DashboardView`.
- Committee warnings from `get_dashboard_warnings()`.
- PDF committee export from `export_committees_pdf()`.
- Excel committee export from `export_committees_excel()`.
- Projects assignment table from `ProjectsAssignmentView`.
- Projects assignment Excel export from `export_projects_assignment_excel()`.
- Frontend reporting views in `ProjectsAssignment.jsx`, `DistributionTable.jsx`, and `CommitteesDashboard.jsx`.

Current gaps:

- Reports count source projects and committee assignments, not active students.
- No active/incomplete student sections exist.
- No failed/withdrawn statistics exist.
- No designation date, reason, or changed-by fields exist.
- Previous committee records cannot label inactive students because no inactive status exists.

### 2.6 Current Permission System

Current permissions are role-string based.

- `accounts.permissions.IsDeanOrAdmin` allows authenticated users with `role == 'dean'`.
- `committees.views.IsDean` is a local permission class that also checks `role == 'dean'`.
- `project_imports.permissions.IsSuperAdmin` requires `role == 'dean'` and `is_superuser`.
- `projects.permissions` defines `IsDoctor`, `IsDoctorOrHod`, `IsStudent`, and `IsHod`.
- Frontend dashboards are routed by `user.role` in `App.jsx`.

Required implication:

- Status modification must use backend authorization, not only frontend hiding.
- The shared permission should be Dean-only. If superuser-but-not-Dean accounts are ever introduced, they must not modify status unless product explicitly grants Dean-equivalent authority.

### 2.7 Current Audit / Logging System

Existing audit-like infrastructure:

- `project_management.ActivityLog` records board/task activity only.
- `project_imports.ImportSession` and `ImportRow` record bulk import history only.
- Application logs exist via Python logging, but those are not queryable domain audit records.

Conclusion:

- There is no suitable general audit log for Dean status changes.
- Add a new participation status audit model in the `projects` app.
- Do not reuse `ActivityLog` because it requires a `ProjectBoard` context and uses task-oriented verbs.

### 2.8 Current Gaps and Risks

- No student-level participation status exists.
- Membership is implicit and split across two project source models.
- Active checks are duplicated across services, selectors, project boards, workflow, import validation, forms, and committee distribution.
- Committee assignment is project-level, while the new business rule is student-level.
- Distribution currently collects the leader only; this is risky when the leader becomes failed or withdrawn and members remain active.
- Existing project lifecycle statuses should not be reused for failed/withdrawn participation because they already describe approval workflow state.
- Existing committee M2M assignments should not be deleted blindly because previous committee records are historical.
- Student board, workflow, task assignment, and GitLab operations currently derive membership from accepted invitations and would continue to include inactive students.
- Reports and exports currently cannot separate active and incomplete students.
- The frontend currently has no Dean page for student participation status management.
- Existing semester support appears in committee templates, not in project source models; semester filtering for student status management requires either deriving from committees or adding a project/participation semester field.

## 3. Final Recommended Design

### 3.1 Selected Data Model Approach

Select Option B: add a separate project participation table.

Justification:

- The codebase lacks a proper project-member pivot/entity.
- Extending only `TeamInvitation` and `ProposalInvitation` would miss leaders.
- Extending only leaders/invitations would duplicate status logic across two different membership shapes.
- A separate table gives one place to query active, failed, and withdrawn participants across both `IdeaApplication` and `StudentIdeaProposal`.
- Existing historical leader/invitation data can remain unchanged.
- Existing lifecycle statuses can remain focused on approval and registration flow.

Recommended model name:

- `projects.ProjectParticipation`

Recommended project reference design:

- Prefer explicit nullable foreign keys over `GenericForeignKey`:
  - `idea_application = ForeignKey(IdeaApplication, null=True, blank=True, related_name='participations')`
  - `student_proposal = ForeignKey(StudentIdeaProposal, null=True, blank=True, related_name='participations')`
- Add a `project_source` choice field with values `idea_application` and `student_proposal`.
- Add database constraints so exactly one project link is set.
- Add unique constraints so a student has only one participation row per source project.

This direct-FK approach matches the current codebase style and keeps committee, board, workflow, and report queries simple.

### 3.2 Student-Level Status Design

Add `ProjectParticipation` fields:

- `id`
- `student`
- `project_source`
- `idea_application`
- `student_proposal`
- `role`: `leader` or `member`
- `status`: `active`, `failed`, `withdrawn`
- `status_reason`
- `status_notes`
- `status_changed_at`
- `status_changed_by`
- `created_at`
- `updated_at`

Optional fields if confirmed by product/data owners:

- `academic_year`
- `semester`
- `original_team_size_snapshot`

Creation rules:

- Create participation rows when an `IdeaApplication` becomes `registered`.
- Create participation rows when a `StudentIdeaProposal` becomes `assigned`.
- Create participation rows during bulk import for every imported assigned project.
- Backfill active rows for existing registered/assigned projects.
- Do not create participation rows for rejected projects.
- Pending projects may continue using invitation state until they become registered/assigned unless product confirms status management should apply before registration.

Status rules:

- `active`: student is operationally participating.
- `failed`: student is no longer active because the Dean marked the student failed.
- `withdrawn`: student is no longer active because the Dean marked the student withdrawn.
- Failed/withdrawn students remain historically visible.
- Failed/withdrawn students must be excluded from future operational flows that assume participation.

### 3.3 Project-Level Derived Status Design

Do not replace existing `IdeaApplication.status` or `StudentIdeaProposal.status`.

Add `operational_status` to both source models:

- `active`
- `partial_team`
- `solo`
- `fully_withdrawn`
- `fully_failed`
- `inactive`

Recommended meaning:

- `active`: every original/current participation is active and active member count is greater than 1.
- `partial_team`: active member count is greater than 1 but lower than original/current participation count.
- `solo`: exactly one active member remains.
- `fully_withdrawn`: no active members remain and all inactive members are withdrawn.
- `fully_failed`: no active members remain and all inactive members are failed.
- `inactive`: no active members remain and inactive statuses are mixed failed/withdrawn.

Derived-state rules:

- If active members count > 1 and active members count equals original participation count, set `active`.
- If active members count > 1 and active members count is lower than original participation count, set `partial_team`.
- If active members count = 1, set `solo`.
- If active members count = 0 and all inactive students are withdrawn, set `fully_withdrawn`.
- If active members count = 0 and all inactive students are failed, set `fully_failed`.
- If active members count = 0 with mixed failed/withdrawn, set `inactive`.

Operational status should be recalculated in the same transaction as every participation status change.

### 3.4 Permission Design

Modification rules:

- Only `role == 'dean'` can change participation status.
- Supervisors, committee members, HoDs, students, and non-Dean admins can view status only where their existing page already grants project visibility.
- Unauthorized status-change requests return `403 Forbidden`.
- The frontend must hide or disable status-change actions for non-Dean users, but backend enforcement is mandatory.

Recommended implementation:

- Reuse or centralize `accounts.permissions.IsDeanOrAdmin` after confirming the name does not imply broader admin access. Consider renaming or adding `IsDean`.
- Apply Dean-only permission to every write endpoint for status changes.
- Add tests for student, doctor, HoD, anonymous, and Dean users.

### 3.5 Audit Logging Design

Add `projects.ProjectParticipationStatusLog`.

Fields:

- `id`
- `participation`
- `student`
- `project_source`
- `idea_application`
- `student_proposal`
- `previous_status`
- `new_status`
- `reason`
- `notes`
- `changed_by`
- `changed_at`
- `action_type`
- `metadata` JSON field

Action types:

- `student_project_status_marked_failed`
- `student_project_status_marked_withdrawn`
- `student_project_status_reversed_to_active`

Audit payload metadata should include:

- original team size
- active team size before change
- active team size after change
- project operational status before change
- project operational status after change
- request IP/user agent if already available safely in request context

Audit visibility:

- Student profile/status endpoint should show status change history for that student.
- Dean status management page should show latest change fields and allow drill-down to history.
- Audit records must not be deleted during normal operations.

### 3.6 Distribution Design

Distribution must use active participations as the eligibility source.

Rules:

- Failed/withdrawn students are never included in new distribution outputs.
- Projects with zero active participations are excluded from new distribution.
- Projects with one active participation remain distributable as solo projects unless academic policy says otherwise.
- Projects with multiple active participations remain distributable as team projects.
- Previous committee assignments remain historically visible.
- Historical records should label failed/withdrawn students instead of deleting them.

Required code changes:

- Update `committees.services._collect_projects()` to query active participations for each registered/assigned source project.
- Stop using the project leader as the sole distribution student.
- Extend `CollectedProject` with active participant fields, inactive participant summaries, active team size, original team size, and operational status.
- Update `build_distribution_plan*()` to ignore projects with no active participants.
- Update `apply_distribution_plan()` to assign only eligible projects, while not destroying historical records outside the distribution scope.
- Return excluded student counts from dry runs and real runs:
  - total excluded
  - excluded failed
  - excluded withdrawn
  - excluded projects with zero active students

### 3.7 Reporting Design

Reports and exports must separate active and incomplete students.

Active section:

- Only `ProjectParticipation.status = active`.

Incomplete section:

- `ProjectParticipation.status IN (failed, withdrawn)`.
- Include student name, university ID, department, project title, supervisor, status, designation date, reason, and changed by.

Statistics must separately count:

- active students
- failed students
- withdrawn students
- partial projects
- solo projects
- fully withdrawn projects
- fully failed projects
- mixed inactive projects if `inactive` is used

Committee exports:

- Existing committee/project rows may still show inactive students for historical traceability.
- Active operational sections should list only active participants.
- Inactive students in historical committee rows should be dimmed/labeled in frontend and marked with status in exports.

### 3.8 UI Design

Add a new Dean page:

- Page name: `Student Status Management`
- Likely component: `frontend/src/components/StudentStatusManagement.jsx` or `frontend/src/components/dean/StudentStatusManagement.jsx`
- Add API helpers in `frontend/src/api.jsx`.
- Add navigation item and module card in `frontend/src/components/DeanDashboard.jsx`.

Table columns:

- Student name
- University ID
- Department
- Registered project
- Supervisor
- Team size
- Current status
- Designation date
- Reason
- Last changed by
- Actions

Team size display:

- `3/3`: all original/current students active.
- `2/3 ⚠️`: one student inactive.
- `1/3 ⚠️ Solo`: only one active student remains.
- `0/3 Cancelled`: no active students remain.

Actions:

- Active students: `Mark as Failed`, `Mark as Withdrawn`.
- Failed/withdrawn students: `Reverse to Active`.

Filters:

- Search by student name.
- Search by university ID.
- Filter by status.
- Filter by department.
- Filter by project.
- Filter by supervisor.
- Filter by academic year/semester only if a reliable source exists.

Quick statistics:

- active students count
- failed students count
- withdrawn students count
- partial projects count
- solo projects count
- fully withdrawn projects count
- fully failed projects count

Confirmation modal:

- Show student name.
- Show current project.
- Show current team members with statuses.
- Show impact message.
- Provide optional reason field.
- Confirm/cancel.

Alerts section:

- Projects that became partial.
- Projects that became solo.
- Projects that became fully withdrawn.
- Projects that became fully failed.
- No approval actions required.

## 4. Implementation Phases

### Phase 0: Safety Preparation and Baseline Understanding

- Start condition:
  - Working tree status is recorded.
  - Current backend and frontend validation commands are identified.
  - No feature code has been changed yet.
- Tasks:
  - Record current branch and `git status --short`.
  - Run or document baseline test status with `cd backend && python manage.py test`.
  - Run or document frontend baseline status with `cd frontend && npm run lint && npm run build`.
  - Confirm database engine used in each deployment environment.
  - Confirm whether academic year/semester exists outside committee templates.
  - Confirm whether GitLab access should be revoked when a student is marked failed/withdrawn.
- End condition:
  - Baseline failures, if any, are documented and separated from feature work.
  - Product decisions needed before implementation are listed.
- Deliverables:
  - Baseline validation notes.
  - Confirmed implementation assumptions.
  - No database or application behavior changes.

### Phase 1: Database and Domain Model Changes

- Start condition:
  - Phase 0 complete.
  - Data model approach approved.
- Tasks:
  - Add `ProjectParticipation` to `backend/projects/models.py`.
  - Add `ProjectParticipationStatusLog` to `backend/projects/models.py`.
  - Add `operational_status` to `IdeaApplication`.
  - Add `operational_status` to `StudentIdeaProposal`.
  - Add model constraints for exactly one project link on `ProjectParticipation`.
  - Add uniqueness constraints for `(student, idea_application)` and `(student, student_proposal)`.
  - Add indexes for status management and reports:
    - `(student, status)`
    - `(status, updated_at)`
    - `(project_source, status)`
    - `(idea_application, status)`
    - `(student_proposal, status)`
    - audit `(student, changed_at)`
    - audit `(changed_by, changed_at)`
  - Create migration files.
  - Add data migration to backfill active participations for:
    - leaders and accepted `TeamInvitation` members of `IdeaApplication(status='registered')`
    - leaders and accepted `ProposalInvitation` members of `StudentIdeaProposal(status='assigned')`
    - imported assigned proposals
  - Backfill `operational_status` for existing registered/assigned projects.
  - Register new models in `backend/projects/admin.py`.
- End condition:
  - Migrations apply cleanly on a copy of current data.
  - Every registered/assigned project has participation rows for every current leader/member.
  - No historical project, invitation, committee, or board data is deleted.
- Deliverables:
  - Migration for schema.
  - Migration for backfill.
  - Admin registration for participation and audit models.
  - Model-level tests for constraints and backfill behavior.

### Phase 2: Backend Services and Business Logic

- Start condition:
  - Phase 1 migrations exist and pass model tests.
- Tasks:
  - Add `StudentProjectStatusService` in `backend/projects/services.py` or a new `backend/projects/participation_services.py`.
  - Implement transactional methods:
    - `mark_as_failed(participation_id, reason, changed_by, notes=None)`
    - `mark_as_withdrawn(participation_id, reason, changed_by, notes=None)`
    - `reverse_to_active(participation_id, reason, changed_by, notes=None)`
    - `recalculate_project_operational_status(project)`
  - Add resolver for Dean attempts by student ID:
    - If no registered/assigned participation exists, raise validation error `This student has no registered project.`
  - Update `student_has_registered_project()` to count only active participations for registered/assigned projects.
  - Update `_student_is_active()` so failed/withdrawn participation does not incorrectly block future active-project workflows, subject to product confirmation.
  - Add helper/queryset methods:
    - `ProjectParticipation.objects.active()`
    - `ProjectParticipation.objects.incomplete()`
    - `get_active_participants_for_project(source_project)`
    - `get_all_participants_with_status_for_project(source_project)`
  - Create participations at the moment an application becomes `registered`.
  - Create participations at the moment a proposal becomes `assigned`.
  - Create participations during project import.
  - Ensure all status-changing operations wrap participation update, audit log creation, project recalculation, and optional notification in one transaction.
- End condition:
  - All project registration paths create participation records.
  - Changing a student status updates participation and derived project operational status atomically.
  - Service tests cover success, invalid transitions, no-project error, and transaction rollback.
- Deliverables:
  - Service layer implementation.
  - Central participation selectors/helpers.
  - Unit tests for status transitions and derived project status.

### Phase 3: Authorization and Audit Logging

- Start condition:
  - Phase 2 service methods exist and are covered by unit tests.
- Tasks:
  - Add or centralize an `IsDean` permission in `backend/accounts/permissions.py`.
  - Add serializers for participation list rows, status-change requests, and audit logs.
  - Add Dean-only endpoints in `backend/projects/views.py` or a dedicated participation view module.
  - Add routes in `backend/projects/urls.py`.
  - Enforce permission in every write endpoint.
  - Return `403 Forbidden` for non-Dean write attempts.
  - Return clear `400 Bad Request` validation errors for invalid transitions and no-project cases.
  - Ensure every successful status change writes a `ProjectParticipationStatusLog`.
  - Add audit-history read endpoint for student profile and Dean page.
- End condition:
  - API can list participation rows, change status, reverse status, and fetch history.
  - Audit log entries are created with previous status, new status, reason, changed_by, changed_at, project, and student.
  - Unauthorized write tests pass.
- Deliverables:
  - API serializers.
  - API views/routes.
  - Permission tests.
  - Audit log tests.

### Phase 4: Committee Distribution Integration

- Start condition:
  - Phase 3 API and service tests pass.
  - Active participation helpers are available.
- Tasks:
  - Update `backend/committees/services.py` `_collect_projects()` to use active participations.
  - Ensure project eligibility is based on `active_participations.exists()`.
  - Handle projects whose leader is failed/withdrawn but accepted members remain active.
  - Extend `CollectedProject` with active participants, inactive participants, active team size, original team size, and operational status.
  - Update distribution dry-run output with excluded counts:
    - failed students
    - withdrawn students
    - zero-active projects
  - Update `build_distribution_plan()` and `build_distribution_plan_for_combo()` to operate on eligible projects only.
  - Update `apply_distribution_plan()` to avoid hard deletion of historical committee records outside the current distribution write scope.
  - Update `Committee.get_all_projects()` to return participants with statuses for display/export.
  - Update `ProjectsAssignmentView` and committee serializers to expose active and inactive participant lists.
  - Add regression tests for distribution after one member withdraws, leader fails, entire team withdraws, and mixed inactive teams.
- End condition:
  - New committee distributions never include failed/withdrawn students.
  - Projects with zero active students are excluded.
  - Partial and solo projects remain distributable.
  - Existing committee records can still show inactive students historically.
- Deliverables:
  - Updated committee distribution service.
  - Updated committee serializers/views.
  - Committee integration tests.

### Phase 5: Reports and Statistics Integration

- Start condition:
  - Phase 4 distribution logic correctly uses active participations.
- Tasks:
  - Update committee dashboard stats to count active/incomplete students separately.
  - Add partial, solo, fully withdrawn, fully failed, and inactive project counts.
  - Update `get_dashboard_warnings()` to report partial/solo/fully inactive projects.
  - Update `export_committees_pdf()` with active and incomplete sections.
  - Update `export_committees_excel()` with active/incomplete worksheets or clearly separated sections.
  - Update `export_projects_assignment_excel()` to include participant status fields.
  - Update `ProjectsAssignmentView` response with active/incomplete separation.
  - Ensure reports filter by active participation when showing active committee operations.
  - Add report regression tests for all required sections and counts.
- End condition:
  - Reports no longer mix active and inactive students.
  - Incomplete student rows include status, reason, date, project, supervisor, department, and changed by.
  - Exports match API report behavior.
- Deliverables:
  - Updated dashboard statistics.
  - Updated PDF/Excel exports.
  - Report/export tests.

### Phase 6: Dean Dashboard UI

- Start condition:
  - Phase 3 status-management APIs are stable.
  - Phase 5 stats/report endpoints expose needed data.
- Tasks:
  - Add API helpers in `frontend/src/api.jsx`.
  - Add `Student Status Management` nav item to `DeanDashboard.jsx`.
  - Add a module card for status management.
  - Create the status management page component.
  - Implement table with required columns.
  - Implement filters for search, university ID, status, department, project, supervisor, and semester if available.
  - Implement statistics cards.
  - Implement alerts section for partial, solo, fully withdrawn, and fully failed projects.
  - Implement action buttons based on current status.
  - Implement confirmation modal with current team members and impact message.
  - Show success/error toasts or inline alerts consistent with existing UI patterns.
  - Prevent non-Dean action rendering, while relying on backend enforcement.
- End condition:
  - Dean can mark active students as failed/withdrawn and reverse them to active from the UI.
  - Table, filters, stats, and alerts refresh after actions.
  - UI correctly handles the no-project validation error.
- Deliverables:
  - New React component.
  - Updated `api.jsx`.
  - Updated Dean navigation.
  - Frontend validation via `npm run lint` and `npm run build`.

### Phase 7: Updates to Existing Pages

- Start condition:
  - Phase 6 Dean page works against the status API.
- Tasks:
  - Update `CommitteesDashboard.jsx` to show excluded failed/withdrawn distribution summary.
  - Update `DistributionTable.jsx` to show `5 students excluded from distribution: 3 withdrawn, 2 failed.` style alerts.
  - Update `CommitteeDetail.jsx` to dim/labeled inactive students in historical committee records.
  - Update `ProjectsAssignment.jsx` to separate active/incomplete participants or label inactive participants clearly.
  - Update `StudentDashboard.jsx` to show current participation status and active/inactive project state.
  - Update `MyProject.jsx` so failed/withdrawn students do not see an active board as their current project.
  - Update `SupervisorProjects.jsx` and `HodProjects.jsx` to use active team size and show partial/solo labels.
  - Update `KanbanBoard.jsx` so new task assignee choices include only active students; historical tasks assigned to inactive students should retain names with a status label.
  - Update workflow components so inactive students cannot submit future active stages and are labeled historically.
  - Update import UI only if the API returns new conflict/status warnings.
  - Add student profile/history UI if a profile page exists; otherwise include history in `StudentDashboard.jsx` until a profile surface exists.
- End condition:
  - No existing page counts failed/withdrawn students as active.
  - Existing pages retain historical visibility with status labels.
  - All modified frontend pages build successfully.
- Deliverables:
  - Updated committee pages.
  - Updated project/board/workflow pages.
  - Updated student profile/status display.
  - Frontend lint/build validation.

### Phase 8: Testing and Regression Validation

- Start condition:
  - Phases 1 through 7 are implemented.
- Tasks:
  - Add unit tests for participation model constraints and derived operational status.
  - Add service tests for all status transitions.
  - Add API tests for Dean and non-Dean behavior.
  - Add committee distribution tests for active, failed, withdrawn, partial, solo, and fully inactive projects.
  - Add report/export tests for active and incomplete sections.
  - Add project board tests for active membership and assignee choices.
  - Add workflow tests for inactive student access denial.
  - Add import tests to confirm imported projects create participations.
  - Add regression tests for `_student_is_active()` and `student_has_registered_project()`.
  - Add transaction rollback tests by forcing audit log or recalculation failure.
  - Run full backend test suite.
  - Run frontend lint/build.
- End condition:
  - Required test matrix passes.
  - Any remaining unrelated baseline failures are documented.
- Deliverables:
  - Backend tests.
  - Frontend validation evidence.
  - Regression summary.

### Phase 9: Final Review, Cleanup, and Documentation

- Start condition:
  - Phase 8 validation is complete.
- Tasks:
  - Review migrations for reversibility and data safety.
  - Review query performance and indexes for status management and distribution.
  - Update API documentation in `DOCS/08-API-REFERENCE.md` if project documentation is maintained.
  - Update database schema documentation in `DOCS/09-DATABASE-SCHEMA.md`.
  - Update security documentation with Dean-only status change rule if maintained.
  - Confirm no grade-related logic was introduced.
  - Confirm no historical data is deleted by status changes.
  - Confirm old committee records remain traceable.
  - Run final tests and build.
- End condition:
  - Code, tests, migrations, frontend pages, and docs are ready for review.
- Deliverables:
  - Updated documentation.
  - Final validation report.
  - Release notes and rollback notes.

## 5. Detailed Task Checklist

- [ ] Confirm final model name: `ProjectParticipation` vs `GraduationProjectParticipation`.
- [ ] Confirm whether `username` is the official university ID for display/export.
- [ ] Confirm whether semester/year should be stored on participation or derived from committees.
- [ ] Add participation status choices in `backend/projects/models.py`.
- [ ] Add project operational status choices in `backend/projects/models.py`.
- [ ] Add `ProjectParticipation`.
- [ ] Add `ProjectParticipationStatusLog`.
- [ ] Add `operational_status` to `IdeaApplication`.
- [ ] Add `operational_status` to `StudentIdeaProposal`.
- [ ] Add migrations with constraints and indexes.
- [ ] Add data migration for registered `IdeaApplication` teams.
- [ ] Add data migration for assigned `StudentIdeaProposal` teams.
- [ ] Add backfill for project operational statuses.
- [ ] Register new models in admin.
- [ ] Add participation manager/queryset methods for active/incomplete filters.
- [ ] Add helpers to retrieve active participants for either project source.
- [ ] Update HoD approval of doctor-idea applications to create participation rows.
- [ ] Update HoD approval of student proposals to create participation rows.
- [ ] Update bulk import project creation to create participation rows.
- [ ] Update import validator active-conflict checks to use active participations.
- [ ] Add `StudentProjectStatusService`.
- [ ] Wrap status changes in `transaction.atomic()`.
- [ ] Lock participation and project source rows during status changes.
- [ ] Validate no-project operations with message `This student has no registered project.`
- [ ] Write audit log entry for every successful status change.
- [ ] Recalculate project operational status after every status change.
- [ ] Do not modify grades or create grade concepts.
- [ ] Add Dean-only permission class or centralize the existing one.
- [ ] Add status management serializers.
- [ ] Add status list endpoint.
- [ ] Add mark-failed endpoint.
- [ ] Add mark-withdrawn endpoint.
- [ ] Add reverse-to-active endpoint.
- [ ] Add status history endpoint.
- [ ] Update `student_has_registered_project()` to use active participation.
- [ ] Update `_student_is_active()` to use active participation for registered/assigned project conflict checks.
- [ ] Update `ProjectBoard.members` to return active members for operational use.
- [ ] Add `ProjectBoard.all_participants_with_status` or equivalent for historical display.
- [ ] Update task assignee validation to reject inactive participants for new assignments.
- [ ] Update workflow access and pending-stage logic to use active participants.
- [ ] Update dynamic form submission rules for active project forms.
- [ ] Update GitLab member sync to use active participants for future sync.
- [ ] Decide whether a status change should remove GitLab repository access immediately.
- [ ] Update committee `_collect_projects()` to use active participations.
- [ ] Update distribution dry-run result with excluded counts.
- [ ] Update distribution apply result with excluded counts.
- [ ] Update `Committee.get_all_projects()` with active/inactive participant details.
- [ ] Update committee dashboard stats.
- [ ] Update committee warnings/alerts.
- [ ] Update committee PDF export.
- [ ] Update committee Excel export.
- [ ] Update project assignment API/export.
- [ ] Add frontend API helpers in `frontend/src/api.jsx`.
- [ ] Add Dean dashboard navigation item.
- [ ] Add Dean dashboard module card.
- [ ] Build `Student Status Management` page.
- [ ] Build confirmation modal with impact message.
- [ ] Build status filters and statistics.
- [ ] Build alerts section.
- [ ] Update committee dashboard frontend.
- [ ] Update distribution table frontend.
- [ ] Update committee detail frontend.
- [ ] Update projects assignment frontend.
- [ ] Update student dashboard/profile status display.
- [ ] Update supervisor/HoD project pages.
- [ ] Update board assignee UI.
- [ ] Update workflow UI.
- [ ] Add backend model tests.
- [ ] Add backend service tests.
- [ ] Add backend API permission tests.
- [ ] Add committee distribution tests.
- [ ] Add report/export tests.
- [ ] Add project board tests.
- [ ] Add workflow tests.
- [ ] Add import tests.
- [ ] Add transaction rollback test.
- [ ] Run `cd backend && python manage.py test`.
- [ ] Run `cd frontend && npm run lint`.
- [ ] Run `cd frontend && npm run build`.

## 6. API / Route Changes

Add routes under `backend/projects/urls.py`.

Recommended endpoints:

| Method | Route | Permission | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/projects/participations/status-management/` | Dean | List rows for the Dean table with filters and stats. |
| `GET` | `/api/projects/participations/status-management/stats/` | Dean | Return quick statistics and alerts if not embedded in list response. |
| `POST` | `/api/projects/participations/{id}/mark-failed/` | Dean | Mark one active participation as failed. |
| `POST` | `/api/projects/participations/{id}/mark-withdrawn/` | Dean | Mark one active participation as withdrawn. |
| `POST` | `/api/projects/participations/{id}/reverse-to-active/` | Dean | Reverse failed/withdrawn participation back to active. |
| `GET` | `/api/projects/participations/{id}/history/` | Dean or project-visible user | Return audit history for one participation. |
| `GET` | `/api/projects/students/{student_id}/participation-history/` | Dean or self/visible role | Return student project participation history. |

Status-change request body:

```json
{
  "reason": "Administrative withdrawal",
  "notes": "Optional notes visible to authorized staff only"
}
```

Successful status-change response:

```json
{
  "id": 123,
  "student": {
    "id": 45,
    "name": "Khaled",
    "university_id": "20201234",
    "department": "software_engineering"
  },
  "project": {
    "source": "student_proposal",
    "id": 88,
    "title": "AI Graduation Project",
    "operational_status": "partial_team"
  },
  "previous_status": "active",
  "status": "withdrawn",
  "status_reason": "Administrative withdrawal",
  "status_changed_at": "2026-06-28T12:00:00Z",
  "status_changed_by": {
    "id": 1,
    "name": "Dean User"
  },
  "team_size": {
    "active": 2,
    "original": 3,
    "label": "2/3 ⚠️"
  }
}
```

Required errors:

- `403 Forbidden` for non-Dean writes.
- `400 Bad Request` with `This student has no registered project.` when no registered/assigned participation exists.
- `400 Bad Request` for invalid transition, for example active to active or failed to withdrawn without reversing first.
- `404 Not Found` for unknown participation IDs.

Filtering parameters for the list endpoint:

- `search`
- `university_id`
- `status`
- `department`
- `project`
- `supervisor`
- `project_source`
- `project_type`
- `semester`, only after a reliable source exists
- `page`
- `page_size`

## 7. Database Migration Plan

Migration 1: schema

- Add `operational_status` to `IdeaApplication`.
- Add `operational_status` to `StudentIdeaProposal`.
- Add `ProjectParticipation`.
- Add `ProjectParticipationStatusLog`.
- Add indexes and constraints.

Migration 2: data backfill

- For every `IdeaApplication(status='registered')`:
  - Create leader participation with `role='leader'`, `status='active'`.
  - Create member participation for every accepted `TeamInvitation` with `role='member'`, `status='active'`.
  - Set operational status based on active count and original team size.
- For every `StudentIdeaProposal(status='assigned')`:
  - Create leader participation with `role='leader'`, `status='active'`.
  - Create member participation for every accepted `ProposalInvitation` with `role='member'`, `status='active'`.
  - Set operational status based on active count and original team size.
- Use idempotent `get_or_create` style migration logic.
- Do not create audit logs for backfilled active rows unless product requires migration audit entries. If created, mark them with `action_type='migration_backfill'`.

Migration 3: optional hardening after verification

- Add non-null constraints only where safe.
- Add stricter check constraints if database backend supports them consistently.
- Add additional composite indexes based on production query plans.

Rollback considerations for migrations:

- Rolling back schema removes participation status and audit history.
- Before rollback in production, export `ProjectParticipation` and `ProjectParticipationStatusLog`.
- Existing leader/invitation/project data remains intact because it is not modified destructively.

## 8. Service Layer Plan

Recommended service:

- `backend/projects/participation_services.py`
- Class: `StudentProjectStatusService`

Core methods:

- `mark_as_failed(participation_id, reason, changed_by, notes=None)`
- `mark_as_withdrawn(participation_id, reason, changed_by, notes=None)`
- `reverse_to_active(participation_id, reason, changed_by, notes=None)`
- `change_status(participation, new_status, reason, changed_by, notes=None)`
- `resolve_current_participation_for_student(student_id, project_source=None, project_id=None)`
- `recalculate_project_operational_status(project_source, project_id)`
- `create_participations_for_idea_application(application)`
- `create_participations_for_student_proposal(proposal)`

Transaction requirements:

- Status change must run inside `transaction.atomic()`.
- Lock the participation row with `select_for_update()`.
- Lock the source project row.
- Calculate previous status and previous project operational status before update.
- Update participation fields.
- Create audit log.
- Recalculate source project operational status.
- Invalidate caches if any are introduced later.
- Dispatch notifications/events only after DB success or with `transaction.on_commit()`.

Validation rules:

- Dean-only write authorization is enforced at the API permission layer and can be asserted in service for defense in depth.
- A student with no registered/assigned project participation must return `This student has no registered project.`
- `active -> failed` is valid.
- `active -> withdrawn` is valid.
- `failed -> active` is valid.
- `withdrawn -> active` is valid.
- `failed -> withdrawn` should be rejected unless product explicitly allows direct conversion.
- `withdrawn -> failed` should be rejected unless product explicitly allows direct conversion.
- Repeating the same status should be rejected as a no-op.

Operational side effects:

- Recalculate project operational status.
- Do not delete committee assignments.
- Do not delete board, workflow, task, form, GitLab, or historical data.
- Active future operations should exclude inactive students through central helpers.
- Optional notification can be sent to the student and supervisor after product approval.

## 9. Frontend Component Plan

New API helpers in `frontend/src/api.jsx`:

- `fetchStudentStatusManagement(params)`
- `fetchStudentStatusStats(params)`
- `markParticipationFailed(participationId, payload)`
- `markParticipationWithdrawn(participationId, payload)`
- `reverseParticipationToActive(participationId, payload)`
- `fetchParticipationHistory(participationId)`
- `fetchStudentParticipationHistory(studentId)`

New Dean page component:

- Preferred path: `frontend/src/components/StudentStatusManagement.jsx` unless the project creates a `components/dean` folder.

State:

- table rows
- loading/error
- pagination
- filters
- selected row
- selected action
- modal reason/notes
- stats
- alerts

UI behavior:

- Load list and stats on mount.
- Debounce search fields if existing app patterns support it.
- Show active/failed/withdrawn status badges.
- Show team size label from backend, not recomputed from inconsistent frontend data.
- Show action buttons based on row status.
- Require confirmation modal before status changes.
- Refresh row, stats, and alerts after success.
- Show validation errors inline in the modal.

Existing page updates:

- `DeanDashboard.jsx`: add navigation item, module card, and renderer branch.
- `CommitteesDashboard.jsx`: display excluded student summary and new alert categories.
- `DistributionTable.jsx`: display excluded counts after dry run/distribution.
- `CommitteeDetail.jsx`: label inactive students in historical project rows.
- `ProjectsAssignment.jsx`: show active and incomplete participant separation.
- `StudentDashboard.jsx`: show participation status and history.
- `MyProject.jsx`: no active board for inactive student participation.
- `SupervisorProjects.jsx`: show active team counts and inactive labels.
- `HodProjects.jsx`: show active team counts and inactive sections.
- `KanbanBoard.jsx`: active students only in new assignee choices.
- Workflow components: active students only for new student actions.

## 10. Report and Export Plan

Backend report changes:

- Update `DashboardView` in `backend/committees/views.py` to include student participation statistics.
- Update `get_dashboard_warnings()` in `backend/committees/services.py` for partial/solo/fully inactive alerts.
- Update `ProjectsAssignmentView` to include participant status fields.
- Update `export_committees_pdf()` to split active and incomplete sections.
- Update `export_committees_excel()` to split active and incomplete sections or worksheets.
- Update `export_projects_assignment_excel()` to include status, designation date, reason, and changed by.

Report row fields for incomplete students:

- student name
- university ID
- department
- project title
- project source and ID
- supervisor
- status
- designation date
- reason
- changed by

Required report behavior:

- Active statistics count only active participations.
- Incomplete statistics count failed/withdrawn participations separately.
- Partial project counts use project operational status.
- Fully withdrawn and fully failed projects are not included in active committee distribution reports.
- Historical committee reports may display inactive students with status labels.

## 11. Distribution Algorithm Changes

Current distribution collects source projects by lifecycle status. It must collect eligible projects by active participation.

Required changes in `backend/committees/services.py`:

- Update `_collect_projects()`:
  - Keep lifecycle filters `IdeaApplication.status='registered'` and `StudentIdeaProposal.status='assigned'`.
  - Add operational filter to exclude `fully_withdrawn`, `fully_failed`, and `inactive`.
  - Require at least one active participation.
  - Include active participants in the collected object.
  - Include inactive participants only for excluded-count summaries and historical labels.
- Update `CollectedProject`:
  - Replace single `student_id/student_name` leader fields with `active_students`.
  - Keep leader metadata separately if useful.
  - Add `active_team_size`.
  - Add `original_team_size`.
  - Add `inactive_counts`.
  - Add `operational_status`.
- Update dry-run result:
  - Include `excluded_students_total`.
  - Include `excluded_failed_students`.
  - Include `excluded_withdrawn_students`.
  - Include `excluded_projects_zero_active`.
- Update apply result:
  - Return same excluded summary.
  - Assign committees only to eligible projects.
- Update swapping:
  - `CommitteeViewSet.swap_project` should reject swapping fully inactive projects into active committees unless the operation is explicitly a historical correction.

Important leader edge case:

- If the leader failed/withdrew but other team members remain active, the project remains eligible and must continue with those active members. Distribution cannot depend on leader participation.

## 12. Permission and Security Plan

Backend:

- Add or reuse `IsDean`.
- Apply `IsAuthenticated` and `IsDean` to all status-changing endpoints.
- Do not trust frontend role checks.
- Use object-level validation to ensure the participation belongs to an existing registered/assigned project.
- Return `403 Forbidden` for unauthorized writes.
- Log failed authorization attempts through normal security logging only if the project already does so.

Frontend:

- Only render status-changing actions in Dean dashboard.
- Treat backend `403` as authoritative.
- Show read-only status badges to supervisors, committee pages, and students where appropriate.
- Do not expose internal audit metadata to students unless product approves it; students can see status, reason, timestamp, and changed-by display name if allowed.

Data security:

- Reasons and notes may contain sensitive administrative context.
- Keep `notes` staff-only if product wants student-visible reasons to be less sensitive.
- Do not include audit notes in public exports unless required.

## 13. Audit Trail Plan

Every successful status change creates a `ProjectParticipationStatusLog`.

Audit entry rules:

- Create inside the same transaction as the participation update.
- Store previous and new status.
- Store reason, notes, changed_by, changed_at.
- Store source project references redundantly enough to survive future query changes.
- Store metadata snapshot for team size and project operational state.

Event names:

- `student_project_status_marked_failed`
- `student_project_status_marked_withdrawn`
- `student_project_status_reversed_to_active`

Audit query surfaces:

- Dean status management row shows latest designation date, reason, and changed by.
- Dean row detail/history modal shows the full status change timeline.
- Student profile/status section shows current participation and history appropriate for the viewer.
- Admin site can inspect audit logs.

Do not:

- Delete audit entries during reversal.
- Rewrite old audit entries.
- Store grades in audit metadata.
- Depend on `project_management.ActivityLog` for this feature.

## 14. Edge Cases

- Student has no registered/assigned project: reject with `This student has no registered project.` and make no database changes.
- Student belongs to pending proposal/application only: reject status designation unless product decides pending participation can be managed.
- Student belongs to multiple historical projects: default to current registered/assigned active or incomplete participation; require explicit project selection if ambiguous.
- Student is leader and withdraws: remaining active members continue and project becomes partial/solo as appropriate.
- Student is non-leader and withdraws: leader and remaining active members continue.
- Leader fails technical committee while members continue: project remains active for remaining members.
- Entire team withdraws: project operational status becomes `fully_withdrawn`.
- Entire team fails: project operational status becomes `fully_failed`.
- Mixed failed/withdrawn inactive team: project operational status becomes `inactive`.
- One active member remains from a team of three: project becomes `solo`.
- Two active members remain from a team of four: project becomes `partial_team`.
- Reversal from failed/withdrawn to active: project operational status recalculates and student re-enters active future workflows.
- Concurrent Dean actions on the same participation: row lock prevents lost updates.
- Distribution starts while status change is in progress: transactions and fresh active queries prevent inconsistent assignment.
- Existing committee assignments include now-inactive students: historical views label them; new distributions exclude them.
- Existing tasks assigned to inactive students: keep history; prevent assigning new tasks to inactive students.
- Existing workflow stage submissions by inactive students: keep history; block future student submissions if inactive.
- GitLab project membership: decide whether to remove access immediately or only prevent future auto-add/sync.
- Reports generated before status feature: remain historical and may not include status labels unless regenerated.
- Imported projects: participations must be created during import so status management works immediately.
- Student reversed to active after project became fully inactive: project operational status must return to solo/partial/active depending on active count.
- Reason omitted: store empty reason or null, and still audit the action.
- Deleted user references: use `SET_NULL` for changed_by if matching existing patterns, but preserve display fallback in audit metadata if possible.

## 15. Test Matrix

| # | Scenario | Test type | Expected result |
| --- | --- | --- | --- |
| 1 | Active student marked as failed | Service + API | Participation becomes `failed`, audit log is created, project status recalculates. |
| 2 | Failed student reversed to active | Service + API | Participation becomes `active`, audit log is created, active workflows include student again. |
| 3 | Active student marked as withdrawn | Service + API | Participation becomes `withdrawn`, audit log is created, active workflows exclude student. |
| 4 | Withdrawn student reversed to active | Service + API | Participation becomes `active`, audit log is created, stats update. |
| 5 | Student has no project | API | Response is `400` with `This student has no registered project.`, no DB writes. |
| 6 | One student withdraws from team of three | Service + distribution | Active size becomes `2/3`, project is `partial_team`, remaining students continue. |
| 7 | Two students withdraw from team of three | Service + distribution | Active size becomes `1/3`, project is `solo`, remaining student continues. |
| 8 | Entire team withdraws | Service + reports | Project is `fully_withdrawn`, excluded from new distribution, historical records remain. |
| 9 | One student fails and others continue | Service + committee | Failed student excluded from future committees; others remain eligible. |
| 10 | Entire team fails | Service + workflow | Project is `fully_failed`, does not proceed to final discussion. |
| 11 | Mixed failed/withdrawn inactive team | Service + reports | Project is `inactive`; report lists all incomplete students with statuses. |
| 12 | Distribution excludes failed/withdrawn students | Integration | Excluded summary counts failed and withdrawn students separately. |
| 13 | Committee pages hide inactive students from active views | API + UI | Active operations show active students; historical rows label inactive students. |
| 14 | Reports show active and incomplete sections separately | Report test | Active and incomplete sections contain correct rows. |
| 15 | Statistics count active/failed/withdrawn correctly | API test | Counts match participation table and project operational statuses. |
| 16 | Non-Dean status change | API permission | Student, doctor, HoD, anonymous users receive `403` or auth failure as appropriate. |
| 17 | Audit log for every status change | Service + API | One immutable audit row is created per successful transition. |
| 18 | Reversal restores active behavior | Regression | Student appears in board/workflow/distribution eligibility again. |
| 19 | Exports reflect active/incomplete separation | Export test | PDF/Excel exports include status fields and correct sections. |
| 20 | Transaction rollback | Unit test | If audit/recalculation fails, participation status remains unchanged. |
| 21 | Leader fails but members remain active | Integration | Project remains eligible and distribution uses active members. |
| 22 | Imported project creates participations | Import test | Imported leader and members have active participation rows. |
| 23 | Existing registered application backfill | Migration test | Leader and accepted invitations get active participation rows. |
| 24 | Existing assigned proposal backfill | Migration test | Leader and accepted invitations get active participation rows. |
| 25 | Task assignment to inactive student | Project board test | New assignment is rejected; old assignment remains visible. |
| 26 | Workflow submission by inactive student | Workflow test | Inactive student cannot submit future active stage. |
| 27 | Dynamic form response by inactive student | Form test | Inactive student cannot submit active project form if the form is project-progress scoped. |
| 28 | GitLab sync uses active members | Integration/unit | Future auto-add/sync does not add inactive students. |
| 29 | Same status repeated | Service test | No-op transition is rejected and no audit row is created. |
| 30 | Concurrent status changes | Service test | Row locking prevents lost updates. |

## 16. Acceptance Criteria

- Dean can mark an active project participant as failed.
- Dean can mark an active project participant as withdrawn.
- Dean can reverse failed/withdrawn participation back to active.
- Non-Dean users cannot modify participation status.
- Student without a registered/assigned project receives `This student has no registered project.`
- Every status change is transactional and audited.
- Historical project, invitation, committee, workflow, task, form, import, and board records are not deleted.
- Active lists exclude failed/withdrawn students.
- New committee distributions exclude failed/withdrawn students.
- Projects with zero active participants are excluded from active distribution.
- Partial and solo projects continue normally.
- Project operational status reflects active member count and inactive status mix.
- Reports separate active and incomplete students.
- Exports include status, reason, designation date, and changed by for incomplete students.
- Student profile/dashboard shows current participation status and history.
- Existing committee records can still show inactive students with clear labels.
- All required backend tests pass.
- Frontend lint and build pass.
- No grade logic is introduced.

## 17. Rollback Plan

Code rollback:

- Revert API, service, frontend, committee, board, workflow, import, and report changes together.
- Do not partially roll back only the frontend because backend active filters would still affect behavior.

Database rollback:

- Before rolling back production migrations, export:
  - `ProjectParticipation`
  - `ProjectParticipationStatusLog`
  - source project IDs and operational statuses
- Reverse migrations only after confirming the feature is not needed for active operations.
- Existing project source data remains intact because the implementation must not delete leader/invitation records.

Operational rollback:

- If distribution was run with the new feature and rollback is required, committee assignments may need to be regenerated under the old rules.
- Keep exported audit logs for compliance even if the audit table is removed.
- Communicate that failed/withdrawn students may reappear in old active lists after rollback because the old system has no inactive concept.

Safer deployment option:

- Add the new schema and backfill first.
- Deploy read-only status views.
- Enable Dean status-change endpoints after validation.
- Enable distribution/report filtering after participation data has been verified.

## 18. Open Questions

- The request mentions both `TODO.md` and `TODO3.md`; implementation work should confirm which planning file is canonical.
- Is `accounts.User.username` the official university ID to display in the Dean table and exports?
- Should participation status apply only after `registered`/`assigned`, or should pending proposals/applications also be manageable?
- Should failed/withdrawn students be allowed to register for another project in the same academic year or semester?
- Where should academic year/semester live for project participation? Current source projects do not appear to have a semester field; committee templates do.
- Should reason be optional, as requested for the UI, or mandatory for audit quality?
- Should `notes` be staff-only while `reason` is visible to students?
- Should marking a student failed/withdrawn remove GitLab repository access immediately, or only prevent future sync/add operations?
- Should inactive students be blocked from viewing the old project board, or only from future operational actions?
- Should old unscheduled committee assignments be cleaned when a project becomes fully inactive, or preserved entirely as historical records?
- Are `fully_withdrawn`, `fully_failed`, and `inactive` acceptable operational status labels for Arabic/localized UI?
- Should Dean status changes notify students, supervisors, HoDs, and committee chairs?
- Should direct transition from `failed` to `withdrawn` or `withdrawn` to `failed` be allowed, or must the Dean reverse to active first?
- Should imported historical projects be allowed to start with failed/withdrawn participants if the import file contains that information later?
