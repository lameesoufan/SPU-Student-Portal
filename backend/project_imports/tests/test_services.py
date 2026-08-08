import hashlib
import zipfile
from io import BytesIO
from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import Workbook

from project_imports.constants import (
    FIELD_HEADERS,
    REQUIRED_HEADERS,
    normalize_department,
    normalize_header_name,
    normalize_project_type,
    resolve_header_field,
)
from project_imports.models import ImportRow, ImportSession
from project_imports.name_utils import (
    parse_person_name,
    split_supervisor_names,
    strip_person_titles,
    supervisor_identity_key,
    username_base_from_name,
)
from project_imports.services import ImportService, ProjectCreator, UserMapper
from project_imports.validators import (
    FileValidator,
    ImportValidationError,
    ParsedWorkbook,
    RowValidator,
    ValidationIssue,
    group_issues,
    normalize_cell_value,
)
from project_management.models import ProjectBoard
from projects.models import (
    ProjectApplication,
    ProjectParticipation,
    ProposalInvitation,
    StudentIdeaProposal,
)


pytestmark = pytest.mark.django_db


def valid_row(number=2, **overrides):
    row = {
        'row_number': number,
        'project_row_number': number,
        'is_project_leader': True,
        'student_name': 'Student Example',
        'university_id': f'2026{number:04d}',
        'email': f'student{number}@example.com',
        'title': f'Project {number}',
        'department': 'software_engineering',
        'supervisor_name': 'Doctor Example',
        'project_type': 'seasonal',
        'github_repo': 'https://github.com/example/project',
    }
    row.update(overrides)
    return row


def workbook_upload(rows, *, headers=None, filename='projects.xlsx'):
    workbook = Workbook()
    sheet = workbook.active
    headers = headers or REQUIRED_HEADERS
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return SimpleUploadedFile(
        filename,
        stream.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )


def mapped_workbook_rows(*rows):
    ordered_fields = list(FIELD_HEADERS.keys())
    values = []
    for row in rows:
        values.append([row.get(field, '') for field in ordered_fields])
    return workbook_upload(values, headers=[FIELD_HEADERS[field] for field in ordered_fields])


class TestNormalizationUtilities:
    def test_header_normalization_removes_bom_diacritics_and_separators(self):
        assert normalize_header_name('\ufeff  إِسم_الطالب  ') == 'اسم الطالب'

    def test_resolve_header_supports_arabic_alias(self):
        assert resolve_header_field('البريد الالكتروني') == 'email'

    def test_resolve_header_supports_english_alias(self):
        assert resolve_header_field('Student Full Name') == 'student_name'

    def test_resolve_header_can_find_known_header_inside_label(self):
        assert resolve_header_field('Required field: project title') == 'title'

    def test_unknown_header_returns_none(self):
        assert resolve_header_field('completely unrelated column') is None

    def test_department_aliases_are_normalized(self):
        assert normalize_department('هندسة البرمجيات') == 'software_engineering'
        assert normalize_department('Cyber Security') == 'information_security'

    def test_unknown_department_is_preserved_for_validation(self):
        assert normalize_department('Unknown Department') == 'Unknown Department'

    def test_project_type_aliases_are_normalized(self):
        assert normalize_project_type('تخرج 1') == 'graduation_1'
        assert normalize_project_type('Graduation II') == 'graduation_2'
        assert normalize_project_type('مشروع فصلي') == 'seasonal'

    def test_person_titles_are_removed_without_corrupting_name(self):
        assert strip_person_titles('أ.د. أحمد خالد') == 'أحمد خالد'

    def test_supervisor_cell_splits_multiple_names_and_deduplicates(self):
        names = split_supervisor_names('د. أحمد خالد\nد. احمد خالد; د. سارة علي')
        assert names == ['د. أحمد خالد', 'د. سارة علي']

    def test_supervisor_identity_normalizes_arabic_variants(self):
        assert supervisor_identity_key('د. أحمد خالد') == supervisor_identity_key('احمد خالد')

    def test_parse_person_name_returns_first_and_remaining_names(self):
        assert parse_person_name('د. أحمد خالد حسن') == ('أحمد', 'خالد حسن')

    def test_username_base_from_arabic_name_is_non_empty_and_safe(self):
        username = username_base_from_name('د. أحمد خالد')
        assert username
        assert ' ' not in username
        assert len(username) <= 120

    def test_normalize_cell_value_handles_none_integer_float_and_whitespace(self):
        assert normalize_cell_value(None) == ''
        assert normalize_cell_value(123.0) == '123'
        assert normalize_cell_value('  value  ') == 'value'

    def test_validation_issue_escapes_message_before_exposure(self):
        issue = ValidationIssue(2, 'title', '<script>alert(1)</script>')
        data = issue.to_dict()
        assert '<script>' not in data['error_message']
        assert '&lt;script&gt;' in data['error_message']

    def test_group_issues_uses_error_type_as_bucket(self):
        grouped = group_issues([
            ValidationIssue(2, 'email', 'bad email', error_type='invalid_value'),
            ValidationIssue(3, 'email', 'duplicate', error_type='duplicate'),
        ])
        assert set(grouped) == {'invalid_value', 'duplicate'}


