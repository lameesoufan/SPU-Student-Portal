# Dynamic Forms System

## 📋 Overview

The Dynamic Forms system allows HoDs to create custom, configurable forms for different project contexts. These forms can be embedded in project proposals, applications, and progress reports, enabling flexible data collection without code changes.

## 🎯 Use Cases

1. **Student Proposal Forms**: Collect additional info when students propose ideas
2. **Application Forms**: Gather motivation/experience when applying to doctor ideas
3. **Progress Reports**: Weekly/monthly structured updates
4. **Milestone Reports**: Deliverable-specific forms
5. **Final Reports**: Comprehensive project documentation

## 🏗️ Architecture

### Entity Hierarchy

```
DynamicForm (one per department+context)
├── FormField (multiple)
│
FormResponse (student submission)
└── FieldResponse (one per field)
```

### Core Models

#### 1. DynamicForm

```python
class DynamicForm:
    hod = ForeignKey(User)  # Creator
    department = CharField(50)
    context = CharField(20)  # propose, browse, weekly_report, etc.
    title = CharField(255)
    description = TextField
    is_recurring = BooleanField
    frequency = CharField  # once, weekly, biweekly, monthly, milestone
    created_at = DateTimeField
    updated_at = DateTimeField
```

**Unique Constraint**: One form per (department, context) pair

**Context Types**:
- `propose`: Student proposes own idea
- `browse`: Student applies to doctor idea
- `weekly_report`: Weekly progress update
- `monthly_report`: Monthly progress update
- `milestone`: Milestone-specific report
- `final_report`: Final project documentation
- `custom`: Custom report type

#### 2. FormField

```python
class FormField:
    form = ForeignKey(DynamicForm)
    label = CharField(255)
    field_type = CharField(10)
    required = BooleanField
    options = JSONField  # For select/radio/checkbox
    order = PositiveSmallIntegerField
```

**Field Types**:
- `text`: Short text input (single line)
- `textarea`: Long text input (multiline)
- `number`: Numeric input
- `select`: Dropdown (single selection)
- `radio`: Radio buttons (single selection)
- `checkbox`: Checkboxes (multiple selections)
- `date`: Date picker
- `file`: File upload

**Options Format** (for select/radio/checkbox):
```json
// Simple array
["Option 1", "Option 2", "Option 3"]

// Or objects with value/label
[
  {"value": "python", "label": "Python"},
  {"value": "java", "label": "Java"},
  {"value": "javascript", "label": "JavaScript"}
]
```

#### 3. FormResponse

```python
class FormResponse:
    form = ForeignKey(DynamicForm)
    student = ForeignKey(User)
    
    # Link to project context
    proposal_id = IntegerField  # If linked to proposal
    application_id = IntegerField  # If linked to application
    project_board_id = IntegerField  # For progress reports
    
    # For recurring reports
    report_period_start = DateField
    report_period_end = DateField
    
    submitted_at = DateTimeField
```

**Relationships**:
- One response can link to either a proposal OR application OR project board
- Progress reports link to project_board_id
- Proposal/application forms link to their respective IDs

#### 4. FieldResponse

```python
class FieldResponse:
    response = ForeignKey(FormResponse)
    field = ForeignKey(FormField)  # Can be null if field deleted
    
    # Snapshot fields (preserve data if field deleted)
    field_label = CharField(255)
    field_type = CharField(10)
    field_options = JSONField
    
    # Response data
    value = TextField  # Legacy text representation
    value_data = JSONField  # Structured data
    file = FileField  # For file uploads
```

**Data Storage**:
- `value`: Plain text representation (backward compatibility)
- `value_data`: Structured JSON (preferred)
  - Text/textarea/number: `"value"`
  - Select/radio: `"selected_option"`
  - Checkbox: `["option1", "option2"]`
  - Date: `"2026-06-22"`
  - File: `{"filename": "report.pdf", "url": "/media/..."}`

## 🔄 Form Management Workflows

### 1. HoD Creates/Updates Form

**Endpoint**: `POST /api/forms/{context}/`

**Permission**: HoD only (for their department)

