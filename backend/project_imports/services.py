import csv
import logging
import os
import time
import uuid
from collections import defaultdict
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from project_management.models import ProjectBoard
from projects.models import ProjectApplication, ProposalInvitation, StudentIdeaProposal

from .constants import DEFAULT_TEMP_PASSWORD_FORMAT
from .models import ImportRow, ImportSession
from .name_utils import (
    normalize_person_spacing,
    parse_person_name,
    split_supervisor_names,
    strip_person_titles,
    supervisor_identity_key,
    username_base_from_name,
)
from .validators import FileValidator, ImportValidationError, RowValidator, ValidationIssue, group_issues


logger = logging.getLogger('project_imports')
User = get_user_model()


class UserMapper:
    def parse_student_name(self, name):
        parts = str(name or '').strip().split(None, 1)
        if not parts:
            return '', ''
        return parts[0], parts[1] if len(parts) > 1 else ''

    def parse_supervisor_name(self, name):
        return parse_person_name(name)

    def generate_password(self, identifier):
        fmt = getattr(settings, 'IMPORT_TEMP_PASSWORD_FORMAT', None) or os.getenv(
            'IMPORT_TEMP_PASSWORD_FORMAT',
            DEFAULT_TEMP_PASSWORD_FORMAT,
        )
        password = fmt.format(identifier=identifier)
        try:
            validate_password(password)
        except DjangoValidationError:
            password = f'{password}Aa1!'
            validate_password(password)
        return password

    def build_plan(self, rows):
        issues = []
        student_ids = {row['university_id'] for row in rows if row.get('university_id')}
        existing_students = {
            user.username: user
            for user in User.objects.filter(username__in=student_ids)
        }

        students_to_create = [
            row['university_id']
            for row in rows
            if row.get('university_id') and row['university_id'] not in existing_students
        ]

        supervisor_map = {}
        supervisors_by_row = {}
        supervisors_to_create = {}
        supervisors_to_reuse = {}
        reserved_usernames = set(User.objects.values_list('username', flat=True))
        planned_supervisors_by_key = {}
        for row in rows:
            row_supervisors = []
            for name in self.supervisor_names_for_row(row):
                existing = self.find_supervisor_by_name(name)
                if len(existing) > 1:
                    issues.append(ValidationIssue(
                        row_number=row['row_number'],
                        field_name='supervisor_name',
                        error_message=(
                            f"Row {row['row_number']}: Supervisor name '{name}' matches multiple doctors. "
                            'Use exact username or create the supervisor manually first.'
                        ),
                        row_data=row,
                        error_type='supervisor_match',
                    ))
                    continue
                if len(existing) == 1:
                    supervisor = existing[0]
                    row_supervisors.append(supervisor)
                    supervisors_to_reuse[supervisor.username] = {
                        'username': supervisor.username,
                        'full_name': supervisor.get_full_name() or strip_person_titles(name),
                        'department': supervisor.department or row.get('department', ''),
                        'source_row_number': row['row_number'],
                        'project_title': row.get('title', ''),
                    }
                    continue

                key = supervisor_identity_key(name)
                username = planned_supervisors_by_key.get(key)
                if not username:
                    username = self.normalize_username(name, reserved_usernames=reserved_usernames)
                    planned_supervisors_by_key[key] = username
                    reserved_usernames.add(username)
                    supervisors_to_create[username] = {
                        'username': username,
                        'full_name': strip_person_titles(name),
                        'department': row.get('department', ''),
                        'source_row_number': row['row_number'],
                        'project_title': row.get('title', ''),
                    }
                row_supervisors.append(username)

            if row_supervisors:
                supervisor_map[row['row_number']] = row_supervisors[0]
                supervisors_by_row[row['row_number']] = row_supervisors

        return {
            'issues': issues,
            'students_to_create': sorted(set(students_to_create)),
            'supervisors_to_create': list(supervisors_to_create.values()),
            'supervisors_to_reuse': list(supervisors_to_reuse.values()),
            'supervisor_map': supervisor_map,
            'supervisors_by_row': supervisors_by_row,
        }

    def resolve_users(self, rows):
        student_ids = {row['university_id'] for row in rows}
        students = {
            user.username: user
            for user in User.objects.select_for_update().filter(username__in=student_ids)
        }
        created_students = []

        for row in rows:
            university_id = row['university_id']
            if university_id in students:
                continue
            first_name, last_name = self.parse_student_name(row.get('student_name', ''))
            student = User.objects.create_user(
                username=university_id,
                password=self.generate_password(university_id),
                first_name=first_name,
                last_name=last_name,
                role='student',
                department=row.get('department') or None,
                must_change_password=True,
                is_active=True,
            )
            students[university_id] = student
            created_students.append(student)

        supervisors = {}
        supervisors_by_row = {}
        created_supervisors = []
        supervisor_credentials = []
        credential_usernames = set()
        supervisors_by_key = {}

        for row in rows:
            row_supervisors = []
            for name in self.supervisor_names_for_row(row):
                existing = self.find_supervisor_by_name(name, lock=True)
                if len(existing) > 1:
                    raise ImportValidationError(
                        f"Row {row['row_number']}: Supervisor name '{name}' became ambiguous. Please preview again."
                    )
                if existing:
                    supervisor = existing[0]
                    self._record_supervisor_credential(
                        supervisor_credentials,
                        credential_usernames,
                        row=row,
                        supervisor=supervisor,
                        full_name=supervisor.get_full_name() or strip_person_titles(name),
                        status='reused_existing_no_password_exported',
                        generated_password='',
                    )
                    row_supervisors.append(supervisor)
                    continue

                key = supervisor_identity_key(name)
                supervisor = supervisors_by_key.get(key)
                if supervisor is None:
                    username = self.normalize_username(name)
                    first_name, last_name = self.parse_supervisor_name(name)
                    generated_password = self.generate_password(username)
                    supervisor = User.objects.create_user(
                        username=username,
                        password=generated_password,
                        first_name=first_name,
                        last_name=last_name,
                        role='doctor',
                        department=row.get('department') or None,
                        must_change_password=True,
                        is_active=True,
                    )
                    supervisors_by_key[key] = supervisor
                    created_supervisors.append(supervisor)
                    self._record_supervisor_credential(
                        supervisor_credentials,
                        credential_usernames,
                        row=row,
                        supervisor=supervisor,
                        full_name=supervisor.get_full_name() or strip_person_titles(name),
                        status='created',
                        generated_password=generated_password,
                    )
                row_supervisors.append(supervisor)

            if row_supervisors:
                supervisors[row['row_number']] = row_supervisors[0]
                supervisors_by_row[row['row_number']] = row_supervisors

        return {
            'students': students,
            'supervisors': supervisors,
            'supervisors_by_row': supervisors_by_row,
            'created_students': created_students,
            'created_supervisors': created_supervisors,
            'supervisor_credentials': supervisor_credentials,
        }

    def find_supervisor_by_name(self, name, *, lock=False):
        raw_needle = normalize_person_spacing(name).casefold()
        clean_needle = strip_person_titles(name)
        if not clean_needle:
            return []
        qs = User.objects.filter(role='doctor')
        if lock:
            qs = qs.select_for_update()
        users = list(qs)
        username_candidate = username_base_from_name(clean_needle)
        username_needles = {raw_needle}
        if username_candidate:
            username_needles.add(username_candidate.casefold())

        username_matches = [
            user for user in users
            if user.username.casefold() in username_needles
        ]
        if username_matches:
            return username_matches

        name_key = supervisor_identity_key(clean_needle)
        full_name_matches = []
        transliterated_matches = []
        for user in users:
            full_name = (user.get_full_name() or '').strip()
            if full_name and supervisor_identity_key(full_name) == name_key:
                full_name_matches.append(user)
            elif full_name and username_base_from_name(full_name) == username_candidate:
                transliterated_matches.append(user)
        return full_name_matches or transliterated_matches

    def normalize_username(self, name, *, reserved_usernames=None):
        base = username_base_from_name(name)
        if not base:
            base = f'doctor_{uuid.uuid5(uuid.NAMESPACE_DNS, str(name)).hex[:10]}'
        username = base[:120]
        candidate = username
        suffix = 1
        reserved = reserved_usernames or set()
        while candidate in reserved or User.objects.filter(username=candidate).exists():
            suffix += 1
            candidate = f'{username[:110]}_{suffix}'
        return candidate

    def supervisor_names_for_row(self, row):
        return row.get('supervisor_names') or split_supervisor_names(row.get('supervisor_name', ''))

    def _record_supervisor_credential(
        self,
        records,
        seen_usernames,
        *,
        row,
        supervisor,
        full_name,
        status,
        generated_password,
    ):
        if supervisor.username in seen_usernames:
            return
        seen_usernames.add(supervisor.username)
        records.append({
            'full_name': full_name,
            'username': supervisor.username,
            # Only newly generated passwords are exportable. Existing passwords
            # are salted hashes in Django and must never be reconstructed.
            'generated_password': generated_password,
            'department': supervisor.department or row.get('department', ''),
            'source_row_number': row.get('row_number'),
            'project_title': row.get('title', ''),
            'created_or_reused': status,
            'created_at': timezone.localtime(timezone.now()).isoformat(),
            'notes': (
                'Password generated during this import. Store securely.'
                if generated_password
                else 'Existing supervisor reused; password is not stored in plaintext and cannot be exported.'
            ),
        })