class TestFileValidator:
    def test_rejects_legacy_xls(self):
        upload = SimpleUploadedFile('legacy.xls', b'legacy')
        with pytest.raises(ImportValidationError, match='Legacy .xls'):
            FileValidator().validate_file(upload)

    def test_rejects_non_xlsx_extension(self):
        upload = SimpleUploadedFile('projects.csv', b'a,b')
        with pytest.raises(ImportValidationError, match='Expected .xlsx'):
            FileValidator().validate_file(upload)

    def test_rejects_file_larger_than_limit_without_reading_content(self):
        upload = SimpleNamespace(name='projects.xlsx', size=(10 * 1024 * 1024) + 1)
        upload.read = lambda: (_ for _ in ()).throw(AssertionError('must not read oversized file'))
        with pytest.raises(ImportValidationError) as exc:
            FileValidator().validate_file(upload)
        assert exc.value.status_code == 413

    def test_rejects_macro_enabled_content_even_with_xlsx_name(self):
        stream = BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('xl/vbaProject.bin', b'macro')
        upload = SimpleUploadedFile('projects.xlsx', stream.getvalue())

        with pytest.raises(ImportValidationError, match='macros'):
            FileValidator().validate_file(upload)

    def test_valid_file_is_rewound_after_validation(self):
        upload = mapped_workbook_rows(valid_row())
        content = FileValidator().validate_file(upload)
        assert content.startswith(b'PK')
        assert upload.tell() == 0

    def test_parse_workbook_maps_required_fields_and_hash(self):
        source = valid_row(2, email='USER@EXAMPLE.COM')
        upload = mapped_workbook_rows(source)
        raw = upload.read()
        upload.seek(0)

        parsed = FileValidator().parse_workbook(upload)

        assert parsed.filename == 'projects.xlsx'
        assert parsed.file_hash == hashlib.sha256(raw).hexdigest()
        assert parsed.rows[0]['university_id'] == source['university_id']
        assert parsed.rows[0]['email'] == 'user@example.com'
        assert parsed.rows[0]['is_project_leader'] is True

    def test_parse_workbook_inherits_project_values_for_following_team_member(self):
        leader = valid_row(2)
        member = valid_row(
            3,
            student_name='Second Student',
            university_id='20260003',
            email='second@example.com',
            title='',
            department='',
            supervisor_name='',
            project_type='',
            github_repo='',
        )
        upload = mapped_workbook_rows(leader, member)

        parsed = FileValidator().parse_workbook(upload)

        assert len(parsed.rows) == 2
        assert parsed.rows[1]['project_row_number'] == parsed.rows[0]['row_number']
        assert parsed.rows[1]['title'] == leader['title']
        assert parsed.rows[1]['supervisor_name'] == leader['supervisor_name']
        assert parsed.rows[1]['is_project_leader'] is False

    def test_parse_workbook_skips_repeated_header_rows(self):
        leader = valid_row(2)
        values = [[leader.get(field, '') for field in FIELD_HEADERS]]
        values.append([FIELD_HEADERS[field] for field in FIELD_HEADERS])
        upload = workbook_upload(values, headers=[FIELD_HEADERS[field] for field in FIELD_HEADERS])

        parsed = FileValidator().parse_workbook(upload)
        assert len(parsed.rows) == 1

    def test_parse_workbook_rejects_formula_in_imported_field(self):
        row = valid_row(2)
        row['title'] = '=1+1'
        upload = mapped_workbook_rows(row)
        with pytest.raises(ImportValidationError, match='Formula cells are not allowed'):
            FileValidator().parse_workbook(upload)

    def test_parse_workbook_reports_missing_required_headers(self):
        upload = workbook_upload([['Student', '20260001']], headers=['Student Name', 'University ID'])
        with pytest.raises(ImportValidationError) as exc:
            FileValidator().parse_workbook(upload)
        assert exc.value.details
        assert 'missing_headers' in exc.value.details[0]

    def test_parse_workbook_rejects_empty_workbook(self):
        upload = workbook_upload([], headers=REQUIRED_HEADERS)
        with pytest.raises(ImportValidationError, match='no data rows'):
            FileValidator().parse_workbook(upload)

    def test_parse_workbook_rejects_corrupted_xlsx(self):
        upload = SimpleUploadedFile('projects.xlsx', b'not a zip workbook')
        with pytest.raises(ImportValidationError, match='corrupted'):
            FileValidator().parse_workbook(upload)


