# Project Imports - Import Process

## 📋 Overview

The import process is a two-phase workflow that enables super administrators to bulk import graduation projects, students, and supervisors into the SPU Student Portal. The system provides a preview mode for validation before committing changes to the database.

## 🎯 Key Features

- **Two-Phase Import**: Preview before execution
- **Atomic Transactions**: All-or-nothing database operations
- **Comprehensive Validation**: Multi-layer error checking
- **Concurrency Control**: Prevents simultaneous imports
- **Audit Trail**: Complete import history tracking
- **Error Recovery**: Detailed error reporting with CSV export
- **Duplicate Prevention**: Checks file and database for conflicts

## 🏗️ Architecture

### Import Flow Components

```
┌─────────────┐
│ File Upload │
└──────┬──────┘
       │
       v
┌──────────────────┐
│ File Validation  │ ← Size, format, macros, formulas
└──────┬───────────┘
       │
       v
┌──────────────────┐
│ Row Validation   │ ← Required fields, data types
└──────┬───────────┘
       │
       v
┌──────────────────┐
│ Duplicate Check  │ ← Within file and database
└──────┬───────────┘
       │
       v
┌──────────────────┐
│ User Mapping     │ ← Student/supervisor resolution
└──────┬───────────┘
       │
       ├─ Dry Run? ─> Return Preview Result + preview_result_id
       │
       v
┌──────────────────┐
│ Execute Import   │ ← Create users and projects
└──────┬───────────┘
       │
       v
┌──────────────────┐
│ Create Session   │ ← Save import history
└──────────────────┘
```

### Service Layers

| Service | Responsibility |
|---------|---------------|
| **ImportService** | Orchestrates entire import workflow |
| **FileValidator** | Validates file structure and security |
| **RowValidator** | Validates row data and checks conflicts |
| **UserMapper** | Resolves/creates students and supervisors |
| **ProjectCreator** | Creates projects, applications, and boards |

## 🔄 Import Workflow

### Phase 1: Preview (Dry Run)

**Purpose**: Validate the file without making changes

**Steps**:
1. Upload Excel file with `dry_run=true`
2. File structure validation
3. Row-level validation
4. Duplicate detection (within file)
5. Database conflict checking
6. User mapping preview
7. Return validation result + `preview_result_id`

**Response**:
```json
{
  "dry_run": true,
  "status": "preview",
  "preview_result_id": "uuid-here",
  "file_hash": "sha256-hash",
  "total_rows_processed": 100,
  "valid_rows_count": 95,
  "invalid_rows_count": 5,
  "users_to_create": {
    "students": ["20250001", "20250002"],
    "supervisors": [
      {"username": "dr_ahmad", "full_name": "أحمد محمد", "department": "software_engineering"}
    ]
  },
  "projects_to_create": 95,
  "validation_errors": [...],
  "warnings": [...],
  "errors_by_type": {
    "validation": [...],
    "duplicate": [...],
    "supervisor_match": [...]
  },
  "execution_time_seconds": 1.234
}
```

### Phase 2: Execute Import

**Purpose**: Commit changes to database

**Steps**:
1. Upload same file with `preview_result_id` from Phase 1
2. Verify file hash matches preview
3. Verify preview hasn't expired (5-minute timeout)
4. Re-validate file
5. **Start transaction**
6. Create student accounts (if needed)
7. Create supervisor accounts (if needed)
8. Create proposals, applications, and boards
9. Create ImportSession and ImportRow records
10. **Commit transaction**
11. Return import result

**Response**:
```json
{
  "import_session_id": "uuid-here",
  "dry_run": false,
  "status": "success",
  "total_rows_processed": 100,
  "valid_rows_count": 95,
  "successful_imports": 95,
  "created_students_count": 50,
  "created_supervisors_count": 3,
  "created_projects_count": 95,
  "validation_errors": [],
  "warnings": [],
  "execution_time_seconds": 5.678
}
```

## 📡 API Integration

### Complete Import Flow

```python
import requests

API_BASE = "https://spu-portal.edu.sy/api/project-imports"
headers = {"Authorization": "Bearer <token>"}

# Step 1: Preview
with open("projects.xlsx", "rb") as f:
    response = requests.post(
        f"{API_BASE}/projects/?dry_run=true",
        files={"file": f},
        headers=headers
    )

preview_result = response.json()
if preview_result["validation_errors"]:
    print("Validation errors found!")
    for error in preview_result["validation_errors"]:
        print(f"Row {error['row_number']}: {error['error_message']}")
    exit(1)

preview_result_id = preview_result["preview_result_id"]
file_hash = preview_result["file_hash"]
print(f"Preview successful! Will create:")
print(f"  - {preview_result['created_students_count']} students")
print(f"  - {preview_result['created_supervisors_count']} supervisors")
print(f"  - {preview_result['created_projects_count']} projects")

# Step 2: Confirm and execute
with open("projects.xlsx", "rb") as f:
    response = requests.post(
        f"{API_BASE}/projects/",
        files={"file": f},
        data={"preview_result_id": preview_result_id},
        headers=headers
    )

result = response.json()
if result["status"] == "success":
    print(f"Import completed successfully!")
    print(f"Session ID: {result['import_session_id']}")
else:
    print("Import failed!")
```

## 🔒 Concurrency Control

### Lock Mechanism

To prevent simultaneous imports by the same user:

```python
lock_key = f'project_import_in_progress_{user_id}'
if not cache.add(lock_key, True, timeout=3600):
    return 409 Conflict
```

**Lock Behavior**:
- One import per user at a time
- Lock expires after 1 hour
- Lock released after import completion
- Prevents file hash conflicts in preview cache