**Request**:
```json
{
  "title": "Project Proposal Questionnaire",
  "description": "Please provide detailed information about your proposed project",
  "fields": [
    {
      "label": "Project Motivation",
      "field_type": "textarea",
      "required": true,
      "order": 1
    },
    {
      "label": "Technology Stack",
      "field_type": "select",
      "required": true,
      "options": [
        "Python/Django",
        "Java/Spring Boot",
        "Node.js/Express",
        "Other"
      ],
      "order": 2
    },
    {
      "label": "Team Experience",
      "field_type": "checkbox",
      "required": false,
      "options": [
        "Web Development",
        "Mobile Development",
        "Machine Learning",
        "Database Design",
        "UI/UX Design"
      ],
      "order": 3
    },
    {
      "label": "Expected Completion Date",
      "field_type": "date",
      "required": true,
      "order": 4
    },
    {
      "label": "Project Proposal Document",
      "field_type": "file",
      "required": false,
      "order": 5
    }
  ]
}
```

**Process**:
1. Get or create DynamicForm for (department, context)
2. Delete all existing fields
3. Create new fields in specified order
4. Return complete form structure

**Response**:
```json
{
  "id": 10,
  "title": "Project Proposal Questionnaire",
  "description": "Please provide detailed information...",
  "department": "software_engineering",
  "context": "propose",
  "fields": [
    {
      "id": 100,
      "label": "Project Motivation",
      "field_type": "textarea",
      "required": true,
      "options": [],
      "order": 1
    },
    {
      "id": 101,
      "label": "Technology Stack",
      "field_type": "select",
      "required": true,
      "options": ["Python/Django", "Java/Spring Boot", ...],
      "order": 2
    }
  ],
  "created_at": "2026-06-22T10:00:00Z"
}
```

### 2. HoD Retrieves Form

**Endpoint**: `GET /api/forms/{context}/`

**Permission**: HoD only

**Response**: Same structure as create

**Empty Form Response** (if no form created yet):
```json
{
  "id": null,
  "title": "",
  "description": "",
  "fields": []
}
```

### 3. Student Fetches Form

**Endpoint**: `GET /api/forms/{department}/{context}/`

**Permission**: Any authenticated user

**Example**: `GET /api/forms/software_engineering/propose/`

**Response**: Same structure (read-only for students)

## 📝 Form Submission Workflows

### 1. Submit Form with Proposal/Application

**Integration Point**: During proposal/application creation

**Request to** `POST /api/propose-idea/`:
```json
{
  "title": "Smart Campus App",
  "description": "Mobile navigation app...",
  "supervisor": 15,
  "team_size": 2,
  "member_ids": ["student002"],
  
  // Dynamic form data
  "form_id": 10,
  "field_responses": [
    {
      "field_id": 100,
      "value": "We want to solve the campus navigation problem..."
    },
    {
      "field_id": 101,
      "value": "Python/Django"
    },
    {
      "field_id": 102,
      "value": ["Web Development", "Mobile Development", "UI/UX Design"]
    },
    {
      "field_id": 103,
      "value": "2026-12-01"
    }
  ]
}
```

**With File Upload** (multipart/form-data):
```http
POST /api/propose-idea/
Content-Type: multipart/form-data

------WebKitFormBoundary
Content-Disposition: form-data; name="title"

Smart Campus App
------WebKitFormBoundary
Content-Disposition: form-data; name="form_id"

10
------WebKitFormBoundary
Content-Disposition: form-data; name="field_responses"

[{"field_id":100,"value":"We want to solve..."},...]
------WebKitFormBoundary
Content-Disposition: form-data; name="field_104"; filename="proposal.pdf"
Content-Type: application/pdf

<binary data>
------WebKitFormBoundary--
```

**Validation**:
```python
def validate_form_submission(form, field_responses, files):
    for field in form.fields.all():
        if field.required:
            value = field_responses.get(str(field.id))
            if not value and field.field_type != 'file':
                raise ValidationError(f"Field '{field.label}' is required")
        
        if field.field_type == 'number':
            validate_number(value)
        elif field.field_type == 'date':
            validate_date_format(value)
        elif field.field_type in ['select', 'radio']:
            validate_option_exists(value, field.options)
        elif field.field_type == 'checkbox':
            validate_all_options_exist(value, field.options)
        elif field.field_type == 'file':
            validate_file(files.get(f'field_{field.id}'))
```

### 2. Standalone Form Submission

**Endpoint**: `POST /api/forms/submit/`

**Permission**: Student only

**Use Case**: Progress reports not tied to proposal creation

**Request**:
```json
{
  "form": 15,  // Form ID
  "project_board_id": 42,
  "report_period_start": "2026-06-15",
  "report_period_end": "2026-06-22",
  "field_responses": [
    {
      "field_id": 200,
      "value": "Completed database design and initial API endpoints"
    },
    {
      "field_id": 201,
      "value": "Performance optimization challenges with large datasets"
    },
    {
      "field_id": 202,
      "value": "Implement caching layer and optimize queries"
    }
  ]
}
```

