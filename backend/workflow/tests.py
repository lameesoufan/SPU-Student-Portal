from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import (
    WorkflowTemplate, WorkflowStage, WorkflowStageField,
    ProjectWorkflow, WorkflowStageInstance, WorkflowFieldResponse,
)
from project_management.models import ProjectBoard
from projects.models import StudentIdeaProposal, ProjectIdea

User = get_user_model()


def _create_full_proposal_board(student, doctor, hod):
    """Helper: create a proposal that is 'assigned' + a ProjectBoard."""
    proposal = StudentIdeaProposal.objects.create(
        student=student,
        supervisor=doctor,
        title='Test Proposal',
        description='desc',
        department='software_engineering',
        team_size=2,
        status='assigned',
    )
    board = ProjectBoard.objects.create(proposal=proposal, title=proposal.title)
    return proposal, board


class WorkflowTemplateModelTests(TestCase):
    """Tests for WorkflowTemplate, WorkflowStage, WorkflowStageField models."""

    def setUp(self):
        self.hod = User.objects.create_user(
            username='wf_hod', password='Pass123', role='hod', department='software_engineering'
        )

    def test_create_template_with_stages_and_fields(self):
        template = WorkflowTemplate.objects.create(
            name='Sprint Workflow',
            description='Weekly sprints',
            department='software_engineering',
            created_by=self.hod,
        )
        stage = WorkflowStage.objects.create(
            template=template, name='Weekly Report', order=1,
            trigger_type='after_days', trigger_days=7,
        )
        field = WorkflowStageField.objects.create(
            stage=stage, label='Accomplishments', field_type='textarea', required=True, order=0,
        )
        self.assertEqual(template.stages.count(), 1)
        self.assertEqual(stage.fields.count(), 1)
        self.assertEqual(str(template), 'Sprint Workflow (software_engineering)')
        self.assertEqual(str(stage), 'Sprint Workflow - Weekly Report')

    def test_template_ordering(self):
        t1 = WorkflowTemplate.objects.create(name='Old', department='software_engineering', created_by=self.hod)
        t2 = WorkflowTemplate.objects.create(name='New', department='software_engineering', created_by=self.hod)
        templates = list(WorkflowTemplate.objects.all())
        self.assertEqual(templates[0].name, 'New')

    def test_unique_active_workflow_per_board_constraint(self):
        doctor = User.objects.create_user(username='wf_doc1', password='Pass123', role='doctor')
        student = User.objects.create_user(username='wf_stu1', password='Pass123', role='student')
        proposal = StudentIdeaProposal.objects.create(
            student=student, supervisor=doctor, title='P1', description='d',
            department='software_engineering', team_size=2, status='assigned',
        )
        board = ProjectBoard.objects.create(proposal=proposal, title='P1')
        template = WorkflowTemplate.objects.create(
            name='WF', department='software_engineering', created_by=self.hod
        )

        pw1 = ProjectWorkflow.objects.create(project_board_id=board.id, template=template, is_active=True)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ProjectWorkflow.objects.create(project_board_id=board.id, template=template, is_active=True)


