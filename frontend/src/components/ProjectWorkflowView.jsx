import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { fetchProjectWorkflow, submitWorkflowStage } from '../api';
import {
  Clock, CheckCircle2, XCircle, AlertCircle, FileText,
  Send, ChevronRight, ChevronDown, Loader2, Zap,
  Calendar, MessageSquare, GitBranch, X, Lock,
} from 'lucide-react';

/**
 * ProjectWorkflowView — النسخة الكاملة المُعاد تصميمها
 *
 * كل منطق العمل الأصلي محفوظ 100% بدون تغيير:
 *   - fetchProjectWorkflow / submitWorkflowStage (API الحقيقي)
 *   - WorkflowStageForm: كل أنواع الحقول (text/textarea/number/date/select/radio/checkbox/file)
 *     + Validation + Scroll-to-error + تعبئة الإجابات السابقة
 *   - منطق canSubmit/hasUnansweredRequired (إعادة فتح مرحلة submitted لو أُضيف لها حقل جديد بالقالب)
 *   - معالجة أخطاء الإرسال (missing_fields, error, object errors)
 *
 * اللي تغيّر هو العرض بس:
 *   - المراحل المنجزة (لا تحتاج إجراء) → صف مضغوط بدل Card كامل
 *   - المراحل التي تحتاج إجراء → Card بارز واحد أو أكثر (نادرًا ما يكون أكثر من واحد)
 *   - المراحل المجدولة → مجموعة مطويّة
 *   - تعبئة النموذج → Drawer جانبي بدل استبدال الصفحة بالكامل
 */

// ─── Status Configuration (نفس الأصل) ────────────────────────────────────────
const STATUS_CONFIG = {
  scheduled:   { label: 'مجدول',        icon: Clock,        badge: 'bg-slate-500/10 text-slate-500 border border-slate-500/20' },
  pending:     { label: 'قيد الانتظار',  icon: Clock,        badge: 'bg-amber-500/10 text-amber-600 border border-amber-500/20' },
  in_progress: { label: 'قيد التنفيذ',   icon: Zap,          badge: 'bg-violet-500/10 text-violet-600 border border-violet-500/20' },
  submitted:   { label: 'تم الإرسال',    icon: Send,         badge: 'bg-blue-500/10 text-blue-600 border border-blue-500/20' },
  approved:    { label: 'تمت الموافقة',  icon: CheckCircle2, badge: 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20' },
  rejected:    { label: 'مرفوض',         icon: XCircle,      badge: 'bg-red-500/10 text-red-500 border border-red-500/20' },
  overdue:     { label: 'متأخر',         icon: AlertCircle,  badge: 'bg-red-500/10 text-red-500 border border-red-500/20' },
};
const getStatus = (status) => STATUS_CONFIG[status] || STATUS_CONFIG.pending;

// ─── هل هالمرحلة تحتاج إجراء من الطالب؟ (نفس منطق الأصل بالضبط) ──────────────
function stageNeedsAction(stageInstance) {
  const status = stageInstance?.status;
  const fields = stageInstance?.stage_details?.fields || [];
  const requiredFields = fields.filter((f) => f.required);
  const respondedFieldIds = new Set(
    (stageInstance?.field_responses || []).filter((r) => r.value).map((r) => r.field)
  );
  const hasUnansweredRequired = requiredFields.some((f) => !respondedFieldIds.has(f.id));
  return (
    ['pending', 'in_progress', 'rejected'].includes(status) ||
    (hasUnansweredRequired && ['submitted', 'approved'].includes(status))
  );
}

// ─── صف مضغوط لمرحلة منجزة (لا تحتاج إجراء) ─────────────────────────────────
function CompletedRow({ stageInstance }) {
  const status = stageInstance?.status;
  const cfg = getStatus(status);
  const Icon = cfg.icon;

  return (
    <div className="flex items-center gap-3 py-2.5 px-1">
      <div
        className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${
          status === 'approved' ? 'bg-emerald-500' : status === 'rejected' ? 'bg-red-500' : 'bg-blue-500'
        }`}
      >
        <Icon size={13} className="text-white" />
      </div>
      <span className="text-[14px] text-foreground flex-1 truncate">
        {stageInstance?.stage_details?.name || 'مرحلة'}
      </span>
      {stageInstance?.submitted_at && (
        <span className="text-[12px] text-muted-foreground hidden sm:inline">
          {new Date(stageInstance.submitted_at).toLocaleDateString()}
        </span>
      )}
      <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full ${cfg.badge}`}>
        {cfg.label}
      </span>
    </div>
  );
}