**Response**:
```json
{
  "id": 500,
  "form": {
    "id": 15,
    "title": "Weekly Progress Report"
  },
  "student": {
    "id": 122,
    "username": "student001",
    "name": "John Doe"
  },
  "project_board_id": 42,
  "report_period_start": "2026-06-15",
  "report_period_end": "2026-06-22",
  "submitted_at": "2026-06-22T16:00:00Z",
  "field_responses": [
    {
      "id": 1000,
      "field": {
        "id": 200,
        "label": "Completed Tasks",
        "field_type": "textarea"
      },
      "value": "Completed database design...",
      "value_data": "Completed database design..."
    }
  ]
}
```

## 📊 View Responses

### 1. HoD Views All Responses

**Endpoint**: `GET /api/forms/{context}/responses/`

**Permission**: HoD (for their department)

**Query Params**:
- `student_id`: Filter by specific student
- `submitted_after`: Date filter
- `submitted_before`: Date filter

**Response**:
```json
[
  {
    "id": 500,
    "form": {
      "id": 15,
      "title": "Weekly Progress Report"
    },
    "student": {
      "id": 122,
      "username": "student001",
      "name": "John Doe"
    },
    "project_board_id": 42,
    "submitted_at": "2026-06-22T16:00:00Z",
    "field_responses": [...]
  }
]
```

### 2. Supervisor Views Proposal/Application Form

**Endpoint**: `GET /api/forms/response/proposal/{proposal_id}/`

**Permission**: Supervisor of the proposal

**Response**: FormResponse with all FieldResponses

**Alternative**: `GET /api/forms/response/application/{application_id}/`

### 3. Student Views Own Response

**Endpoint**: Same as supervisor, but filtered by student ID

## 🔒 File Upload Security

### Validation Rules

```python
MAX_FORM_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_FORM_FILE_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    '.ppt', '.pptx', '.txt', '.csv',
    '.jpg', '.jpeg', '.png', '.gif',
    '.zip', '.rar',
}

FORM_MIME_WHITELIST = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain',
    'text/csv',
    'image/jpeg',
    'image/png',
    'image/gif',
    'application/zip',
    'application/x-rar-compressed',
}
```

### Validation Process

```python
def _validate_form_file(file):
    # Size check
    if file.size > MAX_FORM_FILE_SIZE:
        raise ValueError('File too large. Max 10 MB.')
    
    # Extension check
    extension = os.path.splitext(file.name)[1].lower()
    if extension not in ALLOWED_FORM_FILE_EXTENSIONS:
        raise ValueError(f'Unsupported file type: {extension}')
    
    # MIME type check
    mime_type = mimetypes.guess_type(file.name)[0]
    content_type = getattr(file, 'content_type', None) or mime_type
    if content_type and content_type not in FORM_MIME_WHITELIST:
        raise ValueError('Unsupported file type (MIME mismatch).')
```

### Storage Path

```
media/form_uploads/{year}/{month}/{filename}
```

**Example**: `media/form_uploads/2026/06/proposal_document_abc123.pdf`

## 🎨 Frontend Integration

### Form Builder (HoD)

```javascript
function FormBuilder({ context }) {
  const [fields, setFields] = useState([]);
  
  const addField = (type) => {
    setFields([...fields, {
      label: '',
      field_type: type,
      required: false,
      options: [],
      order: fields.length + 1
    }]);
  };
  
  const saveForm = async () => {
    await api.post(`/api/forms/${context}/`, {
      title: formTitle,
      description: formDescription,
      fields: fields
    });
  };
  
  return (
    <div>
      <input value={formTitle} onChange={...} />
      <textarea value={formDescription} onChange={...} />
      
      <DragDropContext onDragEnd={reorderFields}>
        {fields.map((field, index) => (
          <FieldEditor
            key={index}
            field={field}
            onChange={(updated) => updateField(index, updated)}
            onDelete={() => deleteField(index)}
          />
        ))}
      </DragDropContext>
      
      <FieldTypePicker onSelect={addField} />
      <button onClick={saveForm}>Save Form</button>
    </div>
  );
}
```

### Form Viewer (Student)

