import re

from accounts.models import DEPARTMENTS
from projects.models import PROJECT_TYPES


MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 1000
DEFAULT_TEMP_PASSWORD_FORMAT = 'SPU{identifier}@{random}'

HEADER_STUDENT_NAME = 'اسم الطالب'
HEADER_UNIVERSITY_ID = 'الرقم الجامعي'
HEADER_STUDENT_EMAIL = 'البريد الإلكتروني'
HEADER_PROJECT_TITLE = 'اسم المشروع'
HEADER_DEPARTMENT = 'مجال المشروع'
HEADER_SUPERVISOR_NAME = 'اسم المشرف'
HEADER_PROJECT_TYPE = 'نمط المشروع'
HEADER_GIT_REPO = 'رابط الـ Git'

FIELD_HEADERS = {
    'student_name': HEADER_STUDENT_NAME,
    'university_id': HEADER_UNIVERSITY_ID,
    'email': HEADER_STUDENT_EMAIL,
    'title': HEADER_PROJECT_TITLE,
    'department': HEADER_DEPARTMENT,
    'supervisor_name': HEADER_SUPERVISOR_NAME,
    'project_type': HEADER_PROJECT_TYPE,
    'github_repo': HEADER_GIT_REPO,
}

REQUIRED_FIELDS = list(FIELD_HEADERS.keys())
REQUIRED_HEADERS = [FIELD_HEADERS[field] for field in REQUIRED_FIELDS]

