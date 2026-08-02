# Project Imports - API Reference

## 📋 Overview

Complete REST API documentation for the project imports module. All endpoints require super admin authentication (Dean role with `is_superuser=True`).

## 🎯 Base URL

```
/api/project-imports/
```

## 🔒 Authentication

All endpoints require:
- **Authentication**: JWT token (HttpOnly cookie or Bearer token)
- **Permission**: `IsSuperAdmin` (Dean + is_superuser)
- **Rate Limiting**: 5 requests per hour per user

### Permission Check

```python
class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            user.is_authenticated and
            user.role == 'dean' and
            user.is_superuser
        )
```

### Rate Limiting

```python
class ImportRateThrottle(UserRateThrottle):
    scope = 'import'
    rate = '5/hour'
```

**Response on Rate Limit Exceeded**:
```json
{
  "detail": "Request was throttled. Expected available in 3600 seconds."
}
```

## 📡 Endpoints

### 1. Import Projects

Import graduation projects from Excel file.

#### Endpoint

```
POST /api/project-imports/projects/
```

#### Request

**Headers**:
```
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

**Query Parameters**:
- `dry_run` (optional): `"true"` for preview mode, omit for execution

**Form Data**:
- `file` (required): Excel file (.xlsx)
- `preview_result_id` (optional): ID from preview response (required for execution)

#### Request Example (Preview)

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -F "file=@projects.xlsx" \
  "https://spu-portal.edu.sy/api/project-imports/projects/?dry_run=true"
```

#### Request Example (Execute)

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -F "file=@projects.xlsx" \
  -F "preview_result_id=<uuid-from-preview>" \
  "https://spu-portal.edu.sy/api/project-imports/projects/"
```

#### Response (Preview - Success)

**Status**: `200 OK`

```json
{
  "import_session_id": null,
  "preview_result_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_hash": "abc123def456...",
  "dry_run": true,
  "status": "preview",
  "total_rows_processed": 100,
  "valid_rows_count": 95,
  "invalid_rows_count": 5,
  "successful_imports": 0,
  "failed_imports": 5,
  "created_students_count": 0,
  "created_supervisors_count": 0,
  "created_projects_count": 0,
  "users_to_create": {
    "students": ["20250001", "20250002", "20250003"],
    "supervisors": [
      {
        "username": "dr_ahmad",
        "full_name": "أحمد محمد",
        "department": "software_engineering"
      }
    ]
  },
  "projects_to_create": 95,
  "validation_errors": [
    {
      "row_number": 10,
      "field_name": "department",
      "error_message": "Row 10: Invalid department. Must be one of: software_engineering, artificial_intelligence, networks, information_systems",
      "row_data": {...},
      "level": "error",
      "error_type": "invalid_value"
    }
  ],
  "warnings": [
    {
      "row_number": 15,
      "field_name": "title",
      "error_message": "Rows 5, 15: Duplicate project title 'AI System' found within file",
      "row_data": {...},
      "level": "warning",
      "error_type": "duplicate"
    }
  ],
  "errors_by_type": {
    "validation": [...],
    "duplicate": [...],
    "supervisor_match": [...]
  },
  "execution_time_seconds": 1.234
}
```

#### Response (Execute - Success)

**Status**: `201 Created`

```json
{
  "import_session_id": "660e8400-e29b-41d4-a716-446655440000",
  "preview_result_id": null,
  "file_hash": null,
  "dry_run": false,
  "status": "success",
  "total_rows_processed": 100,
  "valid_rows_count": 95,
  "invalid_rows_count": 0,
  "successful_imports": 95,
  "failed_imports": 0,
  "created_students_count": 50,
  "created_supervisors_count": 3,
  "created_projects_count": 95,
  "users_to_create": {
    "students": [],
    "supervisors": []
  },
  "projects_to_create": 0,
  "validation_errors": [],
  "warnings": [],
  "errors_by_type": {},
  "execution_time_seconds": 5.678
}
```

#### Response (Validation Errors)

**Status**: `400 Bad Request`

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
    },
    {
      "row_number": 10,
      "field_name": "university_id",
      "error_message": "Row 10: Student 20250001 already has an active proposal",
      "level": "error",
      "error_type": "active_project"
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
    "active_project": [
      {
        "row_number": 10,
        "field_name": "university_id",
        "error_message": "Row 10: Student 20250001 already has an active proposal"
      }
    ]
  }
}
```

#### Error Responses

**Missing File**:
```json
{
  "error": "File is required."
}
```
**Status**: `400 Bad Request`

---

**Import Already in Progress**:
```json
{
  "error": "Import already in progress. Please wait for completion."
}
```
**Status**: `409 Conflict`

---

**Preview Expired**:
```json
{
  "error": "Preview has expired. Please preview the file again.",
  "details": []
}
```
**Status**: `400 Bad Request`

---

**File Hash Mismatch**:
```json
{
  "error": "Uploaded file does not match the successful preview. Please preview again.",
  "details": []
}
```
**Status**: `400 Bad Request`

---

**Permission Denied**:
```json
{
  "detail": "Insufficient permissions for bulk import operations"
}
```
**Status**: `403 Forbidden`