## 🔄 Transaction Safety

All database modifications are wrapped in an atomic transaction:

```python
with transaction.atomic():
    user_map = self.user_mapper.resolve_users(valid_rows)
    created = self.project_creator.create_projects(valid_rows, user_map, admin)
    self._mark_success(session, valid_rows, created, user_map)
```

**Rollback Triggers**:
- Any validation error
- Database constraint violation
- User creation failure
- Project creation failure
- Session recording failure

**Result**: All changes are rolled back, leaving database unchanged.

## 📊 Import Session Tracking

### ImportSession Model

Every import attempt creates an `ImportSession` record:

```python
{
  "id": "uuid",
  "super_admin": user_object,
  "filename": "projects.xlsx",
  "file_size_bytes": 1024000,
  "total_rows": 100,
  "successful_rows": 95,
  "failed_rows": 5,
  "started_at": "2026-06-24T10:00:00Z",
  "completed_at": "2026-06-24T10:00:05Z",
  "status": "success",  # or "pending", "failed"
  "error_summary": ""
}
```

### ImportRow Model

Each row in the file gets an `ImportRow` record:

```python
{
  "session": session_object,
  "row_number": 2,
  "university_id": "20250001",
  "project_title": "Project Management System",
  "status": "success",  # or "failed", "skipped"
  "error_message": "",
  "created_student": user_object,
  "created_project": proposal_object
}
```

## 🐛 Error Handling

### Error Types

| Error Type | Description | HTTP Status |
|-----------|-------------|-------------|
| **File Validation** | Invalid format, size, macros | 400 |
| **Row Validation** | Missing fields, invalid values | 400 |
| **Duplicate** | Duplicate within file or database | 400 |
| **Conflict** | Student has active project | 400 |
| **Supervisor Match** | Multiple supervisors match name | 400 |
| **Preview Expired** | Preview timeout (5 minutes) | 400 |
| **File Mismatch** | File hash doesn't match preview | 400 |
| **Concurrency** | Another import in progress | 409 |
| **Server Error** | Unexpected failure | 500 |

### Error Response Format

```json
{
  "status": "failed",
  "validation_errors": [
    {
      "row_number": 5,
      "field_name": "university_id",
      "error_message": "Row 5: University ID is required",
      "level": "error",
      "error_type": "validation"
    }
  ],
  "errors_by_type": {
    "validation": [
      {
        "row_number": 5,
        "field_name": "university_id",
        "error_message": "Row 5: University ID is required"
      }
    ],
    "duplicate": [
      {
        "row_number": 10,
        "field_name": "university_id",
        "error_message": "Row 10: Duplicate university ID 20250001"
      }
    ]
  }
}
```

## 🎨 Frontend Integration Example

```javascript
async function importProjects(file) {
  const formData = new FormData();
  formData.append('file', file);
  
  try {
    // Step 1: Preview
    const previewResponse = await fetch('/api/project-imports/projects/?dry_run=true', {
      method: 'POST',
      body: formData,
      credentials: 'include'
    });
    
    const previewResult = await previewResponse.json();
    
    if (previewResult.validation_errors.length > 0) {
      displayErrors(previewResult.validation_errors);
      return;
    }
    
    // Show preview summary
    const confirmed = await showConfirmDialog({
      students: previewResult.created_students_count,
      supervisors: previewResult.created_supervisors_count,
      projects: previewResult.created_projects_count
    });
    
    if (!confirmed) return;
    
    // Step 2: Execute
    const executeFormData = new FormData();
    executeFormData.append('file', file);
    executeFormData.append('preview_result_id', previewResult.preview_result_id);
    
    const executeResponse = await fetch('/api/project-imports/projects/', {
      method: 'POST',
      body: executeFormData,
      credentials: 'include'
    });
    
    const result = await executeResponse.json();
    
    if (result.status === 'success') {
      showSuccess(`Imported ${result.successful_imports} projects successfully!`);
    } else {
      displayErrors(result.validation_errors);
    }
    
  } catch (error) {
    showError(`Import failed: ${error.message}`);
  }
}
```

## 🐛 Troubleshooting

### Common Issues

**1. Preview expires before execution**
- **Cause**: 5-minute preview cache timeout
- **Solution**: Execute import within 5 minutes or re-run preview

**2. File hash mismatch**
- **Cause**: File modified between preview and execution
- **Solution**: Use the exact same file for both phases

**3. Concurrent import conflict**
- **Cause**: Previous import still in progress
- **Solution**: Wait for previous import to complete or check session status

**4. Transaction rollback**
- **Cause**: Validation error or database constraint
- **Solution**: Check error messages and fix data

**5. Supervisor ambiguity**
- **Cause**: Multiple doctors match the supervisor name
- **Solution**: Use exact username or create supervisor manually first

## 🔗 Related Documentation

- [File Format & Validation](02-FILE-FORMAT-VALIDATION.md)
- [User Management](03-USER-MANAGEMENT.md)
- [API Reference](04-API-REFERENCE.md)
- [Security & Performance](05-SECURITY-PERFORMANCE.md)

## 📦 Code References

- **Services**: `backend/project_imports/services.py`
  - `ImportService.execute_import()`
  - `ImportService._validate_preview()`
  - `ImportService._cache_preview()`
- **Views**: `backend/project_imports/views.py`
  - `ImportProjectsView.post()`
- **Models**: `backend/project_imports/models.py`
  - `ImportSession`
  - `ImportRow`

---

**Document Version**: 1.0  
**Last Updated**: June 24, 2026  
**Maintained By**: Development Team
