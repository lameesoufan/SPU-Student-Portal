import { useState, useEffect } from 'react';
import { fetchStudentForm, submitFormResponse } from '../api';
import DynamicCheckboxGroup from './DynamicCheckboxGroup';

const DEPARTMENTS = [
  { value: 'software_engineering',    label: 'Software Engineering' },
  { value: 'artificial_intelligence', label: 'Artificial Intelligence' },
  { value: 'information_security',    label: 'Information Security' },
  { value: 'communications',          label: 'Communications' },
  { value: 'control_robotics',        label: 'Control & Robotics' },
];

const emptyValueForField = (field) => field.field_type === 'checkbox' ? [] : '';
const isEmptyFieldValue = (value) => Array.isArray(value) ? value.length === 0 : !value;

/**
 * Renders the full form for a student:
 * - Default fields (title, description, department, team_size) based on context
 * - Dynamic fields added by the HoD
 *
 * Props:
 *   context       - 'propose' | 'browse'
 *   department    - pre-selected department (string) or null to let student pick
 *   onSubmit      - callback(defaultValues, dynamicValues, formId) called on submit
 *   submitting    - bool, disables submit button
 *   externalError - error string from parent
 */
export default function DynamicFormView({
  context,
  department: initialDept,
  onSubmit,
  submitting,
  externalError,
}) {
  const [department, setDepartment] = useState(initialDept || '');
  const [dynForm, setDynForm]       = useState(null);
  const [loadingForm, setLoadingForm] = useState(false);

  // Default field values
  const [title, setTitle]           = useState('');
  const [description, setDescription] = useState('');
  const [teamSize, setTeamSize]     = useState(2);

  // Dynamic field values: { fieldId: value }
  const [dynValues, setDynValues]   = useState({});
  const [error, setError]           = useState('');

  // Load dynamic form when department changes
  useEffect(() => {
    if (!department) { setDynForm(null); return; }
    setLoadingForm(true);
    fetchStudentForm(department, context)
      .then(res => {
        setDynForm(res.data);
        // Init dynamic values
        const init = {};
        (res.data.fields || []).forEach(f => { init[f.id] = emptyValueForField(f); });
        setDynValues(init);
      })
      .catch(() => setDynForm(null))
      .finally(() => setLoadingForm(false));
  }, [department, context]);

  const handleDynChange = (fieldId, value) => {
    setDynValues(prev => ({ ...prev, [fieldId]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');

    // Validate required dynamic fields
    if (dynForm) {
      for (const f of dynForm.fields || []) {
        if (f.required && isEmptyFieldValue(dynValues[f.id])) {
          setError(`"${f.label}" is required.`);
          return;
        }
      }
    }

    const defaultValues = { title, description, department, team_size: teamSize };
    const dynamicValues = dynForm
      ? (dynForm.fields || []).map(f => ({ field: f.id, value: dynValues[f.id] ?? emptyValueForField(f) }))
      : [];

    onSubmit(defaultValues, dynamicValues, dynForm?.id || null);
  };

  return (
    <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
      {dynForm?.title && <h3 className="text-lg font-bold text-gray-900 dark:text-white m-0 mb-1">{dynForm.title}</h3>}

      {/* ── Default Fields ── */}
      <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">Basic Information</div>

      {/* Department selector (always shown if not pre-set) */}
      <div className="form-group">
        <label className="text-sm font-medium text-gray-900 dark:text-white">Department <span className="text-red-500 ml-0.5">*</span></label>
        <select
          className="form-control"
          value={department}
          onChange={e => setDepartment(e.target.value)}
          required
          disabled={!!initialDept}
        >
          <option value="">Select department...</option>
          {DEPARTMENTS.map(d => (
            <option key={d.value} value={d.value}>{d.label}</option>
          ))}
        </select>
      </div>

      {context === 'propose' && (
        <>
          <div className="form-group">
            <label className="text-sm font-medium text-gray-900 dark:text-white">Project Title <span className="text-red-500 ml-0.5">*</span></label>
            <input
              className="form-control"
              type="text"
              value={title}
              onChange={e => setTitle(e.target.value)}
              required
              placeholder="Enter your project title"
            />
          </div>
          <div className="form-group">
            <label className="text-sm font-medium text-gray-900 dark:text-white">Project Description <span className="text-red-500 ml-0.5">*</span></label>
            <textarea
              className="form-control"
              rows={4}
              value={description}
              onChange={e => setDescription(e.target.value)}
              required
              placeholder="Describe your project idea..."
            />
          </div>
        </>
      )}

      <div className="form-group">
        <label className="text-sm font-medium text-gray-900 dark:text-white">Team Size <span className="text-red-500 ml-0.5">*</span></label>
        <input
          className="form-control max-w-[120px]"
          type="number"
          min={1}
          max={5}
          value={teamSize}
          onChange={e => setTeamSize(Number(e.target.value))}
          required
        />
      </div>

      {/* ── Dynamic Fields ── */}
      {loadingForm && <div className="text-center text-gray-500 dark:text-gray-400 text-[13px] p-3">Loading department form...</div>}

      {!loadingForm && dynForm && (dynForm.fields || []).length > 0 && (
        <>
          <hr className="border-0 border-t border-gray-200 dark:border-gray-700 my-1" />
          <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 dark:text-gray-400">
            {dynForm.title || 'Additional Information'}
          </div>
          {dynForm.fields.map(field => (
            <DynField
              key={field.id}
              field={field}
              value={dynValues[field.id] ?? emptyValueForField(field)}
              onChange={val => handleDynChange(field.id, val)}
            />
          ))}
        </>
      )}

      {(error || externalError) && (
        <div className="alert">{error || externalError}</div>
      )}

      <button className="btn btn-primary self-end" type="submit" disabled={submitting || !department}>
        {submitting ? 'Submitting...' : 'Submit'}
      </button>
    </form>
  );
}

function DynField({ field, value, onChange }) {
  const { label, field_type, required, options } = field;

  const labelEl = (
    <label className="text-sm font-medium text-gray-900 dark:text-white">
      {label} {required && <span className="text-red-500 ml-0.5">*</span>}
    </label>
  );

  if (field_type === 'text') return (
    <div className="form-group">
      {labelEl}
      <input className="form-control" type="text" value={value} required={required}
        onChange={e => onChange(e.target.value)} />
    </div>
  );

  if (field_type === 'textarea') return (
    <div className="form-group">
      {labelEl}
      <textarea className="form-control" rows={3} value={value} required={required}
        onChange={e => onChange(e.target.value)} />
    </div>
  );

  if (field_type === 'number') return (
    <div className="form-group">
      {labelEl}
      <input 
        className="form-control max-w-[120px]" 
        type="number" 
        value={value} 
        required={required}
        min="0"
        step="any"
        onChange={e => onChange(e.target.value)} 
      />
    </div>
  );

  if (field_type === 'date') return (
    <div className="form-group">
      {labelEl}
      <input className="form-control" type="date" value={value} required={required}
        onChange={e => onChange(e.target.value)} />
    </div>
  );

  if (field_type === 'select') return (
    <div className="form-group">
      {labelEl}
      <select className="form-control" value={value} required={required}
        onChange={e => onChange(e.target.value)}>
        <option value="">Select...</option>
        {(options || []).map(opt => <option key={opt} value={opt}>{opt}</option>)}
      </select>
    </div>
  );

  if (field_type === 'radio') return (
    <div className="form-group">
      {labelEl}
      <div className="flex flex-col gap-2">
        {(options || []).map(opt => (
          <label key={opt} className="flex items-center gap-2 text-sm text-gray-900 dark:text-white cursor-pointer">
            <input type="radio" name={`field-${field.id}`} value={opt}
              checked={value === opt} onChange={() => onChange(opt)} required={required} />
            {opt}
          </label>
        ))}
      </div>
    </div>
  );

  if (field_type === 'checkbox') return (
    <div className="form-group">
      {labelEl}
      <DynamicCheckboxGroup field={field} value={value} onChange={onChange} />
    </div>
  );

  if (field_type === 'file') return (
    <div className="form-group">
      {labelEl}
      <input 
        className="form-control" 
        type="file" 
        required={required}
        accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.gif"
        onChange={e => {
          const file = e.target.files?.[0];
          if (file) {
            onChange(file.name);
          }
        }} 
      />
      <small className="text-xs text-gray-500 dark:text-gray-400 -mt-0.5 block">Upload a file (PDF, DOC, or image)</small>
    </div>
  );

  return null;
}