import { useState, useEffect } from 'react';
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors,
} from '@dnd-kit/core';
import {
  SortableContext, verticalListSortingStrategy,
  useSortable, arrayMove,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { fetchHodForm, saveHodForm } from '../api';
import {
  GripVertical, Trash2, Plus, Save, Check, Lock,
  FileText, Loader2,
} from 'lucide-react';

const FIELD_TYPES = [
  { value: 'text',     label: 'Short Text' },
  { value: 'textarea', label: 'Long Text' },
  { value: 'number',   label: 'Number' },
  { value: 'select',   label: 'Dropdown' },
  { value: 'radio',    label: 'Radio Buttons' },
  { value: 'checkbox', label: 'Checkboxes' },
  { value: 'date',     label: 'Date' },
  { value: 'file',     label: 'File Upload' },
];

const optionFieldTypes = ['select', 'radio', 'checkbox'];

function OptionEditor({ field, index, onChange }) {
  const [draft, setDraft] = useState('');
  const options = field.options || [];
  const helper = field.field_type === 'checkbox'
    ? 'Checkboxes let students choose multiple answers.'
    : 'Add the choices students can pick from.';

  const addOption = () => {
    const option = draft.trim();
    if (!option || options.includes(option)) return;
    onChange(index, 'options', [...options, option]);
    setDraft('');
  };

  const removeOption = (option) => {
    onChange(index, 'options', options.filter((item) => item !== option));
  };

  return (
    <div className="flex flex-col gap-2.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-md p-3.5 mt-1">
      <div className="flex justify-between gap-3 flex-wrap items-center">
        <span className="text-[11px] font-bold uppercase tracking-wider text-violet-600 dark:text-violet-400">Choices</span>
        <span className="text-xs text-gray-500 dark:text-gray-400 italic">{helper}</span>
      </div>
      <div className="flex gap-2">
        <input
          className="flex-1 min-w-0 text-[13px] py-2 px-3 border border-gray-300 dark:border-gray-600 rounded-md bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none transition-all placeholder:text-gray-400 dark:placeholder:text-gray-500"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              addOption();
            }
          }}
          placeholder="Type a choice and press Enter"
        />
        <button
          type="button"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md bg-violet-600 text-white hover:bg-violet-700 transition-colors"
          onClick={addOption}
        >
          <Plus size={14} />
          Add
        </button>
      </div>
      {options.length > 0 ? (
        <div className="flex flex-wrap gap-1.5 mt-1">
          {options.map((option) => (
            <span
              key={option}
              className="inline-flex items-center gap-1.5 max-w-full bg-violet-500/10 text-violet-600 dark:text-violet-400 border border-violet-500/20 rounded-full py-1 px-3 text-xs font-semibold transition-colors hover:bg-violet-500/20"
            >
              {option}
              <button
                type="button"
                onClick={() => removeOption(option)}
                aria-label={`Remove ${option}`}
                className="inline-flex items-center justify-center w-[18px] h-[18px] border-none rounded-full bg-violet-500/20 text-violet-600 dark:text-violet-400 hover:bg-violet-600 hover:text-white cursor-pointer text-sm leading-none transition-colors"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      ) : (
        <div className="text-xs text-gray-500 dark:text-gray-400 italic">No choices yet. Add at least one before saving.</div>
      )}
    </div>
  );
}

const CONTEXT_LABELS = {
  propose: 'Propose Own Idea',
  browse:  'Apply on Doctor Idea',
};

const DEFAULT_FIELDS = {
  propose: [
    { label: 'Project Title',       field_type: 'text',     required: true,  options: [], _default: true },
    { label: 'Project Description', field_type: 'textarea', required: true,  options: [], _default: true },
    { label: 'Department',          field_type: 'select',   required: true,  options: [], _default: true },
    { label: 'Team Size',           field_type: 'number',   required: true,  options: [], _default: true },
  ],
  browse: [
    { label: 'Department',          field_type: 'select',   required: true,  options: [], _default: true },
    { label: 'Team Size',           field_type: 'number',   required: true,  options: [], _default: true },
  ],
};

function SortableField({ field, index, onChange, onRemove }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: field._id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const needsOptions = ['select', 'radio', 'checkbox'].includes(field.field_type);

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-start gap-3 rounded-lg p-4 transition-all relative ${
        field._default
          ? 'bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-700 border-l-[3px] border-l-violet-500 hover:border-gray-200 dark:hover:border-gray-700 hover:border-l-violet-500 hover:shadow-none'
          : 'bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 hover:border-violet-500/30 hover:shadow-sm'
      }`}
    >
      <div
        {...attributes}
        {...listeners}
        className={`flex items-center justify-center w-6 h-6 rounded-md flex-shrink-0 pt-2 transition-colors ${
          field._default
            ? 'cursor-default text-violet-500/80'
            : 'cursor-grab text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-600'
        }`}
      >
        {field._default ? <Lock size={14} /> : <GripVertical size={16} />}
      </div>

      <div className="flex-1 flex flex-col gap-3 min-w-0">
        <div className="flex gap-2.5 flex-wrap items-center">
          <input
            className="flex-1 min-w-[140px] py-2.5 px-3.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white transition-all placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none disabled:opacity-70 disabled:bg-gray-50 dark:disabled:bg-gray-700/50 disabled:cursor-not-allowed"
            placeholder="Field label"
            value={field.label}
            disabled={field._default}
            onChange={e => onChange(index, 'label', e.target.value)}
          />
          <select
            className="min-w-[160px] max-w-[200px] py-2.5 px-3.5 text-sm border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-800 text-gray-900 dark:text-white transition-all cursor-pointer appearance-none disabled:opacity-70 disabled:bg-gray-50 dark:disabled:bg-gray-700/50 disabled:cursor-not-allowed focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none"
            style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E")`,
              backgroundRepeat: 'no-repeat',
              backgroundPosition: 'right 12px center',
              paddingRight: '36px',
            }}
            value={field.field_type}
            disabled={field._default}
            onChange={e => {
              onChange(index, 'field_type', e.target.value);
              if (!optionFieldTypes.includes(e.target.value)) onChange(index, 'options', []);
            }}
          >
            {FIELD_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <label className="flex items-center gap-1.5 text-[13px] font-medium text-gray-500 dark:text-gray-400 cursor-pointer whitespace-nowrap select-none py-1.5 px-2.5 rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 transition-colors hover:border-violet-500/30">
            <input
              type="checkbox"
              checked={field.required}
              disabled={field._default}
              onChange={e => onChange(index, 'required', e.target.checked)}
              className="w-4 h-4 accent-violet-600 cursor-pointer"
            />
            Required
          </label>
        </div>

        {needsOptions && !field._default && (
          <OptionEditor field={field} index={index} onChange={onChange} />
        )}
      </div>

      {!field._default && (
        <button
          className="text-red-500 dark:text-red-400 p-1.5 flex-shrink-0 rounded-lg mt-1 transition-colors hover:bg-red-50 dark:hover:bg-red-900/20 hover:border-red-300 dark:hover:border-red-700/30"
          onClick={() => onRemove(index)}
          title="Remove field"
        >
          <Trash2 size={16} />
        </button>
      )}
    </div>
  );
}