class ProjectCreator:
    def create_projects(self, rows, user_map, super_admin):
        created = []
        now = timezone.localtime(timezone.now()).strftime('%Y-%m-%d')
        for group_rows in self._group_project_rows(rows):
            row = self._leader_row(group_rows)
            members = [member_row for member_row in group_rows if member_row is not row]
            student = user_map['students'][row['university_id']]
            supervisors = self._supervisors_for_row(user_map, row)
            supervisor = supervisors[0]
            proposal = StudentIdeaProposal.objects.create(
                student=student,
                supervisor=supervisor,
                title=row['title'],
                description=f'Imported by {super_admin.username} on {now}',
                department=row['department'],
                team_size=len(group_rows),
                team_size_reason='Bulk import by super admin',
                project_type=row['project_type'],
                status='assigned',
            )
            if len(supervisors) > 1:
                proposal.co_supervisors.set(supervisors[1:])
            for member_row in members:
                ProposalInvitation.objects.create(
                    proposal=proposal,
                    invitee=user_map['students'][member_row['university_id']],
                    status='accepted',
                )
            application = ProjectApplication.objects.create(
                proposal=proposal,
                student=student,
                status='accepted',
            )
            board = ProjectBoard.objects.create(
                proposal=proposal,
                application=None,
                title=row['title'],
                github_repo=row.get('github_repo') or None,
            )
            created.append({'proposal': proposal, 'application': application, 'board': board, 'rows': group_rows})
        return created

    def _supervisors_for_row(self, user_map, row):
        supervisors = user_map.get('supervisors_by_row', {}).get(row['row_number'])
        if supervisors:
            return supervisors
        supervisor = user_map['supervisors'][row['row_number']]
        return supervisor if isinstance(supervisor, list) else [supervisor]

    def _group_project_rows(self, rows):
        grouped = defaultdict(list)
        for row in rows:
            grouped[row.get('project_row_number') or row['row_number']].append(row)
        return [grouped[key] for key in sorted(grouped.keys())]

    def _leader_row(self, rows):
        for row in rows:
            if row.get('is_project_leader'):
                return row
        return rows[0]


