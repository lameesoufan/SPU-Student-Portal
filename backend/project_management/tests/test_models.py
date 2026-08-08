"""Model tests for project boards, tasks, comments, attachments, and activity logs."""

from datetime import date, timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from project_management.models import (
    ActivityLog,
    ProjectBoard,
    Task,
    TaskAttachment,
    TaskComment,
    _attachment_upload_path,
)
from projects.models import (
    IdeaApplication,
    ProjectIdea,
    ProjectParticipation,
    ProposalInvitation,
    StudentIdeaProposal,
    TeamInvitation,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def isolated_media_root(settings, tmp_path):
    """Keep uploaded test files isolated and collision-free."""
    settings.MEDIA_ROOT = tmp_path


def create_proposal(student, doctor, **overrides):
    data = {
        'student': student,
        'supervisor': doctor,
        'title': 'Smart Campus Platform',
        'description': 'A student-proposed graduation project.',
        'department': 'software_engineering',
        'team_size': 2,
        'project_type': 'graduation_1',
        'status': 'assigned',
        'operational_status': 'active',
    }
    data.update(overrides)
    return StudentIdeaProposal.objects.create(**data)


def create_idea(doctor, **overrides):
    data = {
        'doctor': doctor,
        'title': 'Distributed Systems Monitor',
        'description': 'A doctor-proposed graduation project.',
        'department': 'software_engineering',
        'max_team_size': 3,
        'project_type': 'graduation_1',
        'status': 'approved',
    }
    data.update(overrides)
    return ProjectIdea.objects.create(**data)


def create_application(student, doctor, **overrides):
    idea = overrides.pop('idea', None) or create_idea(doctor)
    data = {
        'idea': idea,
        'student': student,
        'team_size': 2,
        'project_type': 'graduation_1',
        'status': 'registered',
        'operational_status': 'active',
    }
    data.update(overrides)
    return IdeaApplication.objects.create(**data)


def create_board(student, doctor, *, source='proposal', **overrides):
    title = overrides.pop('title', 'Graduation Project Board')
    if source == 'proposal':
        proposal = overrides.pop('proposal', None) or create_proposal(student, doctor)
        return ProjectBoard.objects.create(proposal=proposal, title=title, **overrides)
    application = overrides.pop('application', None) or create_application(student, doctor)
    return ProjectBoard.objects.create(application=application, title=title, **overrides)


def create_task(board, creator, **overrides):
    data = {
        'board': board,
        'title': 'Implement authentication flow',
        'description': 'Add login, refresh, and logout behavior.',
        'created_by': creator,
    }
    data.update(overrides)
    return Task.objects.create(**data)


class TestProjectBoardModel:
    def test_defaults_string_and_proposal_reverse_relation(self, student, doctor):
        proposal = create_proposal(student, doctor)
        board = ProjectBoard.objects.create(proposal=proposal, title='Portal Board')

        assert board.application is None
        assert board.github_repo is None
        assert str(board) == 'Board: Portal Board'
        assert proposal.board == board
        assert board.created_at is not None

    def test_application_reverse_relation(self, student, doctor):
        application = create_application(student, doctor)
        board = ProjectBoard.objects.create(application=application, title='Doctor Idea Board')

        assert board.proposal is None
        assert application.board == board

    def test_proposal_can_have_only_one_board(self, student, doctor):
        proposal = create_proposal(student, doctor)
        ProjectBoard.objects.create(proposal=proposal, title='First Board')

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProjectBoard.objects.create(proposal=proposal, title='Second Board')

    def test_application_can_have_only_one_board(self, student, doctor):
        application = create_application(student, doctor)
        ProjectBoard.objects.create(application=application, title='First Board')

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ProjectBoard.objects.create(application=application, title='Second Board')

    @pytest.mark.parametrize('source', ['proposal', 'application'])
    def test_source_deletion_cascades_to_board(self, source, student, doctor):
        board = create_board(student, doctor, source=source)
        source_object = board.proposal or board.application
        board_id = board.id

        source_object.delete()

        assert not ProjectBoard.objects.filter(pk=board_id).exists()

    def test_members_fall_back_to_proposal_leader_and_accepted_invitees(
        self,
        student,
        doctor,
        user_factory,
    ):
        accepted_member = user_factory(role='student', department='software_engineering')
        pending_member = user_factory(role='student', department='software_engineering')
        proposal = create_proposal(student, doctor, team_size=3)
        ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=accepted_member,
            status='accepted',
        )
        ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=pending_member,
            status='pending',
        )
        board = ProjectBoard.objects.create(proposal=proposal, title='Proposal Board')

        member_ids = set(board.members.values_list('id', flat=True))

        assert member_ids == {student.id, accepted_member.id}
        assert board.members is board.members

    def test_members_fall_back_to_application_leader_and_accepted_invitees(
        self,
        student,
        doctor,
        user_factory,
    ):
        accepted_member = user_factory(role='student', department='software_engineering')
        rejected_member = user_factory(role='student', department='software_engineering')
        application = create_application(student, doctor, team_size=3)
        TeamInvitation.objects.create(
            application=application,
            invitee=accepted_member,
            status='accepted',
        )
        TeamInvitation.objects.create(
            application=application,
            invitee=rejected_member,
            status='rejected',
        )
        board = ProjectBoard.objects.create(application=application, title='Application Board')

        member_ids = set(board.members.values_list('id', flat=True))

        assert member_ids == {student.id, accepted_member.id}

    def test_members_use_participations_and_include_only_active_students(
        self,
        student,
        doctor,
        user_factory,
    ):
        active_member = user_factory(role='student', department='software_engineering')
        failed_member = user_factory(role='student', department='software_engineering')
        proposal = create_proposal(student, doctor, team_size=3)
        ProjectParticipation.objects.create(
            student=student,
            project_source='student_proposal',
            student_proposal=proposal,
            role='leader',
            status='active',
        )
        ProjectParticipation.objects.create(
            student=active_member,
            project_source='student_proposal',
            student_proposal=proposal,
            role='member',
            status='active',
        )
        ProjectParticipation.objects.create(
            student=failed_member,
            project_source='student_proposal',
            student_proposal=proposal,
            role='member',
            status='failed',
        )
        board = ProjectBoard.objects.create(proposal=proposal, title='Participation Board')

        member_ids = set(board.members.values_list('id', flat=True))

        assert member_ids == {student.id, active_member.id}

    def test_participants_with_status_returns_empty_for_source_less_board(self):
        board = ProjectBoard.objects.create(title='Unlinked Board')

        assert board.participants_with_status == []

    def test_participants_with_status_uses_active_fallback_members(
        self,
        student,
        doctor,
        user_factory,
    ):
        member = user_factory(
            role='student',
            department='software_engineering',
            first_name='Team',
            last_name='Member',
        )
        proposal = create_proposal(student, doctor)
        ProposalInvitation.objects.create(
            proposal=proposal,
            invitee=member,
            status='accepted',
        )
        board = ProjectBoard.objects.create(proposal=proposal, title='Fallback Board')

        participants = {item['username']: item for item in board.participants_with_status}

        assert set(participants) == {student.username, member.username}
        assert participants[member.username] == {
            'id': member.id,
            'username': member.username,
            'name': 'Team Member',
            'status': 'active',
            'is_active': True,
        }

    def test_participants_with_status_exposes_roles_and_inactive_designations(
        self,
        student,
        doctor,
        user_factory,
    ):
        withdrawn_member = user_factory(
            role='student',
            department='software_engineering',
            first_name='Former',
            last_name='Member',
        )
        proposal = create_proposal(student, doctor)
        changed_at = timezone.now()
        ProjectParticipation.objects.create(
            student=student,
            project_source='student_proposal',
            student_proposal=proposal,
            role='leader',
            status='active',
        )
        ProjectParticipation.objects.create(
            student=withdrawn_member,
            project_source='student_proposal',
            student_proposal=proposal,
            role='member',
            status='withdrawn',
            status_reason='Personal circumstances',
            status_changed_at=changed_at,
        )
        board = ProjectBoard.objects.create(proposal=proposal, title='Status Board')

        participants = {item['username']: item for item in board.participants_with_status}

        withdrawn = participants[withdrawn_member.username]
        assert withdrawn['name'] == 'Former Member'
        assert withdrawn['role'] == 'member'
        assert withdrawn['status'] == 'withdrawn'
        assert withdrawn['is_active'] is False
        assert withdrawn['designation_date'] == changed_at
        assert withdrawn['reason'] == 'Personal circumstances'