class TestRowValidator:
    def test_valid_row_normalizes_email_department_project_type_and_repo(self):
        row = valid_row(
            email=' USER@Example.COM ',
            department='هندسة البرمجيات',
            project_type='تخرج 1',
            github_repo='github.com/example/repo',
        )
        issues = RowValidator().validate_row(row)

        assert issues == []
        assert row['email'] == 'user@example.com'
        assert row['department'] == 'software_engineering'
        assert row['project_type'] == 'graduation_1'
        assert row['github_repo'] == 'https://github.com/example/repo'

    def test_placeholder_repository_value_becomes_empty(self):
        row = valid_row(github_repo='لا يوجد')
        assert RowValidator().validate_row(row) == []
        assert row['github_repo'] == ''

    def test_invalid_email_is_rejected(self):
        issues = RowValidator().validate_row(valid_row(email='not-an-email'))
        assert any(issue.field_name == 'email' and issue.error_type == 'invalid_value' for issue in issues)

    def test_invalid_department_and_project_type_are_rejected(self):
        issues = RowValidator().validate_row(valid_row(department='unknown', project_type='unknown'))
        assert {issue.field_name for issue in issues} >= {'department', 'project_type'}

    def test_repository_must_be_github_or_gitlab_http_url(self):
        issues = RowValidator().validate_row(valid_row(github_repo='https://example.com/repo'))
        assert any(issue.field_name == 'github_repo' for issue in issues)

    def test_missing_supervisor_is_rejected(self):
        issues = RowValidator().validate_row(valid_row(supervisor_name=''))
        assert any(issue.field_name == 'supervisor_name' for issue in issues)

    def test_duplicate_university_id_and_email_in_file_are_errors(self):
        first = valid_row(2, university_id='20260001', email='same@example.com')
        second = valid_row(3, university_id='20260001', email='same@example.com')
        issues = RowValidator().check_duplicates_in_file([first, second])
        duplicates = [issue for issue in issues if issue.error_type == 'duplicate']
        assert len([issue for issue in duplicates if issue.field_name == 'university_id']) == 2
        assert len([issue for issue in duplicates if issue.field_name == 'email']) == 2

    def test_duplicate_project_title_across_projects_is_warning_only(self):
        first = valid_row(2, title='Same title')
        second = valid_row(3, title='Same title')
        issues = RowValidator().check_duplicates_in_file([first, second])
        title_issues = [issue for issue in issues if issue.field_name == 'title']
        assert len(title_issues) == 2
        assert all(issue.level == 'warning' for issue in title_issues)

    def test_existing_non_student_username_is_rejected(self, doctor):
        row = valid_row(university_id=doctor.username, email=doctor.email)
        issues = RowValidator().check_duplicates_in_db([row])
        assert any(issue.field_name == 'university_id' for issue in issues)

    def test_existing_student_with_different_email_is_rejected(self, student):
        row = valid_row(university_id=student.username, email='different@example.com')
        issues = RowValidator().check_duplicates_in_db([row])
        assert any(issue.error_type == 'email_mismatch' for issue in issues)

    def test_email_owned_by_another_account_is_rejected(self, user_factory):
        owner = user_factory(role='student', username='existing', email='owned@example.com')
        row = valid_row(university_id='new-student', email=owner.email)
        issues = RowValidator().check_duplicates_in_db([row])
        assert any(issue.field_name == 'email' and issue.error_type == 'duplicate' for issue in issues)

    def test_existing_same_title_for_student_is_rejected(self, student, doctor):
        StudentIdeaProposal.objects.create(
            student=student,
            supervisor=doctor,
            title='Existing title',
            description='Existing',
            department='software_engineering',
            team_size=1,
            team_size_reason='Solo',
            project_type='seasonal',
            status='rejected',
        )
        row = valid_row(university_id=student.username, email=student.email, title='existing TITLE')
        issues = RowValidator().check_duplicates_in_db([row])
        assert any(issue.field_name == 'title' and issue.error_type == 'duplicate' for issue in issues)

    def test_assigned_project_blocks_student_import(self, student, doctor):
        StudentIdeaProposal.objects.create(
            student=student,
            supervisor=doctor,
            title='Assigned',
            description='Assigned',
            department='software_engineering',
            team_size=1,
            team_size_reason='Solo',
            project_type='seasonal',
            status='assigned',
        )
        row = valid_row(university_id=student.username, email=student.email)
        issues = RowValidator().check_active_project_conflicts([row])
        assert any(issue.error_type == 'active_project' for issue in issues)


