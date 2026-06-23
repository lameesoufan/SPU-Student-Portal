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

REQUIRED_HEADERS = [
    HEADER_STUDENT_NAME,
    HEADER_UNIVERSITY_ID,
    HEADER_PROJECT_TITLE,
    HEADER_DEPARTMENT,
    HEADER_SUPERVISOR_NAME,
    HEADER_PROJECT_TYPE,
    HEADER_GIT_REPO,
]

HEADER_TO_FIELD = {
    HEADER_STUDENT_NAME: 'student_name',
    HEADER_UNIVERSITY_ID: 'university_id',
    HEADER_PROJECT_TITLE: 'title',
    HEADER_DEPARTMENT: 'department',
    HEADER_SUPERVISOR_NAME: 'supervisor_name',
    HEADER_PROJECT_TYPE: 'project_type',
    HEADER_GIT_REPO: 'github_repo',
}

VALID_DEPARTMENTS = [value for value, _label in DEPARTMENTS]
VALID_PROJECT_TYPES = [value for value, _label in PROJECT_TYPES]
