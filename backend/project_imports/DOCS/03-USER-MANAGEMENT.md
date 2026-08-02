# Project Imports - User Management

## 📋 Overview

The project imports module automatically creates student and supervisor (doctor) accounts during the import process. This document details the account creation logic, username generation, password management, and user resolution strategies.

## 🎯 Key Features

- **Auto Student Creation**: Generates student accounts from university IDs
- **Auto Supervisor Creation**: Creates doctor accounts when needed
- **Smart Supervisor Resolution**: Matches existing supervisors by username or name
- **Username Normalization**: Converts names to valid usernames
- **Secure Password Generation**: Configurable temporary password format
- **Must-Change-Password**: Forces users to change password on first login
- **Department Assignment**: Auto-assigns department from import data
- **Duplicate Prevention**: Checks existing users before creation

## 🏗️ Architecture

### User Mapping Flow

```
┌─────────────────────┐
│ Parse Import Rows   │
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ Extract User IDs    │
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ Check Existing      │ ← Query database
│ Students            │
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ Resolve Supervisors │ ← Match by username/name
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ Build User Plan     │ ← Preview mode stops here
└──────────┬──────────┘
           │
           v (Execute mode)
┌─────────────────────┐
│ Create Students     │
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ Create Supervisors  │
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ Return User Map     │
└─────────────────────┘
```

## 👨‍🎓 Student Account Creation

### Student Fields

| Field | Source | Logic |
|-------|--------|-------|
| **username** | `university_id` | Used as-is (e.g., "20250001") |
| **password** | Generated | `SPU{university_id}@2025-2026` |
| **first_name** | `student_name` | First word in name |
| **last_name** | `student_name` | Remaining words |
| **role** | Fixed | `'student'` |
| **department** | `department` | From import row |
| **must_change_password** | Fixed | `True` |
| **is_active** | Fixed | `True` |

### Creation Logic

```python
def resolve_users(self, rows):
    # Get existing students
    student_ids = {row['university_id'] for row in rows}
    students = User.objects.filter(username__in=student_ids)
    
    # Create missing students
    for row in rows:
        if university_id in students:
            continue  # Skip existing
        
        first_name, last_name = self.parse_student_name(row['student_name'])
        
        student = User.objects.create_user(
            username=university_id,
            password=self.generate_password(university_id),
            first_name=first_name,
            last_name=last_name,
            role='student',
            department=row['department'],
            must_change_password=True,
            is_active=True
        )
        students[university_id] = student
```

### Name Parsing

```python
def parse_student_name(self, name):
    """
    Split name into first and last.
    Examples:
      "محمد أحمد" → first="محمد", last="أحمد"
      "سارة" → first="سارة", last=""
      "" → first="", last=""
    """
    parts = str(name or '').strip().split(None, 1)
    if not parts:
        return '', ''
    return parts[0], parts[1] if len(parts) > 1 else ''
```

### Password Generation

```python
def generate_password(self, identifier):
    """
    Generate temporary password with configurable format.
    Default: SPU{identifier}@2025-2026
    Example: SPU20250001@2025-2026
    """
    fmt = getattr(settings, 'IMPORT_TEMP_PASSWORD_FORMAT', None) or \
          os.getenv('IMPORT_TEMP_PASSWORD_FORMAT', DEFAULT_TEMP_PASSWORD_FORMAT)
    
    password = fmt.format(identifier=identifier)
    
    try:
        validate_password(password)
    except DjangoValidationError:
        # If format doesn't meet Django password requirements, add complexity
        password = f'{password}Aa1!'
        validate_password(password)
    
    return password
```

**Configuration**:

```python
# settings.py
IMPORT_TEMP_PASSWORD_FORMAT = 'SPU{identifier}@2025-2026'

# Environment Variable
IMPORT_TEMP_PASSWORD_FORMAT=YourCustomFormat{identifier}!
```

**Password Requirements**:
- Must pass Django's `validate_password()` checks
- Automatically adds `Aa1!` suffix if format fails validation
- Default format: `SPU20250001@2025-2026`