class TestUserMapper:
    def test_generate_password_uses_identifier_and_configured_pattern_with_random_suffix(self, settings):
        settings.IMPORT_TEMP_PASSWORD_FORMAT = 'TEMP-{identifier}-2026!'
        first = UserMapper().generate_password('20260001')
        second = UserMapper().generate_password('20260001')

        assert first.startswith('TEMP-20260001-2026!-')
        assert second.startswith('TEMP-20260001-2026!-')
        assert first != second

    def test_find_supervisor_matches_arabic_name_variants(self, user_factory):
        doctor = user_factory(role='doctor', first_name='أحمد', last_name='خالد')
        mapper = UserMapper()
        assert mapper.find_supervisor_by_name('د. احمد خالد') == [doctor]

    def test_normalize_username_is_stable_for_same_identity(self):
        mapper = UserMapper()
        first = mapper.normalize_username('د. أحمد خالد')
        second = mapper.normalize_username('احمد خالد')
        assert first == second

    def test_normalize_username_avoids_existing_username(self, user_factory):
        existing_mapper = UserMapper()
        base = existing_mapper.normalize_username('Doctor Example')
        user_factory(role='doctor', username=base)
        mapper = UserMapper()
        generated = mapper.normalize_username('Doctor Example')
        assert generated != base

    def test_build_plan_lists_new_students_and_supervisors(self):
        mapper = UserMapper()
        plan = mapper.build_plan([valid_row(supervisor_name='New Doctor Name')])
        assert plan['students_to_create'] == ['20260002']
        assert len(plan['supervisors_to_create']) == 1
        assert plan['supervisors_to_create'][0]['full_name'] == 'New Doctor Name'

    def test_build_plan_warns_when_cell_contains_multiple_supervisors(self):
        mapper = UserMapper()
        plan = mapper.build_plan([valid_row(supervisor_name='د. أحمد خالد; د. سارة علي')])
        assert any(issue.error_type == 'supervisor_multiple' and issue.level == 'warning' for issue in plan['issues'])

    def test_resolve_users_creates_hashed_student_and_supervisor_accounts(self, settings):
        settings.IMPORT_TEMP_PASSWORD_FORMAT = 'Strong-{identifier}-Pass!'
        row = valid_row(student_name='Ali Student', supervisor_name='Sara Doctor')
        mapper = UserMapper()
        result = mapper.resolve_users([row])

        student = result['students'][row['university_id']]
        supervisor = result['supervisors'][row['row_number']]
        assert student.role == 'student'
        assert student.must_change_password is True
        assert student.check_password(result['credentials'][student.id]['password'])
        assert supervisor.role == 'doctor'
        assert supervisor.must_change_password is True
        assert supervisor.must_change_username is True
        assert supervisor.check_password(result['credentials'][supervisor.id]['password'])

    def test_resolve_users_reuses_existing_student_and_fills_missing_email(self, user_factory):
        student = user_factory(role='student', username='20260002', email='')
        mapper = UserMapper()
        row = valid_row(university_id='20260002', email='filled@example.com')
        result = mapper.resolve_users([row])
        student.refresh_from_db()

        assert result['students']['20260002'].pk == student.pk
        assert student.email == 'filled@example.com'
        assert result['created_students'] == []


