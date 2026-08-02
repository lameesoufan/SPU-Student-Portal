import csv
import logging
import os
import time
import uuid
from collections import defaultdict
from io import StringIO

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from project_management.models import ProjectBoard
from projects.models import ProjectApplication, ProposalInvitation, StudentIdeaProposal
from projects.participation_services import create_participations_for_student_proposal

from .constants import DEFAULT_TEMP_PASSWORD_FORMAT
from .models import ImportRow, ImportSession
from .name_utils import (
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
    def __init__(self):
        self._all_supervisors_cache = None
        self._existing_usernames = set(User.objects.values_list('username', flat=True))
        self._generated_usernames_by_identity = {}
        # ✅ Cache supervisor identities to avoid N+1 queries
        self._supervisor_identity_cache = self._build_supervisor_identity_cache()

    def generate_password(self, identifier):
        """Generate a temporary password for import. User must change on first login."""
        fmt = getattr(settings, 'IMPORT_TEMP_PASSWORD_FORMAT', None) or os.getenv(
            'IMPORT_TEMP_PASSWORD_FORMAT',
            DEFAULT_TEMP_PASSWORD_FORMAT,
        )
        return fmt.format(identifier=identifier)

    def parse_supervisor_name(self, name):
        return parse_person_name(strip_person_titles(name))

    def parse_student_name(self, name):
        parts = str(name or '').split(None, 1)
        if not parts:
            return '', ''
        return parts[0], parts[1] if len(parts) > 1 else ''

    def _build_supervisor_identity_cache(self):
        """Build identity_key -> User mapping for O(1) supervisor lookups."""
        supervisors = User.objects.filter(role__in=['doctor', 'hod']).only('id', 'username', 'first_name', 'last_name')
        cache = {}
        for sup in supervisors:
            full_name = sup.get_full_name() or ''
            identity_key = supervisor_identity_key(full_name)
            if identity_key not in cache:
                cache[identity_key] = []
            cache[identity_key].append(sup)
        return cache

    def _get_all_supervisors(self, lock=False):
        """Cache all supervisors — load from DB once instead of per-name."""
        if self._all_supervisors_cache is None:
            qs = User.objects.filter(role__in=['doctor', 'hod'])
            if lock:
                qs = qs.select_for_update()
            self._all_supervisors_cache = list(qs)
        return self._all_supervisors_cache

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

        # ── Supervisor planning with identity_key dedup ──
        supervisor_map = {}
        supervisors_to_create = {}
        supervisors_by_row = defaultdict(list)
        all_supervisor_keys_in_plan = []

        for row in rows:
            raw_name = row.get('supervisor_name', '').strip()
            if not raw_name:
                continue

            names = row.get('supervisor_names') or split_supervisor_names(raw_name)
            if not names:
                continue

            if len(names) > 1:
                issues.append(ValidationIssue(
                    row_number=row['row_number'],
                    field_name='supervisor_name',
                    error_message=(
                        f"Row {row['row_number']}: Cell contains {len(names)} supervisor names. "
                        f"The first one ('{names[0]}') will be assigned to the project. "
                        f"All names found: {', '.join(names)}"
                    ),
                    row_data=row,
                    level='warning',
                    error_type='supervisor_multiple',
                ))

            for idx, name in enumerate(names):
                identity_key = supervisor_identity_key(name)
                is_primary = (idx == 0)

                existing = self.find_supervisor_by_name(name)
                if len(existing) > 1 and is_primary:
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
                elif len(existing) == 0:
                    if identity_key not in supervisors_to_create:
                        username = self.normalize_username(name)
                        supervisors_to_create[identity_key] = {
                            'username': username,
                            'full_name': strip_person_titles(name),
                            'raw_name': name,
                            'department': row.get('department', ''),
                        }

                if len(existing) >= 1:
                    supervisors_by_row[row['row_number']].append(existing[0].username)
                elif identity_key in supervisors_to_create:
                    supervisors_by_row[row['row_number']].append(supervisors_to_create[identity_key]['username'])

                if is_primary:
                    if len(existing) >= 1:
                        supervisor_map[row['row_number']] = existing[0]
                    else:
                        supervisor_map[row['row_number']] = identity_key

                all_supervisor_keys_in_plan.append((identity_key, row['row_number'], is_primary, name))

        return {
            'issues': issues,
            'students_to_create': sorted(set(students_to_create)),
            'supervisors_to_create': list(supervisors_to_create.values()),
            'supervisor_map': supervisor_map,
            'supervisors_by_row': dict(supervisors_by_row),
            'all_supervisor_keys': all_supervisor_keys_in_plan,
        }

    def resolve_users(self, rows):
        student_ids = {row['university_id'] for row in rows}
        students = {
            user.username: user
            for user in User.objects.select_for_update().filter(username__in=student_ids)
        }
        created_students = []
        created_supervisors = []
        credentials = {}

        # ── Student resolution ──
        for row in rows:
            university_id = row['university_id']
            email = row.get('email', '').strip().lower()
            if university_id in students:
                student = students[university_id]
                if email and not student.email:
                    student.email = email
                    student.save(update_fields=['email'])
                continue
            first_name, last_name = parse_person_name(row.get('student_name', ''))
            password = self.generate_password(university_id)
            student = User.objects.create_user(
                username=university_id,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role='student',
                department=row.get('department') or None,
                must_change_password=True,
                is_active=True,
            )
            students[university_id] = student
            created_students.append(student)
            credentials[student.id] = {
                'username': university_id,
                'email': email,
                'password': password,
                'full_name': f'{first_name} {last_name}'.strip(),
                'department': row.get('department', ''),
                'role': 'student',
            }

        # ── Supervisor resolution ──
        supervisors = {}
        co_supervisors_map = {}
        identity_to_user = {}

        for row in rows:
            raw_name = row.get('supervisor_name', '').strip()
            if not raw_name:
                continue

            names = row.get('supervisor_names') or split_supervisor_names(raw_name)
            if not names:
                continue

            for idx, name in enumerate(names):
                identity_key = supervisor_identity_key(name)
                is_primary = (idx == 0)

                if identity_key in identity_to_user:
                    if is_primary:
                        supervisors[row['row_number']] = identity_to_user[identity_key]
                    continue

                existing = self.find_supervisor_by_name(name, lock=True)
                if existing:
                    identity_to_user[identity_key] = existing[0]
                    if is_primary:
                        supervisors[row['row_number']] = existing[0]
                    continue

                first_name, last_name = parse_person_name(name)
                username = self.normalize_username(name)
                password = self.generate_password(username)
                supervisor = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    role='doctor',
                    department=row.get('department') or None,
                    must_change_password=True,
                    must_change_username=True,
                    is_active=True,
                )
                identity_to_user[identity_key] = supervisor
                created_supervisors.append(supervisor)
                credentials[supervisor.id] = {
                    'username': username,
                    'password': password,
                    'full_name': strip_person_titles(name),
                    'department': row.get('department', ''),
                    'role': 'doctor',
                }

                if is_primary:
                    supervisors[row['row_number']] = supervisor
                else:
                    co_supervisors_map.setdefault(row['row_number'], []).append(supervisor)

        return {
            'students': students,
            'supervisors': supervisors,
            'co_supervisors_map': co_supervisors_map,
            'created_students': created_students,
            'created_supervisors': created_supervisors,
            'credentials': credentials,
            'identity_to_user': identity_to_user,
        }

    # ── Supervisor lookup ──

    def find_supervisor_by_name(self, name, *, lock=False):
        """Look up a supervisor by name using O(1) cached identity lookups.

        Strips titles (د., م., أ.د.) before comparing and uses
        supervisor_identity_key() to normalise Arabic variants so that
        "أحمد خالد" matches "احمد خالد" and "أحمـد خالـد".
        """
        needle = str(name or '').strip()
        if not needle:
            return []

        identity_key = supervisor_identity_key(needle)
        
        # ✅ O(1) lookup from cache instead of O(n) iteration
        cached_matches = self._supervisor_identity_cache.get(identity_key, [])
        if cached_matches:
            return cached_matches
        
        # Fallback to legacy logic for edge cases (partial matches)
        clean_needle = strip_person_titles(needle)
        first_part, last_part = parse_person_name(needle)
        all_supervisors = self._get_all_supervisors(lock=lock)

        username_matches = [
            u for u in all_supervisors
            if u.username.casefold() == needle.casefold()
        ]
        if username_matches:
            return username_matches

        # Step 1: exact matches on first_name + last_name
        exact_matches = [
            u for u in all_supervisors
            if (
                (first_part and last_part and u.first_name.lower() == first_part.lower() and u.last_name.lower() == last_part.lower())
                or (first_part and u.first_name.lower() == first_part.lower())
                or u.first_name.lower() == clean_needle.lower()
            )
        ]

        if exact_matches:
            verified = [
                u for u in exact_matches
                if supervisor_identity_key(u.get_full_name() or '') == identity_key
            ]
            if verified:
                return verified

        # Step 2: partial match on full name as last resort
        needle_lower = clean_needle.lower()
        return [
            u for u in all_supervisors
            if (u.get_full_name() or '').strip()
            and (
                needle_lower in (u.get_full_name() or '').strip().lower()
                or (u.get_full_name() or '').strip().lower() in needle_lower
            )
        ]

    def normalize_username(self, name):
        identity_key = supervisor_identity_key(name) or str(name).strip().casefold()
        if identity_key in self._generated_usernames_by_identity:
            return self._generated_usernames_by_identity[identity_key]

        base = username_base_from_name(name)
        if not base:
            base = f'doctor_{uuid.uuid5(uuid.NAMESPACE_DNS, str(name)).hex[:10]}'
        username = base[:120]
        candidate = username
        suffix = 1
        while (
            candidate.lower() in self._existing_usernames
            or User.objects.filter(username__iexact=candidate).exists()
        ):
            suffix += 1
            candidate = f'{username[:110]}_{suffix}'
        self._existing_usernames.add(candidate.lower())
        self._generated_usernames_by_identity[identity_key] = candidate
        return candidate