export default function HodFormBuilder({ onBack }) {
  const [context, setContext]   = useState('propose');
  const [fields, setFields]     = useState([]);
  const [title, setTitle]       = useState('');
  const [saving, setSaving]     = useState(false);
  const [saved, setSaved]       = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  const sensors = useSensors(useSensor(PointerSensor));

  const loadForm = (ctx) => {
    setLoading(true);
    setError('');
    fetchHodForm(ctx)
      .then(res => {
        const defaults = DEFAULT_FIELDS[ctx].map((f, i) => ({ ...f, _id: `default-${i}` }));
        const saved = (res.data.fields || []).map((f, i) => ({ ...f, _id: `saved-${i}-${f.id}` }));
        setTitle(res.data.title || '');
        setFields([...defaults, ...saved]);
      })
      .catch(() => {
        const defaults = DEFAULT_FIELDS[ctx].map((f, i) => ({ ...f, _id: `default-${i}` }));
        setFields(defaults);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadForm(context); }, [context]);

  const handleDragEnd = ({ active, over }) => {
    if (!over || active.id === over.id) return;
    const oldIdx = fields.findIndex(f => f._id === active.id);
    const newIdx = fields.findIndex(f => f._id === over.id);
    const defaultCount = DEFAULT_FIELDS[context].length;
    if (oldIdx < defaultCount || newIdx < defaultCount) return;
    setFields(arrayMove(fields, oldIdx, newIdx));
  };

  const addField = () => {
    setFields(prev => [...prev, {
      _id: `new-${Date.now()}`,
      label: '', field_type: 'text', required: false, options: [],
    }]);
  };

  const updateField = (index, key, value) => {
    setFields(prev => prev.map((f, i) => i === index ? { ...f, [key]: value } : f));
  };

  const removeField = (index) => {
    setFields(prev => prev.filter((_, i) => i !== index));
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      const customFields = fields
        .filter(f => !f._default)
        .map(({ label, field_type, required, options }) => ({ label, field_type, required, options }));
      await saveHodForm(context, { title, fields: customFields });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (err) {
      const details = err.response?.data?.details;
      setError(typeof details === 'string' ? details : err.response?.data?.error || 'Failed to save form. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto pb-6">
      {/* ── Header ── */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-violet-500/10 text-violet-600 dark:text-violet-400">
          <FileText size={20} />
        </div>
        <h2 className="text-2xl font-extrabold tracking-tight text-gray-900 dark:text-white">Form Builder</h2>
      </div>

      {/* ── Context Tabs ── */}
      <div className="flex gap-0 mb-6 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-1.5 shadow-sm">
        {Object.entries(CONTEXT_LABELS).map(([key, label]) => (
          <button
            key={key}
            className={`flex-1 py-2.5 px-5 rounded-md text-sm font-semibold transition-all border-[1.5px] ${
              context === key
                ? 'bg-violet-600 text-white border-violet-600 shadow-md shadow-violet-500/25'
                : 'bg-transparent text-gray-500 dark:text-gray-400 border-transparent hover:bg-violet-500/10 hover:text-violet-600'
            }`}
            onClick={() => setContext(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center items-center min-h-[200px] bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-7 shadow-sm">
          <Loader2 size={32} className="animate-spin text-violet-600" />
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-7 shadow-sm mb-5">
          {/* ── Form Title ── */}
          <div className="mb-5">
            <input
              className="w-full text-base font-semibold py-3.5 px-4 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white transition-all placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 focus:bg-gray-50 dark:focus:bg-gray-700 outline-none"
              placeholder="Form title (optional)"
              value={title}
              onChange={e => setTitle(e.target.value)}
            />
          </div>

          {/* ── Defaults Note ── */}
          <div className="flex items-center gap-2 text-[13px] font-medium text-gray-600 dark:text-gray-300 bg-violet-500/10 border border-violet-500/20 rounded-lg py-3 px-4 mb-5">
            <Lock size={14} className="text-violet-600 dark:text-violet-400 flex-shrink-0" />
            Locked fields are default and cannot be removed or reordered.
          </div>

          {/* ── Sortable Fields ── */}
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={fields.map(f => f._id)} strategy={verticalListSortingStrategy}>
              <div className="flex flex-col gap-3 mb-4">
                {fields.map((field, index) => (
                  <SortableField
                    key={field._id}
                    field={field}
                    index={index}
                    onChange={updateField}
                    onRemove={removeField}
                  />
                ))}
              </div>
            </SortableContext>
          </DndContext>

          {/* ── Add Field Button ── */}
          <button
            className="flex items-center justify-center gap-2 w-full py-3.5 px-5 mb-6 border-dashed border-2 border-violet-500/30 rounded-lg text-violet-600 dark:text-violet-400 bg-violet-500/5 font-semibold text-sm transition-all hover:border-violet-500 hover:bg-violet-500/15 hover:shadow-md hover:shadow-violet-500/10 hover:-translate-y-0.5"
            onClick={addField}
          >
            <Plus size={16} className="flex-shrink-0" />
            Add Field
          </button>

          {/* ── Error Alert ── */}
          {error && (
            <div className="border border-red-300 dark:border-red-700/50 rounded-lg py-3.5 px-4.5 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 font-medium text-sm mb-4">
              {error}
            </div>
          )}

          {/* ── Footer ── */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              className={`min-w-[160px] justify-center py-3 px-6 text-[15px] font-bold rounded-lg transition-all inline-flex items-center gap-2 ${
                saved
                  ? 'bg-emerald-500 text-white shadow-md shadow-emerald-500/20'
                  : 'bg-violet-600 text-white shadow-md shadow-violet-500/20 hover:shadow-lg hover:shadow-violet-500/25 hover:-translate-y-0.5'
              } disabled:opacity-60 disabled:cursor-not-allowed`}
              onClick={handleSave}
              disabled={saving}
            >
              {saving ? (
                <><Loader2 size={16} className="animate-spin" /> Saving...</>
              ) : saved ? (
                <><Check size={16} /> Saved!</>
              ) : (
                <><Save size={16} /> Save Form</>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}