```javascript
function DynamicFormView({ formId, onSubmit }) {
  const [form, setForm] = useState(null);
  const [responses, setResponses] = useState({});
  
  useEffect(() => {
    api.get(`/api/forms/${department}/${context}/`)
      .then(res => setForm(res.data));
  }, []);
  
  const handleSubmit = async () => {
    const fieldResponses = Object.entries(responses).map(
      ([fieldId, value]) => ({ field_id: fieldId, value })
    );
    
    await onSubmit({ form_id: formId, field_responses: fieldResponses });
  };
  
  return (
    <div>
      <h2>{form?.title}</h2>
      <p>{form?.description}</p>
      
      {form?.fields.map(field => (
        <DynamicField
          key={field.id}
          field={field}
          value={responses[field.id]}
          onChange={(value) => setResponses({
            ...responses,
            [field.id]: value
          })}
        />
      ))}
      
      <button onClick={handleSubmit}>Submit</button>
    </div>
  );
}
```

### Dynamic Field Component

```javascript
function DynamicField({ field, value, onChange }) {
  switch (field.field_type) {
    case 'text':
      return <input type="text" value={value} onChange={e => onChange(e.target.value)} />;
    
    case 'textarea':
      return <textarea value={value} onChange={e => onChange(e.target.value)} />;
    
    case 'number':
      return <input type="number" value={value} onChange={e => onChange(e.target.value)} />;
    
    case 'select':
      return (
        <select value={value} onChange={e => onChange(e.target.value)}>
          <option value="">-- Select --</option>
          {field.options.map(opt => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      );
    
    case 'checkbox':
      return (
        <div>
          {field.options.map(opt => (
            <label key={opt}>
              <input
                type="checkbox"
                checked={value?.includes(opt)}
                onChange={e => {
                  const newValue = e.target.checked
                    ? [...(value || []), opt]
                    : value.filter(v => v !== opt);
                  onChange(newValue);
                }}
              />
              {opt}
            </label>
          ))}
        </div>
      );
    
    case 'date':
      return <input type="date" value={value} onChange={e => onChange(e.target.value)} />;
    
    case 'file':
      return <input type="file" onChange={e => onChange(e.target.files[0])} />;
    
    default:
      return <div>Unsupported field type</div>;
  }
}
```

## 📊 Data Preservation

### Field Deletion Handling

When a form field is deleted from the template, existing responses are preserved:

```python
class FieldResponse:
    field = ForeignKey(FormField, null=True)  # Can be null
    
    # Snapshot fields preserve original data
    field_label = CharField(255)
    field_type = CharField(10)
    field_options = JSONField
```

**Display Logic**:
```python
def display_response(field_response):
    if field_response.field:
        # Field still exists, use current data
        label = field_response.field.label
        field_type = field_response.field.field_type
    else:
        # Field deleted, use snapshot
        label = field_response.field_label
        field_type = field_response.field_type
    
    return f"{label}: {field_response.value}"
```

## 🔍 Access Control

### Permission Matrix

| Action | Dean | HoD | Doctor | Student |
|--------|------|-----|--------|---------|
| Create/Edit form | ✅ | ✅ (own dept) | ❌ | ❌ |
| View form template | ✅ | ✅ | ✅ | ✅ |
| Submit form | ❌ | ❌ | ❌ | ✅ |
| View all responses | ✅ | ✅ (own dept) | ❌ | ❌ |
| View proposal/app response | ✅ | ✅ (dept) | ✅ (supervised) | ✅ (own) |

## 🐛 Troubleshooting

### Issue: "Field is required" but field is filled
**Cause**: Field type validation failed (e.g., invalid date format)  
**Solution**: Check value format matches field type

### Issue: File upload not saving
**Cause**: Content-Type or extension not allowed  
**Solution**: Verify file extension in whitelist, check MIME type

### Issue: Form not appearing for students
**Cause**: HoD hasn't created form for that (department, context)  
**Solution**: HoD must create form first

### Issue: Response data lost after field deleted
**Cause**: Not using snapshot fields  
**Solution**: Data preserved in `field_label`, `field_type`, `value_data`

---

**Related Documentation**:
- [Project Lifecycle](02-PROJECT-LIFECYCLE.md) - Form integration points
- [Workflow System](03-WORKFLOW-SYSTEM.md) - Similar field system
- [API Reference](08-API-REFERENCE.md) - Complete endpoint specs

**Code References**:
- Models: `backend/dy_forms/models.py`
- Views: `backend/dy_forms/views.py`
- Serializers: `backend/dy_forms/serializers.py`
- Validators: `backend/dy_forms/validators.py`
- Frontend: `frontend/src/components/DynamicFormView.jsx`, `HodFormBuilder.jsx`

**Last Updated**: June 22, 2026
