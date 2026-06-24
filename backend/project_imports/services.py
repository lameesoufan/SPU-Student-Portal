import csv
import logging
import os
import re
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
from projects.models import ProjectApplication, StudentIdeaProposal

from .constants import DEFAULT_TEMP_PASSWORD_FORMAT
from .models import ImportRow, ImportSession
from .validators import FileValidator, ImportValidationError, RowValidator, ValidationIssue, group_issues


logger = logging.getLogger('project_imports')
User = get_user_model()


class UserMapper:
    username_cleaner = re.compile(r'[^A-Za-z0-9_]+')

    def parse_student_name(self, name):
        parts = str(name or '').strip().split(None, 1)
        if not parts:
            return '', ''
        return parts[0], parts[1] if len(parts) > 1 else ''

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
        supervisors_to_create = {}
        for row in rows:
            name = row.get('supervisor_name', '').strip()
            if not name:
                continue
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
            elif len(existing) == 1:
                supervisor_map[row['row_number']] = existing[0]
            else:
                username = self.normalize_username(name)
                supervisors_to_create[username] = {
                    'username': username,
                    'full_name': name,
                    'department': row.get('department', ''),
                }
                supervisor_map[row['row_number']] = username

        return {
            'issues': issues,
            'students_to_create': sorted(set(students_to_create)),
            'supervisors_to_create': list(supervisors_to_create.values()),
            'supervisor_map': supervisor_map,
        }

    def resolve_users(self, rows):
        student_ids = {row['university_id'] for row in rows}
        students = {
            user.username: user
            for user in User.objects.select_for_update().filter(username__in=student_ids)
        }
        created_students = []
        created_supervisors = []

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
        for row in rows:
            name = row.get('supervisor_name', '').strip()
            existing = self.find_supervisor_by_name(name, lock=True)
            if existing:
                supervisors[row['row_number']] = existing[0]
                continue

            username = self.normalize_username(name)
            if username in supervisors:
                supervisors[row['row_number']] = supervisors[username]
                continue

            first_name, last_name = self.parse_student_name(name)
            supervisor = User.objects.create_user(
                username=username,
                password=self.generate_password(username),
                first_name=first_name,
                last_name=last_name,
                role='doctor',
                department=row.get('department') or None,
                must_change_password=True,
                is_active=True,
            )
            supervisors[row['row_number']] = supervisor
            supervisors[username] = supervisor
            created_supervisors.append(supervisor)

        return {
            'students': students,
            'supervisors': supervisors,
            'created_students': created_students,
            'created_supervisors': created_supervisors,
        }

    def find_supervisor_by_name(self, name, *, lock=False):
        needle = str(name or '').strip().lower()
        if not needle:
            return []
        qs = User.objects.filter(role='doctor')
        if lock:
            qs = qs.select_for_update()
        matches = []
        exact_matches = []
        for user in qs:
            full_name = (user.get_full_name() or '').strip()
            haystacks = [user.username.lower(), full_name.lower()]
            if needle in haystacks:
                exact_matches.append(user)
            elif any(needle in value for value in haystacks if value):
                matches.append(user)
        return exact_matches or matches

    def normalize_username(self, name):
        base = self.username_cleaner.sub('_', str(name or '').strip()).strip('_').lower()
        if not base:
            base = f'doctor_{uuid.uuid5(uuid.NAMESPACE_DNS, str(name)).hex[:10]}'
        username = base[:120]
        candidate = username
        suffix = 1
        while User.objects.filter(username=candidate).exists():
            suffix += 1
            candidate = f'{username[:110]}_{suffix}'
        return candidate


class ProjectCreator:
    def create_projects(self, rows, user_map, super_admin):
        created = []
        now = timezone.localtime(timezone.now()).strftime('%Y-%m-%d')
        for row in rows:
            student = user_map['students'][row['university_id']]
            supervisor = user_map['supervisors'][row['row_number']]
            proposal = StudentIdeaProposal.objects.create(
                student=student,
                supervisor=supervisor,
                title=row['title'],
                description=f'Imported by {super_admin.username} on {now}',
                department=row['department'],
                team_size=1,
                team_size_reason='Bulk import by super admin',
                project_type=row['project_type'],
                status='assigned',
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
            created.append({'proposal': proposal, 'application': application, 'board': board})
        return created


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
        errors = [issue for issue in issues if issue.level == 'error']

        if errors:
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

        if dry_run:
            preview_id = self._cache_preview(parsed.file_hash, len(valid_rows))
            return self._build_result(
                parsed=parsed,
                session=None,
                issues=issues,
                dry_run=True,
                execution_time=time.perf_counter() - started,
                plan=plan,
                created=None,
                preview_result_id=preview_id,
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
                self._mark_success(session, valid_rows, created, user_map)
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
        session.failed_rows = len([issue for issue in issues if issue.level == 'error'])
        session.successful_rows = 0
        session.status = ImportSession.STATUS_FAILED
        session.error_summary = f'{session.failed_rows} validation error(s)'
        session.completed_at = timezone.now()
        session.save(update_fields=['failed_rows', 'successful_rows', 'status', 'error_summary', 'completed_at'])

    def _mark_success(self, session, rows, created, user_map):
        proposals_by_row = {
            row['row_number']: created_item['proposal']
            for row, created_item in zip(rows, created)
        }
        ImportRow.objects.bulk_create([
            ImportRow(
                session=session,
                row_number=row['row_number'],
                university_id=row.get('university_id', ''),
                project_title=row.get('title', ''),
                status=ImportRow.STATUS_SUCCESS,
                created_student=user_map['students'].get(row['university_id']),
                created_project=proposals_by_row.get(row['row_number']),
            )
            for row in rows
        ])
        session.successful_rows = len(rows)
        session.failed_rows = 0
        session.status = ImportSession.STATUS_SUCCESS
        session.completed_at = timezone.now()
        session.save(update_fields=['successful_rows', 'failed_rows', 'status', 'completed_at'])
        logger.info('Project import completed: session=%s user=%s rows=%s', session.id, self.super_admin.username, len(rows))

    def _build_result(self, *, parsed, session, issues, dry_run, execution_time, plan, created, preview_result_id=None):
        errors = [issue.to_dict() for issue in issues if issue.level == 'error']
        warnings = [issue.to_dict() for issue in issues if issue.level == 'warning']
        created = created or {'projects': [], 'students': [], 'supervisors': []}

        total_rows = len(parsed.rows)
        invalid_rows = len({error['row_number'] for error in errors if error.get('row_number')})
        result = {
            'import_session_id': str(session.id) if session else None,
            'preview_result_id': preview_result_id,
            'file_hash': parsed.file_hash if dry_run else None,
            'dry_run': dry_run,
            'status': 'preview' if dry_run and not errors else ('failed' if errors else 'success'),
            'total_rows_processed': total_rows,
            'valid_rows_count': max(total_rows - invalid_rows, 0),
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
            'projects_to_create': max(total_rows - invalid_rows, 0) if dry_run else 0,
            'validation_errors': errors,
            'warnings': warnings,
            'errors_by_type': group_issues([issue for issue in issues if issue.level == 'error']),
            'execution_time_seconds': round(execution_time, 3),
        }
        return result