// ─── بطاقة بارزة لمرحلة تحتاج إجراء ──────────────────────────────────────────
function ActionStageCard({ stageInstance, onOpen }) {
  const status = stageInstance?.status;
  const cfg = getStatus(status);
  const Icon = cfg.icon;
  const fields = stageInstance?.stage_details?.fields || [];
  const hasFields = fields.length > 0;

  const requiredFields = fields.filter((f) => f.required);
  const respondedFieldIds = new Set(
    (stageInstance?.field_responses || []).filter((r) => r.value).map((r) => r.field)
  );
  const hasUnansweredRequired = requiredFields.some((f) => !respondedFieldIds.has(f.id));

  const actionLabel =
    status === 'rejected' ? 'إعادة الإرسال'
    : hasUnansweredRequired ? 'إكمال الحقول الجديدة'
    : status === 'in_progress' ? 'متابعة'
    : 'ملء النموذج';

  return (
    <div className="bg-card rounded-xl border-2 border-violet-500/30 p-5">
      <div className="flex items-start gap-3 mb-3">
        <div
          className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
            status === 'rejected' || status === 'overdue' ? 'bg-red-500' : 'bg-violet-600'
          }`}
        >
          <Icon size={18} className="text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full ${cfg.badge}`}>
            {cfg.label}
          </span>
          <h3 className="text-[16px] font-semibold text-foreground mt-1.5 m-0 leading-tight">
            {stageInstance?.stage_details?.name || 'مرحلة'}
          </h3>
        </div>
      </div>

      {stageInstance?.feedback && (
        <div className="bg-amber-500/5 border-l-[3px] border-l-amber-500 rounded-r-lg px-3 py-2.5 mb-3">
          <div className="flex items-center gap-1.5 mb-1">
            <MessageSquare size={11} className="text-amber-600" />
            <span className="text-[11px] font-semibold text-amber-600 uppercase tracking-wide">ملاحظات</span>
          </div>
          <p className="text-[13px] text-foreground/80 m-0 leading-relaxed">{stageInstance.feedback}</p>
        </div>
      )}

      {hasFields ? (
        <>
          <div className="flex items-center gap-2 mb-4 text-[13px] text-muted-foreground">
            <FileText size={14} />
            <span>{fields.length} حقول</span>
          </div>
          <button
            className="w-full inline-flex items-center justify-center gap-1.5 py-2.5 rounded-lg bg-violet-600 text-white text-[14px] font-semibold hover:bg-violet-700 transition-colors shadow-sm hover:shadow-md active:scale-[0.98]"
            onClick={() => onOpen(stageInstance)}
          >
            <ChevronRight size={15} />
            {actionLabel}
          </button>
        </>
      ) : (
        <div className="flex items-center gap-2 py-2 px-3 bg-muted/50 rounded-lg text-[13px] text-muted-foreground italic">
          <FileText size={13} className="text-muted-foreground/50" />
          لا يوجد نموذج مُعدّ لهذه المرحلة.
        </div>
      )}
    </div>
  );
}