## 👨‍🏫 Supervisor Account Creation

### Supervisor Resolution Strategy

The system attempts to match supervisors in this order:

1. **Exact username match** (highest priority)
2. **Exact full name match**
3. **Partial name match**
4. **Create new supervisor** (if no match)

### Matching Logic

```python
def find_supervisor_by_name(self, name, *, lock=False):
    """
    Find doctor by username or name.
    Returns list of matches (empty, one, or multiple).
    """
    needle = str(name or '').strip().lower()
    if not needle:
        return []
    
    qs = User.objects.filter(role='doctor')
    if lock:
        qs = qs.select_for_update()  # Lock during execution
    
    matches = []
    exact_matches = []
    
    for user in qs:
        full_name = (user.get_full_name() or '').strip()
        haystacks = [user.username.lower(), full_name.lower()]
        
        if needle in haystacks:
            exact_matches.append(user)  # Exact match
        elif any(needle in value for value in haystacks if value):
            matches.append(user)  # Partial match
    
    return exact_matches or matches
```

### Ambiguity Handling

If multiple supervisors match the name → **ERROR**

```json
{
  "row_number": 5,
  "field_name": "supervisor_name",
  "error_message": "Row 5: Supervisor name 'أحمد' matches multiple doctors. Use exact username or create the supervisor manually first.",
  "level": "error",
  "error_type": "supervisor_match"
}
```

**Resolution**:
- Use exact username (e.g., `dr_ahmad`)
- Use full unique name (e.g., `أحمد محمد الخطيب`)
- Create supervisor manually before import

### Username Normalization

When creating new supervisors, names are normalized to usernames:

```python
def normalize_username(self, name):
    """
    Convert name to valid username.
    Examples:
      "Dr. Ahmad" → "dr_ahmad"
      "أحمد محمد" → "______" (Arabic removed) → "doctor_abcd1234"
      "user@#$name" → "user_name"
    """
    # Remove non-alphanumeric (keep underscores)
    base = self.username_cleaner.sub('_', str(name or '').strip())
    base = base.strip('_').lower()
    
    if not base:
        # Fallback: generate UUID-based username
        base = f'doctor_{uuid.uuid5(uuid.NAMESPACE_DNS, str(name)).hex[:10]}'
    
    username = base[:120]  # Django username max length
    
    # Handle duplicates
    candidate = username
    suffix = 1
    while User.objects.filter(username=candidate).exists():
        suffix += 1
        candidate = f'{username[:110]}_{suffix}'
    
    return candidate
```

**Examples**:
- `"Dr. Ali"` → `"dr_ali"`
- `"محمد أحمد"` → `"doctor_a1b2c3d4e5"` (UUID-based)
- `"ahmad"` (if exists) → `"ahmad_2"`

### Supervisor Fields

| Field | Source | Logic |
|-------|--------|-------|
| **username** | Normalized name | See normalization logic |
| **password** | Generated | `SPU{username}@2025-2026` |
| **first_name** | `supervisor_name` | First word |
| **last_name** | `supervisor_name` | Remaining words |
| **role** | Fixed | `'doctor'` |
| **department** | `department` | From import row |
| **must_change_password** | Fixed | `True` |
| **is_active** | Fixed | `True` |

### Creation Logic

```python
for row in rows:
    name = row.get('supervisor_name', '').strip()
    existing = self.find_supervisor_by_name(name, lock=True)
    
    if existing:
        supervisors[row['row_number']] = existing[0]
        continue
    
    username = self.normalize_username(name)
    
    # Check if already created in this batch
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
        is_active=True
    )
    
    supervisors[row['row_number']] = supervisor
    supervisors[username] = supervisor  # Cache for deduplication
    created_supervisors.append(supervisor)
```

## 📊 User Plan (Preview Mode)

In preview mode, the system builds a plan without creating users:

```json
{
  "users_to_create": {
    "students": ["20250001", "20250002", "20250003"],
    "supervisors": [
      {
        "username": "dr_ahmad",
        "full_name": "أحمد محمد",
        "department": "software_engineering"
      },
      {
        "username": "dr_sara",
        "full_name": "سارة خالد",
        "department": "artificial_intelligence"
      }
    ]
  },
  "created_students_count": 3,
  "created_supervisors_count": 2
}
```

This allows the admin to review what will be created before execution.

## 🔒 Security Considerations

### Password Security

- Temporary passwords are hashed before storage (Django's `create_user()`)
- `must_change_password` flag forces password change on first login
- Password format is configurable via settings/environment

### Username Uniqueness

- Usernames are guaranteed unique via database constraints
- Duplicate detection during normalization
- UUID fallback for non-Latin characters

### Database Locking

During execution mode, supervisor lookup uses `select_for_update()` to prevent race conditions:

```python
qs = User.objects.select_for_update().filter(role='doctor')
```

### Role Enforcement

- Students are always created with `role='student'`
- Supervisors are always created with `role='doctor'`
- No elevation of privileges possible via import

## 🎨 Frontend Integration

### Display User Creation Summary

```javascript
function showUserCreationSummary(result) {
  const summary = document.createElement('div');
  
  summary.innerHTML = `
    <h3>Users to be created:</h3>
    <ul>
      <li>
        <strong>Students:</strong> ${result.created_students_count}
        <ul>
          ${result.users_to_create.students.map(id => 
            `<li>${id}</li>`
          ).join('')}
        </ul>
      </li>
      <li>
        <strong>Supervisors:</strong> ${result.created_supervisors_count}
        <ul>
          ${result.users_to_create.supervisors.map(sup => 
            `<li>${sup.username} (${sup.full_name})</li>`
          ).join('')}
        </ul>
      </li>
    </ul>
    <p>Default password format: SPU{identifier}@2025-2026</p>
    <p class="warning">Users must change password on first login.</p>
  `;
  
  return summary;
}
```

## 🐛 Troubleshooting

### Common Issues

**1. "Supervisor name matches multiple doctors"**
- **Problem**: Name is ambiguous (e.g., "أحمد")
- **Solution**: 
  - Use exact username: `dr_ahmad`
  - Use more specific name: `أحمد محمد الخطيب`
  - Create supervisor manually first

**2. Student username already exists**
- **Problem**: University ID already used
- **Solution**: Check existing user's role. If non-student, cannot import.

**3. Password doesn't meet requirements**
- **Problem**: Custom password format fails Django validation
- **Solution**: System automatically adds `Aa1!` suffix

**4. Arabic names generate strange usernames**
- **Problem**: Non-Latin characters removed during normalization
- **Solution**: System falls back to UUID-based username (safe)

### Best Practices

**For Clean Imports**:
1. Create all supervisors manually before import (recommended)
2. Use exact supervisor usernames in Excel file
3. Verify no duplicate university IDs
4. Ensure student names are properly formatted

**For Supervisor Management**:
1. Assign meaningful usernames to supervisors manually
2. Document supervisor username mapping for admins
3. Consider creating a supervisor reference sheet

## 🔗 Related Documentation

- [Module Overview](00-MODULE-OVERVIEW.md)
- [Import Process](01-IMPORT-PROCESS.md)
- [File Format & Validation](02-FILE-FORMAT-VALIDATION.md)
- [API Reference](04-API-REFERENCE.md)

## 📦 Code References

- **Services**: `backend/project_imports/services.py`
  - `UserMapper.parse_student_name()`
  - `UserMapper.generate_password()`
  - `UserMapper.build_plan()`
  - `UserMapper.resolve_users()`
  - `UserMapper.find_supervisor_by_name()`
  - `UserMapper.normalize_username()`
- **Constants**: `backend/project_imports/constants.py`
  - `DEFAULT_TEMP_PASSWORD_FORMAT`
- **Models**: `backend/accounts/models.py`
  - `User` model

---

**Document Version**: 1.0  
**Last Updated**: June 24, 2026  
**Maintained By**: Development Team