class TestProjectCreatorAndImportService:
    def test_group_project_rows_and_leader_selection(self):
        leader = valid_row(2)
        member = valid_row(3, project_row_number=2, is_project_leader=False)
        other = valid_row(4)
        creator = ProjectCreator()

        groups = creator._group_project_rows([member, other, leader])
        assert [len(group) for group in groups] == [2, 1]
        assert creator._leader_row(groups[0])['row_number'] == 2

    def test_create_projects_builds_proposal_application_board_invitation_and_participations(self, dean, user_factory):
        leader = user_factory(role='student', username='20260002')
        member = user_factory(role='student', username='20260003')
        doctor = user_factory(role='doctor', username='supervisor')
        leader_row = valid_row(2, university_id=leader.username)
        member_row = valid_row(
            3,
            project_row_number=2,
            is_project_leader=False,
            university_id=member.username,
            email=member.email,
            title=leader_row['title'],
        )
        user_map = {
            'students': {leader.username: leader, member.username: member},
            'supervisors': {2: doctor},
            'co_supervisors_map': {},
            'supervisors_by_row': {},
        }

        created = ProjectCreator().create_projects([leader_row, member_row], user_map, dean)
        proposal = created[0]['proposal']

        assert proposal.student == leader
        assert proposal.supervisor == doctor
        assert proposal.team_size == 2
        assert proposal.status == 'assigned'
        assert ProposalInvitation.objects.filter(proposal=proposal, invitee=member, status='accepted').exists()
        assert ProjectApplication.objects.filter(proposal=proposal, student=leader, status='accepted').exists()
        assert ProjectBoard.objects.filter(proposal=proposal, github_repo=leader_row['github_repo']).exists()
        assert ProjectParticipation.objects.filter(student_proposal=proposal, student=leader, status='active').exists()
        assert ProjectParticipation.objects.filter(student_proposal=proposal, student=member, status='active').exists()

    def test_error_csv_contains_safe_structured_columns(self, dean):
        service = ImportService(dean)
        csv_text = service.generate_error_csv([
            ValidationIssue(2, 'email', 'Invalid email', error_type='invalid_value')
        ])
        assert 'row_number,field_name,level,error_type,error_message' in csv_text
        assert '2,email,error,invalid_value,Invalid email' in csv_text

    def test_preview_cache_is_bound_to_user_and_file_hash(self, dean, user_factory):
        service = ImportService(dean)
        preview_id = service._cache_preview('abc123', 3)
        service._validate_preview('abc123', preview_id)

        other_dean = user_factory(role='dean', username='other-dean')
        with pytest.raises(ImportValidationError, match='expired'):
            ImportService(other_dean)._validate_preview('abc123', preview_id)

    def test_preview_rejects_different_file_hash(self, dean):
        service = ImportService(dean)
        preview_id = service._cache_preview('first-hash', 1)
        with pytest.raises(ImportValidationError, match='does not match'):
            service._validate_preview('second-hash', preview_id)

    def test_remove_error_rows_removes_only_error_level_rows(self, dean):
        rows = [valid_row(2), valid_row(3), valid_row(4)]
        issues = [
            ValidationIssue(2, 'email', 'error', level='error'),
            ValidationIssue(3, 'title', 'warning', level='warning'),
        ]
        remaining = ImportService(dean)._remove_error_rows(rows, issues)
        assert [row['row_number'] for row in remaining] == [3, 4]

    def test_mark_failed_creates_row_audit_and_finalizes_session(self, dean):
        service = ImportService(dean)
        session = ImportSession.objects.create(
            super_admin=dean,
            filename='projects.xlsx',
            file_size_bytes=1,
            total_rows=2,
        )
        rows = [valid_row(2), valid_row(3)]
        issues = [ValidationIssue(2, 'email', 'bad email')]

        service._mark_failed(session, rows, issues)
        session.refresh_from_db()

        assert session.status == 'failed'
        assert session.failed_rows == 1
        assert session.successful_rows == 0
        assert session.completed_at is not None
        assert list(session.rows.values_list('status', flat=True)) == ['failed', 'skipped']

    def test_dry_run_returns_preview_without_creating_session_or_users(self, dean):
        row = valid_row(2, supervisor_name='Preview Doctor')
        upload = mapped_workbook_rows(row)
        before_sessions = ImportSession.objects.count()

        result = ImportService(dean).execute_import(upload, dry_run=True)

        assert result['dry_run'] is True
        assert result['status'] == 'preview'
        assert result['preview_result_id']
        assert result['projects_to_create'] == 1
        assert result['import_session_id'] is None
        assert ImportSession.objects.count() == before_sessions

    def test_build_result_marks_partial_preview_when_some_rows_invalid(self, dean):
        service = ImportService(dean)
        parsed = ParsedWorkbook('projects.xlsx', 1, 'hash', [valid_row(2), valid_row(3)])
        issues = [ValidationIssue(3, 'email', 'bad email')]
        plan = {'students_to_create': [], 'supervisors_to_create': []}

        result = service._build_result(
            parsed=parsed,
            session=None,
            issues=issues,
            dry_run=True,
            execution_time=0.1,
            plan=plan,
            created=None,
        )

        assert result['status'] == 'partial_preview'
        assert result['partial_import'] is True
        assert result['valid_rows_count'] == 1
        assert result['invalid_rows_count'] == 1

    def test_project_count_groups_team_rows_as_one_project(self, dean):
        rows = [
            valid_row(2),
            valid_row(3, project_row_number=2, is_project_leader=False),
            valid_row(4),
        ]
        assert ImportService(dean)._project_count(rows) == 2

    def test_cached_preview_can_expire_cleanly(self, dean):
        service = ImportService(dean)
        preview_id = service._cache_preview('hash', 1)
        cache.delete(service._preview_key(preview_id))
        with pytest.raises(ImportValidationError, match='expired'):
            service._validate_preview('hash', preview_id)