---

### 2. Download Template

Download Excel import template.

#### Endpoint

```
GET /api/project-imports/template/
```

#### Request

```bash
curl -X GET \
  -H "Authorization: Bearer <token>" \
  -o template.xlsx \
  "https://spu-portal.edu.sy/api/project-imports/template/"
```

#### Response

**Status**: `200 OK`

**Headers**:
```
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="project_import_template.xlsx"
```

**Body**: Binary Excel file content

#### Template Structure

- **Projects Sheet**: Contains required columns with sample data
- **Instructions Sheet**: Field descriptions and valid values

---

### 3. Import History

List all import sessions for the authenticated user.

#### Endpoint

```
GET /api/project-imports/history/
```

#### Request

```bash
curl -X GET \
  -H "Authorization: Bearer <token>" \
  "https://spu-portal.edu.sy/api/project-imports/history/"
```

#### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `status` | string | Filter by status: `pending`, `success`, `failed` |
| `from_date` | date | Filter by start date (YYYY-MM-DD) |
| `to_date` | date | Filter by end date (YYYY-MM-DD) |

#### Examples

**Filter by status**:
```
GET /api/project-imports/history/?status=success
```

**Filter by date range**:
```
GET /api/project-imports/history/?from_date=2026-06-01&to_date=2026-06-30
```

**Combined filters**:
```
GET /api/project-imports/history/?status=failed&from_date=2026-06-01
```

#### Response

**Status**: `200 OK`

```json
[
  {
    "id": "660e8400-e29b-41d4-a716-446655440000",
    "super_admin": 1,
    "super_admin_username": "dean_user",
    "filename": "projects.xlsx",
    "file_size_bytes": 1024000,
    "total_rows": 100,
    "successful_rows": 95,
    "failed_rows": 5,
    "started_at": "2026-06-24T10:00:00Z",
    "completed_at": "2026-06-24T10:00:05Z",
    "status": "success",
    "error_summary": ""
  },
  {
    "id": "770e8400-e29b-41d4-a716-446655440001",
    "super_admin": 1,
    "super_admin_username": "dean_user",
    "filename": "test_import.xlsx",
    "file_size_bytes": 512000,
    "total_rows": 50,
    "successful_rows": 0,
    "failed_rows": 50,
    "started_at": "2026-06-23T15:30:00Z",
    "completed_at": "2026-06-23T15:30:02Z",
    "status": "failed",
    "error_summary": "50 validation error(s)"
  }
]
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Session unique identifier |
| `super_admin` | integer | User ID of admin who initiated |
| `super_admin_username` | string | Username of admin |
| `filename` | string | Original uploaded filename |
| `file_size_bytes` | integer | File size in bytes |
| `total_rows` | integer | Total rows in file |
| `successful_rows` | integer | Successfully imported rows |
| `failed_rows` | integer | Failed/invalid rows |
| `started_at` | datetime | Import start timestamp |
| `completed_at` | datetime | Import completion timestamp |
| `status` | string | `pending`, `success`, or `failed` |
| `error_summary` | string | Brief error description |

---

### 4. Import Session Rows

Get detailed row-level results for a specific import session.

#### Endpoint

```
GET /api/project-imports/history/<session_id>/rows/
```

#### Request

```bash
curl -X GET \
  -H "Authorization: Bearer <token>" \
  "https://spu-portal.edu.sy/api/project-imports/history/660e8400-e29b-41d4-a716-446655440000/rows/"
```

#### Response

**Status**: `200 OK`

```json
[
  {
    "id": 1,
    "session": "660e8400-e29b-41d4-a716-446655440000",
    "row_number": 2,
    "university_id": "20250001",
    "project_title": "Project Management System",
    "status": "success",
    "error_message": "",
    "created_student": 101,
    "created_student_username": "20250001",
    "created_project": 501,
    "created_project_title": "Project Management System"
  },
  {
    "id": 2,
    "session": "660e8400-e29b-41d4-a716-446655440000",
    "row_number": 3,
    "university_id": "20250002",
    "project_title": "AI Data Analysis",
    "status": "success",
    "error_message": "",
    "created_student": null,
    "created_student_username": null,
    "created_project": 502,
    "created_project_title": "AI Data Analysis"
  },
  {
    "id": 3,
    "session": "660e8400-e29b-41d4-a716-446655440000",
    "row_number": 5,
    "university_id": "20250003",
    "project_title": "Invalid Project",
    "status": "failed",
    "error_message": "Row 5: Invalid department. Must be one of: software_engineering, artificial_intelligence, networks, information_systems",
    "created_student": null,
    "created_student_username": null,
    "created_project": null,
    "created_project_title": null
  }
]
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | integer | Row record ID |
| `session` | UUID | Import session ID |
| `row_number` | integer | Excel row number |
| `university_id` | string | Student university ID |
| `project_title` | string | Project title |
| `status` | string | `success`, `failed`, or `skipped` |
| `error_message` | string | Error description (if failed) |
| `created_student` | integer | Created student user ID (null if existed) |
| `created_student_username` | string | Created student username |
| `created_project` | integer | Created project proposal ID |
| `created_project_title` | string | Created project title |