class TestTaskModel:
    def test_defaults_string_and_reverse_relations(self, student, doctor):
        board = create_board(student, doctor)
        task = create_task(board, student)

        assert task.status == 'todo'
        assert task.priority == 'medium'
        assert task.assignee is None
        assert task.due_date is None
        assert str(task) == 'Implement authentication flow [todo]'
        assert board.tasks.get() == task
        assert student.created_tasks.get() == task

    def test_task_persists_optional_assignment_priority_status_and_due_date(
        self,
        student,
        doctor,
        user_factory,
    ):
        assignee = user_factory(role='student', department='software_engineering')
        board = create_board(student, doctor)
        due_date = date.today() + timedelta(days=14)
        task = create_task(
            board,
            student,
            assignee=assignee,
            status='in_progress',
            priority='high',
            due_date=due_date,
        )

        assert task.assignee == assignee
        assert task.status == 'in_progress'
        assert task.priority == 'high'
        assert task.due_date == due_date
        assert assignee.assigned_tasks.get() == task

    def test_assignee_deletion_sets_assignee_to_null(self, student, doctor, user_factory):
        assignee = user_factory(role='student', department='software_engineering')
        task = create_task(create_board(student, doctor), student, assignee=assignee)

        assignee.delete()
        task.refresh_from_db()

        assert task.assignee is None

    def test_creator_deletion_sets_created_by_to_null(self, student, doctor, user_factory):
        creator = user_factory(role='student', department='software_engineering')
        task = create_task(create_board(student, doctor), creator)

        creator.delete()
        task.refresh_from_db()

        assert task.created_by is None

    def test_board_deletion_cascades_to_tasks(self, student, doctor):
        board = create_board(student, doctor)
        task = create_task(board, student)
        task_id = task.id

        board.delete()

        assert not Task.objects.filter(pk=task_id).exists()