class ImportService:
    def __init__(self, super_admin):
        self.super_admin = super_admin
        self.file_validator = FileValidator()
        self.row_validator = RowValidator()
        self.user_mapper = UserMapper()
        self.project_creator = ProjectCreator()

    def execute_import(self, upload, *, dry_run=False, preview_result_id=None):
        started = time.perf_counter()
        parsed = self.file_validator.parse_workbook(upload)
        session = None

        if not dry_run:
            session = ImportSession.objects.create(
                super_admin=self.super_admin,
                filename=parsed.filename,
                file_size_bytes=parsed.file_size_bytes,
                total_rows=len(parsed.rows),
                status=ImportSession.STATUS_PENDING,
            )

        valid_rows, issues = self.row_validator.validate_rows(parsed.rows)
        plan = self.user_mapper.build_plan(valid_rows)
        issues.extend(plan['issues'])
        valid_rows = self._remove_error_rows(valid_rows, issues)
        if plan['issues']:
            plan = self.user_mapper.build_plan(valid_rows)
        errors = [issue for issue in issues if issue.level == 'error']

        if dry_run:
            preview_id = self._cache_preview(parsed.file_hash, len(valid_rows)) if valid_rows else None
            return self._build_result(
                parsed=parsed,
                session=session,
                issues=issues,
                dry_run=dry_run,
                execution_time=time.perf_counter() - started,
                plan=plan,
                created=None,
                preview_result_id=preview_id,
            )

        if errors and not valid_rows:
            if session:
                self._mark_failed(session, parsed.rows, issues)
            return self._build_result(
                parsed=parsed,
                session=session,
                issues=issues,
                dry_run=dry_run,
                execution_time=time.perf_counter() - started,
                plan=plan,
                created=None,
            )

        try:
            self._validate_preview(parsed.file_hash, preview_result_id)
        except ImportValidationError as exc:
            if session:
                session.status = ImportSession.STATUS_FAILED
                session.error_summary = exc.message[:1000]
                session.completed_at = timezone.now()
                session.save(update_fields=['status', 'error_summary', 'completed_at'])
            raise

        try:
            with transaction.atomic():
                user_map = self.user_mapper.resolve_users(valid_rows)
                created = self.project_creator.create_projects(valid_rows, user_map, self.super_admin)
                self._mark_success(session, parsed.rows, valid_rows, created, user_map, issues)
        except Exception as exc:
            if session:
                session.status = ImportSession.STATUS_FAILED
                session.error_summary = str(exc)[:1000]
                session.completed_at = timezone.now()
                session.save(update_fields=['status', 'error_summary', 'completed_at'])
            logger.error('Project import transaction failed: session=%s error=%s', session.id if session else None, exc, exc_info=True)
            raise

        return self._build_result(
            parsed=parsed,
            session=session,
            issues=issues,
            dry_run=False,
            execution_time=time.perf_counter() - started,
            plan=plan,
            created={
                'projects': created,
                'students': user_map['created_students'],
                'supervisors': user_map['created_supervisors'],
                'supervisor_credentials': user_map.get('supervisor_credentials', []),
            },
        )

    def generate_error_csv(self, issues):
        stream = StringIO()
        writer = csv.DictWriter(stream, fieldnames=['row_number', 'field_name', 'level', 'error_type', 'error_message'])
        writer.writeheader()
        for issue in issues:
            writer.writerow({
                'row_number': issue.row_number,
                'field_name': issue.field_name,
                'level': issue.level,
                'error_type': issue.error_type,
                'error_message': issue.error_message,
            })
        return stream.getvalue()

    def _cache_preview(self, file_hash, valid_rows_count):
        preview_id = str(uuid.uuid4())
        cache.set(
            self._preview_key(preview_id),
            {'user_id': self.super_admin.id, 'file_hash': file_hash, 'valid_rows_count': valid_rows_count},
            timeout=300,
        )
        return preview_id

    def _validate_preview(self, file_hash, preview_result_id):
        if not preview_result_id:
            return
        cached = cache.get(self._preview_key(preview_result_id))
        if not cached or cached.get('user_id') != self.super_admin.id:
            raise ImportValidationError('Preview has expired. Please preview the file again.')
        if cached.get('file_hash') != file_hash:
            raise ImportValidationError('Uploaded file does not match the successful preview. Please preview again.')

    def _preview_key(self, preview_result_id):
        return f'project_import_preview_{preview_result_id}'

    def _remove_error_rows(self, rows, issues):
        error_rows = {
            issue.row_number
            for issue in issues
            if issue.level == 'error' and issue.row_number is not None
        }
        return [row for row in rows if row['row_number'] not in error_rows]

    def _mark_failed(self, session, rows, issues):
        by_row = defaultdict(list)
        for issue in issues:
            if issue.row_number:
                by_row[issue.row_number].append(issue.error_message)
        failed_row_numbers = {
            issue.row_number
            for issue in issues
            if issue.level == 'error' and issue.row_number is not None
        }

        ImportRow.objects.bulk_create([
            ImportRow(
                session=session,
                row_number=row['row_number'],
                university_id=row.get('university_id', ''),
                project_title=row.get('title', ''),
                status=ImportRow.STATUS_FAILED if row['row_number'] in by_row else ImportRow.STATUS_SKIPPED,
                error_message='; '.join(by_row.get(row['row_number'], []))[:2000],
            )
            for row in rows
        ])
        session.failed_rows = len(failed_row_numbers)
        session.successful_rows = 0
        session.status = ImportSession.STATUS_FAILED
        session.error_summary = f'{session.failed_rows} validation error(s)'
        session.completed_at = timezone.now()
        session.save(update_fields=['failed_rows', 'successful_rows', 'status', 'error_summary', 'completed_at'])

    def _mark_success(self, session, all_rows, valid_rows, created, user_map, issues):
        issue_messages_by_row = defaultdict(list)
        failed_row_numbers = set()
        for issue in issues:
            if issue.level == 'error' and issue.row_number is not None:
                failed_row_numbers.add(issue.row_number)
                issue_messages_by_row[issue.row_number].append(issue.error_message)

        valid_row_numbers = {row['row_number'] for row in valid_rows}
        proposals_by_row = {}
        for created_item in created:
            for row in created_item.get('rows', []):
                proposals_by_row[row['row_number']] = created_item['proposal']

        import_rows = []
        for row in all_rows:
            row_number = row['row_number']
            is_success = row_number in valid_row_numbers
            import_rows.append(ImportRow(
                session=session,
                row_number=row_number,
                university_id=row.get('university_id', ''),
                project_title=row.get('title', ''),
                status=ImportRow.STATUS_SUCCESS if is_success else ImportRow.STATUS_FAILED,
                error_message='' if is_success else '; '.join(issue_messages_by_row.get(row_number, []))[:2000],
                created_student=user_map['students'].get(row.get('university_id')) if is_success else None,
                created_project=proposals_by_row.get(row_number) if is_success else None,
            ))

        ImportRow.objects.bulk_create(import_rows)
        session.successful_rows = len(valid_rows)
        session.failed_rows = len(failed_row_numbers)
        session.status = ImportSession.STATUS_SUCCESS
        session.error_summary = (
            f'Imported {session.successful_rows} row(s); skipped {session.failed_rows} invalid row(s)'
            if session.failed_rows
            else ''
        )
        session.completed_at = timezone.now()
        session.save(update_fields=['successful_rows', 'failed_rows', 'status', 'error_summary', 'completed_at'])
        logger.info(
            'Project import completed: session=%s user=%s success_rows=%s failed_rows=%s',
            session.id,
            self.super_admin.username,
            session.successful_rows,
            session.failed_rows,
        )

    def _project_count(self, rows):
        return len({
            row.get('project_row_number') or row.get('row_number')
            for row in rows
        })

    def _build_result(self, *, parsed, session, issues, dry_run, execution_time, plan, created, preview_result_id=None):
        errors = [issue.to_dict() for issue in issues if issue.level == 'error']
        warnings = [issue.to_dict() for issue in issues if issue.level == 'warning']
        created = created or {'projects': [], 'students': [], 'supervisors': []}
        supervisor_credentials = created.get('supervisor_credentials', [])

        total_rows = len(parsed.rows)
        invalid_row_numbers = {
            error['row_number']
            for error in errors
            if error.get('row_number') is not None
        }
        invalid_rows = len(invalid_row_numbers)
        valid_rows = self._remove_error_rows(parsed.rows, [
            ValidationIssue(
                row_number=error.get('row_number'),
                field_name=error.get('field_name', ''),
                error_message=error.get('error_message', ''),
            )
            for error in errors
        ])
        valid_rows_count = len(valid_rows)
        has_errors = bool(errors)
        partial_import = has_errors and valid_rows_count > 0
        if dry_run:
            result_status = 'partial_preview' if partial_import else ('failed' if has_errors else 'preview')
        else:
            result_status = 'partial_success' if partial_import else ('failed' if has_errors else 'success')

        result = {
            'import_session_id': str(session.id) if session else None,
            'preview_result_id': preview_result_id,
            'file_hash': parsed.file_hash if dry_run else None,
            'dry_run': dry_run,
            'status': result_status,
            'partial_import': partial_import,
            'total_rows_processed': total_rows,
            'valid_rows_count': valid_rows_count,
            'invalid_rows_count': invalid_rows,
            'successful_imports': len(created['projects']),
            'failed_imports': invalid_rows,
            'created_students_count': len(created['students']),
            'created_supervisors_count': len(created['supervisors']),
            'created_projects_count': len(created['projects']),
            'users_to_create': {
                'students': plan.get('students_to_create', []),
                'supervisors': plan.get('supervisors_to_create', []),
            },
            'users_to_reuse': {
                'supervisors': plan.get('supervisors_to_reuse', []),
            },
            'projects_to_create': self._project_count(valid_rows) if dry_run else 0,
            'supervisor_credentials_export': self._build_supervisor_credentials_export(
                supervisor_credentials,
                session=session,
                dry_run=dry_run,
            ),
            'validation_errors': errors,
            'warnings': warnings,
            'errors_by_type': group_issues([issue for issue in issues if issue.level == 'error']),
            'execution_time_seconds': round(execution_time, 3),
        }
        return result

    def _build_supervisor_credentials_export(self, rows, *, session, dry_run):
        security_note = (
            'For security reasons, passwords are only available for supervisor accounts newly created '
            'during this import. Existing supervisor passwords are not stored in plaintext and cannot be exported.'
        )
        columns = [
            'source_row_number',
            'project_title',
            'department',
            'full_name',
            'username',
            'generated_password',
            'created_or_reused',
            'created_at',
            'notes',
        ]
        return {
            'available': bool(rows) and not dry_run,
            'filename': f'supervisor_credentials_{session.id}.csv' if session else 'supervisor_credentials.csv',
            'columns': columns,
            'rows': rows if not dry_run else [],
            'security_note': security_note,
        }
