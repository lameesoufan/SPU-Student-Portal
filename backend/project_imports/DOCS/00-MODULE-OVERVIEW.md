# Module Overview

## Purpose

The **Project Imports** module enables super administrators (deans) to bulk import student projects, creating students, supervisors, and project assignments in a single streamlined operation.

## Problem Statement

Manual entry of student projects is time-consuming and error-prone, especially at the start of academic terms when hundreds of projects need to be registered. The system needs to:

- Import student records with their assigned projects
- Create missing student accounts automatically
- Create or match supervisor (doctor) accounts
- Assign projects with proper status tracking
- Validate data comprehensively before committing
- Provide clear error reporting for corrections

## Solution Overview

The module provides a **secure, validated bulk import system** that:

1. **Accepts Excel files** with structured project data
2. **Validates comprehensively** across multiple layers:
   - File format and structure
   - Required field presence
   - Data type and format correctness
   - Business rule compliance
   - Duplicate detection (file and database)
   - Active project conflicts
3. **Previews changes** with dry-run mode before actual import
4. **Creates users automatically** when they don't exist
5. **Creates projects atomically** in all-or-nothing transactions
6. **Tracks import history** with detailed audit logs

## Key Features

### 🔐 Security First
- **Super admin only** access (dean + is_superuser)
- **Rate limiting** to prevent abuse
- **Macro detection** blocks malicious files
- **Formula blocking** prevents Excel injection attacks
- **Preview verification** ensures intended file is imported

### ✅ Comprehensive Validation
- Multi-layer validation pipeline
- Detailed error messages with row numbers
- Field-level error attribution
- Duplicate detection across file and database
- Active project conflict checking

### 👥 Automatic User Management
- Creates student accounts from university IDs
- Creates or matches supervisor accounts by name
- Generates secure temporary passwords
- Forces password change on first login
- Handles name parsing and username generation

### 📊 Import Tracking
- Complete import session history
- Row-level success/failure tracking
- Links to created students and projects
- Execution time monitoring
- Error summary aggregation

### 🔄 Preview & Verify Workflow
1. Upload file with `dry_run=true`
2. Review validation results and preview
3. Submit actual import with preview_result_id
4. System verifies file hash matches preview

## Architecture Components

| Component | Responsibility |
|-----------|----------------|
| **Views** | API endpoints and request handling |
| **Services** | Business logic orchestration |
| **Validators** | Multi-layer data validation |
| **UserMapper** | User creation and matching logic |
| **ProjectCreator** | Project and board creation |
| **Models** | Import session and row tracking |
| **Permissions** | Access control enforcement |
| **Throttles** | Rate limiting implementation |

## Workflow Summary

```
┌─────────────────────┐
│  Upload Excel File  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Parse & Validate   │◄─── File format, headers, cell types
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Validate Rows      │◄─── Required fields, data types, business rules
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Check Duplicates   │◄─── File duplicates, DB conflicts
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Build User Plan    │◄─── Students/supervisors to create
└──────────┬──────────┘
           │
           ├─────► dry_run=true  ─────► Return preview
           │
           ▼
┌─────────────────────┐
│  Verify Preview ID  │◄─── Hash match confirmation
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Create Users       │◄─── Students, supervisors (atomic)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Create Projects    │◄─── Proposals, applications, boards
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Record Results     │◄─── Import session, row tracking
└─────────────────────┘
```

## Data Flow

### Input
- **Excel file (.xlsx)** with required columns in Arabic headers
- **Dry run flag** for preview mode
- **Preview result ID** for verification (actual import)

### Processing
1. File parsing and header validation
2. Row-by-row data extraction
3. Multi-layer validation
4. User existence checking and planning
5. Transaction-wrapped creation

### Output
- **Preview response** with validation results and planned changes
- **Import result** with created records and statistics
- **Import session** record with audit trail
- **Import rows** with individual row outcomes

## Integration Points

### Dependencies
- **accounts**: User model, departments
- **projects**: StudentIdeaProposal, ProjectApplication models
- **project_management**: ProjectBoard model

### Used By
- Admin dashboard (frontend)
- Bulk import UI components
- Import history viewers

## File Structure

```
project_imports/
├── models.py           # ImportSession, ImportRow
├── views.py            # API endpoints
├── services.py         # ImportService orchestration
├── validators.py       # FileValidator, RowValidator
├── serializers.py      # API serialization
├── permissions.py      # IsSuperAdmin permission
├── throttles.py        # ImportRateThrottle
├── templates.py        # Excel template generation
├── constants.py        # Configuration constants
├── urls.py             # URL routing
└── DOCS/               # This documentation folder
```

## Next Steps

- Read [01-ARCHITECTURE.md](01-ARCHITECTURE.md) for detailed component design
- Review [02-IMPORT-PROCESS.md](02-IMPORT-PROCESS.md) for workflow details
- Check [03-FILE-FORMAT.md](03-FILE-FORMAT.md) for template specifications