class TestTaskCommentModel:
    def test_string_and_reverse_relations(self, student, doctor):
        task = create_task(create_board(student, doctor), student)
        comment = TaskComment.objects.create(task=task, author=student, body='Looks good.')

        assert str(comment) == f'Comment by {student} on {task}'
        assert task.comments.get() == comment
        assert student.task_comments.get() == comment

    def test_comments_are_ordered_oldest_first(self, student, doctor):
        task = create_task(create_board(student, doctor), student)
        first = TaskComment.objects.create(task=task, author=student, body='First')
        second = TaskComment.objects.create(task=task, author=student, body='Second')
        now = timezone.now()
        TaskComment.objects.filter(pk=first.pk).update(created_at=now - timedelta(minutes=1))
        TaskComment.objects.filter(pk=second.pk).update(created_at=now)

        assert list(task.comments.all()) == [first, second]

    def test_author_deletion_sets_author_to_null(self, student, doctor, user_factory):
        author = user_factory(role='student', department='software_engineering')
        task = create_task(create_board(student, doctor), student)
        comment = TaskComment.objects.create(task=task, author=author, body='Temporary author')

        author.delete()
        comment.refresh_from_db()

        assert comment.author is None
        assert str(comment) == f'Comment by None on {task}'

    def test_task_deletion_cascades_to_comments(self, student, doctor):
        task = create_task(create_board(student, doctor), student)
        comment = TaskComment.objects.create(task=task, author=student, body='Will be deleted')
        comment_id = comment.id

        task.delete()

        assert not TaskComment.objects.filter(pk=comment_id).exists()


