import re

from accounts.models import DEPARTMENTS
from projects.models import PROJECT_TYPES


MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 1000
DEFAULT_TEMP_PASSWORD_FORMAT = 'SPU{identifier}@2025-2026'

HEADER_STUDENT_NAME = 'اسم الطالب'
HEADER_UNIVERSITY_ID = 'الرقم الجامعي'
HEADER_PROJECT_TITLE = 'اسم المشروع'
HEADER_DEPARTMENT = 'مجال المشروع'
HEADER_SUPERVISOR_NAME = 'اسم المشرف'
HEADER_PROJECT_TYPE = 'نمط المشروع'
HEADER_GIT_REPO = 'رابط الـ Git'

FIELD_HEADERS = {
    'student_name': HEADER_STUDENT_NAME,
    'university_id': HEADER_UNIVERSITY_ID,
    'title': HEADER_PROJECT_TITLE,
    'department': HEADER_DEPARTMENT,
    'supervisor_name': HEADER_SUPERVISOR_NAME,
    'project_type': HEADER_PROJECT_TYPE,
    'github_repo': HEADER_GIT_REPO,
}

REQUIRED_FIELDS = list(FIELD_HEADERS.keys())
REQUIRED_HEADERS = [FIELD_HEADERS[field] for field in REQUIRED_FIELDS]

HEADER_ALIASES = {
    'student_name': (HEADER_STUDENT_NAME, 'student_name', 'student name'),
    'university_id': (HEADER_UNIVERSITY_ID, 'university_id', 'university id', 'student_id', 'student id'),
    'title': (HEADER_PROJECT_TITLE, 'title', 'project_title', 'project title'),
    'department': (HEADER_DEPARTMENT, 'department', 'project_department', 'project department'),
    'supervisor_name': (
        HEADER_SUPERVISOR_NAME,
        'supervisor_name',
        'supervisor name',
        'supervisor',
        'doctor_name',
        'doctor name',
    ),
    'project_type': (HEADER_PROJECT_TYPE, 'project_type', 'project type', 'type'),
    'github_repo': (
        HEADER_GIT_REPO,
        'github_repo',
        'github repo',
        'git_repo',
        'git_repository',
        'git repo',
        'git repository',
        'repository',
        'repo',
        'رابط Git',
        'رابط ال Git',
        'رابط الـGit',
    ),
}

HEADER_SEPARATOR_RE = re.compile(r'[:：|/\r\n]+')


def normalize_header_name(value):
    normalized = ' '.join(str(value or '').strip().split())
    normalized = normalized.replace('ـ', '')
    return normalized.casefold()


HEADER_TO_FIELD = {
    normalize_header_name(header): field
    for field, aliases in HEADER_ALIASES.items()
    for header in aliases
}


def resolve_header_field(value):
    normalized = normalize_header_name(value)
    if not normalized:
        return None

    exact = HEADER_TO_FIELD.get(normalized)
    if exact:
        return exact

    for part in HEADER_SEPARATOR_RE.split(normalized):
        field = HEADER_TO_FIELD.get(part.strip())
        if field:
            return field

    for alias, field in sorted(HEADER_TO_FIELD.items(), key=lambda item: len(item[0]), reverse=True):
        if alias and alias in normalized:
            return field
    return None

VALID_DEPARTMENTS = [value for value, _label in DEPARTMENTS]
VALID_PROJECT_TYPES = [value for value, _label in PROJECT_TYPES]
