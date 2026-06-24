# Project Imports - File Format & Validation

## 📋 Overview

The project imports module accepts Excel (.xlsx) files with a specific structure. This document details the required file format, validation rules, and security checks applied during the import process.

## 🎯 Key Features

- **Excel Template**: Pre-formatted template with required columns
- **Multi-Layer Validation**: File, row, and database-level checks
- **Security Scanning**: Macro and formula detection
- **Duplicate Prevention**: Within-file and cross-database validation
- **Type Coercion**: Automatic data type conversion
- **Error Localization**: Row-level error reporting

## 🏗️ File Format

### Required Columns (Arabic or English Headers)

The first row may use either the Arabic template headers or the English field-name headers.

| Arabic Header | English Header | Type | Required | Description |
|--------------|----------------|------|----------|-------------|
| اسم الطالب | student_name | Text | Yes | Full student name (first and last) |
| الرقم الجامعي | university_id | Text | Yes | Student university ID (becomes username) |
| اسم المشروع | title | Text | Yes | Project title (max 255 chars) |
| مجال المشروع | department | Choice | Yes | Department code |
| اسم المشرف | supervisor_name | Text | Yes | Supervisor username or name |
| نمط المشروع | project_type | Choice | Yes | Project type code |
| رابط الـ Git | github_repo | URL | No | GitHub/GitLab repository URL |

### Valid Department Codes

```python
VALID_DEPARTMENTS = [
    'software_engineering',
    'artificial_intelligence',
    'information_security',
    'communications',
    'control_robotics'
]
```

### Valid Project Type Codes

```python
VALID_PROJECT_TYPES = [
    'seasonal',
    'graduation_1',
    'graduation_2'
]
```

## 📊 Template Structure

### Sample Template (Excel)

| اسم الطالب | الرقم الجامعي | اسم المشروع | مجال المشروع | اسم المشرف | نمط المشروع | رابط الـ Git |
|-----------|---------------|--------------|--------------|------------|-------------|-------------|
| محمد أحمد | 20250001 | نظام إدارة مشاريع التخرج | software_engineering | dr_ali | graduation_1 | https://github.com/example/spu-project |
| سارة خالد | 20250002 | تحليل ذكي للبيانات الجامعية | artificial_intelligence | dr_sara | graduation_2 | |

### Template Features

- **Right-to-Left (RTL)**: Sheet direction set for Arabic
- **Frozen Header**: First row frozen for scrolling
- **Styled Header**: Bold with background color
- **Auto-Width Columns**: Readable column widths
- **Instructions Sheet**: Separate sheet with field descriptions

### Downloading the Template

```bash
# API Endpoint
GET /api/project-imports/template/

# cURL Example
curl -X GET \
  -H "Authorization: Bearer <token>" \
  -o template.xlsx \
  https://spu-portal.edu.sy/api/project-imports/template/
```

## 🔍 Validation Layers

### Layer 1: File Validation

**Checks**:
- ✅ File extension is `.xlsx` (not `.xls`)
- ✅ File size under 10 MB
- ✅ File is a valid Excel workbook
- ✅ No VBA macros present
- ✅ No formula cells in data rows

**Security**:
```python
# Macro detection
if self._contains_vba(content):
    raise ImportValidationError('Files with macros are not permitted')

# Formula blocking
if cell.data_type == 'f' or str(cell.value).startswith('='):
    raise ImportValidationError('Formula cells are not allowed')
```

**Limits**:
- Max file size: 10 MB (`MAX_FILE_SIZE_BYTES`)
- Max rows: 1,000 (`MAX_ROWS`)

### Layer 2: Header Validation

**Checks**:
- ✅ All required headers present
- ✅ Headers in first row
- ✅ Headers match either the Arabic template names or English field names

**Error Example**:
```json
{
  "error": "Missing required headers: اسم الطالب, الرقم الجامعي",
  "details": {
    "missing_headers": ["اسم الطالب", "الرقم الجامعي"]
  }
}
```

### Layer 3: Row Validation

**Per-Row Checks**:

| Field | Validation Rules |
|-------|-----------------|
| **university_id** | Required, non-empty |
| **student_name** | Optional (auto-splits to first/last) |
| **title** | Required, max 255 characters |
| **department** | Required, must be in `VALID_DEPARTMENTS` |
| **project_type** | Required, must be in `VALID_PROJECT_TYPES` |
| **supervisor_name** | Required, non-empty |
| **github_repo** | Optional, must be valid URL (github.com or gitlab.com) |

**Example Validation Errors**:
```json
{
  "row_number": 5,
  "field_name": "department",
  "error_message": "Row 5: Invalid department. Must be one of: software_engineering, artificial_intelligence, networks, information_systems",
  "level": "error",
  "error_type": "invalid_value"
}
```

### Layer 4: Duplicate Detection (Within File)

**Checks**:
- ✅ No duplicate `university_id` within file (ERROR)
- ✅ No duplicate `title` within file (WARNING)

**Example Error**:
```json
{
  "row_number": 10,
  "field_name": "university_id",
  "error_message": "Rows 5, 10: Duplicate university ID 20250001 found within file",
  "level": "error",
  "error_type": "duplicate"
}
```

**Example Warning**:
```json
{
  "row_number": 8,
  "field_name": "title",
  "error_message": "Rows 3, 8: Duplicate project title 'Project Management System' found within file",
  "level": "warning",
  "error_type": "duplicate"
}
```

### Layer 5: Database Conflict Detection

**Checks**:
- ✅ `university_id` not already used by non-student
- ✅ Student + title combination not already in database
- ✅ Student doesn't have active proposal
- ✅ Student doesn't have accepted application
- ✅ Student not member of active team

**Conflict Types**:

| Conflict | Description | Action |
|----------|-------------|--------|
| **Non-student role** | University ID exists with doctor/HoD role | ERROR: Block import |
| **Duplicate project** | Same student + title exists | ERROR: Block import |
| **Active proposal** | Student has proposal in progress | ERROR: Block import |
| **Accepted application** | Student has accepted application | ERROR: Block import |
| **Team member** | Student is team member elsewhere | ERROR: Block import |

**Example Error**:
```json
{
  "row_number": 7,
  "field_name": "university_id",
  "error_message": "Row 7: Student 20250001 already has an active proposal",
  "level": "error",
  "error_type": "active_project"
}
```

### Layer 6: Supervisor Resolution

**Matching Logic**:
1. Try exact username match
2. Try exact full name match
3. Try partial name match

**Supervisor Ambiguity**:
- If multiple doctors match the name → ERROR
- If no match found → Create new supervisor

**Example Error**:
```json
{
  "row_number": 12,
  "field_name": "supervisor_name",
  "error_message": "Row 12: Supervisor name 'أحمد' matches multiple doctors. Use exact username or create the supervisor manually first.",
  "level": "error",
  "error_type": "supervisor_match"
}
```

## 🔒 Security Validation

### Macro Detection

```python
def _contains_vba(self, content: bytes) -> bool:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            return any(name.lower().endswith('vbaproject.bin') 
                      for name in archive.namelist())
    except zipfile.BadZipFile:
        return False
```

**Rationale**: Macros can execute arbitrary code and pose security risks.

### Formula Blocking

```python
if cell.data_type == 'f' or str(cell.value or '').startswith('='):
    raise ImportValidationError('Formula cells are not allowed')
```

**Rationale**: Formulas can reference external data or cause injection attacks.

### URL Validation

```python
def _valid_repo_url(self, value):
    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return False
    host = parsed.netloc.lower()
    return (host == 'github.com' or host.endswith('.github.com') or 
            host == 'gitlab.com' or host.endswith('.gitlab.com'))
```

**Allowed Hosts**:
- `github.com` and subdomains
- `gitlab.com` and subdomains

## 📊 Data Type Handling

### Cell Value Normalization

```python
def normalize_cell_value(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # Convert 20250001.0 → 20250001
    return str(value).strip()
```