// ─── مجموعة المراحل المجدولة (مطويّة افتراضيًا) ──────────────────────────────
function ScheduledGroup({ stages }) {
  const [open, setOpen] = useState(false);
  if (!stages || stages.length === 0) return null;

  return (
    <div className="border border-dashed border-slate-400/40 rounded-lg overflow-hidden mt-2">
      <button
        className="w-full flex items-center justify-between py-2.5 px-3.5 text-[13px] text-slate-500 hover:bg-muted/50 transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="flex items-center gap-2">
          <Lock size={13} />
          {stages.length} {stages.length === 1 ? 'مرحلة قادمة' : 'مراحل قادمة'}
        </span>
        <ChevronDown size={15} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="border-t border-dashed border-slate-400/40">
          {stages.map((s) => (
            <div key={s.id} className="flex items-center justify-between py-2 px-3.5 text-[13px] border-b border-dashed border-slate-400/30 last:border-0">
              <span className="text-slate-500">{s.stage_details?.name || 'مرحلة'}</span>
              <span className="text-slate-400">
                {s.due_date ? new Date(s.due_date).toLocaleDateString() : 'تاريخ لاحق'}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Workflow Stage Form (منطق الأصل كاملاً، بدون أي تغيير بالتحقق أو الحقول) ──
function WorkflowStageForm({ stageInstance, onSubmit, onCancel, submitting, error }) {
  const fields = useMemo(
    () => stageInstance?.stage_details?.fields || [],
    [stageInstance?.stage_details?.fields]
  );
  const [formData, setFormData] = useState({});
  const [validationErrors, setValidationErrors] = useState({});

  useEffect(() => {
    const initialData = {};
    fields.forEach((field) => { initialData[field.id] = ''; });
    (stageInstance?.field_responses || []).forEach((response) => {
      initialData[response.field] = response.value || '';
    });
    setFormData(initialData);
    setValidationErrors({});
  }, [stageInstance, fields]);

  const handleFieldChange = (fieldId, value) => {
    setFormData((prev) => ({ ...prev, [fieldId]: value }));
    if (validationErrors[fieldId]) {
      setValidationErrors((prev) => {
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
      newOptions = currentOptions.filter((o) => o !== option);
    }
    setFormData((prev) => ({ ...prev, [fieldId]: newOptions.join(',') }));
    if (validationErrors[fieldId]) {
      setValidationErrors((prev) => {
        const next = { ...prev };
        delete next[fieldId];
        return next;
      });
    }
  };

  const isFieldEmpty = (field, value) => {
    if (value === null || value === undefined) return true;
    if (typeof value === 'string') return value.trim() === '';
    if (Array.isArray(value)) return value.length === 0;
    if (typeof value === 'number') return false;
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
      if (field.required && (field.field_type === 'radio' || field.field_type === 'select' || field.field_type === 'checkbox')) {
        if (isFieldEmpty(field, value)) errors[field.id] = 'يرجى اختيار قيمة';
      }
      if (field.required && field.field_type === 'file' && isFieldEmpty(field, value)) {
        errors[field.id] = 'يرجى رفع ملف';
      }
    }
    return errors;
  };

  const handleSubmit = () => {
    const errors = validateForm();
    if (Object.keys(errors).length > 0) {
      setValidationErrors(errors);
      const firstErrorFieldId = Object.keys(errors)[0];
      const errorElement = document.querySelector(`[data-field-id="${firstErrorFieldId}"]`);
      if (errorElement) {
        errorElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        errorElement.focus?.();
      }
      return;
    }
    setValidationErrors({});
    const responseData = {};
    fields.forEach((field) => { responseData[field.id] = formData[field.id] || ''; });
    onSubmit(responseData);
  };

  const FIELD_ICONS = { text: FileText, textarea: MessageSquare, number: ChevronRight, date: Calendar, select: ChevronRight, file: FileText };

  return (
    <div className="flex flex-col gap-5">
      {fields.map((field) => {
        const value = formData[field.id] || '';
        const FieldIcon = FIELD_ICONS[field.field_type] || FileText;
        const fieldError = validationErrors[field.id];
        const hasError = !!fieldError;
        const errorBorderClass = hasError
          ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20'
          : 'border-border focus:border-violet-500 focus:ring-violet-500/20';

        return (
          <div key={field.id} className="flex flex-col gap-1.5" data-field-id={field.id}>
            <label htmlFor={`field-input-${field.id}`} className="text-[13px] font-semibold text-foreground flex items-center gap-1.5">
              <FieldIcon size={13} className="text-muted-foreground" />
              {field.label}
              {field.required && <span className="text-red-500 ml-0.5">*</span>}
            </label>

            {field.field_type === 'text' && (
              <input id={`field-input-${field.id}`} type="text" data-field-id={field.id} required={field.required || undefined} aria-invalid={hasError || undefined} aria-describedby={hasError ? `error-${field.id}` : undefined} className={`w-full py-2.5 px-3 text-sm border-[1.5px] ${errorBorderClass} rounded-lg bg-input text-foreground transition-all placeholder:text-muted-foreground/50 focus:ring-2 outline-none`} value={value} onChange={(e) => handleFieldChange(field.id, e.target.value)} placeholder={`أدخل ${field.label}...`} />
            )}
            {field.field_type === 'textarea' && (
              <textarea id={`field-input-${field.id}`} data-field-id={field.id} required={field.required || undefined} aria-invalid={hasError || undefined} aria-describedby={hasError ? `error-${field.id}` : undefined} className={`w-full py-2.5 px-3 text-sm border-[1.5px] ${errorBorderClass} rounded-lg bg-input text-foreground transition-all placeholder:text-muted-foreground/50 focus:ring-2 outline-none resize-none`} rows={4} value={value} onChange={(e) => handleFieldChange(field.id, e.target.value)} placeholder={`أدخل ${field.label}...`} />
            )}
            {field.field_type === 'number' && (
              <input id={`field-input-${field.id}`} type="number" data-field-id={field.id} required={field.required || undefined} aria-invalid={hasError || undefined} aria-describedby={hasError ? `error-${field.id}` : undefined} className={`w-full py-2.5 px-3 text-sm border-[1.5px] ${errorBorderClass} rounded-lg bg-input text-foreground transition-all placeholder:text-muted-foreground/50 focus:ring-2 outline-none`} value={value} onChange={(e) => handleFieldChange(field.id, e.target.value)} min="0" step="any" />
            )}
            {field.field_type === 'date' && (
              <div className="relative flex items-center">
                <Calendar size={15} className="absolute left-3 text-muted-foreground pointer-events-none z-[1]" />
                <input id={`field-input-${field.id}`} type="date" data-field-id={field.id} required={field.required || undefined} aria-invalid={hasError || undefined} aria-describedby={hasError ? `error-${field.id}` : undefined} className={`w-full !py-2.5 !pl-9 !pr-3 text-sm border-[1.5px] ${errorBorderClass} rounded-lg bg-input text-foreground transition-all focus:ring-2 outline-none [color-scheme:light] dark:[color-scheme:dark]`} value={value} onChange={(e) => handleFieldChange(field.id, e.target.value)} />
              </div>
            )}
            {field.field_type === 'select' && (
              <select id={`field-input-${field.id}`} data-field-id={field.id} required={field.required || undefined} aria-invalid={hasError || undefined} aria-describedby={hasError ? `error-${field.id}` : undefined} className={`w-full py-2.5 px-3 text-sm border-[1.5px] ${errorBorderClass} rounded-lg bg-input text-foreground transition-all focus:ring-2 outline-none`} value={value} onChange={(e) => handleFieldChange(field.id, e.target.value)}>
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
                    <input type="radio" name={'field-' + field.id} value={option} checked={value === option} onChange={(e) => handleFieldChange(field.id, e.target.value)} className="accent-violet-600 w-4 h-4 cursor-pointer" />
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
                      <input type="checkbox" checked={selectedOptions.includes(option)} onChange={(e) => handleCheckboxChange(field.id, option, e.target.checked)} className="accent-violet-600 w-4 h-4 rounded cursor-pointer" />
                      <span className="group-hover/check:text-violet-600 transition-colors">{option}</span>
                    </label>
                  );
                })}
              </div>
            )}
            {field.field_type === 'file' && (
              <input id={`field-input-${field.id}`} type="file" data-field-id={field.id} required={field.required || undefined} aria-invalid={hasError || undefined} aria-describedby={hasError ? `error-${field.id}` : undefined} className={`w-full py-2 px-3 text-sm border-[1.5px] ${errorBorderClass} rounded-lg bg-input text-foreground transition-all focus:ring-2 outline-none file:mr-3 file:py-1 file:px-3 file:rounded-md file:border-0 file:text-[13px] file:font-semibold file:bg-violet-600 file:text-white hover:file:bg-violet-700 file:cursor-pointer cursor-pointer`} onChange={(e) => { const file = e.target.files[0]; if (file) handleFieldChange(field.id, file.name); }} accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.gif" />
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

      <div className="flex justify-end gap-3 pt-4 border-t border-border">
        <button type="button" className="inline-flex items-center justify-center gap-1.5 py-2 px-4 text-sm font-medium rounded-lg bg-muted text-muted-foreground border border-border hover:bg-border transition-colors" onClick={onCancel}>
          إلغاء
        </button>
        <button type="button" className="inline-flex items-center justify-center gap-1.5 py-2 px-5 text-sm font-semibold rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-all shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]" disabled={submitting} onClick={handleSubmit}>
          {submitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          {submitting ? 'جاري الإرسال...' : 'إرسال'}
        </button>
      </div>
    </div>
  );
}

// ─── Drawer الجانبي لتعبئة النموذج (بديل استبدال الصفحة كاملة) ───────────────
function StageDrawer({ stageInstance, onClose, onSubmit, submitting, error }) {
  if (!stageInstance) return null;
  const cfg = getStatus(stageInstance?.status);

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-card h-full flex flex-col shadow-2xl">
        <div className="flex items-start justify-between p-5 border-b border-border flex-shrink-0">
          <div>
            <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full ${cfg.badge}`}>
              {cfg.label}
            </span>
            <h3 className="text-[17px] font-semibold text-foreground mt-1.5 m-0">
              {stageInstance?.stage_details?.name || 'مرحلة'}
            </h3>
          </div>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground p-1 rounded-lg hover:bg-muted transition-colors" aria-label="إغلاق">
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-5">
          {stageInstance?.stage_details?.description && (
            <div className="py-3 px-4 bg-muted/50 rounded-lg text-[14px] text-muted-foreground mb-5 border border-border/50">
              {stageInstance.stage_details.description}
            </div>
          )}
          <WorkflowStageForm
            stageInstance={stageInstance}
            onSubmit={onSubmit}
            onCancel={onClose}
            submitting={submitting}
            error={error}
          />
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
      const cleanData = {};
      Object.entries(formData).forEach(([key, value]) => {
        if (value === null || value === undefined) {
          cleanData[key] = '';
        } else if (value instanceof File) {
          cleanData[key] = value.name;
        } else if (typeof value === 'object' && !(value instanceof Array)) {
          cleanData[key] = '';
        } else {
          cleanData[key] = String(value);
        }
      });
      await submitWorkflowStage(selectedStage.id, { field_responses: cleanData });
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

  // ── Error ──
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

  // ── Empty ──
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

  // ── تصنيف المراحل ──
  const stages = workflow?.stage_instances || [];
  const scheduledStages = stages.filter((s) => s?.status === 'scheduled');
  const actionStages = stages.filter((s) => s?.status !== 'scheduled' && stageNeedsAction(s));
  const doneStages = stages.filter((s) => s?.status !== 'scheduled' && !stageNeedsAction(s));

  const completedCount = stages.filter((s) => ['submitted', 'approved'].includes(s?.status)).length;
  const progress = stages.length > 0 ? (completedCount / stages.length) * 100 : 0;

  return (
    <div className="w-full overflow-x-hidden">
      <div className="max-w-2xl mx-auto p-2 sm:p-4">
        {/* Header */}
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

        {/* Progress */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-[14px] text-muted-foreground font-medium">
              اكتملت {completedCount} من {stages.length} مرحلة
            </span>
            <span className={`text-[14px] font-bold px-2.5 py-0.5 rounded-full ${progress === 100 ? 'bg-emerald-500/10 text-emerald-600' : 'bg-violet-500/10 text-violet-600'}`}>
              {Math.round(progress)}%
            </span>
          </div>
          <div className="h-2.5 bg-muted/60 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-[width] duration-700 ease-out ${progress === 100 ? 'bg-gradient-to-r from-emerald-500 to-green-400' : 'bg-gradient-to-r from-violet-600 to-indigo-500'}`}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* المراحل المنجزة — صفوف مضغوطة */}
        {doneStages.length > 0 && (
          <div className="mb-4 bg-card rounded-xl border border-border divide-y divide-border/60 px-3">
            {doneStages.map((s) => <CompletedRow key={s?.id} stageInstance={s} />)}
          </div>
        )}

        {/* المراحل التي تحتاج إجراء — بارزة */}
        {actionStages.length > 0 && (
          <div className="flex flex-col gap-3 mb-4">
            {actionStages.map((s) => (
              <ActionStageCard key={s?.id} stageInstance={s} onOpen={setSelectedStage} />
            ))}
          </div>
        )}

        {/* المراحل المجدولة — مطويّة */}
        <ScheduledGroup stages={scheduledStages} />

        {/* رسالة خطأ عامة (خارج الـ Drawer) */}
        {error && workflow && (
          <div role="alert" aria-live="assertive" className="flex items-center gap-2 py-2.5 px-3.5 bg-red-500/10 border border-red-500/20 rounded-lg text-[13px] text-red-600 mt-4">
            <AlertCircle size={14} className="flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Drawer لتعبئة النموذج */}
      <StageDrawer
        stageInstance={selectedStage}
        onClose={() => { setSelectedStage(null); setError(''); }}
        onSubmit={handleSubmitStage}
        submitting={submitting}
        error={error}
      />
    </div>
  );
}
