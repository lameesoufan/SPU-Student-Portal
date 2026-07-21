import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { fetchProjectWorkflow, submitWorkflowStage } from '../api';
import {
  Clock, CheckCircle2, XCircle, AlertCircle, FileText,
  Send, ArrowLeft, ChevronRight, Loader2, Sparkles,
  Calendar, MessageSquare, GitBranch, Zap, ArrowRight, Lock,
} from 'lucide-react';

// ─── Status Configuration ────────────────────────────────────────────────────
const STATUS_CONFIG = {
    scheduled: {
    label: 'مجدول',
    icon: Clock,
    dot: 'bg-slate-400',
    badge: 'bg-slate-500/10 text-slate-500 border border-slate-500/20',
    card: 'border-l-slate-400',
    glow: '',
    accent: '#64748b',
    },
  pending: {
    label: 'قيد الانتظار',
    icon: Clock,
    dot: 'bg-slate-300',
    badge: 'bg-amber-500/10 text-amber-600 border border-amber-500/20',
    card: 'border-l-slate-300',
    glow: '',
    accent: '#94a3b8',
  },
  in_progress: {
    label: 'قيد التنفيذ',
    icon: Zap,
    dot: 'bg-violet-500 animate-pulse',
    badge: 'bg-violet-500/10 text-violet-600 border border-violet-500/20',
    card: 'border-l-violet-500',
    glow: 'shadow-[0_0_25px_rgba(139,92,246,0.15)]',
    accent: '#8b5cf6',
  },
  submitted: {
    label: 'تم الإرسال',
    icon: Send,
    dot: 'bg-blue-500',
    badge: 'bg-blue-500/10 text-blue-600 border border-blue-500/20',
    card: 'border-l-blue-500',
    glow: '',
    accent: '#3b82f6',
  },
  approved: {
    label: 'تمت الموافقة',
    icon: CheckCircle2,
    dot: 'bg-emerald-500',
    badge: 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20',
    card: 'border-l-emerald-500',
    glow: '',
    accent: '#10b981',
  },
  rejected: {
    label: 'مرفوض',
    icon: XCircle,
    dot: 'bg-red-500',
    badge: 'bg-red-500/10 text-red-500 border border-red-500/20',
    card: 'border-l-red-500',
    glow: '',
    accent: '#ef4444',
  },
  overdue: {
    label: 'متأخر',
    icon: AlertCircle,
    dot: 'bg-red-500 animate-pulse',
    badge: 'bg-red-500/10 text-red-500 border border-red-500/20',
    card: 'border-l-red-500',
    glow: 'shadow-[0_0_25px_rgba(239,68,68,0.15)]',
    accent: '#ef4444',
  },
};

const getStatus = (status) => STATUS_CONFIG[status] || STATUS_CONFIG.pending;