class TestTaskAttachmentModel:
    def test_upload_path_removes_directories_and_normalizes_filename(self, student, doctor):
        task = create_task(create_board(student, doctor), student)
        attachment = TaskAttachment(task=task, uploaded_by=student)

        path = _attachment_upload_path(attachment, '../../reports/Final Report.PDF')

        assert path == (
            f'task_attachments/{task.board_id}/{task.id}/Final_Report.PDF'
        )
        assert '..' not in path

    def test_file_is_stored_in_task_specific_directory_with_original_content(
        self,
        student,
        doctor,
    ):
        task = create_task(create_board(student, doctor), student)
        upload = SimpleUploadedFile(
            'progress-report.txt',
            b'weekly progress',
            content_type='text/plain',
        )
        attachment = TaskAttachment.objects.create(
            task=task,
            uploaded_by=student,
            file=upload,
            filename='progress-report.txt',
            file_size=len(b'weekly progress'),
        )

        assert attachment.file.name.startswith(
            f'task_attachments/{task.board_id}/{task.id}/progress-report'
        )
        assert attachment.file.name.endswith('.txt')
        with attachment.file.open('rb') as stored_file:
            assert stored_file.read() == b'weekly progress'

    @pytest.mark.parametrize(
        ('filename', 'expected_extension'),
        [
            ('REPORT.PDF', 'pdf'),
            ('archive.tar.GZ', 'gz'),
            ('README', ''),
        ],
    )
    def test_extension_is_normalized(self, filename, expected_extension, student, doctor):
        task = create_task(create_board(student, doctor), student)
        attachment = TaskAttachment(
            task=task,
            uploaded_by=student,
            filename=filename,
        )

        assert attachment.extension == expected_extension

    def test_file_url_is_none_without_file_and_available_with_file(self, student, doctor):
        task = create_task(create_board(student, doctor), student)
        empty_attachment = TaskAttachment(
            task=task,
            uploaded_by=student,
            filename='missing.txt',
        )
        stored_attachment = TaskAttachment.objects.create(
            task=task,
            uploaded_by=student,
            file=SimpleUploadedFile('notes.txt', b'notes'),
            filename='notes.txt',
            file_size=5,
        )

        assert empty_attachment.file_url is None
        assert stored_attachment.file_url.endswith('.txt')
        assert '/media/' in stored_attachment.file_url

    def test_defaults_string_and_reverse_relations(self, student, doctor):
        task = create_task(create_board(student, doctor), student)
        attachment = TaskAttachment.objects.create(
            task=task,
            uploaded_by=student,
            file=SimpleUploadedFile('design.pdf', b'%PDF-test'),
            filename='design.pdf',
        )

        assert attachment.file_size == 0
        assert str(attachment) == f'design.pdf → {task}'
        assert task.attachments.get() == attachment
        assert student.task_attachments.get() == attachment

    def test_uploader_deletion_sets_uploaded_by_to_null(self, student, doctor, user_factory):
        uploader = user_factory(role='student', department='software_engineering')
        task = create_task(create_board(student, doctor), student)
        attachment = TaskAttachment.objects.create(
            task=task,
            uploaded_by=uploader,
            file=SimpleUploadedFile('notes.txt', b'notes'),
            filename='notes.txt',
            file_size=5,
        )

        uploader.delete()
        attachment.refresh_from_db()

        assert attachment.uploaded_by is None

    def test_task_deletion_cascades_to_attachments(self, student, doctor):
        task = create_task(create_board(student, doctor), student)
        attachment = TaskAttachment.objects.create(
            task=task,
            uploaded_by=student,
            file=SimpleUploadedFile('notes.txt', b'notes'),
            filename='notes.txt',
            file_size=5,
        )
        attachment_id = attachment.id

        task.delete()

        assert not TaskAttachment.objects.filter(pk=attachment_id).exists()


class TestActivityLogModel:
    def test_defaults_string_and_reverse_relations(self, student, doctor):
        board = create_board(student, doctor)
        task = create_task(board, student)
        log = ActivityLog.objects.create(
            board=board,
            task=task,
            actor=student,
            verb='created',
        )

        assert log.detail == ''
        assert str(log).startswith(f'{student} created [')
        assert board.activities.get() == log
        assert task.activities.get() == log
        assert student.project_activities.get() == log

    def test_activity_logs_are_ordered_newest_first(self, student, doctor):
        board = create_board(student, doctor)
        first = ActivityLog.objects.create(board=board, actor=student, verb='created')
        second = ActivityLog.objects.create(
            board=board,
            actor=student,
            verb='status_changed',
            detail='todo → in_progress',
        )
        now = timezone.now()
        ActivityLog.objects.filter(pk=first.pk).update(created_at=now - timedelta(minutes=1))
        ActivityLog.objects.filter(pk=second.pk).update(created_at=now)

        assert list(board.activities.all()) == [second, first]

    def test_task_deletion_preserves_activity_and_sets_task_to_null(self, student, doctor):
        board = create_board(student, doctor)
        task = create_task(board, student)
        log = ActivityLog.objects.create(
            board=board,
            task=task,
            actor=student,
            verb='deleted',
            detail=task.title,
        )

        task.delete()
        log.refresh_from_db()

        assert log.task is None
        assert log.detail == 'Implement authentication flow'

    def test_actor_deletion_preserves_activity_and_sets_actor_to_null(
        self,
        student,
        doctor,
        user_factory,
    ):
        actor = user_factory(role='student', department='software_engineering')
        board = create_board(student, doctor)
        log = ActivityLog.objects.create(board=board, actor=actor, verb='created')

        actor.delete()
        log.refresh_from_db()

        assert log.actor is None
        assert str(log).startswith('None created [')

    def test_board_deletion_cascades_to_activity_logs(self, student, doctor):
        board = create_board(student, doctor)
        log = ActivityLog.objects.create(board=board, actor=student, verb='created')
        log_id = log.id

        board.delete()

        assert not ActivityLog.objects.filter(pk=log_id).exists()
