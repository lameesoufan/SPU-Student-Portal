import { useState, useEffect } from 'react';
import {
  DndContext, closestCenter, PointerSensor, useSensor, useSensors,
} from '@dnd-kit/core';
import {
  SortableContext, verticalListSortingStrategy,
  useSortable, arrayMove,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  fetchWorkflowTemplates, createWorkflowTemplate, updateWorkflowTemplate,
  deleteWorkflowTemplate
} from '../api';

const TRIGGER_TYPES = [
  { value: 'project_start', label: 'بداية المشروع' },
  { value: 'after_days', label: 'بعد X يوم' },
  { value: 'date', label: 'Specific Date' },
  { value: 'milestone', label: 'عند里程碑' },
  { value: 'manual', label: 'تشغيل يدوي' },
];

const FIELD_TYPES = [
  { value: 'text',     label: 'نص قصير' },
  { value: 'textarea', label: 'نص طويل' },
  { value: 'number',   label: 'رقم' },
  { value: 'select',   label: 'قائمة منسدلة' },
  { value: 'radio',    label: 'أزرار اختيار' },
  { value: 'checkbox', label: 'مربعات اختيار' },
  { value: 'date',     label: 'Date' },
  { value: 'file',     label: 'رفع ملف' },
];

const RECURRENCE_UNITS = [
  { value: '', label: 'بدون تكرار' },
  { value: 'weekly', label: 'أسبوعي' },
  { value: 'biweekly', label: 'Every 2 Weeks' },
  { value: 'monthly', label: 'شهري' },
];

const WEEK_DAYS = [
  { value: 0, label: 'الإثنين' },
  { value: 1, label: 'الثلاثاء' },
  { value: 2, label: 'الأربعاء' },
  { value: 3, label: 'الخميس' },
  { value: 4, label: 'الجمعة' },
  { value: 5, label: 'السبت' },
  { value: 6, label: 'الأحد' },
];

const STATUS_BADGE = {
  active: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300',
  draft: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300',
  archived: 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400',
};

const TRIGGER_COLORS = {
  project_start: 'bg-emerald-500',
  after_days: 'bg-amber-500',
  date: 'bg-blue-500',
  milestone: 'bg-violet-500',
  manual: 'bg-rose-500',
};

const TRIGGER_DOT_COLORS = {
  project_start: 'bg-emerald-400',
  after_days: 'bg-amber-400',
  date: 'bg-blue-400',
  milestone: 'bg-violet-400',
  manual: 'bg-rose-400',
};

const Icons = {
  Grip: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="9" cy="5" r="1"/><circle cx="9" cy="12" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="19" r="1"/></svg>,
  Trash: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>,
  Plus: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>,
  Save: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>,
  Edit: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>,
  ArrowLeft: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>,
  List: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>,
  ChevronDown: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>,
  ChevronUp: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="18 15 12 9 6 15"/></svg>,
  Clock: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>,
  Calendar: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>,
  Flag: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" y1="22" x2="4" y2="15"/></svg>,
  Cursor: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z"/><path d="M13 13l6 6"/></svg>,
  Zap: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>,
  Eye: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>,
  ChevronRight: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>,
  X: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>,
};

function getTriggerIcon(triggerType) {
  switch (triggerType) {
    case 'project_start': return Icons.Zap;
    case 'after_days': return Icons.Clock;
    case 'date': return Icons.Calendar;
    case 'milestone': return Icons.Flag;
    case 'manual': return Icons.Cursor;
    default: return Icons.Zap;
  }
}

function getTriggerLabel(triggerType, stage) {
  switch (triggerType) {
    case 'project_start': return 'Project Start';
    case 'after_days': return stage.trigger_days ? `After ${stage.trigger_days} days` : 'After X Days';
    case 'date': return stage.trigger_date ? `On ${stage.trigger_date}` : 'Specific Date';
    case 'milestone': return 'عند الحد';
    case 'manual': return 'Manual Trigger';
    default: return triggerType;
  }
}

// ── Mini Pipeline (for list view cards) ──────────────────────────────────────
function MiniPipeline({ stages }) {
  if (!stages || stages.length === 0) return null;
  return (
    <div className="flex items-center gap-0 overflow-x-auto py-2">
      {stages.map((s, i) => (
        <div key={i} className="flex items-center">
          <div className="flex flex-col items-center">
            <div
              className={`w-3 h-3 rounded-full ${
                s.is_required
                  ? TRIGGER_DOT_COLORS[s.trigger_type] || 'bg-emerald-400'
                  : 'bg-gray-300 dark:bg-gray-600'
              }`}
              title={s.name || `Stage ${i + 1}`}
            />
            <span className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5 max-w-[48px] truncate text-center">
              {s.name || i + 1}
            </span>
          </div>
          {i < stages.length - 1 && (
            <div className="w-4 h-0.5 bg-violet-300 dark:bg-violet-600 mx-0.5 mb-3" />
          )}
        </div>
      ))}
    </div>
  );
}