class WorkflowTemplateAPITests(TestCase):
    """Tests for workflow template CRUD API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.hod = User.objects.create_user(
            username='wf_api_hod', password='Pass123', role='hod', department='software_engineering'
        )
        self.client.force_authenticate(user=self.hod)

    def test_create_template(self):
        data = {
            'name': 'Sprint Template',
            'description': 'A sprint-based workflow',
            'stages': [
                {
                    'name': 'Planning',
                    'order': 1,
                    'trigger_type': 'project_start',
                    'fields': [
                        {'label': 'Sprint Goals', 'field_type': 'textarea', 'required': True, 'order': 0}
                    ],
                },
                {
                    'name': 'Review',
                    'order': 2,
                    'trigger_type': 'after_days',
                    'trigger_days': 14,
                    'fields': [],
                },
            ],
        }
        response = self.client.post('/api/workflow/templates/create/', data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['name'], 'Sprint Template')
        self.assertEqual(len(response.data['stages']), 2)
        self.assertEqual(response.data['stages'][0]['fields'][0]['label'], 'Sprint Goals')

    def test_cleanup_duplicate_stages_preserves_instance_metadata(self):
        self.client.force_authenticate(user=self.hod)

        template = WorkflowTemplate.objects.create(
            name='Duplicate Template', department='software_engineering', created_by=self.hod
        )
        original_stage = WorkflowStage.objects.create(
            template=template, name='Repeated Stage', order=1, trigger_type='manual'
        )
        duplicate_stage = WorkflowStage.objects.create(
            template=template, name='Repeated Stage', order=2, trigger_type='manual'
        )

        original_field = WorkflowStageField.objects.create(
            stage=original_stage, label='Status', field_type='text', required=True, order=0
        )
        duplicate_field = WorkflowStageField.objects.create(
            stage=duplicate_stage, label='Status', field_type='text', required=True, order=0
        )

        proposal, board = _create_full_proposal_board(
            User.objects.create_user(username='cleanup_stu', password='Pass123', role='student'),
            User.objects.create_user(username='cleanup_doc', password='Pass123', role='doctor'),
            self.hod,
        )
        workflow = ProjectWorkflow.objects.create(project_board=board, template=template, is_active=True)
        original_instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow,
            stage=original_stage,
            status='pending',
            occurrence_number=1,
        )
        duplicate_instance = WorkflowStageInstance.objects.create(
            project_workflow=workflow,
            stage=duplicate_stage,
            status='approved',
            submitted_at=timezone.now(),
            reviewed_at=timezone.now(),
            reviewed_by=self.hod,
            feedback='Looks good',
            occurrence_number=1,
        )
        WorkflowFieldResponse.objects.create(
            stage_instance=duplicate_instance,
            field=duplicate_field,
            value='Complete',
        )

        response = self.client.post('/api/workflow/cleanup-duplicates/')
        self.assertEqual(response.status_code, 200)

        original_instance.refresh_from_db()
        self.assertEqual(WorkflowStage.objects.filter(template=template, name='Repeated Stage').count(), 1)
        self.assertEqual(WorkflowStageInstance.objects.filter(project_workflow=workflow).count(), 1)
        self.assertEqual(original_instance.status, 'approved')
        self.assertIsNotNone(original_instance.submitted_at)
        self.assertIsNotNone(original_instance.reviewed_at)
        self.assertEqual(original_instance.reviewed_by, self.hod)
        self.assertEqual(original_instance.feedback, 'Looks good')
        self.assertEqual(original_instance.field_responses.count(), 1)
        self.assertEqual(original_instance.field_responses.first().field, original_field)

    def test_list_templates(self):
        WorkflowTemplate.objects.create(name='T1', department='software_engineering', created_by=self.hod)
        WorkflowTemplate.objects.create(name='T2', department='software_engineering', created_by=self.hod)

        response = self.client.get('/api/workflow/templates/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

    def test_get_template_detail(self):
        template = WorkflowTemplate.objects.create(
            name='Detail T', department='software_engineering', created_by=self.hod
        )
        response = self.client.get(f'/api/workflow/templates/{template.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Detail T')

    def test_get_template_not_found(self):
        response = self.client.get('/api/workflow/templates/99999/')
        self.assertEqual(response.status_code, 404)

    def test_update_template(self):
        template = WorkflowTemplate.objects.create(
            name='Old Name', department='software_engineering', created_by=self.hod
        )
        WorkflowStage.objects.create(template=template, name='S1', order=1, trigger_type='manual')

        data = {
            'name': 'Updated Name',
            'stages': [
                {
                    'name': 'New Stage',
                    'order': 1,
                    'trigger_type': 'after_days',
                    'trigger_days': 7,
                    'fields': [],
                }
            ],
        }
        response = self.client.put(f'/api/workflow/templates/{template.id}/update/', data, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['name'], 'Updated Name')
        self.assertEqual(len(response.data['stages']), 1)
        self.assertEqual(response.data['stages'][0]['name'], 'New Stage')

    def test_delete_template(self):
        template = WorkflowTemplate.objects.create(
            name='To Delete', department='software_engineering', created_by=self.hod
        )
        response = self.client.delete(f'/api/workflow/templates/{template.id}/delete/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(WorkflowTemplate.objects.filter(id=template.id).exists())

    def test_student_cannot_create_template(self):
        student = User.objects.create_user(
            username='wf_stu2', password='Pass123', role='student', department='software_engineering'
        )
        self.client.force_authenticate(user=student)
        response = self.client.post('/api/workflow/templates/create/', {'name': 'X'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_different_department_template_not_visible(self):
        hod_ai = User.objects.create_user(
            username='hod_ai', password='Pass123', role='hod', department='artificial_intelligence'
        )
        WorkflowTemplate.objects.create(name='SE Only', department='software_engineering', created_by=self.hod)
        self.client.force_authenticate(user=hod_ai)
        response = self.client.get('/api/workflow/templates/')
        self.assertEqual(len(response.data), 0)


class ApplyWorkflowAPITests(TestCase):
    """Tests for applying a workflow to a project."""

    def setUp(self):
        self.client = APIClient()
        self.hod = User.objects.create_user(
            username='apply_hod', password='Pass123', role='hod', department='software_engineering'
        )
        self.doctor = User.objects.create_user(
            username='apply_doc', password='Pass123', role='doctor'
        )
        self.student = User.objects.create_user(
            username='apply_stu', password='Pass123', role='student'
        )
        self.template = WorkflowTemplate.objects.create(
            name='Apply Template', department='software_engineering', created_by=self.hod
        )
        WorkflowStage.objects.create(
            template=self.template, name='Stage 1', order=1, trigger_type='project_start'
        )
        WorkflowStage.objects.create(
            template=self.template, name='Stage 2', order=2, trigger_type='after_days', trigger_days=7
        )
        _, self.board = _create_full_proposal_board(self.student, self.doctor, self.hod)

    def test_apply_workflow_to_project(self):
        self.client.force_authenticate(user=self.hod)
        response = self.client.post('/api/workflow/apply/', {
            'project_board_id': self.board.id,
            'template_id': self.template.id,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.data['stage_instances']), 2)

    def test_apply_workflow_duplicate_blocked(self):
        self.client.force_authenticate(user=self.hod)
        self.client.post('/api/workflow/apply/', {
            'project_board_id': self.board.id, 'template_id': self.template.id,
        }, format='json')
        response = self.client.post('/api/workflow/apply/', {
            'project_board_id': self.board.id, 'template_id': self.template.id,
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('already has an active workflow', response.data['error'])

    def test_apply_workflow_nonexistent_project(self):
        self.client.force_authenticate(user=self.hod)
        response = self.client.post('/api/workflow/apply/', {
            'project_board_id': 99999, 'template_id': self.template.id,
        }, format='json')
        self.assertEqual(response.status_code, 404)

    def test_apply_workflow_nonexistent_template(self):
        self.client.force_authenticate(user=self.hod)
        response = self.client.post('/api/workflow/apply/', {
            'project_board_id': self.board.id, 'template_id': 99999,
        }, format='json')
        self.assertEqual(response.status_code, 404)

    def test_student_cannot_apply_workflow(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post('/api/workflow/apply/', {
            'project_board_id': self.board.id, 'template_id': self.template.id,
        }, format='json')
        self.assertEqual(response.status_code, 403)

    def test_doctor_cannot_apply_to_other_supervisors_project(self):
        other_doc = User.objects.create_user(username='other_doc2', password='Pass123', role='doctor')
        self.client.force_authenticate(user=other_doc)
        response = self.client.post('/api/workflow/apply/', {
            'project_board_id': self.board.id, 'template_id': self.template.id,
        }, format='json')
        self.assertIn(response.status_code, [403, 404])


class WorkflowSubmitAndReviewTests(TestCase):
    """Tests for student submitting and HoD/Doctor reviewing workflow stages."""

    def setUp(self):
        self.client = APIClient()
        self.hod = User.objects.create_user(
            username='review_hod', password='Pass123', role='hod', department='software_engineering'
        )
        self.doctor = User.objects.create_user(
            username='review_doc', password='Pass123', role='doctor'
        )
        self.student = User.objects.create_user(
            username='review_stu', password='Pass123', role='student'
        )

        self.template = WorkflowTemplate.objects.create(
            name='Review Template', department='software_engineering', created_by=self.hod
        )
        self.stage1 = WorkflowStage.objects.create(
            template=self.template, name='Report', order=1, trigger_type='project_start'
        )
        self.field1 = WorkflowStageField.objects.create(
            stage=self.stage1, label='Summary', field_type='textarea', required=True, order=0
        )
        self.field2 = WorkflowStageField.objects.create(
            stage=self.stage1, label='Comments', field_type='text', required=False, order=1
        )

        proposal, self.board = _create_full_proposal_board(self.student, self.doctor, self.hod)

        self.project_workflow = ProjectWorkflow.objects.create(
            project_board_id=self.board.id, template=self.template, is_active=True
        )
        self.stage_instance = WorkflowStageInstance.objects.create(
            project_workflow=self.project_workflow, stage=self.stage1, status='pending'
        )

    def test_student_submit_workflow_stage(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post(f'/api/workflow/stage/{self.stage_instance.id}/submit/', {
            'field_responses': {
                str(self.field1.id): 'This is my summary.',
                str(self.field2.id): 'Some comments.',
            }
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'submitted')

        self.stage_instance.refresh_from_db()
        self.assertEqual(self.stage_instance.status, 'submitted')
        self.assertEqual(WorkflowFieldResponse.objects.filter(stage_instance=self.stage_instance).count(), 2)

    def test_student_submit_missing_required_field(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post(f'/api/workflow/stage/{self.stage_instance.id}/submit/', {
            'field_responses': {
                str(self.field2.id): 'Only optional field.',
            }
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('required', response.data['error'])

    def test_student_submit_invalid_field_id(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post(f'/api/workflow/stage/{self.stage_instance.id}/submit/', {
            'field_responses': {
                '99999': 'Invalid field value.',
            }
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid field', response.data['error'])

    def test_non_member_cannot_submit(self):
        other_student = User.objects.create_user(username='other_stu', password='Pass123', role='student')
        self.client.force_authenticate(user=other_student)
        response = self.client.post(f'/api/workflow/stage/{self.stage_instance.id}/submit/', {
            'field_responses': {str(self.field1.id): 'value'}
        }, format='json')
        self.assertEqual(response.status_code, 403)

    def test_review_approve_stage(self):
        self.stage_instance.status = 'submitted'
        self.stage_instance.save()

        self.client.force_authenticate(user=self.hod)
        response = self.client.post(f'/api/workflow/stage/{self.stage_instance.id}/review/', {
            'action': 'approve',
            'feedback': 'Good work!',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'approved')
        self.assertEqual(response.data['feedback'], 'Good work!')

    def test_review_reject_stage(self):
        self.stage_instance.status = 'submitted'
        self.stage_instance.save()

        self.client.force_authenticate(user=self.hod)
        response = self.client.post(f'/api/workflow/stage/{self.stage_instance.id}/review/', {
            'action': 'reject',
            'feedback': 'Needs more detail.',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['status'], 'rejected')

    def test_review_invalid_action(self):
        self.stage_instance.status = 'submitted'
        self.stage_instance.save()

        self.client.force_authenticate(user=self.hod)
        response = self.client.post(f'/api/workflow/stage/{self.stage_instance.id}/review/', {
            'action': 'invalid_action',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_non_creator_cannot_review(self):
        other_hod = User.objects.create_user(
            username='other_hod2', password='Pass123', role='hod', department='artificial_intelligence'
        )
        self.stage_instance.status = 'submitted'
        self.stage_instance.save()

        self.client.force_authenticate(user=other_hod)
        response = self.client.post(f'/api/workflow/stage/{self.stage_instance.id}/review/', {
            'action': 'approve',
        }, format='json')
        self.assertEqual(response.status_code, 403)


class GetProjectWorkflowTests(TestCase):
    """Tests for viewing project workflow."""

    def setUp(self):
        self.client = APIClient()
        self.hod = User.objects.create_user(
            username='view_hod', password='Pass123', role='hod', department='software_engineering'
        )
        self.doctor = User.objects.create_user(username='view_doc', password='Pass123', role='doctor')
        self.student = User.objects.create_user(username='view_stu', password='Pass123', role='student')

        proposal, self.board = _create_full_proposal_board(self.student, self.doctor, self.hod)
        self.template = WorkflowTemplate.objects.create(
            name='View Template', department='software_engineering', created_by=self.hod
        )
        WorkflowStage.objects.create(template=self.template, name='S1', order=1, trigger_type='manual')

    def test_get_project_workflow(self):
        pw = ProjectWorkflow.objects.create(
            project_board_id=self.board.id, template=self.template, is_active=True
        )
        WorkflowStageInstance.objects.create(project_workflow=pw, stage=self.template.stages.first(), status='pending')

        self.client.force_authenticate(user=self.student)
        response = self.client.get(f'/api/workflow/project/{self.board.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['is_active'], True)
        self.assertEqual(len(response.data['stage_instances']), 1)

    def test_get_project_workflow_not_found(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.get(f'/api/workflow/project/{self.board.id}/')
        self.assertEqual(response.status_code, 404)

    def test_unauthorized_user_cannot_view(self):
        pw = ProjectWorkflow.objects.create(
            project_board_id=self.board.id, template=self.template, is_active=True
        )
        other_student = User.objects.create_user(username='other_stu2', password='Pass123', role='student')
        self.client.force_authenticate(user=other_student)
        response = self.client.get(f'/api/workflow/project/{self.board.id}/')
        self.assertEqual(response.status_code, 403)


class BulkApplyWorkflowTests(TestCase):
    """Tests for bulk applying workflows."""

    def setUp(self):
        self.client = APIClient()
        self.hod = User.objects.create_user(
            username='bulk_hod', password='Pass123', role='hod', department='software_engineering'
        )
        self.doctor = User.objects.create_user(username='bulk_doc', password='Pass123', role='doctor')
        self.student1 = User.objects.create_user(username='bulk_stu1', password='Pass123', role='student')
        self.student2 = User.objects.create_user(username='bulk_stu2', password='Pass123', role='student')

        self.template = WorkflowTemplate.objects.create(
            name='Bulk Template', department='software_engineering', created_by=self.hod
        )
        WorkflowStage.objects.create(template=self.template, name='S1', order=1, trigger_type='manual')

        _, self.board1 = _create_full_proposal_board(self.student1, self.doctor, self.hod)
        _, self.board2 = _create_full_proposal_board(self.student2, self.doctor, self.hod)

    def test_bulk_apply(self):
        self.client.force_authenticate(user=self.hod)
        response = self.client.post('/api/workflow/apply-bulk/', {
            'template_id': self.template.id,
            'project_ids': [self.board1.id, self.board2.id],
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['applied_count'], 2)
        self.assertEqual(response.data['error_count'], 0)

    def test_bulk_apply_exceeds_limit(self):
        self.client.force_authenticate(user=self.hod)
        response = self.client.post('/api/workflow/apply-bulk/', {
            'template_id': self.template.id,
            'project_ids': list(range(101)),
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_bulk_apply_empty_project_ids(self):
        self.client.force_authenticate(user=self.hod)
        response = self.client.post('/api/workflow/apply-bulk/', {
            'template_id': self.template.id,
            'project_ids': [],
        }, format='json')
        self.assertEqual(response.status_code, 400)


class ReplaceWorkflowTests(TestCase):
    """Tests for replacing an active workflow for a project."""

    def setUp(self):
        self.client = APIClient()
        self.hod = User.objects.create_user(
            username='replace_hod', password='Pass123', role='hod', department='software_engineering'
        )
        self.doctor = User.objects.create_user(username='replace_doc', password='Pass123', role='doctor')
        self.student = User.objects.create_user(username='replace_stu', password='Pass123', role='student')

        self.template1 = WorkflowTemplate.objects.create(
            name='Old Template', department='software_engineering', created_by=self.hod
        )
        WorkflowStage.objects.create(template=self.template1, name='Old Stage', order=1, trigger_type='manual')

        self.template2 = WorkflowTemplate.objects.create(
            name='New Template', department='software_engineering', created_by=self.hod
        )
        WorkflowStage.objects.create(template=self.template2, name='New Stage', order=1, trigger_type='after_days', trigger_days=7)

        proposal, self.board = _create_full_proposal_board(self.student, self.doctor, self.hod)
        self.old_workflow = ProjectWorkflow.objects.create(
            project_board_id=self.board.id, template=self.template1, is_active=True
        )
        WorkflowStageInstance.objects.create(
            project_workflow=self.old_workflow, stage=self.template1.stages.first(), status='pending'
        )

    def test_replace_workflow(self):
        self.client.force_authenticate(user=self.hod)
        response = self.client.put(f'/api/workflow/project/{self.board.id}/replace/', {
            'new_template_id': self.template2.id,
            'keep_completed_stages': True,
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertIn('new_workflow_id', response.data)

        self.old_workflow.refresh_from_db()
        self.assertFalse(self.old_workflow.is_active)

    def test_replace_workflow_no_active_workflow(self):
        other_doc = User.objects.create_user(username='replace_doc2', password='Pass123', role='doctor')
        other_stu = User.objects.create_user(username='replace_stu2', password='Pass123', role='student')
        proposal = StudentIdeaProposal.objects.create(
            student=other_stu, supervisor=other_doc, title='No WF',
            description='d', department='software_engineering', team_size=2, status='assigned',
        )
        board2 = ProjectBoard.objects.create(proposal=proposal, title='No WF Board')
        self.client.force_authenticate(user=self.hod)
        response = self.client.put(f'/api/workflow/project/{board2.id}/replace/', {
            'new_template_id': self.template2.id,
        }, format='json')
        self.assertIn(response.status_code, [400, 404])


class WorkflowProjectsStatusTests(TestCase):
    """Tests for workflow status dashboard endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.hod = User.objects.create_user(
            username='status_hod', password='Pass123', role='hod', department='software_engineering'
        )
        self.doctor = User.objects.create_user(username='status_doc', password='Pass123', role='doctor')
        self.student = User.objects.create_user(username='status_stu', password='Pass123', role='student')

        self.template = WorkflowTemplate.objects.create(
            name='Status Template', department='software_engineering', created_by=self.hod
        )
        WorkflowStage.objects.create(template=self.template, name='S1', order=1, trigger_type='manual')

    def test_available_projects(self):
        proposal, board = _create_full_proposal_board(self.student, self.doctor, self.hod)
        self.client.force_authenticate(user=self.hod)
        response = self.client.get('/api/workflow/available-projects/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.data) >= 1)

    def test_projects_workflow_status(self):
        proposal, board = _create_full_proposal_board(self.student, self.doctor, self.hod)
        self.client.force_authenticate(user=self.hod)
        response = self.client.get('/api/workflow/projects-status/')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

    def test_reviewable_projects(self):
        proposal, board = _create_full_proposal_board(self.student, self.doctor, self.hod)
        pw = ProjectWorkflow.objects.create(
            project_board_id=board.id, template=self.template, is_active=True
        )
        self.client.force_authenticate(user=self.hod)
        response = self.client.get('/api/workflow/reviewable-projects/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(len(response.data) >= 1)

    def test_student_cannot_access_status_endpoints(self):
        self.client.force_authenticate(user=self.student)
        for url in ['/api/workflow/available-projects/', '/api/workflow/projects-status/', '/api/workflow/reviewable-projects/']:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 403)