class ProjectCreator:
    def create_projects(self, rows, user_map, super_admin):
        created = []
        now = timezone.localtime(timezone.now()).strftime('%Y-%m-%d')
        co_supervisors_map = user_map.get('co_supervisors_map', {})
        supervisors_by_row = user_map.get('supervisors_by_row', {})

        for group_rows in self._group_project_rows(rows):
            row = self._leader_row(group_rows)
            members = [member_row for member_row in group_rows if member_row is not row]
            student = user_map['students'][row['university_id']]
            supervisor = user_map['supervisors'][row['row_number']]
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

            # ── Link co-supervisors (secondary supervisors) to the proposal ──
            project_co_supervisors = set()
            for gr in group_rows:
                for co_sup in co_supervisors_map.get(gr['row_number'], []):
                    project_co_supervisors.add(co_sup)
                row_supervisors = supervisors_by_row.get(gr['row_number'], [])
                for co_sup in row_supervisors[1:]:
                    if co_sup != supervisor:
                        project_co_supervisors.add(co_sup)
            if project_co_supervisors:
                proposal.co_supervisors.set(project_co_supervisors)

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
            create_participations_for_student_proposal(proposal)
            created.append({'proposal': proposal, 'application': application, 'board': board, 'rows': group_rows})
        return created

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
    # ✅ Batch size for transaction batching
    BATCH_SIZE = 50

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

        if dry_run:
            preview_id = self._cache_preview(parsed.file_hash, len(valid_rows)) if valid_rows else None
            return self._build_result(
                parsed=parsed,
                session=session,
                issues=issues,
                dry_run=True,
                execution_time=time.perf_counter() - started,
                plan=plan,
                created=None,
                preview_result_id=preview_id,
            )

        self._validate_preview(parsed.file_hash, preview_result_id)

        try:
            user_map, created = self._execute_batched_import(valid_rows, session)
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
            },
            import_valid_rows=valid_rows,
            import_user_map=user_map,
        )

    def _execute_batched_import(self, valid_rows, session):
        """Execute import in batches to avoid long-running transactions."""
        # Step 1: Resolve all users in one transaction
        with transaction.atomic():
            user_map = self.user_mapper.resolve_users(valid_rows)
        
        # Step 2: Create projects in batches
        project_groups = list(self.project_creator._group_project_rows(valid_rows))
        total_projects = len(project_groups)
        created_projects = []
        
        for batch_idx in range(0, total_projects, self.BATCH_SIZE):
            batch_groups = project_groups[batch_idx:batch_idx + self.BATCH_SIZE]
            
            # Process batch in its own transaction
            with transaction.atomic():
                for group_rows in batch_groups:
                    project_data = self._create_single_project(
                        group_rows, 
                        user_map, 
                        self.super_admin
                    )
                    created_projects.append(project_data)
        
        return user_map, created_projects

    def _create_single_project(self, group_rows, user_map, super_admin):
        """Create a single project with all its related objects."""
        now = timezone.localtime(timezone.now()).strftime('%Y-%m-%d')
        co_supervisors_map = user_map.get('co_supervisors_map', {})
        
        row = self.project_creator._leader_row(group_rows)
        members = [member_row for member_row in group_rows if member_row is not row]
        student = user_map['students'][row['university_id']]
        supervisor = user_map['supervisors'][row['row_number']]
        
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

        # Link co-supervisors
        project_co_supervisors = set()
        for gr in group_rows:
            for co_sup in co_supervisors_map.get(gr['row_number'], []):
                project_co_supervisors.add(co_sup)
        if project_co_supervisors:
            proposal.co_supervisors.set(project_co_supervisors)

        # Create invitations
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
        create_participations_for_student_proposal(proposal)
        
        return {
            'proposal': proposal, 
            'application': application, 
            'board': board, 
            'rows': group_rows
        }

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

    def _build_result(self, *, parsed, session, issues, dry_run, execution_time, plan, created,
                      preview_result_id=None, import_valid_rows=None, import_user_map=None):
        errors = [issue.to_dict() for issue in issues if issue.level == 'error']
        warnings = [issue.to_dict() for issue in issues if issue.level == 'warning']
        created = created or {'projects': [], 'students': [], 'supervisors': []}

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

        supervisor_credentials_export = None
        student_credentials_export = None
        if import_user_map and not dry_run and import_valid_rows:
            supervisor_credentials_export = self._build_supervisor_credentials_export(
                import_valid_rows, import_user_map,
            )
            student_credentials_export = self._build_student_credentials_export(
                import_valid_rows, import_user_map,
            )

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
            'projects_to_create': self._project_count(valid_rows) if dry_run else 0,
            'validation_errors': errors,
            'warnings': warnings,
            'errors_by_type': group_issues([issue for issue in issues if issue.level == 'error']),
            'execution_time_seconds': round(execution_time, 3),
            'supervisor_credentials_export': supervisor_credentials_export,
            'student_credentials_export': student_credentials_export,
        }
        return result

    # ── Credentials export builders ──

    def _build_supervisor_credentials_export(self, valid_rows, user_map):
        """Build supervisor credentials export data for CSV download.

        Each unique supervisor appears ONCE with all their assigned projects combined.
        Includes ALL supervisors from multi-name cells (not just the primary).
        """
        credentials = user_map.get('credentials', {})
        created_supervisor_ids = {s.id for s in user_map.get('created_supervisors', [])}
        identity_to_user = user_map.get('identity_to_user', {})

        # First pass: build identity_key -> list of {title, department, row_number}  (O(n))
        supervisor_projects = defaultdict(list)
        for row in valid_rows:
            raw_name = row.get('supervisor_name', '').strip()
            if not raw_name:
                continue
            names = row.get('supervisor_names') or split_supervisor_names(raw_name)
            for name in names:
                identity_key = supervisor_identity_key(name)
                supervisor_projects[identity_key].append({
                    'title': row.get('title', ''),
                    'department': row.get('department', ''),
                    'row_number': row['row_number'],
                })

        # Second pass: build supervisor_info from the map
        supervisor_info = defaultdict(lambda: {'projects': [], 'departments': set(), 'row_numbers': []})
        seen_supervisor_ids = set()

        for identity_key, projects in supervisor_projects.items():
            supervisor = identity_to_user.get(identity_key)
            if not supervisor:
                continue
            if supervisor.id in seen_supervisor_ids:
                continue
            seen_supervisor_ids.add(supervisor.id)
            for p in projects:
                supervisor_info[supervisor.id]['projects'].append(p['title'])
                if p['department']:
                    supervisor_info[supervisor.id]['departments'].add(p['department'])
                supervisor_info[supervisor.id]['row_numbers'].append(p['row_number'])

        rows_data = []
        for supervisor_id, info in supervisor_info.items():
            cred = credentials.get(supervisor_id, {})
            is_created = supervisor_id in created_supervisor_ids

            supervisor = None
            for s in identity_to_user.values():
                if hasattr(s, 'id') and s.id == supervisor_id:
                    supervisor = s
                    break
            if not supervisor:
                for s in user_map.get('supervisors', {}).values():
                    if hasattr(s, 'id') and s.id == supervisor_id:
                        supervisor = s
                        break
            if not supervisor:
                continue

            co_sup_map = user_map.get('co_supervisors_map', {})
            co_sup_ids = set()
            for co_list in co_sup_map.values():
                for cs in co_list:
                    co_sup_ids.add(cs.id)

            if supervisor.id in co_sup_ids and supervisor.id not in {s.id for s in user_map.get('supervisors', {}).values() if hasattr(s, 'id')}:
                role_in_project = 'co-supervisor'
            else:
                role_in_project = 'primary'

            rows_data.append({
                'full_name': supervisor.get_full_name() or cred.get('full_name', ''),
                'username': supervisor.username,
                'generated_password': cred.get('password', '') if is_created else '',
                'role_in_project': role_in_project,
                'project_titles': '; '.join(dict.fromkeys(info['projects'])),
                'department': '; '.join(sorted(info['departments'])) if info['departments'] else '',
                'created_or_reused': 'created' if is_created else 'reused_existing_no_password_exported',
                'notes': 'Must change password and username on first login' if is_created else 'Already existed in system',
            })

        if not rows_data:
            return None

        return {
            'available': True,
            'security_note': 'This file contains sensitive credentials. Share securely and delete after distribution.',
            'filename': 'supervisor_credentials.csv',
            'columns': [
                'full_name',
                'username',
                'generated_password',
                'role_in_project',
                'project_titles',
                'department',
                'created_or_reused',
                'notes',
            ],
            'rows': rows_data,
        }

    def _build_student_credentials_export(self, valid_rows, user_map):
        """Build student credentials export data for CSV download."""
        credentials = user_map.get('credentials', {})
        created_student_ids = {s.id for s in user_map.get('created_students', [])}

        rows_data = []
        seen_university_ids = set()
        for row in valid_rows:
            university_id = row.get('university_id', '')
            if not university_id or university_id in seen_university_ids:
                continue
            seen_university_ids.add(university_id)

            student = user_map['students'].get(university_id)
            if not student:
                continue

            cred = credentials.get(student.id, {})
            is_created = student.id in created_student_ids

            student_projects = [
                r.get('title', '') for r in valid_rows
                if r.get('university_id') == university_id and r.get('title')
            ]

            rows_data.append({
                'university_id': university_id,
                'email': student.email or row.get('email', ''),
                'project_title': '; '.join(student_projects),
                'department': row.get('department', ''),
                'full_name': student.get_full_name() or cred.get('full_name', ''),
                'username': student.username,
                'generated_password': cred.get('password', '') if is_created else '(existing user)',
                'created_or_reused': 'created' if is_created else 'reused',
                'notes': 'Must change password on first login' if is_created else 'Already existed in system',
            })

        if not rows_data:
            return None

        return {
            'available': True,
            'security_note': 'This file contains sensitive credentials. Share securely and delete after distribution.',
            'filename': 'student_credentials.csv',
            'columns': [
                'university_id',
                'email',
                'project_title',
                'department',
                'full_name',
                'username',
                'generated_password',
                'created_or_reused',
                'notes',
            ],
            'rows': rows_data,
        }