// ── SortableField ────────────────────────────────────────────────────────────
function SortableField({ field, fieldIndex, stageIndex, onChange, onRemove }) {
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
      className="flex items-start gap-2 p-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg"
    >
      <div
        {...attributes}
        {...listeners}
        className="cursor-grab text-gray-400 dark:text-gray-500 mt-1 flex-shrink-0"
      >
        {Icons.Grip}
      </div>

      <div className="flex-1 min-w-0 space-y-2">
        <div className="flex items-center gap-2 flex-wrap">
          <input
            className="flex-1 min-w-[120px] px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200"
            placeholder="تسمية الحقل"
            value={field.label}
            onChange={e => onChange(stageIndex, fieldIndex, 'label', e.target.value)}
          />
          <select
            className="px-2 py-1.5 text-sm border border-gray-200 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200"
            value={field.field_type}
            onChange={e => onChange(stageIndex, fieldIndex, 'field_type', e.target.value)}
          >
            {FIELD_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <label className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-violet-600 focus:ring-violet-500 dark:focus:ring-violet-400 dark:bg-gray-700"
              checked={field.required}
              onChange={e => onChange(stageIndex, fieldIndex, 'required', e.target.checked)}
            />
            <span className="hidden sm:inline">إجباري</span>
          </label>
        </div>

        {needsOptions && (
          <div className="space-y-1">
            <span className="text-xs text-gray-500 dark:text-gray-400">Options (one per line):</span>
            <textarea
              className="w-full px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200 resize-y"
              rows={2}
              value={(field.options || []).join('\n')}
              onChange={e => onChange(stageIndex, fieldIndex, 'options', e.target.value.split('\n').filter(Boolean))}
              placeholder="Option 1&#10;Option 2&#10;Option 3"
            />
          </div>
        )}
      </div>

      <button
        className="p-1.5 text-gray-400 hover:text-red-500 dark:text-gray-500 dark:hover:text-red-400 rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors duration-200 flex-shrink-0"
        onClick={() => onRemove(stageIndex, fieldIndex)}
        title="إزالة الحقل"
      >
        {Icons.Trash}
      </button>
    </div>
  );
}