HEADER_ALIASES = {
    'student_name': (
        HEADER_STUDENT_NAME,
        'أسماء الطلاب',
        'اسماء الطلاب',
        'أسماء الطلبة',
        'اسماء الطلبة',
        'أسماء الطالبات',
        'اسماء الطالبات',
        'اسم الطلاب',
        'اسم الطلبة',
        'اسم الطالبات',
        'اسم الطالبة',
        'اسم الطالب والطالبة',
        'اسم الطالب أو الطالبة',
        'الاسم الكامل للطالب',
        'الاسم الكامل',
        'student_name',
        'student name',
        'student-name',
        'student',
        'full_name',
        'full name',
        'student full name',
    ),
    'university_id': (HEADER_UNIVERSITY_ID, 'university_id', 'university id', 'student_id', 'student id'),
    'email': (
        HEADER_STUDENT_EMAIL,
        'البريد الالكتروني',
        'البريد الجامعي',
        'بريد الطالب',
        'ايميل الطالب',
        'إيميل الطالب',
        'الايميل',
        'الإيميل',
        'email',
        'student_email',
        'student email',
        'email_address',
        'email address',
    ),
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
        'رابط GitHub',
        'رابط Github',
        'رابط github',
        'رابط جيت هب',
        'رابط المستودع',
        'رابط مستودع Git',
        'رابط مستودع GitHub',
        'رابط المشروع على GitHub',
        'github_repo',
        'github repo',
        'github',
        'github url',
        'github link',
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

HEADER_INVISIBLE_CHARS = str.maketrans('', '', '\ufeff\u061c\u200b\u200c\u200d\u200e\u200f')
HEADER_ARABIC_CHAR_TRANSLATION = str.maketrans({
    'أ': 'ا',
    'إ': 'ا',
    'آ': 'ا',
    'ٱ': 'ا',
    'ى': 'ي',
    'ؤ': 'و',
    'ئ': 'ي',
    'ة': 'ه',
})
HEADER_ARABIC_DIACRITICS_RE = re.compile(r'[\u064b-\u065f\u0670]')
HEADER_SEPARATOR_RE = re.compile(r'[:：|/\\\r\n]+')
HEADER_WORD_SEPARATOR_RE = re.compile(r'[\s_\-–—:：|/\\()\[\]{}]+')
HEADER_COMPACT_RE = re.compile(r'[\W_]+', re.UNICODE)
AMBIGUOUS_SUBSTRING_HEADERS = {'repo', 'student', 'type'}
DIGIT_TRANSLATION = str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')


def normalize_header_name(value):
    normalized = str(value or '').translate(HEADER_INVISIBLE_CHARS)
    normalized = normalized.replace('\xa0', ' ')
    normalized = normalized.replace('ـ', '')
    normalized = normalized.translate(DIGIT_TRANSLATION)
    normalized = normalized.translate(HEADER_ARABIC_CHAR_TRANSLATION)
    normalized = HEADER_ARABIC_DIACRITICS_RE.sub('', normalized)
    normalized = HEADER_WORD_SEPARATOR_RE.sub(' ', normalized)
    normalized = ' '.join(normalized.strip().split())
    return normalized.casefold()


def compact_header_name(value):
    return HEADER_COMPACT_RE.sub('', normalize_header_name(value))


HEADER_TO_FIELD = {
    normalize_header_name(header): field
    for field, aliases in HEADER_ALIASES.items()
    for header in aliases
}

COMPACT_HEADER_TO_FIELD = {
    compact_header_name(header): field
    for field, aliases in HEADER_ALIASES.items()
    for header in aliases
}


def resolve_header_field(value):
    normalized = normalize_header_name(value)
    if not normalized:
        return None
    compact = compact_header_name(value)

    exact = HEADER_TO_FIELD.get(normalized)
    if exact:
        return exact
    exact = COMPACT_HEADER_TO_FIELD.get(compact)
    if exact:
        return exact

    for part in HEADER_SEPARATOR_RE.split(normalized):
        field = HEADER_TO_FIELD.get(part.strip())
        if field:
            return field
        field = COMPACT_HEADER_TO_FIELD.get(compact_header_name(part))
        if field:
            return field

    for alias, field in sorted(HEADER_TO_FIELD.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in AMBIGUOUS_SUBSTRING_HEADERS:
            continue
        if alias and alias in normalized:
            return field
    for alias, field in sorted(COMPACT_HEADER_TO_FIELD.items(), key=lambda item: len(item[0]), reverse=True):
        if alias in AMBIGUOUS_SUBSTRING_HEADERS:
            continue
        if alias and alias in compact:
            return field
    if normalized in {'name', 'student'}:
        return 'student_name'
    if ('student' in normalized and 'name' in normalized) or ('student' in compact and 'name' in compact):
        return 'student_name'
    if 'اسم' in normalized and 'طالب' in normalized:
        return 'student_name'
    return None

VALID_DEPARTMENTS = [value for value, _label in DEPARTMENTS]
VALID_PROJECT_TYPES = [value for value, _label in PROJECT_TYPES]

DEPARTMENT_ALIASES = {
    'software_engineering': (
        'software_engineering',
        'software engineering',
        'هندسة برمجيات',
        'هندسة البرمجيات',
        'هندسه برمجيات',
        'هندسه البرمجيات',
        'برمجيات',
    ),
    'artificial_intelligence': (
        'artificial_intelligence',
        'artificial intelligence',
        'ai',
        'ذكاء صنعي',
        'ذكاء اصطناعي',
        'الذكاء الصنعي',
        'الذكاء الاصطناعي',
    ),
    'information_security': (
        'information_security',
        'information security',
        'cyber security',
        'cybersecurity',
        'أمن معلومات',
        'امن معلومات',
        'أمن المعلومات',
        'امن المعلومات',
        'أمن النظم والشبكات',
        'امن النظم والشبكات',
        'هندسة أمن النظم والشبكات الحاسوبية',
        'هندسه امن النظم والشبكات الحاسوبيه',
    ),
    'communications': (
        'communications',
        'communication',
        'اتصالات',
        'الاتصالات',
        'هندسة الاتصالات',
        'هندسه الاتصالات',
    ),
    'control_robotics': (
        'control_robotics',
        'control robotics',
        'control and robotics',
        'control & robotics',
        'تحكم وروبوت',
        'تحكم و روبوت',
        'تحكم وروبوتات',
        'تحكم و روبوتات',
        'التحكم والروبوت',
        'التحكم والروبوتات',
    ),
}

PROJECT_TYPE_ALIASES = {
    'seasonal': (
        'seasonal',
        'فصلي',
        'مشروع فصلي',
        'الفصل الصيفي',
        'صيفي',
    ),
    'graduation_1': (
        'graduation_1',
        'graduation 1',
        'graduation i',
        'grad 1',
        'تخرج 1',
        'تخرج1',
        'نخرج1',
        'مشروع تخرج 1',
        'مشروع تخرج1',
        'تخرج أول',
        'تخرج اول',
        'سيمنار أول',
        'سيمنار اول',
    ),
    'graduation_2': (
        'graduation_2',
        'graduation 2',
        'graduation ii',
        'grad 2',
        'تخرج 2',
        'تخرج2',
        'مشروع تخرج 2',
        'مشروع تخرج2',
        'تخرج ثاني',
        'تخرج نهائي',
        'سيمنار ثاني',
    ),
}


def _build_choice_aliases(definitions):
    aliases = {}
    for code, values in definitions.items():
        for value in values:
            aliases[normalize_header_name(value)] = code
            aliases[compact_header_name(value)] = code
    return aliases


DEPARTMENT_ALIAS_MAP = _build_choice_aliases(DEPARTMENT_ALIASES)
PROJECT_TYPE_ALIAS_MAP = _build_choice_aliases(PROJECT_TYPE_ALIASES)


def normalize_department(value):
    normalized = normalize_header_name(value)
    compact = compact_header_name(value)
    if not normalized:
        return ''
    if normalized in DEPARTMENT_ALIAS_MAP:
        return DEPARTMENT_ALIAS_MAP[normalized]
    if compact in DEPARTMENT_ALIAS_MAP:
        return DEPARTMENT_ALIAS_MAP[compact]
    if 'برمج' in normalized or 'software' in normalized:
        return 'software_engineering'
    if 'ذكاء' in normalized or 'اصطناع' in normalized or normalized == 'ai':
        return 'artificial_intelligence'
    if 'امن' in normalized or 'security' in normalized or 'سيبراني' in normalized:
        return 'information_security'
    if 'اتصال' in normalized or 'communication' in normalized:
        return 'communications'
    if 'تحكم' in normalized or 'روبوت' in normalized or 'robot' in normalized or 'control' in normalized:
        return 'control_robotics'
    return str(value or '').strip()


def normalize_project_type(value):
    normalized = normalize_header_name(value)
    compact = compact_header_name(value)
    if not normalized:
        return ''
    if normalized in PROJECT_TYPE_ALIAS_MAP:
        return PROJECT_TYPE_ALIAS_MAP[normalized]
    if compact in PROJECT_TYPE_ALIAS_MAP:
        return PROJECT_TYPE_ALIAS_MAP[compact]
    if 'فصل' in normalized or 'صيف' in normalized or 'season' in normalized:
        return 'seasonal'
    if 'تخرج' in normalized or 'سيمنار' in normalized or 'graduation' in normalized or 'grad' in normalized:
        tokens = normalized.split()
        if '2' in tokens or 'ثاني' in normalized or 'نهائي' in normalized or 'ii' in tokens:
            return 'graduation_2'
        if '1' in tokens or 'اول' in normalized or 'i' in tokens:
            return 'graduation_1'
    return str(value or '').strip()