**Examples**:
- `None` → `""`
- `20250001.0` → `"20250001"`
- `"  text  "` → `"text"`

### Empty Row Detection

Rows where all cells are empty are automatically skipped:

```python
if all(normalize_cell_value(cell.value) == '' for cell in excel_row):
    continue  # Skip empty row
```

## 🎨 Frontend Integration

### File Upload with Validation

```javascript
async function uploadAndValidate(file) {
  // Step 1: Client-side pre-checks
  const MAX_SIZE = 10 * 1024 * 1024; // 10 MB
  
  if (!file.name.endsWith('.xlsx')) {
    showError('Please upload an .xlsx file');
    return;
  }
  
  if (file.size > MAX_SIZE) {
    showError('File size exceeds 10 MB limit');
    return;
  }
  
  // Step 2: Server validation (dry run)
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch('/api/project-imports/projects/?dry_run=true', {
    method: 'POST',
    body: formData,
    credentials: 'include'
  });
  
  const result = await response.json();
  
  // Step 3: Display validation results
  if (result.validation_errors.length > 0) {
    displayErrorTable(result.errors_by_type);
  } else {
    showPreviewSummary(result);
  }
}

function displayErrorTable(errorsByType) {
  const table = document.createElement('table');
  
  for (const [errorType, errors] of Object.entries(errorsByType)) {
    const section = document.createElement('tr');
    section.innerHTML = `<th colspan="3">${errorType} errors</th>`;
    table.appendChild(section);
    
    errors.forEach(error => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>Row ${error.row_number}</td>
        <td>${error.field_name}</td>
        <td>${error.error_message}</td>
      `;
      table.appendChild(row);
    });
  }
  
  document.getElementById('errors-container').appendChild(table);
}
```

## 🐛 Troubleshooting

### Common Validation Errors

**1. "Missing required headers"**
- **Cause**: Excel headers don't match expected Arabic names
- **Solution**: Download and use the official template

**2. "Invalid department"**
- **Cause**: Department value not in allowed list
- **Solution**: Use values from `VALID_DEPARTMENTS` list

**3. "Supervisor name matches multiple doctors"**
- **Cause**: Ambiguous supervisor name (e.g., "أحمد")
- **Solution**: Use exact username (e.g., "dr_ahmad") or more specific name

**4. "Student already has an active proposal"**
- **Cause**: Student has existing project in database
- **Solution**: Complete or cancel existing project first

**5. "Formula cells are not allowed"**
- **Cause**: Cell contains Excel formula
- **Solution**: Convert formulas to values (Paste Special → Values)

**6. "Files with macros are not permitted"**
- **Cause**: File contains VBA macros
- **Solution**: Save as `.xlsx` without macros

### Validation Checklist

Before importing, verify:

- [ ] File is `.xlsx` format (not `.xls`)
- [ ] File size under 10 MB
- [ ] All required columns present
- [ ] Department codes are valid
- [ ] Project type codes are valid
- [ ] No duplicate university IDs
- [ ] Supervisor names are specific enough
- [ ] No formulas in data cells
- [ ] No macros in workbook
- [ ] Git URLs are valid (if provided)

## 🔗 Related Documentation

- [Module Overview](00-MODULE-OVERVIEW.md)
- [Import Process](01-IMPORT-PROCESS.md)
- [User Management](03-USER-MANAGEMENT.md)
- [API Reference](04-API-REFERENCE.md)

## 📦 Code References

- **Validators**: `backend/project_imports/validators.py`
  - `FileValidator.parse_workbook()`
  - `RowValidator.validate_rows()`
  - `RowValidator.check_duplicates_in_file()`
  - `RowValidator.check_duplicates_in_db()`
- **Constants**: `backend/project_imports/constants.py`
  - `REQUIRED_HEADERS`
  - `VALID_DEPARTMENTS`
  - `VALID_PROJECT_TYPES`
- **Template**: `backend/project_imports/templates.py`
  - `TemplateGenerator.generate_template()`

---

**Document Version**: 1.0  
**Last Updated**: June 24, 2026  
**Maintained By**: Development Team