// ── Pipeline Connector ───────────────────────────────────────────────────────
function PipelineConnector({ stage }) {
  const triggerIcon = getTriggerIcon(stage.trigger_type);
  const triggerLabel = getTriggerLabel(stage.trigger_type, stage);

  return (
    <div className="flex flex-col items-center py-1">
      <div className="w-0.5 h-4 bg-violet-300 dark:bg-violet-600" />
      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-violet-50 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300 text-xs font-medium">
        {triggerIcon}
        <span>{triggerLabel}</span>
      </div>
      <div className="w-0.5 h-4 bg-violet-300 dark:bg-violet-600" />
      <svg width="12" height="8" viewBox="0 0 12 8" className="text-violet-300 dark:text-violet-600">
        <path d="M1 0 L6 7 L11 0" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

// ── SortableStage (Redesigned — Compact Card + Expandable Edit Panel) ───────
function SortableStage({
  stage, index, editingStage, onToggleEdit,
  onChange, onRemove, onFieldChange, onFieldRemove, onFieldAdd,
  onSelectForPreview,
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: stage._id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const isEditing = editingStage === index;
  const fields = stage.fields || [];
  const needsDays = stage.trigger_type === 'after_days';
  const needsDate = stage.trigger_type === 'date';
  const triggerIcon = getTriggerIcon(stage.trigger_type);
  const triggerLabel = getTriggerLabel(stage.trigger_type, stage);

  const fieldSensors = useSensors(useSensor(PointerSensor));

  const handleFieldDragEnd = ({ active, over }) => {
    if (!over || active.id === over.id) return;
    const oldIdx = fields.findIndex(f => f._id === active.id);
    const newIdx = fields.findIndex(f => f._id === over.id);
    const newFields = arrayMove(fields, oldIdx, newIdx);
    onChange(index, 'fields', newFields);
  };

  return (
    <div ref={setNodeRef} style={style}>
      {/* Compact Stage Card */}
      <div
        className={`flex items-center gap-3 p-3 bg-white dark:bg-gray-800 border rounded-xl transition-all duration-200 cursor-pointer ${
          isEditing
            ? 'ring-2 ring-violet-500 border-violet-300 dark:border-violet-600 shadow-md'
            : 'border-gray-200 dark:border-gray-700 hover:border-violet-300 dark:hover:border-violet-600 hover:shadow-sm'
        }`}
        onClick={() => {
          onSelectForPreview(index);
          onToggleEdit(index);
        }}
      >
        {/* Drag Handle */}
        <div
          {...attributes}
          {...listeners}
          className="cursor-grab text-gray-400 dark:text-gray-500 flex-shrink-0"
          onClick={e => e.stopPropagation()}
        >
          {Icons.Grip}
        </div>

        {/* Stage Number Circle */}
        <div className="w-7 h-7 rounded-full bg-violet-600 dark:bg-violet-500 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
          {index + 1}
        </div>

        {/* Stage Info */}
        <div className="flex-1 min-w-0">
          <div className="font-medium text-gray-900 dark:text-gray-100 truncate">
            {stage.name || 'Untitled Stage'}
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mt-0.5">
            <span className="flex items-center gap-1">
              {triggerIcon} {triggerLabel}
            </span>
            <span className="text-gray-300 dark:text-gray-600">|</span>
            <span>{fields.length} حقل</span>
            {stage.is_required && (
              <>
                <span className="text-gray-300 dark:text-gray-600">|</span>
                <span className="text-emerald-600 dark:text-emerald-400">إجباري</span>
              </>
            )}
          </div>
        </div>

        {/* Edit / Delete Buttons */}
        <div className="flex items-center gap-1 flex-shrink-0" onClick={e => e.stopPropagation()}>
          <button
            className="p-1.5 text-gray-400 hover:text-violet-600 dark:text-gray-500 dark:hover:text-violet-400 rounded-md hover:bg-violet-50 dark:hover:bg-violet-900/20 transition-colors duration-200"
            onClick={() => onToggleEdit(index)}
            title={isEditing ? 'طي' : 'تعديل'}
          >
            {isEditing ? Icons.ChevronUp : Icons.Edit}
          </button>
          <button
            className="p-1.5 text-gray-400 hover:text-red-500 dark:text-gray-500 dark:hover:text-red-400 rounded-md hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors duration-200"
            onClick={() => onRemove(index)}
            title="إزالة المرحلة"
          >
            {Icons.Trash}
          </button>
        </div>
      </div>

      {/* Expandable Edit Panel */}
      <div
        className={`overflow-hidden transition-all duration-300 ease-in-out ${
          isEditing ? 'max-h-[2000px] opacity-100' : 'max-h-0 opacity-0'
        }`}
      >
        <div className="mt-2 ml-6 mr-2 p-4 bg-white dark:bg-gray-800 border border-violet-200 dark:border-violet-700 rounded-xl space-y-3">
          {/* Name */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">الاسم</label>
            <input
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200"
              placeholder="اسم المرحلة"
              value={stage.name}
              onChange={e => onChange(index, 'name', e.target.value)}
            />
          </div>

          {/* Description */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">الوصف</label>
            <textarea
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200 resize-y"
              rows={2}
              placeholder="Stage description"
              value={stage.description}
              onChange={e => onChange(index, 'description', e.target.value)}
            />
          </div>

          {/* Trigger Type */}
          <div className="space-y-1">
            <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">المحفّز</label>
            <select
              className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200"
              value={stage.trigger_type}
              onChange={e => onChange(index, 'trigger_type', e.target.value)}
            >
              {TRIGGER_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>

          {/* Conditional: After Days */}
          {needsDays && (
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">أيام بعد بداية المشروع</label>
              <input
                className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200"
                type="number"
                min="1"
                value={stage.trigger_days || ''}
                onChange={e => onChange(index, 'trigger_days', e.target.value)}
              />
            </div>
          )}

          {/* Conditional: Specific Date */}
          {needsDate && (
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">تاريخ محدد</label>
              <input
                className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200"
                type="date"
                value={stage.trigger_date || ''}
                onChange={e => onChange(index, 'trigger_date', e.target.value)}
              />
            </div>
          )}

          {/* Required + Notify */}
          <div className="flex items-center gap-4 flex-wrap">
            <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-violet-600 focus:ring-violet-500 dark:focus:ring-violet-400 dark:bg-gray-700"
                checked={stage.is_required}
                onChange={e => onChange(index, 'is_required', e.target.checked)}
              />
              Required stage
            </label>
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-500 dark:text-gray-400">Notify before:</label>
              <input
                className="w-16 px-2 py-1 text-sm border border-gray-200 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200"
                type="number"
                min="0"
                value={stage.notify_before_days || 3}
                onChange={e => onChange(index, 'notify_before_days', e.target.value)}
              />
              <span className="text-xs text-gray-500 dark:text-gray-400">days</span>
            </div>
          </div>

          {/* Optional automatic closing */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-3 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50/60 dark:bg-amber-900/10">
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-600 dark:text-gray-300">تاريخ انتهاء المرحلة (اختياري)</label>
              <input
                className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-amber-500"
                type="date"
                value={stage.end_date || ''}
                onChange={e => onChange(index, 'end_date', e.target.value || null)}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-gray-600 dark:text-gray-300">التنبيه قبل الإغلاق (أيام)</label>
              <input
                className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-amber-500 disabled:opacity-50"
                type="number"
                min="0"
                disabled={!stage.end_date}
                value={stage.close_notify_before_days ?? 1}
                onChange={e => onChange(index, 'close_notify_before_days', e.target.value === '' ? null : Number(e.target.value))}
              />
            </div>
            <p className="md:col-span-2 text-xs text-gray-500 dark:text-gray-400">عند ترك تاريخ الانتهاء فارغًا تبقى المرحلة مفتوحة ولا يتم إرسال تنبيه إغلاق.</p>
          </div>

          {/* Recurring */}
          <div className="space-y-2">
            <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 cursor-pointer">
              <input
                type="checkbox"
                className="w-4 h-4 rounded border-gray-300 dark:border-gray-600 text-violet-600 focus:ring-violet-500 dark:focus:ring-violet-400 dark:bg-gray-700"
                checked={stage.is_recurring || false}
                onChange={e => onChange(index, 'is_recurring', e.target.checked)}
              />
              Recurring
            </label>

            {stage.is_recurring && (
              <div className="ml-6 space-y-2 p-3 bg-violet-50 dark:bg-violet-900/20 rounded-lg border border-violet-100 dark:border-violet-800">
                <div className="flex items-center gap-2">
                  <label className="text-xs font-medium text-gray-500 dark:text-gray-400 w-16">التكرار:</label>
                  <select
                    className="flex-1 px-2 py-1.5 text-sm border border-gray-200 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200"
                    value={stage.recurrence_unit || ''}
                    onChange={e => onChange(index, 'recurrence_unit', e.target.value)}
                  >
                    {RECURRENCE_UNITS.map(u => (
                      <option key={u.value} value={u.value}>{u.label}</option>
                    ))}
                  </select>
                </div>

                {(stage.recurrence_unit === 'weekly' || stage.recurrence_unit === 'biweekly') && (
                  <div className="flex items-center gap-2">
                    <label className="text-xs font-medium text-gray-500 dark:text-gray-400 w-16">On:</label>
                    <select
                      className="flex-1 px-2 py-1.5 text-sm border border-gray-200 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200"
                      value={stage.recurrence_day_of_week ?? 3}
                      onChange={e => onChange(index, 'recurrence_day_of_week', Number(e.target.value))}
                    >
                      {WEEK_DAYS.map(d => (
                        <option key={d.value} value={d.value}>{d.label}</option>
                      ))}
                    </select>
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <label className="text-xs font-medium text-gray-500 dark:text-gray-400 w-16">End date:</label>
                  <input
                    className="flex-1 px-2 py-1.5 text-sm border border-gray-200 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200"
                    type="date"
                    value={stage.recurrence_end_date || ''}
                    onChange={e => onChange(index, 'recurrence_end_date', e.target.value)}
                    placeholder="Optional"
                  />
                </div>

                <div className="flex items-center gap-2">
                  <label className="text-xs font-medium text-gray-500 dark:text-gray-400 w-16">Max:</label>
                  <input
                    className="flex-1 px-2 py-1.5 text-sm border border-gray-200 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200"
                    type="number"
                    min="1"
                    value={stage.max_occurrences || ''}
                    onChange={e => onChange(index, 'max_occurrences', e.target.value ? Number(e.target.value) : null)}
                    placeholder="Max occurrences (optional)"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Form Fields Section */}
          <div className="pt-2 border-t border-gray-100 dark:border-gray-700">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-violet-500" />
                حقول النموذج ({fields.length})
              </h4>
              <button
                className="flex items-center gap-1 px-2.5 py-1 text-xs font-medium text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-900/20 rounded-md hover:bg-violet-100 dark:hover:bg-violet-900/40 transition-colors duration-200"
                onClick={() => onFieldAdd(index)}
                type="button"
              >
                {Icons.Plus} إضافة حقل
              </button>
            </div>

            {fields.length === 0 ? (
              <div className="py-6 text-center text-sm text-gray-400 dark:text-gray-500">
                No fields yet. Add fields for students to fill.
              </div>
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                <DndContext sensors={fieldSensors} collisionDetection={closestCenter} onDragEnd={handleFieldDragEnd}>
                  <SortableContext items={fields.map(f => f._id)} strategy={verticalListSortingStrategy}>
                    {fields.map((field, fieldIndex) => (
                      <SortableField
                        key={field._id}
                        field={field}
                        fieldIndex={fieldIndex}
                        stageIndex={index}
                        onChange={onFieldChange}
                        onRemove={onFieldRemove}
                      />
                    ))}
                  </SortableContext>
                </DndContext>
              </div>
            )}
          </div>

          {/* Done Button */}
          <div className="pt-2 flex justify-end">
            <button
              className="px-4 py-1.5 text-sm font-medium text-white bg-violet-600 dark:bg-violet-500 rounded-lg hover:bg-violet-700 dark:hover:bg-violet-600 transition-colors duration-200"
              onClick={() => onToggleEdit(index)}
              type="button"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Form Preview (Right Panel) ──────────────────────────────────────────────
function FormPreview({ stages, selectedStageForPreview }) {
  const stage = stages[selectedStageForPreview];
  const fields = stage?.fields || [];

  const renderFieldPreview = (field) => {
    switch (field.field_type) {
      case 'text':
        return (
          <input
            className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-400 dark:text-gray-500"
            placeholder={field.label || 'Text input'}
            disabled
          />
        );
      case 'textarea':
        return (
          <textarea
            className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-400 dark:text-gray-500 resize-none"
            rows={3}
            placeholder={field.label || 'إدخال نص طويل'}
            disabled
          />
        );
      case 'number':
        return (
          <input
            className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-400 dark:text-gray-500"
            type="number"
            placeholder={field.label || 'إدخال رقم'}
            disabled
          />
        );
      case 'select':
        return (
          <select className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-400 dark:text-gray-500" disabled>
            <option>{(field.options && field.options[0]) || 'Select an option...'}</option>
            {(field.options || []).slice(1).map((opt, i) => (
              <option key={i}>{opt}</option>
            ))}
          </select>
        );
      case 'radio':
        return (
          <div className="space-y-1.5">
            {(field.options || []).length === 0 ? (
              <span className="text-xs text-gray-400 dark:text-gray-500">لا توجد خيارات محددة</span>
            ) : (
              (field.options || []).map((opt, i) => (
                <label key={i} className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                  <span className="w-4 h-4 rounded-full border-2 border-gray-300 dark:border-gray-600" />
                  {opt}
                </label>
              ))
            )}
          </div>
        );
      case 'checkbox':
        return (
          <div className="space-y-1.5">
            {(field.options || []).length === 0 ? (
              <span className="text-xs text-gray-400 dark:text-gray-500">لا توجد خيارات محددة</span>
            ) : (
              (field.options || []).map((opt, i) => (
                <label key={i} className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                  <span className="w-4 h-4 rounded border-2 border-gray-300 dark:border-gray-600" />
                  {opt}
                </label>
              ))
            )}
          </div>
        );
      case 'date':
        return (
          <input
            className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-400 dark:text-gray-500"
            type="date"
            disabled
          />
        );
      case 'file':
        return (
          <div className="w-full px-3 py-6 text-sm border-2 border-dashed border-gray-200 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-400 dark:text-gray-500 text-center">
            Click or drag file to upload
          </div>
        );
      default:
        return (
          <input
            className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-400 dark:text-gray-500"
            placeholder={field.label || 'إدخال'}
            disabled
          />
        );
    }
  };

  return (
    <div className="bg-gray-50 dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 h-fit sticky top-4">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4">
        <span className="p-1.5 rounded-lg bg-violet-100 dark:bg-violet-900/30 text-violet-600 dark:text-violet-400">
          {Icons.Eye}
        </span>
        Student Preview
      </h3>

      {stage ? (
        <div className="space-y-4">
          <div>
            <div className="font-medium text-gray-900 dark:text-gray-100 text-lg">
              {stage.name || 'Untitled Stage'}
            </div>
            <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 mt-1">
              {getTriggerIcon(stage.trigger_type)}
              <span>{getTriggerLabel(stage.trigger_type, stage)}</span>
            </div>
          </div>

          <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-4">
            {fields.length === 0 ? (
              <div className="py-8 text-center text-sm text-gray-400 dark:text-gray-500">
                No fields in this stage yet.
              </div>
            ) : (
              fields.map((field, i) => (
                <div key={field._id || i} className="space-y-1.5">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    {field.label || 'Untitled Field'}
                    {field.required && <span className="text-red-500 ml-0.5">*</span>}
                  </label>
                  {renderFieldPreview(field)}
                </div>
              ))
            )}

            <button
              className="w-full py-2 text-sm font-medium text-white bg-violet-600 dark:bg-violet-500 rounded-lg opacity-70 cursor-not-allowed"
              disabled
            >
              Submit Stage
            </button>
          </div>

          {/* Pipeline Progress */}
          <div>
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">تقدم المسار</div>
            <div className="flex items-center gap-0">
              {stages.map((s, i) => (
                <div key={i} className="flex items-center">
                  <div
                    className={`w-3 h-3 rounded-full transition-colors duration-200 ${
                      i === selectedStageForPreview
                        ? 'bg-violet-500 ring-2 ring-violet-300 dark:ring-violet-600'
                        : i < selectedStageForPreview
                        ? 'bg-emerald-400'
                        : 'bg-gray-300 dark:bg-gray-600'
                    }`}
                  />
                  {i < stages.length - 1 && (
                    <div className={`w-3 h-0.5 ${
                      i < selectedStageForPreview
                        ? 'bg-emerald-400'
                        : 'bg-gray-300 dark:bg-gray-600'
                    }`} />
                  )}
                </div>
              ))}
            </div>
            <div className="flex justify-between mt-1">
              {stages.map((s, i) => (
                <span key={i} className={`text-[9px] ${i === selectedStageForPreview ? 'text-violet-600 dark:text-violet-400 font-bold' : 'text-gray-400 dark:text-gray-500'}`}>
                  {i + 1}
                </span>
              ))}
            </div>
          </div>
        </div>
      ) : (
        <div className="py-12 text-center">
          <div className="text-gray-300 dark:text-gray-600 mb-3">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mx-auto">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
              <circle cx="12" cy="12" r="3"/>
            </svg>
          </div>
          <p className="text-sm text-gray-400 dark:text-gray-500">
            Click on a stage to preview how<br />students will see the form
          </p>
        </div>
      )}
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────────────
export default function WorkflowBuilder({ onBack }) {
  const [view, setView] = useState('list');
  const [templates, setTemplates] = useState([]);
  const [currentTemplate, setCurrentTemplate] = useState(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [stages, setStages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [editingStage, setEditingStage] = useState(null);
  const [selectedStageForPreview, setSelectedStageForPreview] = useState(null);
  const [showPreview, setShowPreview] = useState(true);

  const sensors = useSensors(useSensor(PointerSensor));

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = () => {
    setLoading(true);
    fetchWorkflowTemplates()
      .then(res => setTemplates(res.data))
      .catch(() => setError('فشل تحميل القوالب'))
      .finally(() => setLoading(false));
  };

  const handleDragEnd = ({ active, over }) => {
    if (!over || active.id === over.id) return;
    const oldIdx = stages.findIndex(s => s._id === active.id);
    const newIdx = stages.findIndex(s => s._id === over.id);
    setStages(arrayMove(stages, oldIdx, newIdx));
  };

  const addStage = () => {
    const newStage = {
      _id: `new-${Date.now()}`,
      name: '',
      description: '',
      trigger_type: 'project_start',
      trigger_days: null,
      trigger_date: null,
      notify_before_days: 3,
      end_date: null,
      close_notify_before_days: 1,
      is_required: true,
      is_recurring: false,
      recurrence_unit: '',
      recurrence_day_of_week: null,
      recurrence_interval: 1,
      recurrence_end_date: null,
      max_occurrences: null,
      fields: [],
      _showFields: true,
    };
    setStages(prev => [...prev, newStage]);
    const newIndex = stages.length;
    setEditingStage(newIndex);
    setSelectedStageForPreview(newIndex);
  };

  const updateStage = (index, key, value) => {
    setStages(prev => prev.map((s, i) => i === index ? { ...s, [key]: value } : s));
  };

  const removeStage = (index) => {
    setStages(prev => prev.filter((_, i) => i !== index));
    if (editingStage === index) {
      setEditingStage(null);
      setSelectedStageForPreview(null);
    } else if (editingStage !== null && editingStage > index) {
      setEditingStage(editingStage - 1);
      if (selectedStageForPreview !== null && selectedStageForPreview > index) {
        setSelectedStageForPreview(selectedStageForPreview - 1);
      }
    }
    if (selectedStageForPreview !== null && selectedStageForPreview > index) {
      setSelectedStageForPreview(prev => prev !== null ? prev - 1 : null);
    }
  };

  const toggleStageFields = (index) => {
    setStages(prev => prev.map((s, i) => i === index ? { ...s, _showFields: !s._showFields } : s));
  };

  const toggleEdit = (index) => {
    if (editingStage === index) {
      setEditingStage(null);
    } else {
      setEditingStage(index);
      setSelectedStageForPreview(index);
    }
  };

  const addField = (stageIndex) => {
    setStages(prev => prev.map((s, i) => {
      if (i === stageIndex) {
        return {
          ...s,
          fields: [...(s.fields || []), {
            _id: `field-${Date.now()}`,
            label: '',
            field_type: 'text',
            required: false,
            options: [],
          }]
        };
      }
      return s;
    }));
  };

  const updateField = (stageIndex, fieldIndex, key, value) => {
    setStages(prev => prev.map((s, i) => {
      if (i === stageIndex) {
        return {
          ...s,
          fields: s.fields.map((f, fi) => fi === fieldIndex ? { ...f, [key]: value } : f)
        };
      }
      return s;
    }));
  };

  const removeField = (stageIndex, fieldIndex) => {
    setStages(prev => prev.map((s, i) => {
      if (i === stageIndex) {
        return {
          ...s,
          fields: s.fields.filter((_, fi) => fi !== fieldIndex)
        };
      }
      return s;
    }));
  };

  const handleSave = async () => {
    if (!name.trim()) {
      setError('Template name is required');
      return;
    }
    if (stages.length === 0) {
      setError('أضف مرحلة واحدة على الأقل');
      return;
    }

    setSaving(true);
    setError('');
    try {
      const data = {
        name,
        description,
        stages: stages.map((s, idx) => ({
          id: s.id || null,
          name: s.name,
          description: s.description,
          order: idx,
          trigger_type: s.trigger_type,
          trigger_days: s.trigger_days ? Number(s.trigger_days) : null,
          trigger_date: s.trigger_date || null,
          notify_before_days: Number(s.notify_before_days || 3),
          end_date: s.end_date || null,
          close_notify_before_days: s.end_date ? Number(s.close_notify_before_days ?? 1) : null,
          is_required: s.is_required,
          is_recurring: s.is_recurring || false,
          recurrence_unit: s.is_recurring ? (s.recurrence_unit || null) : null,
          recurrence_day_of_week: s.is_recurring ? (s.recurrence_day_of_week ?? null) : null,
          recurrence_interval: s.is_recurring ? (s.recurrence_interval || 1) : null,
          recurrence_end_date: s.is_recurring ? (s.recurrence_end_date || null) : null,
          max_occurrences: s.is_recurring ? (s.max_occurrences ? Number(s.max_occurrences) : null) : null,
          fields: (s.fields || []).map((f, fidx) => ({
            id: f.id || null,
            label: f.label,
            field_type: f.field_type,
            required: f.required,
            options: f.options || [],
            order: fidx,
          })),
        })),
      };

      if (currentTemplate) {
        await updateWorkflowTemplate(currentTemplate.id, data);
      } else {
        await createWorkflowTemplate(data);
      }

      loadTemplates();
      setView('list');
      resetForm();
    } catch (err) {
      const respData = err.response?.data;
      if (respData && typeof respData === 'object') {
        if (respData.error === 'لا يمكن تحديث قالب مع سير عمل نشط') {
          const projects = (respData.projects || []).filter(Boolean).join(', ');
          alert(
            'لا يمكن تحديث "' + (respData.template_name || '') + '"\n\n' +
            'هذا القالب لديه ' + respData.active_count + ' سير عمل نشط قيد التشغيل.\n' +
            (projects ? 'المشاريع: ' + projects + '\n' : '') +
            '\nيرجى تعطيل أو إكمال سير العمل أولاً، أو استخدام "استبدال سير العمل" لتعيين قالب جديد.'
          );
        } else if (respData.error === 'لا يمكن حذف قالب مع سير عمل نشط') {
          const projects = (respData.projects || []).filter(Boolean).join(', ');
          alert(
            'لا يمكن حذف "' + (respData.template_name || '') + '"\n\n' +
            'هذا القالب لديه ' + respData.active_count + ' سير عمل نشط قيد التشغيل.\n' +
            (projects ? 'المشاريع: ' + projects + '\n' : '') +
            '\nيرجى تعطيل أو إكمال سير العمل أولاً، ثم حاول مرة أخرى.'
          );
        } else {
          setError(respData.error || respData.detail || 'فشل حفظ القالب');
        }
      } else {
        setError('فشل حفظ القالب');
      }
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (template) => {
    setCurrentTemplate(template);
    setName(template.name);
    setDescription(template.description);
    setStages(template.stages.map((s, i) => ({
      _id: `stage-${i}-${s.id}`,
      ...s,
      fields: (s.fields || []).map((f, fi) => ({
        _id: `field-${i}-${fi}-${f.id}`,
        ...f,
      })),
      _showFields: false,
    })));
    setEditingStage(null);
    setSelectedStageForPreview(null);
    setView('create');
  };

  const handleDelete = async (templateId) => {
    if (!window.confirm('Delete this workflow template?')) return;
    try {
      await deleteWorkflowTemplate(templateId);
      loadTemplates();
    } catch (err) {
      const data = err.response?.data;
      if (data && typeof data === 'object') {
        if (data.error === 'Cannot delete template with active workflows') {
          const projects = (data.projects || []).filter(Boolean).join(', ');
          alert(
            'لا يمكن حذف "' + (data.template_name || '') + '"\n\n' +
            'هذا القالب لديه ' + data.active_count + ' سير عمل نشط قيد التشغيل.\n' +
            (projects ? 'المشاريع: ' + projects + '\n' : '') +
            '\nيرجى تعطيل أو إكمال سير العمل أولاً، ثم حاول مرة أخرى.'
          );
        } else {
          setError(data.error || data.detail || 'فشل حذف القالب');
        }
      } else {
        setError('فشل حذف القالب');
      }
    }
  };

  const resetForm = () => {
    setCurrentTemplate(null);
    setName('');
    setDescription('');
    setStages([]);
    setError('');
    setEditingStage(null);
    setSelectedStageForPreview(null);
  };

  const handleNewTemplate = () => {
    resetForm();
    setView('create');
  };

  // ── List View ────────────────────────────────────────────────────────────
  if (view === 'list') {
    return (
      <div className="w-full overflow-x-hidden p-2 sm:p-4">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <button
                className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-violet-600 dark:hover:text-violet-400 hover:bg-violet-50 dark:hover:bg-violet-900/20 rounded-lg transition-colors duration-200"
                onClick={onBack}
              >
                {Icons.ArrowLeft} رجوع
              </button>
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">
                قوالب سير العمل
              </h2>
            </div>
            <button
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-violet-600 dark:bg-violet-500 rounded-lg hover:bg-violet-700 dark:hover:bg-violet-600 shadow-sm transition-colors duration-200"
              onClick={handleNewTemplate}
            >
              {Icons.Plus} قالب جديد
            </button>
          </div>

          {/* Loading */}
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
              <span className="ml-3 text-gray-500 dark:text-gray-400">Loading templates...</span>
            </div>
          ) : templates.length === 0 ? (
            /* Empty State */
            <div className="text-center py-16 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
              <div className="text-gray-300 dark:text-gray-600 mb-4">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mx-auto">
                  <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/>
                  <line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
                </svg>
              </div>
              <p className="text-gray-500 dark:text-gray-400 font-medium">لا توجد قوالب سير عمل بعد.</p>
              <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">أنشئ واحداً لتحديد مراحل وأشكال المشاريع.</p>
            </div>
          ) : (
            /* Template Cards with Mini Pipeline */
            <div className="space-y-4">
              {templates.map(t => (
                <div
                  key={t.id}
                  className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 hover:border-violet-300 dark:hover:border-violet-600 hover:shadow-md transition-all duration-200 overflow-hidden"
                >
                  <div className="p-4 sm:p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 truncate">
                          {t.name}
                        </h3>
                        {t.description && (
                          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">
                            {t.description}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <button
                          className="p-2 text-gray-400 hover:text-violet-600 dark:text-gray-500 dark:hover:text-violet-400 rounded-lg hover:bg-violet-50 dark:hover:bg-violet-900/20 transition-colors duration-200"
                          onClick={() => handleEdit(t)}
                          title="تعديل"
                        >
                          {Icons.Edit}
                        </button>
                        <button
                          className="p-2 text-gray-400 hover:text-red-500 dark:text-gray-500 dark:hover:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors duration-200"
                          onClick={() => handleDelete(t.id)}
                          title="حذف"
                        >
                          {Icons.Trash}
                        </button>
                      </div>
                    </div>

                    {/* Mini Pipeline */}
                    {t.stages && t.stages.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
                        <MiniPipeline stages={t.stages} />
                      </div>
                    )}

                    {/* Meta Row */}
                    <div className="mt-3 flex items-center gap-3 text-sm">
                      <span className="flex items-center gap-1.5 text-gray-500 dark:text-gray-400">
                        {Icons.List}
                        <span>{t.stages?.length || 0} stage{t.stages?.length !== 1 ? 's' : ''}</span>
                      </span>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[t.status] || STATUS_BADGE.draft}`}>
                        {t.status}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Create/Edit View (Split Layout) ──────────────────────────────────────
  return (
    <div className="w-full overflow-x-hidden">
      <div className="max-w-6xl mx-auto p-2 sm:p-4">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <button
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-violet-600 dark:hover:text-violet-400 hover:bg-violet-50 dark:hover:bg-violet-900/20 rounded-lg transition-colors duration-200"
            onClick={() => { setView('list'); resetForm(); }}
          >
            {Icons.ArrowLeft} العودة للقائمة
          </button>
          <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">
            {currentTemplate ? 'تعديل' : 'إنشاء'} قالب سير العمل
          </h2>
        </div>

        <div className="flex flex-col lg:flex-row gap-6">
          {/* Left Side — Pipeline Builder (60%) */}
          <div className="flex-1 lg:max-w-[60%] space-y-5">
            {/* Template Info Card */}
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 sm:p-5 space-y-3">
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">اسم القالب</label>
                <input
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200"
                  placeholder="مثال: سير عمل مشاريع هندسة البرمجيات"
                  value={name}
                  onChange={e => setName(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">الوصف</label>
                <textarea
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200 resize-y"
                  rows={3}
                  placeholder="صف قالب سير العمل هذا..."
                  value={description}
                  onChange={e => setDescription(e.target.value)}
                />
              </div>
            </div>

            {/* Pipeline */}
            <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 sm:p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-violet-500" />
                  Pipeline
                </h3>
                <button
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-900/20 rounded-lg hover:bg-violet-100 dark:hover:bg-violet-900/40 transition-colors duration-200"
                  onClick={addStage}
                >
                  {Icons.Plus} إضافة مرحلة
                </button>
              </div>

              {stages.length === 0 ? (
                <div className="py-12 text-center bg-gray-50 dark:bg-gray-800/50 rounded-lg border-2 border-dashed border-gray-200 dark:border-gray-700">
                  <div className="text-gray-300 dark:text-gray-600 mb-3">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mx-auto">
                      <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
                    </svg>
                  </div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">لا توجد مراحل بعد. أضف مراحل لتحديد سير عملك.</p>
                </div>
              ) : (
                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
                  <SortableContext items={stages.map(s => s._id)} strategy={verticalListSortingStrategy}>
                    <div className="space-y-0">
                      {stages.map((stage, index) => (
                        <div key={stage._id}>
                          {/* Connector between stages */}
                          {index > 0 && (
                            <PipelineConnector stage={stages[index - 1]} />
                          )}
                          <SortableStage
                            stage={stage}
                            index={index}
                            editingStage={editingStage}
                            onToggleEdit={toggleEdit}
                            onChange={updateStage}
                            onRemove={removeStage}
                            onFieldChange={updateField}
                            onFieldRemove={removeField}
                            onFieldAdd={addField}
                            onToggleFields={toggleStageFields}
                            onSelectForPreview={setSelectedStageForPreview}
                          />
                        </div>
                      ))}
                    </div>
                  </SortableContext>
                </DndContext>
              )}
            </div>

            {/* Error */}
            {error && (
              <div className="px-4 py-3 text-sm text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                {error}
              </div>
            )}

            {/* Save Button */}
            <div className="flex justify-end">
              <button
                className="flex items-center gap-2 px-6 py-2.5 text-sm font-medium text-white bg-violet-600 dark:bg-violet-500 rounded-lg hover:bg-violet-700 dark:hover:bg-violet-600 shadow-sm transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={handleSave}
                disabled={saving}
              >
                {Icons.Save} {saving ? 'جاري الحفظ...' : 'حفظ القالب'}
              </button>
            </div>
          </div>

          {/* Right Side — Form Preview (40%) */}
          <div className="lg:w-[40%]">
            {/* Toggle for small screens */}
            <div className="lg:hidden mb-4">
              <button
                className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-900/20 rounded-lg hover:bg-violet-100 dark:hover:bg-violet-900/40 transition-colors duration-200 w-full justify-center"
                onClick={() => setShowPreview(!showPreview)}
              >
                {Icons.Eye} {showPreview ? 'Hide' : 'Show'} Preview
                {showPreview ? Icons.ChevronUp : Icons.ChevronDown}
              </button>
            </div>
            <div className={`${showPreview ? 'block' : 'hidden'} lg:block`}>
              <FormPreview
                stages={stages}
                selectedStageForPreview={selectedStageForPreview}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