---

## 🔗 Integration Examples

### Python (requests)

```python
import requests

API_BASE = "https://spu-portal.edu.sy/api/project-imports"

class ProjectImportClient:
    def __init__(self, token):
        self.headers = {"Authorization": f"Bearer {token}"}
    
    def download_template(self, output_path="template.xlsx"):
        response = requests.get(
            f"{API_BASE}/template/",
            headers=self.headers
        )
        response.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(response.content)
    
    def preview_import(self, file_path):
        with open(file_path, "rb") as f:
            response = requests.post(
                f"{API_BASE}/projects/?dry_run=true",
                files={"file": f},
                headers=self.headers
            )
        response.raise_for_status()
        return response.json()
    
    def execute_import(self, file_path, preview_result_id):
        with open(file_path, "rb") as f:
            response = requests.post(
                f"{API_BASE}/projects/",
                files={"file": f},
                data={"preview_result_id": preview_result_id},
                headers=self.headers
            )
        response.raise_for_status()
        return response.json()
    
    def get_history(self, status=None, from_date=None, to_date=None):
        params = {}
        if status:
            params['status'] = status
        if from_date:
            params['from_date'] = from_date
        if to_date:
            params['to_date'] = to_date
        
        response = requests.get(
            f"{API_BASE}/history/",
            params=params,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()
    
    def get_session_rows(self, session_id):
        response = requests.get(
            f"{API_BASE}/history/{session_id}/rows/",
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

# Usage
client = ProjectImportClient(token="your-jwt-token")

# Download template
client.download_template()

# Preview import
preview = client.preview_import("projects.xlsx")
print(f"Will create {preview['created_projects_count']} projects")

if preview['validation_errors']:
    print("Validation errors found!")
    for error in preview['validation_errors']:
        print(f"  Row {error['row_number']}: {error['error_message']}")
else:
    # Execute import
    result = client.execute_import("projects.xlsx", preview['preview_result_id'])
    print(f"Imported {result['successful_imports']} projects")

# View history
history = client.get_history(status="success")
for session in history:
    print(f"{session['filename']}: {session['successful_rows']} rows")
```

### JavaScript (Fetch API)

```javascript
class ProjectImportClient {
  constructor(apiBase = '/api/project-imports') {
    this.apiBase = apiBase;
  }
  
  async downloadTemplate() {
    const response = await fetch(`${this.apiBase}/template/`, {
      credentials: 'include'
    });
    
    if (!response.ok) throw new Error('Failed to download template');
    
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'project_import_template.xlsx';
    a.click();
    URL.revokeObjectURL(url);
  }
  
  async previewImport(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${this.apiBase}/projects/?dry_run=true`, {
      method: 'POST',
      body: formData,
      credentials: 'include'
    });
    
    return await response.json();
  }
  
  async executeImport(file, previewResultId) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('preview_result_id', previewResultId);
    
    const response = await fetch(`${this.apiBase}/projects/`, {
      method: 'POST',
      body: formData,
      credentials: 'include'
    });
    
    return await response.json();
  }
  
  async getHistory(filters = {}) {
    const params = new URLSearchParams(filters);
    const response = await fetch(
      `${this.apiBase}/history/?${params}`,
      { credentials: 'include' }
    );
    
    return await response.json();
  }
  
  async getSessionRows(sessionId) {
    const response = await fetch(
      `${this.apiBase}/history/${sessionId}/rows/`,
      { credentials: 'include' }
    );
    
    return await response.json();
  }
}

// Usage
const client = new ProjectImportClient();

async function importProjects(file) {
  try {
    // Preview
    const preview = await client.previewImport(file);
    
    if (preview.validation_errors.length > 0) {
      displayErrors(preview.validation_errors);
      return;
    }
    
    // Confirm
    const confirmed = confirm(
      `Create ${preview.created_projects_count} projects?`
    );
    if (!confirmed) return;
    
    // Execute
    const result = await client.executeImport(file, preview.preview_result_id);
    alert(`Imported ${result.successful_imports} projects!`);
    
  } catch (error) {
    console.error('Import failed:', error);
    alert(`Error: ${error.message}`);
  }
}
```

## 🔗 Related Documentation

- [Module Overview](00-MODULE-OVERVIEW.md)
- [Import Process](01-IMPORT-PROCESS.md)
- [File Format & Validation](02-FILE-FORMAT-VALIDATION.md)
- [Security & Performance](05-SECURITY-PERFORMANCE.md)

## 📦 Code References

- **Views**: `backend/project_imports/views.py`
  - `ImportProjectsView`
  - `DownloadTemplateView`
  - `ImportHistoryView`
  - `ImportRowsView`
- **Permissions**: `backend/project_imports/permissions.py`
  - `IsSuperAdmin`
- **Throttles**: `backend/project_imports/throttles.py`
  - `ImportRateThrottle`
- **URLs**: `backend/project_imports/urls.py`

---

**Document Version**: 1.0  
**Last Updated**: June 24, 2026  
**Maintained By**: Development Team