// ─── Horizontal Pipeline ─────────────────────────────────────────────────────
function HorizontalPipeline({ stages }) {
  if (!stages || stages.length === 0) return null;

  const isCompleted = (status) => ['submitted', 'approved'].includes(status);
  const isActive = (status) => status === 'in_progress';
  const isFailed = (status) => ['rejected', 'overdue'].includes(status);
  const isScheduled = (status) => status === 'scheduled';

  return (
    <div className="flex items-center gap-0 w-full overflow-x-auto py-2">
      {stages.map((stage, idx) => {
        const status = stage?.status;
        const completed = isCompleted(status);
        const active = isActive(status);
        const failed = isFailed(status);
        const scheduled = isScheduled(status);
        const isLast = idx === stages.length - 1;

        return (
          <div key={stage?.id || idx} className="flex items-center flex-shrink-0">
            {/* Node */}
            <div className="flex flex-col items-center">
              <div className={`w-9 h-9 rounded-full flex items-center justify-center transition-all duration-500 border-2 ${
                completed
                  ? 'bg-emerald-500 border-emerald-500 text-white shadow-[0_0_12px_rgba(16,185,129,0.3)]'
                  : active
                  ? 'bg-violet-500 border-violet-500 text-white shadow-[0_0_15px_rgba(139,92,246,0.4)] animate-pulse'
                  : failed
                  ? 'bg-red-500 border-red-500 text-white shadow-[0_0_12px_rgba(239,68,68,0.3)]'
                  : scheduled
                  ? 'bg-slate-300 border-slate-400 text-slate-500 border-dashed'
                  : 'bg-card border-border text-muted-foreground'
              }`}>
                {completed ? <CheckCircle2 size={18} /> : active ? <Zap size={16} /> : failed ? <XCircle size={16} /> : scheduled ? <Clock size={14} /> : <span className="text-xs font-bold">{idx + 1}</span>}
              </div>
              <span className={`text-[11px] font-medium mt-1.5 text-center max-w-[100px] leading-tight line-clamp-2 ${scheduled ? 'text-slate-400' : 'text-foreground'}`}>
                {stage?.stage_details?.name || `المرحلة ${idx + 1}`}
              </span>
              <span className={`text-[10px] font-semibold mt-0.5 px-1.5 py-0.5 rounded-full ${
                completed ? 'bg-emerald-500/10 text-emerald-600' :
                active ? 'bg-violet-500/10 text-violet-600' :
                failed ? 'bg-red-500/10 text-red-500' :
                scheduled ? 'bg-slate-500/10 text-slate-500' :
                'bg-muted text-muted-foreground'
              }`}>
                {completed ? (status === 'approved' ? 'تمت الموافقة' : 'تم الإرسال') :
                 active ? 'قيد التنفيذ' :
                 failed ? (status === 'overdue' ? 'متأخر' : 'مرفوض') :
                 scheduled ? 'مجدول' :
                 'قيد الانتظار'}
              </span>
            </div>

            {/* Connector Line */}
            {!isLast && (
              <div className={`w-10 sm:w-14 h-[3px] mx-1 rounded-full transition-all duration-500 ${
                completed
                  ? 'bg-emerald-500'
                  : active
                  ? 'bg-gradient-to-r from-violet-500 to-border'
                  : scheduled
                  ? 'bg-slate-300 border-t border-dashed border-slate-400'
                  : 'bg-border'
              }`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Stage Card ──────────────────────────────────────────────────────────────
function StageCard({ stageInstance, idx, onOpen }) {
  const status = stageInstance?.status;
  const cfg = getStatus(status);
  const Icon = cfg.icon;
  const isScheduled = status === 'scheduled';
  const fields = stageInstance?.stage_details?.fields || [];
  const hasFields = fields.length > 0;
  const requiredFields = fields.filter(f => f.required);
  const respondedFieldIds = new Set(
    (stageInstance?.field_responses || []).filter(r => r.value).map(r => r.field)
  );
  const hasUnansweredRequired = requiredFields.some(f => !respondedFieldIds.has(f.id));
  const canSubmit = ['pending', 'in_progress', 'rejected'].includes(status)
    || (hasUnansweredRequired && ['submitted', 'approved'].includes(status));

  const actionLabel = status === 'rejected'
    ? 'إعادة الإرسال'
    : hasUnansweredRequired ? 'إكمال الحقول الجديدة'
    : status === 'in_progress' ? 'متابعة'
    : 'ملء النموذج';

  return (
    <div className={`group relative bg-card rounded-xl border overflow-hidden transition-all duration-300 border-l-[3px] ${cfg.card} ${cfg.glow} ${
      isScheduled ? 'border-dashed opacity-60 hover:shadow-none hover:translate-y-0' : 'border-border hover:shadow-lg hover:-translate-y-0.5'
    }`}>
      <div className="absolute inset-0 bg-gradient-to-br from-transparent to-transparent group-hover:from-violet-500/[0.02] group-hover:to-indigo-500/[0.02] transition-all duration-300 pointer-events-none" />
      <div className="relative p-4">
        <div className="flex items-start gap-3 mb-3">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 font-bold text-sm text-white shadow-sm ${
            status === 'approved' ? 'bg-emerald-500' :
            status === 'in_progress' ? 'bg-violet-500' :
            status === 'rejected' || status === 'overdue' ? 'bg-red-500' :
            status === 'submitted' ? 'bg-blue-500' :
            isScheduled ? 'bg-slate-400' :
            'bg-slate-400'
          }`}>
            {isScheduled ? <Clock size={16} /> : idx + 1}
          </div>
          <div className="flex-1 min-w-0">
            <h4 className={`text-[15px] font-semibold m-0 leading-tight truncate ${isScheduled ? 'text-slate-500' : 'text-foreground'}`}>
              {stageInstance?.stage_details?.name || 'مرحلة'}
            </h4>
            <div className="flex items-center gap-2 mt-1.5">
              <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full ${cfg.badge}`}>
                <Icon size={10} />
                {cfg.label}
              </span>
              {fields.length > 0 && !isScheduled && (
                <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                  <FileText size={9} />
                  {fields.length} حقول
                </span>
              )}
            </div>
          </div>
        </div>

        {/* المراحل المجدولة - عرض رسالة القفل */}
        {isScheduled && (
          <div className="flex items-center gap-2 py-2.5 px-3 bg-slate-500/5 border border-dashed border-slate-400/40 rounded-lg text-[13px] text-slate-500">
            <Clock size={14} className="text-slate-400 flex-shrink-0" />
            <span>ستكون هذه المرحلة متاحة بتاريخ {stageInstance?.due_date ? new Date(stageInstance.due_date).toLocaleDateString() : 'تاريخ لاحق'}</span>
          </div>
        )}

        {/* المراحل العادية */}
        {!isScheduled && (
          <>
            {stageInstance?.submitted_at && (
              <div className="flex items-center gap-1.5 text-[12px] text-muted-foreground mb-3">
                <Calendar size={11} className="text-muted-foreground/60" />
                أُرسلت بتاريخ {new Date(stageInstance.submitted_at).toLocaleDateString()}
              </div>
            )}

            {stageInstance?.feedback && (
              <div className="bg-amber-500/5 border-l-[3px] border-l-amber-500 rounded-r-lg px-3 py-2.5 mb-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <MessageSquare size={11} className="text-amber-600" />
                  <span className="text-[11px] font-semibold text-amber-600 uppercase tracking-wide">ملاحظات</span>
                </div>
                <p className="text-[13px] text-foreground/80 m-0 leading-relaxed">{stageInstance.feedback}</p>
              </div>
            )}

            {canSubmit && hasFields && (
              <button
                className="inline-flex items-center gap-1.5 py-1.5 px-3.5 text-[13px] font-semibold rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-all shadow-sm hover:shadow-md active:scale-[0.98]"
                onClick={() => onOpen(stageInstance)}
              >
                <ChevronRight size={14} />
                {actionLabel}
              </button>
            )}

            {!hasFields && canSubmit && (
              <div className="flex items-center gap-2 py-2 px-3 bg-muted/50 rounded-lg text-[13px] text-muted-foreground italic">
                <FileText size={13} className="text-muted-foreground/50" />
                لا يوجد نموذج مُعدّ لهذه المرحلة.
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ─── Workflow Stage Form ─────────────────────────────────────────────────────
function WorkflowStageForm({ stageInstance, onSubmit, onCancel, submitting, error }) {
  const fields = useMemo(
    () => stageInstance?.stage_details?.fields || [],
    [stageInstance?.stage_details?.fields]
  );
  const [formData, setFormData] = useState({});
  const [fileFields, setFileFields] = useState({}); // Store actual File objects
  const [validationErrors, setValidationErrors] = useState({});

  useEffect(() => {
    const initialData = {};
    fields.forEach(field => { initialData[field.id] = ''; });
    (stageInstance?.field_responses || []).forEach(response => {
      initialData[response.field] = response.value || '';
    });
    setFormData(initialData);
    setFileFields({});
    setValidationErrors({});
  }, [stageInstance, fields]);

  const handleFieldChange = (fieldId, value) => {
    setFormData(prev => ({ ...prev, [fieldId]: value }));
    // Clear validation error when user starts typing
    if (validationErrors[fieldId]) {
      setValidationErrors(prev => {
        const next = { ...prev };
        delete next[fieldId];
        return next;
      });
    }
  };

  const handleFileChange = (fieldId, file) => {
    setFormData(prev => ({ ...prev, [fieldId]: file ? file.name : '' }));
    setFileFields(prev => ({ ...prev, [fieldId]: file }));
    // Clear validation error when user uploads file
    if (validationErrors[fieldId]) {
      setValidationErrors(prev => {
        const next = { ...prev };
        delete next[fieldId];
        return next;
      });
    }
  };

  const handleCheckboxChange = (fieldId, option, checked) => {
    const currentValue = formData[fieldId] || '';
    const currentOptions = currentValue ? currentValue.split(',') : [];
    let newOptions;
    if (checked) {
      newOptions = [...currentOptions, option];
    } else {
      newOptions = currentOptions.filter(o => o !== option);
    }
    setFormData(prev => ({ ...prev, [fieldId]: newOptions.join(',') }));
    // Clear validation error when user interacts
    if (validationErrors[fieldId]) {
      setValidationErrors(prev => {
        const next = { ...prev };
        delete next[fieldId];
        return next;
      });
    }
  };

  // ── Validation helper ──
  const isFieldEmpty = (field, value) => {
    if (value === null || value === undefined) return true;
    if (typeof value === 'string') return value.trim() === '';
    if (Array.isArray(value)) return value.length === 0;
    if (typeof value === 'number') return false; // 0 is a valid number
    if (typeof value === 'object') return Object.keys(value).length === 0;
    return !value;
  };

  const validateForm = () => {
    const errors = {};
    for (const field of fields) {
      const value = formData[field.id];
      if (field.required && isFieldEmpty(field, value)) {
        errors[field.id] = 'هذا الحقل مطلوب';
      }
      // Validate radio/select/checkbox requires non-empty value
      if (field.required && (field.field_type === 'radio' || field.field_type === 'select' || field.field_type === 'checkbox')) {
        if (isFieldEmpty(field, value)) {
          errors[field.id] = 'يرجى اختيار قيمة';
        }
      }
      // Validate file upload
      if (field.required && field.field_type === 'file' && isFieldEmpty(field, value)) {
        errors[field.id] = 'يرجى رفع ملف';
      }
    }
    return errors;
  };

  const handleSubmit = (e) => {
    // ── Run validation ──
    const errors = validateForm();
    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      // Scroll to first error
      const firstErrorFieldId = Object.keys(errors)[0];
      const errorElement = document.querySelector(`[data-field-id="${firstErrorFieldId}"]`);
      if (errorElement) {
        errorElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        errorElement.focus?.();
      }
      return;
    }
    // ── Validation passed, submit ──
    setValidationErrors({});
    const responseData = {};
    fields.forEach(field => { responseData[field.id] = formData[field.id] || ''; });
    // Include actual File objects from fileFields
    Object.entries(fileFields).forEach(([fieldId, file]) => {
      if (file instanceof File) {
        responseData[fieldId] = file;
      }
    });
    onSubmit(responseData);
  };

  const FIELD_ICONS = {
    text: FileText,
    textarea: MessageSquare,
    number: ArrowRight,
    date: Calendar,
    select: ChevronRight,
    file: FileText,
  };

  return (
    <div className="bg-card rounded-xl border border-border overflow-hidden shadow-sm">
      <div className="p-5 flex flex-col gap-5">
        {fields.map(field => {
          const value = formData[field.id] || '';
          const FieldIcon = FIELD_ICONS[field.field_type] || FileText;
          const fieldError = validationErrors[field.id];
          const hasError = !!fieldError;
          const errorBorderClass = hasError ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20' : 'border-border focus:border-violet-500 focus:ring-violet-500/20';

          return (
            <div key={field.id} className="flex flex-col gap-1.5" data-field-id={field.id}>
              <label htmlFor={`field-input-${field.id}`} className="text-[13px] font-semibold text-foreground flex items-center gap-1.5">
                <FieldIcon size={13} className="text-muted-foreground" />
                {field.label}
                {field.required && <span className="text-red-500 ml-0.5">*</span>}
              </label>

              {field.field_type === 'text' && (
                <input id={`field-input-${field.id}`} type="text" data-field-id={field.id} required={field.required || undefined} aria-invalid={hasError || undefined} aria-describedby={hasError ? `error-${field.id}` : undefined} className={`w-full py-2.5 px-3 text-sm border-[1.5px] ${errorBorderClass} rounded-lg bg-input text-foreground transition-all placeholder:text-muted-foreground/50 focus:ring-2 outline-none`} value={value} onChange={e => handleFieldChange(field.id, e.target.value)} placeholder={`أدخل ${field.label}...`} />
              )}
              {field.field_type === 'textarea' && (
                <textarea id={`field-input-${field.id}`} data-field-id={field.id} required={field.required || undefined} aria-invalid={hasError || undefined} aria-describedby={hasError ? `error-${field.id}` : undefined} className={`w-full py-2.5 px-3 text-sm border-[1.5px] ${errorBorderClass} rounded-lg bg-input text-foreground transition-all placeholder:text-muted-foreground/50 focus:ring-2 outline-none resize-none`} rows={4} value={value} onChange={e => handleFieldChange(field.id, e.target.value)} placeholder={`أدخل ${field.label}...`} />
              )}
              {field.field_type === 'number' && (
                <input id={`field-input-${field.id}`} type="number" data-field-id={field.id} required={field.required || undefined} aria-invalid={hasError || undefined} aria-describedby={hasError ? `error-${field.id}` : undefined} className={`w-full py-2.5 px-3 text-sm border-[1.5px] ${errorBorderClass} rounded-lg bg-input text-foreground transition-all placeholder:text-muted-foreground/50 focus:ring-2 outline-none`} value={value} onChange={e => handleFieldChange(field.id, e.target.value)} min="0" step="any" />
              )}
              {field.field_type === 'date' && (
                <div className="relative flex items-center">
                  <Calendar size={15} className="absolute left-3 text-muted-foreground pointer-events-none z-[1]" />
                  <input id={`field-input-${field.id}`} type="date" data-field-id={field.id} required={field.required || undefined} aria-invalid={hasError || undefined} aria-describedby={hasError ? `error-${field.id}` : undefined} className={`w-full !py-2.5 !pl-9 !pr-3 text-sm border-[1.5px] ${errorBorderClass} rounded-lg bg-input text-foreground transition-all focus:ring-2 outline-none [color-scheme:light] dark:[color-scheme:dark] [&::-webkit-calendar-picker-indicator]:opacity-40 [&::-webkit-calendar-picker-indicator]:cursor-pointer [&::-webkit-calendar-picker-indicator]:hover:opacity-100`} value={value} onChange={e => handleFieldChange(field.id, e.target.value)} />
                </div>
              )}
              {field.field_type === 'select' && (
                <select id={`field-input-${field.id}`} data-field-id={field.id} required={field.required || undefined} aria-invalid={hasError || undefined} aria-describedby={hasError ? `error-${field.id}` : undefined} className={`w-full py-2.5 px-3 text-sm border-[1.5px] ${errorBorderClass} rounded-lg bg-input text-foreground transition-all focus:ring-2 outline-none`} value={value} onChange={e => handleFieldChange(field.id, e.target.value)}>
                  <option value="">اختر خياراً...</option>
                  {(field.options || []).map((option, optIdx) => (
                    <option key={optIdx} value={option}>{option}</option>
                  ))}
                </select>
              )}
              {field.field_type === 'radio' && (
                <div data-field-id={field.id} role="radiogroup" aria-invalid={hasError || undefined} aria-describedby={hasError ? `error-${field.id}` : undefined} className={`flex flex-col gap-2.5 mt-1 p-2 rounded-lg ${hasError ? 'bg-red-500/5 border border-red-500/20' : ''}`}>
                  {(field.options || []).map((option, optIdx) => (
                    <label key={optIdx} className="flex items-center gap-2.5 text-[14px] text-foreground cursor-pointer group/radio">
                      <input type="radio" name={'field-' + field.id} value={option} checked={value === option} onChange={e => handleFieldChange(field.id, e.target.value)} className="accent-violet-600 w-4 h-4 cursor-pointer" />
                      <span className="group-hover/radio:text-violet-600 transition-colors">{option}</span>
                    </label>
                  ))}
                </div>
              )}
              {field.field_type === 'checkbox' && (
                <div data-field-id={field.id} role="group" aria-invalid={hasError || undefined} aria-describedby={hasError ? `error-${field.id}` : undefined} className={`flex flex-col gap-2.5 mt-1 p-2 rounded-lg ${hasError ? 'bg-red-500/5 border border-red-500/20' : ''}`}>
                  {(field.options || []).map((option, optIdx) => {
                    const selectedOptions = value ? value.split(',') : [];
                    return (
                      <label key={optIdx} className="flex items-center gap-2.5 text-[14px] text-foreground cursor-pointer group/check">
                        <input type="checkbox" checked={selectedOptions.includes(option)} onChange={e => handleCheckboxChange(field.id, option, e.target.checked)} className="accent-violet-600 w-4 h-4 rounded cursor-pointer" />
                        <span className="group-hover/check:text-violet-600 transition-colors">{option}</span>
                      </label>
                    );
                  })}
                </div>
              )}
              {field.field_type === 'file' && (
                <input 
                  id={`field-input-${field.id}`} 
                  type="file" 
                  data-field-id={field.id} 
                  required={field.required || undefined} 
                  aria-invalid={hasError || undefined} 
                  aria-describedby={hasError ? `error-${field.id}` : undefined} 
                  className={`w-full py-2 px-3 text-sm border-[1.5px] ${errorBorderClass} rounded-lg bg-input text-foreground transition-all focus:ring-2 outline-none file:mr-3 file:py-1 file:px-3 file:rounded-md file:border-0 file:text-[13px] file:font-semibold file:bg-violet-600 file:text-white hover:file:bg-violet-700 file:cursor-pointer cursor-pointer`} 
                  onChange={e => { 
                    const file = e.target.files[0]; 
                    if (file) { 
                      handleFileChange(field.id, file); 
                    } else {
                      handleFileChange(field.id, null);
                    }
                  }} 
                  accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.gif" 
                />
              )}

              {hasError && (
                <div id={`error-${field.id}`} className="flex items-center gap-1.5 text-[12px] text-red-600 mt-0.5 font-medium">
                  <AlertCircle size={12} className="flex-shrink-0" />
                  <span>{fieldError}</span>
                </div>
              )}
            </div>
          );
        })}

        {error && (
          <div role="alert" aria-live="assertive" className="flex items-center gap-2 py-2.5 px-3.5 bg-red-500/10 border border-red-500/20 rounded-lg text-[13px] text-red-600">
            <AlertCircle size={14} className="flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {Object.keys(validationErrors).length > 0 && (
          <div role="alert" aria-live="assertive" className="flex items-center gap-2 py-2.5 px-3.5 bg-red-500/10 border border-red-500/20 rounded-lg text-[13px] text-red-600 font-medium">
            <AlertCircle size={14} className="flex-shrink-0" />
            <span>
              يرجى ملء {Object.keys(validationErrors).length} حقلاً مطلوباً مميزاً بعلامة <span className="text-red-500 font-bold">*</span>
            </span>
          </div>
        )}

        <div className="flex justify-end gap-3 pt-5 mt-2 border-t border-border">
          <button type="button" className="inline-flex items-center justify-center gap-1.5 py-2 px-4 text-sm font-medium rounded-lg bg-muted text-muted-foreground border border-border hover:bg-border transition-colors" onClick={onCancel}>
            إلغاء
          </button>
          <button type="button" className="inline-flex items-center justify-center gap-1.5 py-2 px-5 text-sm font-semibold rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-all shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]" disabled={submitting} onClick={handleSubmit}>
            {submitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
            {submitting ? 'جاري الإرسال...' : 'إرسال'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Component ──────────────────────────────────────────────────────────
export default function ProjectWorkflowView({ projectBoardId }) {
  const [selectedStage, setSelectedStage] = useState(null);
  const [error, setError] = useState('');
  const [workflow, setWorkflow] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const loadWorkflow = useCallback(async () => {
    if (!projectBoardId) { setLoading(false); return; }
    setLoading(true);
    try {
      const res = await fetchProjectWorkflow(projectBoardId);
      setWorkflow(res.data);
      setError('');
    } catch (err) {
      setError(err.response?.data?.error || 'فشل تحميل سير العمل.');
      setWorkflow(null);
    } finally {
      setLoading(false);
    }
  }, [projectBoardId]);

  useEffect(() => { loadWorkflow(); }, [loadWorkflow]);

  const handleSubmitStage = async (formData) => {
    setError('');
    setSubmitting(true);
    try {
      // Check if we have any File objects
      const hasFiles = Object.values(formData).some(v => v instanceof File);
      
      if (hasFiles) {
        // Send FormData directly, don't clean File objects
        const formDataToSend = new FormData();
        Object.entries(formData).forEach(([key, value]) => {
          if (value instanceof File) {
            formDataToSend.append(`field_${key}`, value);
          } else {
            formDataToSend.append(`field_${key}`, value || '');
          }
        });
        
        await submitWorkflowStage(selectedStage.id, formData);
      } else {
        // Regular JSON submission
        const cleanData = {};
        Object.entries(formData).forEach(([key, value]) => {
          if (value === null || value === undefined) {
            cleanData[key] = '';
          } else if (typeof value === 'object' && !(value instanceof Array)) {
            cleanData[key] = '';
          } else {
            cleanData[key] = String(value);
          }
        });
        await submitWorkflowStage(selectedStage.id, { field_responses: cleanData });
      }
      
      await loadWorkflow();
      setSelectedStage(null);
    } catch (err) {
      const data = err.response?.data;
      if (Array.isArray(data?.missing_fields) && data.missing_fields.length) {
        setError(`يرجى ملء الحقول المطلوبة: ${data.missing_fields.join('، ')}`);
      } else if (data?.error) {
        setError(data.error);
      } else if (data && typeof data === 'object') {
        setError(Object.values(data).flat().join(' '));
      } else {
        setError('فشل إرسال المرحلة. حاول مرة أخرى.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  // ── Loading ──
  if (loading) {
    return (
      <div className="w-full overflow-x-hidden flex flex-col items-center justify-center py-16 gap-4">
        <div className="w-10 h-10 border-[3px] border-violet-500/20 border-t-violet-500 rounded-full animate-spin" />
        <span className="text-[15px] text-muted-foreground">جارٍ تحميل سير العمل...</span>
      </div>
    );
  }

  // ── Error State ──
  if (error && !workflow) {
    return (
      <div className="w-full overflow-x-hidden flex flex-col items-center justify-center py-16 gap-3 text-center">
        <div className="w-14 h-14 rounded-full bg-red-500/10 flex items-center justify-center">
          <AlertCircle size={24} className="text-red-500" />
        </div>
        <p className="text-[15px] text-muted-foreground max-w-[400px] m-0">{error}</p>
        <button className="mt-1 inline-flex items-center gap-1.5 py-2 px-4 text-sm font-medium rounded-lg bg-muted text-muted-foreground border border-border hover:bg-border hover:border-violet-500 hover:text-violet-600 transition-all" onClick={() => { setError(''); loadWorkflow(); }}>
          إعادة المحاولة
        </button>
      </div>
    );
  }

  // ── Empty State ──
  if (!workflow) {
    return (
      <div className="w-full overflow-x-hidden flex flex-col items-center justify-center py-16 gap-3 text-center">
        <div className="w-14 h-14 rounded-full bg-violet-500/10 flex items-center justify-center">
          <GitBranch size={24} className="text-violet-500" />
        </div>
        <p className="text-[15px] text-muted-foreground max-w-[400px] m-0">لا يوجد سير عمل معيّن لهذا المشروع بعد.</p>
      </div>
    );
  }

  // ── Stage Form View ──
  if (selectedStage) {
    const cfg = getStatus(selectedStage?.status);
    return (
      <div className="w-full overflow-x-hidden">
        <div className="max-w-5xl mx-auto p-2 sm:p-4">
          <button
            className="inline-flex items-center gap-2 py-2 px-3.5 text-[14px] font-medium rounded-lg border border-border text-foreground hover:bg-muted hover:border-violet-500 hover:text-violet-600 transition-all mb-5"
            onClick={() => setSelectedStage(null)}
          >
            <ArrowLeft size={15} />
            العودة إلى سير العمل
          </button>

          <div className="flex items-center gap-3 mb-2">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-white font-bold shadow-sm ${
              selectedStage?.status === 'approved' ? 'bg-emerald-500' :
              selectedStage?.status === 'in_progress' ? 'bg-violet-500' :
              selectedStage?.status === 'rejected' || selectedStage?.status === 'overdue' ? 'bg-red-500' :
              'bg-slate-400'
            }`}>
              <Sparkles size={18} />
            </div>
            <div>
              <h3 className="text-[18px] font-bold text-foreground m-0 leading-tight">{selectedStage?.stage_details?.name || 'مرحلة'}</h3>
              <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full mt-0.5 ${cfg.badge}`}>
                {cfg.label}
              </span>
            </div>
          </div>

          {selectedStage?.stage_details?.description && (
            <div className="py-3 px-4 bg-muted/50 rounded-lg text-[14px] text-muted-foreground mb-5 border border-border/50">
              {selectedStage.stage_details.description}
            </div>
          )}

          <WorkflowStageForm
            stageInstance={selectedStage}
            onSubmit={handleSubmitStage}
            onCancel={() => setSelectedStage(null)}
            submitting={submitting}
            error={error}
          />
        </div>
      </div>
    );
  }

  // ── Main Workflow View ──
  const stages = workflow?.stage_instances || [];
  const completedCount = stages.filter(s => ['submitted', 'approved'].includes(s?.status)).length;
  const progress = stages.length > 0 ? (completedCount / stages.length) * 100 : 0;

  return (
    <div className="w-full overflow-x-hidden">
      <div className="max-w-5xl mx-auto p-2 sm:p-4">
        {/* Page Header */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-md">
              <GitBranch size={20} className="text-white" />
            </div>
            <div>
              <h2 className="text-[22px] font-bold text-foreground m-0 leading-tight">سير عمل المشروع</h2>
              <p className="text-[15px] text-muted-foreground m-0">{workflow?.template_details?.name || 'سير العمل'}</p>
            </div>
          </div>

          {workflow?.template_details?.description && (
            <div className="mt-4 py-3 px-4 bg-background border-l-[3px] border-l-violet-500 rounded-r-lg text-[14px] text-muted-foreground">
              {workflow.template_details.description}
            </div>
          )}
        </div>

        {/* Progress Section */}
        <div className="mb-7">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[14px] text-muted-foreground font-medium">
              اكتملت {completedCount} من {stages.length} مرحلة
            </span>
            <span className={`text-[14px] font-bold px-2.5 py-0.5 rounded-full ${
              progress === 100 ? 'bg-emerald-500/10 text-emerald-600' : 'bg-violet-500/10 text-violet-600'
            }`}>
              {Math.round(progress)}%
            </span>
          </div>
          <div className="h-2.5 bg-muted/60 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-[width] duration-700 ease-out ${
                progress === 100
                  ? 'bg-gradient-to-r from-emerald-500 to-green-400'
                  : 'bg-gradient-to-r from-violet-600 to-indigo-500'
              }`}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Pipeline */}
        <div className="mb-7 bg-card rounded-xl border border-border p-4">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-3 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-500" />
            تقدّم المراحل
          </h3>
          <HorizontalPipeline stages={stages} />
        </div>

        {/* Stage Cards Grid */}
        <div className="grid grid-cols-2 gap-4 max-[768px]:grid-cols-1">
          {stages.map((stageInstance, idx) => (
            <StageCard
              key={stageInstance?.id || idx}
              stageInstance={stageInstance}
              idx={idx}
              onOpen={setSelectedStage}
            />
          ))}
        </div>

        {/* Error */}
        {error && (
          <div role="alert" aria-live="assertive" className="flex items-center gap-2 py-2.5 px-3.5 bg-red-500/10 border border-red-500/20 rounded-lg text-[13px] text-red-600 mt-4">
            <AlertCircle size={14} className="flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>
    </div>
  );
}