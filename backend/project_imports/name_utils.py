import re
import unicodedata


ARABIC_DIACRITICS_RE = re.compile(r'[\u064b-\u065f\u0670]')
ARABIC_TATWEEL = '\u0640'
NON_BREAKING_SPACES = '\u00a0\u2007\u202f'
WHITESPACE_RE = re.compile(r'[ \t\f\v%s]+' % NON_BREAKING_SPACES)
USERNAME_UNSAFE_RE = re.compile(r'[^a-z0-9_]+')
SUPERVISOR_SEPARATOR_RE = re.compile(
    r'\r\n|\r|\n|[+\\/|,،;&؛]+|\band\b|(?:(?<=^)|(?<=\s))و(?=\s|$)',
    re.IGNORECASE,
)

ARABIC_CHAR_TRANSLATION = str.maketrans({
    'أ': 'ا',
    'إ': 'ا',
    'آ': 'ا',
    'ٱ': 'ا',
    'ى': 'ي',
    'ؤ': 'و',
    'ئ': 'ي',
})

TITLE_PREFIX_RE = re.compile(
    r'^(?:'
    r'(?:أ|ا)\s*\.\s*د\s*\.?|(?:أ|ا)\s+د\s+|'  # أ.د. / ا.د. / أ د
    r'د\s*\.|د(?=\s)|دكتور|الدكتور|'
    r'م\s*\.|م(?=\s)|مهندس|المهندس|'
    r'(?:أ|ا)\s*\.|(?:أ|ا)(?=\s)|أستاذ|استاذ|الأستاذ|الاستاذ|'
    r'prof\.?|dr\.?|eng\.?'
    r')\s*',
    re.IGNORECASE,
)

ARABIC_WORD_TRANSLITERATION = {
    'انس': 'anas',
    'عامر': 'amir',
    'محمد': 'mohammad',
    'احمد': 'ahmad',
    'عبد': 'abd',
    'العزيز': 'alaziz',
    'عزيز': 'aziz',
    'خورشيد': 'khurshid',
    'علي': 'ali',
    'حسن': 'hasan',
    'حسين': 'hussein',
    'خالد': 'khaled',
    'محمود': 'mahmoud',
    'مصطفي': 'mustafa',
    'مصطفى': 'mustafa',
    'يوسف': 'yousef',
    'ابراهيم': 'ibrahim',
    'ابراهیم': 'ibrahim',
    'سعيد': 'saeed',
    'سعد': 'saad',
    'رامي': 'rami',
    'عماد': 'imad',
    'ايمن': 'ayman',
    'سامر': 'samer',
    'ماهر': 'maher',
    'فادي': 'fadi',
    'لؤي': 'loay',
    'لوي': 'loay',
    'باسل': 'basel',
    'نزار': 'nizar',
    'طارق': 'tarek',
    'عبدالله': 'abdullah',
    'عبد': 'abd',
    'الله': 'allah',
}

ARABIC_CHAR_TRANSLITERATION = {
    'ا': 'a',
    'ب': 'b',
    'ت': 't',
    'ث': 'th',
    'ج': 'j',
    'ح': 'h',
    'خ': 'kh',
    'د': 'd',
    'ذ': 'dh',
    'ر': 'r',
    'ز': 'z',
    'س': 's',
    'ش': 'sh',
    'ص': 's',
    'ض': 'd',
    'ط': 't',
    'ظ': 'z',
    'ع': 'a',
    'غ': 'gh',
    'ف': 'f',
    'ق': 'q',
    'ك': 'k',
    'ک': 'k',
    'ل': 'l',
    'م': 'm',
    'ن': 'n',
    'ه': 'h',
    'ة': 'h',
    'و': 'w',
    'ي': 'y',
    'ى': 'a',
    'ء': '',
}


def normalize_arabic_text(value):
    normalized = unicodedata.normalize('NFKC', str(value or ''))
    normalized = normalized.translate(ARABIC_CHAR_TRANSLATION)
    normalized = normalized.replace(ARABIC_TATWEEL, '')
    normalized = ARABIC_DIACRITICS_RE.sub('', normalized)
    return normalized


def normalize_person_spacing(value, *, keep_line_breaks=False):
    normalized = unicodedata.normalize('NFKC', str(value or ''))
    for space in NON_BREAKING_SPACES:
        normalized = normalized.replace(space, ' ')
    normalized = normalized.replace('\t', ' ')
    if not keep_line_breaks:
        normalized = re.sub(r'[\r\n]+', ' ', normalized)
    return WHITESPACE_RE.sub(' ', normalized).strip()


def strip_person_titles(value):
    name = normalize_person_spacing(value)
    previous = None
    while previous != name:
        previous = name
        name = TITLE_PREFIX_RE.sub('', name).strip()
    return name


def split_supervisor_names(value):
    """Split one spreadsheet supervisor cell into deterministic supervisor names.

    Newlines and explicit punctuation split names. A plain space never splits names
    because Arabic names naturally contain spaces. Standalone Arabic "و" is a
    separator only when surrounded by whitespace.
    """
    normalized = normalize_person_spacing(value, keep_line_breaks=True)
    if not normalized:
        return []

    fragments = SUPERVISOR_SEPARATOR_RE.split(normalized)
    names = []
    seen = set()
    for fragment in fragments:
        name = normalize_person_spacing(fragment)
        if not name:
            continue
        key = supervisor_identity_key(name)
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def supervisor_identity_key(value):
    clean_name = strip_person_titles(value)
    normalized = normalize_arabic_text(clean_name).casefold()
    return normalize_person_spacing(normalized)


def parse_person_name(value):
    clean_name = strip_person_titles(value)
    parts = clean_name.split(None, 1)
    if not parts:
        return '', ''
    return parts[0], parts[1] if len(parts) > 1 else ''


def username_base_from_name(value):
    clean_name = strip_person_titles(value)
    normalized = normalize_arabic_text(clean_name).casefold()
    tokens = []
    for token in normalized.split():
        tokens.append(ARABIC_WORD_TRANSLITERATION.get(token, transliterate_token(token)))
    base = '_'.join(token for token in tokens if token)
    base = USERNAME_UNSAFE_RE.sub('_', base).strip('_')
    base = re.sub(r'_+', '_', base)
    return base[:120]


def transliterate_token(token):
    result = []
    for char in token:
        if char.isascii():
            result.append(char.lower() if char.isalnum() else '_')
        else:
            result.append(ARABIC_CHAR_TRANSLITERATION.get(char, ''))
    return ''.join(result)
