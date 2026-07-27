import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { fetchProjectWorkflow, submitWorkflowStage } from '../api';
import {
  CheckCircle2, XCircle, AlertCircle, FileText,
  Send, ChevronDown, ChevronUp, Loader2, Zap,
  Calendar, MessageSquare, GitBranch, X, Lock,
  Clock, ArrowLeft, RotateCcw, Eye, CircleDot,
  GraduationCap, ClipboardList, Timer, BookOpen,
} from 'lucide-react';

/* ═══════════════════════════════════════════════════════════════════════════
   University Workflow View — تصميم جامعي جديد كلياً
   ═══════════════════════════════════════════════════════════════════════════ */

// ─── الألوان الأساسية ──────────────────────────────────────────────────
const COLORS = {
  primary:   { bg: 'bg-blue-600',       light: 'bg-blue-50',    text: 'text-blue-600',       border: 'border-blue-200',    ring: 'ring-blue-500/20' },
  success:   { bg: 'bg-emerald-600',    light: 'bg-emerald-50', text: 'text-emerald-600',    border: 'border-emerald-200', ring: 'ring-emerald-500/20' },
  warning:   { bg: 'bg-amber-500',      light: 'bg-amber-50',   text: 'text-amber-600',      border: 'border-amber-200',   ring: 'ring-amber-500/20' },
  danger:    { bg: 'bg-red-500',        light: 'bg-red-50',     text: 'text-red-600',         border: 'border-red-200',     ring: 'ring-red-500/20' },
  neutral:   { bg: 'bg-slate-500',      light: 'bg-slate-50',   text: 'text-slate-500',      border: 'border-slate-200',   ring: 'ring-slate-500/20' },
  info:      { bg: 'bg-indigo-500',     light: 'bg-indigo-50',  text: 'text-indigo-600',     border: 'border-indigo-200',  ring: 'ring-indigo-500/20' },
};

const STATUS_STYLE = {
  scheduled:   { ...COLORS.neutral,  label: 'مجدول',        icon: Clock },
  pending:     { ...COLORS.warning,  label: 'قيد الانتظار',  icon: CircleDot },
  in_progress: { ...COLORS.info,     label: 'قيد التنفيذ',   icon: Zap },
  submitted:   { ...COLORS.primary,  label: 'تم الإرسال',    icon: Send },
  approved:    { ...COLORS.success,  label: 'تمت الموافقة',  icon: CheckCircle2 },
  rejected:    { ...COLORS.danger,   label: 'مرفوض',         icon: XCircle },
  overdue:     { ...COLORS.danger,   label: 'متأخر',         icon: AlertCircle },
};
const getStatus = (s) => STATUS_STYLE[s] || STATUS_STYLE.pending;

// ─── هل المرحلة تحتاج إجراء؟ ──────────────────────────────────────────
function stageNeedsAction(si) {
  const st = si?.status;
  const fields = si?.stage_details?.fields || [];
  const reqIds = new Set(fields.filter((f) => f.required).map((f) => f.id));
  const ansIds = new Set((si?.field_responses || []).filter((r) => r.value).map((r) => r.field));
  const hasUnanswered = fields.filter((f) => f.required).some((f) => !ansIds.has(f.id));
  return ['pending', 'in_progress', 'rejected'].includes(st) || (hasUnanswered && ['submitted', 'approved'].includes(st));
}

// ─── حساب الأيام المتبقية ─────────────────────────────────────────────
function getDaysLeft(due) {
  if (!due) return null;
  return Math.ceil((new Date(due) - new Date()) / 86400000);
}

function daysLabel(d) {
  if (d === null) return null;
  if (d < 0) return { text: `متأخر ${Math.abs(d)} يوم`, color: COLORS.danger };
  if (d === 0) return { text: 'ينتهي اليوم', color: COLORS.warning };
  if (d <= 3) return { text: `${d} أيام متبقية`, color: COLORS.warning };
  if (d <= 7) return { text: `${d} أيام متبقية`, color: COLORS.primary };
  return { text: `${d} يوم متبقي`, color: COLORS.neutral };
}

// ═══════════════════════════════════════════════════════════════════════════
//   HEADER — بطاقة المشروع
// ═══════════════════════════════════════════════════════════════════════════
function ProjectHeader({ workflow, stages, completedCount }) {
  const progress = stages.length > 0 ? Math.round((completedCount / stages.length) * 100) : 0;
  const activeCount = stages.filter((s) => stageNeedsAction(s)).length;

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-700/60 overflow-hidden">
      {/* الشريط العلوي الأكاديمي */}
      <div className="h-1.5 bg-gradient-to-l from-blue-600 via-blue-500 to-indigo-600" />

      <div className="p-6 sm:p-8">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          {/* المعلومات */}
          <div className="flex items-start gap-4">
            <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-blue-600 to-indigo-700 flex items-center justify-center shadow-lg shadow-blue-500/20 flex-shrink-0">
              <GraduationCap size={26} className="text-white" />
            </div>
            <div>
              <h1 className="text-xl sm:text-2xl font-bold text-slate-800 dark:text-white m-0 leading-tight">
                {workflow?.template_details?.name || 'سير عمل المشروع'}
              </h1>
              <p className="text-slate-500 dark:text-slate-400 text-sm mt-1 m-0">
                {workflow?.template_details?.description || 'تابع تقدم مشروعك الجامعي خطوة بخطوة'}
              </p>
            </div>
          </div>

          {/* الإحصائيات */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <div className="text-center px-4 py-2.5 bg-blue-50 dark:bg-blue-950/40 rounded-xl border border-blue-100 dark:border-blue-900/50">
              <div className="text-2xl font-bold text-blue-600 dark:text-blue-400 leading-none">{progress}%</div>
              <div className="text-[11px] text-blue-500 dark:text-blue-400/70 mt-1 font-medium">مكتمل</div>
            </div>
            <div className="text-center px-4 py-2.5 bg-amber-50 dark:bg-amber-950/40 rounded-xl border border-amber-100 dark:border-amber-900/50">
              <div className="text-2xl font-bold text-amber-600 dark:text-amber-400 leading-none">{activeCount}</div>
              <div className="text-[11px] text-amber-500 dark:text-amber-400/70 mt-1 font-medium">بحاجة لإجراء</div>
            </div>
            <div className="text-center px-4 py-2.5 bg-emerald-50 dark:bg-emerald-950/40 rounded-xl border border-emerald-100 dark:border-emerald-900/50">
              <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 leading-none">{completedCount}</div>
              <div className="text-[11px] text-emerald-500 dark:text-emerald-400/70 mt-1 font-medium">منجزة</div>
            </div>
          </div>
        </div>

        {/* شريط التقدم */}
        <div className="mt-6">
          <div className="h-2 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-1000 ease-out ${
                progress === 100
                  ? 'bg-gradient-to-l from-emerald-500 to-emerald-400'
                  : 'bg-gradient-to-l from-blue-600 to-indigo-500'
              }`}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
//   SECTION TITLE — عنوان قسم
// ═══════════════════════════════════════════════════════════════════════════
function SectionTitle({ icon: Icon, title, count, color = 'primary' }) {
  const c = COLORS[color] || COLORS.primary;
  return (
    <div className="flex items-center gap-2.5 mb-4 mt-8 first:mt-0">
      <div className={`w-8 h-8 rounded-lg ${c.light} ${c.text} flex items-center justify-center`}>
        <Icon size={16} />
      </div>
      <h2 className="text-base font-bold text-slate-800 dark:text-white m-0">{title}</h2>
      {count !== undefined && (
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${c.light} ${c.text}`}>
          {count}
        </span>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
//   ACTIVE STAGE CARD — المرحلة النشطة (بارزة)
// ═══════════════════════════════════════════════════════════════════════════
function ActiveStageCard({ stage, index, total, onOpen }) {
  const st = getStatus(stage?.status);
  const Icon = st.icon;
  const fields = stage?.stage_details?.fields || [];
  const ansIds = new Set((stage?.field_responses || []).filter((r) => r.value).map((r) => r.field));
  const filled = fields.filter((f) => ansIds.has(f.id)).length;
  const isOverdue = stage?.status === 'overdue';
  const isRejected = stage?.status === 'rejected';
  const days = getDaysLeft(stage?.due_date);
  const dl = daysLabel(days);

  const borderColor = isOverdue || isRejected ? 'border-red-300 dark:border-red-800' : 'border-blue-200 dark:border-blue-800';
  const accentBg = isOverdue || isRejected ? 'bg-red-600' : 'bg-blue-600';

  const actionText = isRejected ? 'إعادة الإرسال' : stage?.status === 'in_progress' ? 'متابعة التعبئة' : 'ابدأ التعبئة';

  return (
    <div className={`relative bg-white dark:bg-slate-900 rounded-2xl border-2 ${borderColor} overflow-hidden transition-shadow hover:shadow-xl hover:shadow-blue-500/5`}>
      {/* شريط علوي ملون */}
      <div className={`h-1 ${accentBg}`} />

      <div className="p-5 sm:p-6">
        {/* الرأس: رقم + عنوان + حالة */}
        <div className="flex items-start gap-4 mb-4">
          <div className="relative flex-shrink-0">
            <div className={`w-12 h-12 rounded-xl ${accentBg} flex items-center justify-center shadow-lg ${isOverdue ? 'shadow-red-500/20 animate-pulse' : 'shadow-blue-500/20'}`}>
              <Icon size={22} className="text-white" />
            </div>
            <span className="absolute -top-1.5 -right-1.5 w-6 h-6 rounded-full bg-white dark:bg-slate-900 border-2 border-blue-600 dark:border-blue-500 flex items-center justify-center text-[10px] font-bold text-blue-600 dark:text-blue-400">
              {index}
            </span>
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <h3 className="text-lg font-bold text-slate-800 dark:text-white m-0">
                {stage?.stage_details?.name || `المرحلة ${index}`}
              </h3>
              <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full ${st.light} ${st.text} ${st.border} border`}>
                <Icon size={11} />
                {st.label}
              </span>
              {dl && (
                <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full ${dl.color.light} ${dl.color.text} ${dl.color.border} border`}>
                  <Timer size={10} />
                  {dl.text}
                </span>
              )}
            </div>

            {/* تقدم الحقول */}
            {fields.length > 0 && (
              <div className="flex items-center gap-3 mt-3">
                <div className="flex-1 h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500 rounded-full transition-all duration-500" style={{ width: `${(filled / fields.length) * 100}%` }} />
                </div>
                <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 flex-shrink-0">
                  {filled}/{fields.length} حقول
                </span>
              </div>
            )}
          </div>
        </div>

        {/* ملاحظات */}
        {stage?.feedback && (
          <div className="mb-4 p-3.5 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/50 rounded-xl">
            <div className="flex items-center gap-1.5 mb-1.5">
              <MessageSquare size={12} className="text-amber-600 dark:text-amber-400" />
              <span className="text-[11px] font-bold text-amber-600 dark:text-amber-400 uppercase tracking-wider">ملاحظات المشرف</span>
            </div>
            <p className="text-sm text-amber-800 dark:text-amber-200/80 m-0 leading-relaxed">{stage.feedback}</p>
          </div>
        )}

        {/* زر الإجراء */}
        {fields.length > 0 ? (
          <button
            onClick={() => onOpen(stage)}
            className={`w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-bold transition-all active:scale-[0.98] ${
              isOverdue || isRejected
                ? 'bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-500/20'
                : 'bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-500/20'
            }`}
          >
            {isRejected && <RotateCcw size={15} />}
            {!isRejected && <ArrowLeft size={15} />}
            {actionText}
          </button>
        ) : (
          <div className="flex items-center gap-2 py-3 px-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl text-sm text-slate-400">
            <ClipboardList size={15} />
            لا يوجد نموذج مُعدّ لهذه المرحلة بعد
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
//   COMPLETED STAGE ROW — مرحلة منجزة
// ═══════════════════════════════════════════════════════════════════════════
function CompletedStageRow({ stage, index }) {
  const st = getStatus(stage?.status);
  const Icon = st.icon;
  const [showFeedback, setShowFeedback] = useState(false);

  const iconBg = stage?.status === 'approved' ? 'bg-emerald-500' : stage?.status === 'rejected' ? 'bg-red-500' : 'bg-blue-500';

  return (
    <>
      <div className="group flex items-center gap-3.5 py-3.5 px-4 rounded-xl transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/40">
        {/* رقم */}
        <span className="w-7 h-7 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-[11px] font-bold text-slate-500 dark:text-slate-400 flex-shrink-0">
          {index}
        </span>

        {/* أيقونة */}
        <div className={`w-8 h-8 rounded-lg ${iconBg} flex items-center justify-center flex-shrink-0 transition-transform group-hover:scale-110`}>
          <Icon size={14} className="text-white" />
        </div>

        {/* اسم */}
        <span className="flex-1 text-sm font-medium text-slate-700 dark:text-slate-300 truncate">
          {stage?.stage_details?.name || `المرحلة ${index}`}
        </span>

        {/* زر الملاحظات */}
        {stage?.feedback && (
          <button
            onClick={() => setShowFeedback(!showFeedback)}
            className="flex items-center gap-1 text-[11px] font-semibold text-amber-600 hover:text-amber-700 px-2.5 py-1 rounded-lg hover:bg-amber-50 dark:hover:bg-amber-950/30 transition-all opacity-0 group-hover:opacity-100"
          >
            <Eye size={11} />
            ملاحظات
          </button>
        )}

        {/* تاريخ */}
        {stage?.submitted_at && (
          <span className="hidden sm:flex items-center gap-1.5 text-xs text-slate-400 flex-shrink-0">
            <Calendar size={12} />
            {new Date(stage.submitted_at).toLocaleDateString('ar-SY')}
          </span>
        )}

        {/* badge */}
        <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full ${st.light} ${st.text} ${st.border} border flex-shrink-0`}>
          {st.label}
        </span>
      </div>

      {/* ملاحظات مطوية */}
      {stage?.feedback && showFeedback && (
        <div className="mr-16 mb-3 p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800/50 rounded-xl">
          <div className="flex items-center gap-1.5 mb-1">
            <MessageSquare size={11} className="text-amber-600" />
            <span className="text-[11px] font-bold text-amber-600 uppercase tracking-wider">ملاحظات</span>
          </div>
          <p className="text-sm text-amber-800 dark:text-amber-200/80 m-0 leading-relaxed">{stage.feedback}</p>
        </div>
      )}
    </>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
//   SCHEDULED STAGES — المراحل القادمة
// ═══════════════════════════════════════════════════════════════════════════
function ScheduledStages({ stages }) {
  const [open, setOpen] = useState(false);
  if (!stages?.length) return null;

  const nearest = stages
    .filter((s) => s.due_date)
    .sort((a, b) => new Date(a.due_date) - new Date(b.due_date))[0];
  const ndl = daysLabel(getDaysLeft(nearest?.due_date));

  return (
    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-700/60 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-800 flex items-center justify-center">
            <Lock size={15} className="text-slate-400" />
          </div>
          <div className="text-right">
            <div className="text-sm font-semibold text-slate-700 dark:text-slate-300">
              المراحل القادمة
              <span className="text-xs font-normal text-slate-400 mr-2">({stages.length})</span>
            </div>
            {ndl && (
              <div className={`text-[11px] font-medium mt-0.5 ${ndl.color.text}`}>
                أقرب موعد: {ndl.text}
              </div>
            )}
          </div>
        </div>
        <ChevronDown size={18} className={`text-slate-400 transition-transform duration-300 ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="border-t border-slate-100 dark:border-slate-800">
          {stages.map((s, i) => {
            const days = getDaysLeft(s.due_date);
            const dl = daysLabel(days);
            return (
              <div
                key={s.id || i}
                className="flex items-center justify-between px-4 py-3 border-b border-slate-50 dark:border-slate-800/50 last:border-0 hover:bg-slate-50/50 dark:hover:bg-slate-800/20 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <Calendar size={14} className="text-slate-300 dark:text-slate-600" />
                  <span className="text-sm text-slate-600 dark:text-slate-400">{s.stage_details?.name || `مرحلة`}</span>
                </div>
                <div className="flex items-center gap-2">
                  {dl && (
                    <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${dl.color.light} ${dl.color.text}`}>
                      {dl.text}
                    </span>
                  )}
                  <span className="text-xs text-slate-400">
                    {s.due_date ? new Date(s.due_date).toLocaleDateString('ar-SY') : '—'}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
//   WORKFLOW STAGE FORM — نموذج التعبئة
// ═══════════════════════════════════════════════════════════════════════════
function WorkflowStageForm({ stageInstance, onSubmit, onCancel, submitting, error }) {
  const fields = useMemo(() => stageInstance?.stage_details?.fields || [], [stageInstance?.stage_details?.fields]);
  const [formData, setFormData] = useState({});
  const [validationErrors, setValidationErrors] = useState({});

  useEffect(() => {
    const init = {};
    fields.forEach((f) => { init[f.id] = ''; });
    (stageInstance?.field_responses || []).forEach((r) => { init[r.field] = r.value || ''; });
    setFormData(init);
    setValidationErrors({});
  }, [stageInstance, fields]);

  const change = (id, val) => {
    setFormData((p) => ({ ...p, [id]: val }));
    if (validationErrors[id]) setValidationErrors((p) => { const n = { ...p }; delete n[id]; return n; });
  };

  const checkChange = (id, opt, checked) => {
    const cur = (formData[id] || '').split(',').filter(Boolean);
    const next = checked ? [...cur, opt] : cur.filter((o) => o !== opt);
    change(id, next.join(','));
  };

  const isEmpty = (f, v) => {
    if (v == null) return true;
    if (typeof v === 'string') return !v.trim();
    if (Array.isArray(v)) return !v.length;
    if (typeof v === 'number') return false;
    if (typeof v === 'object') return !Object.keys(v).length;
    return !v;
  };

  const validate = () => {
    const e = {};
    for (const f of fields) {
      const v = formData[f.id];
      if (f.required && isEmpty(f, v)) {
        e[f.id] = f.field_type === 'file' ? 'يرجى رفع ملف' : ['radio', 'select', 'checkbox'].includes(f.field_type) ? 'يرجى اختيار قيمة' : 'هذا الحقل مطلوب';
      }
    }
    return e;
  };

  const submit = () => {
    const e = validate();
    if (Object.keys(e).length) {
      setValidationErrors(e);
      const el = document.querySelector(`[data-field-id="${Object.keys(e)[0]}"]`);
      if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); el.focus?.(); }
      return;
    }
    setValidationErrors({});
    const d = {};
    fields.forEach((f) => { d[f.id] = formData[f.id] || ''; });
    onSubmit(d);
  };

  const INPUT_CLS = (hasErr) =>
    `w-full py-3 px-4 text-sm border-2 rounded-xl bg-white dark:bg-slate-900 text-slate-800 dark:text-white transition-all outline-none placeholder:text-slate-400 focus:ring-4 ${
      hasErr
        ? 'border-red-300 dark:border-red-700 focus:border-red-500 focus:ring-red-500/10'
        : 'border-slate-200 dark:border-slate-700 focus:border-blue-500 focus:ring-blue-500/10'
    }`;

  return (
    <div className="flex flex-col gap-6">
      {fields.map((field) => {
        const val = formData[field.id] || '';
        const err = validationErrors[field.id];
        const hasErr = !!err;
        return (
          <div key={field.id} data-field-id={field.id} className="flex flex-col gap-1.5">
            <label className="text-sm font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
              <BookOpen size={13} className="text-blue-500" />
              {field.label}
              {field.required && <span className="text-red-500">*</span>}
            </label>

            {field.field_type === 'text' && (
              <input type="text" className={INPUT_CLS(hasErr)} value={val} onChange={(e) => change(field.id, e.target.value)} placeholder={`أدخل ${field.label}...`} />
            )}
            {field.field_type === 'textarea' && (
              <textarea className={`${INPUT_CLS(hasErr)} resize-none`} rows={4} value={val} onChange={(e) => change(field.id, e.target.value)} placeholder={`أدخل ${field.label}...`} />
            )}
            {field.field_type === 'number' && (
              <input type="number" className={INPUT_CLS(hasErr)} value={val} onChange={(e) => change(field.id, e.target.value)} min="0" step="any" />
            )}
            {field.field_type === 'date' && (
              <div className="relative">
                <Calendar size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                <input type="date" className={`${INPUT_CLS(hasErr)} !pl-10`} value={val} onChange={(e) => change(field.id, e.target.value)} />
              </div>
            )}
            {field.field_type === 'select' && (
              <select className={INPUT_CLS(hasErr)} value={val} onChange={(e) => change(field.id, e.target.value)}>
                <option value="">اختر خياراً...</option>
                {(field.options || []).map((o, i) => <option key={i} value={o}>{o}</option>)}
              </select>
            )}
            {field.field_type === 'radio' && (
              <div className={`flex flex-col gap-3 p-3 rounded-xl ${hasErr ? 'bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800' : 'bg-slate-50 dark:bg-slate-800/30'}`}>
                {(field.options || []).map((o, i) => (
                  <label key={i} className="flex items-center gap-3 text-sm text-slate-700 dark:text-slate-300 cursor-pointer hover:text-blue-600 transition-colors">
                    <input type="radio" name={`f-${field.id}`} value={o} checked={val === o} onChange={(e) => change(field.id, e.target.value)} className="accent-blue-600 w-4 h-4" />
                    {o}
                  </label>
                ))}
              </div>
            )}
            {field.field_type === 'checkbox' && (
              <div className={`flex flex-col gap-3 p-3 rounded-xl ${hasErr ? 'bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-800' : 'bg-slate-50 dark:bg-slate-800/30'}`}>
                {(field.options || []).map((o, i) => {
                  const sel = val ? val.split(',') : [];
                  return (
                    <label key={i} className="flex items-center gap-3 text-sm text-slate-700 dark:text-slate-300 cursor-pointer hover:text-blue-600 transition-colors">
                      <input type="checkbox" checked={sel.includes(o)} onChange={(e) => checkChange(field.id, o, e.target.checked)} className="accent-blue-600 w-4 h-4 rounded" />
                      {o}
                    </label>
                  );
                })}
              </div>
            )}
            {field.field_type === 'file' && (
              <input type="file" className={INPUT_CLS(hasErr)} onChange={(e) => { const f = e.target.files[0]; if (f) change(field.id, f.name); }} accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.gif" />
            )}

            {hasErr && (
              <div className="flex items-center gap-1.5 text-xs text-red-600 font-medium mt-0.5">
                <AlertCircle size={12} /><span>{err}</span>
              </div>
            )}
          </div>
        );
      })}

      {/* أخطاء */}
      {error && (
        <div className="flex items-center gap-2.5 p-3.5 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-xl text-sm text-red-700 dark:text-red-300">
          <AlertCircle size={16} className="flex-shrink-0" /><span>{error}</span>
        </div>
      )}
      {Object.keys(validationErrors).length > 0 && (
        <div className="flex items-center gap-2.5 p-3.5 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-xl text-sm text-red-700 dark:text-red-300 font-semibold">
          <AlertCircle size={16} className="flex-shrink-0" />
          <span>يرجى ملء {Object.keys(validationErrors).length} حقلاً مطلوباً <span className="text-red-500 font-bold">*</span></span>
        </div>
      )}

      {/* أزرار */}
      <div className="flex items-center justify-between pt-5 mt-2 border-t border-slate-100 dark:border-slate-800">
        <button type="button" onClick={onCancel} className="px-5 py-2.5 text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-white rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors">
          إلغاء
        </button>
        <button type="button" disabled={submitting} onClick={submit} className="flex items-center gap-2 px-6 py-2.5 text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 rounded-xl shadow-lg shadow-blue-500/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]">
          {submitting ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
          {submitting ? 'جاري الإرسال...' : 'إرسال'}
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
//   DRAWER — النافذة الجانبية
// ═══════════════════════════════════════════════════════════════════════════
function StageDrawer({ stageInstance, onClose, onSubmit, submitting, error }) {
  const [slideIn, setSlideIn] = useState(false);
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (stageInstance) {
      setShow(true);
      requestAnimationFrame(() => requestAnimationFrame(() => setSlideIn(true)));
    } else {
      setSlideIn(false);
      const t = setTimeout(() => setShow(false), 300);
      return () => clearTimeout(t);
    }
  }, [stageInstance]);

  if (!show && !slideIn) return null;

  const st = getStatus(stageInstance?.status);

  return (
    <div className={`fixed inset-0 z-50 ${show ? 'pointer-events-auto' : 'pointer-events-none'}`} role="dialog" aria-modal="true">
      {/* backdrop */}
      <div className={`absolute inset-0 bg-black/30 backdrop-blur-sm transition-opacity duration-300 ${slideIn ? 'opacity-100' : 'opacity-0'}`} onClick={onClose} />
      {/* panel */}
      <div className={`absolute top-0 left-0 h-full w-full max-w-xl bg-white dark:bg-slate-900 shadow-2xl flex flex-col transition-transform duration-300 ease-out ${slideIn ? 'translate-x-0' : '-translate-x-full'}`}>
        {/* header */}
        <div className="flex items-start justify-between p-6 border-b border-slate-100 dark:border-slate-800 flex-shrink-0">
          <div>
            <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2.5 py-0.5 rounded-full ${st.light} ${st.text} ${st.border} border`}>
              {st.label}
            </span>
            <h3 className="text-lg font-bold text-slate-800 dark:text-white mt-2 m-0">
              {stageInstance?.stage_details?.name || 'مرحلة'}
            </h3>
          </div>
          <button onClick={onClose} className="p-2 rounded-xl text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors" aria-label="إغلاق">
            <X size={18} />
          </button>
        </div>
        {/* body */}
        <div className="flex-1 overflow-y-auto p-6">
          {stageInstance?.stage_details?.description && (
            <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-950/30 border border-blue-100 dark:border-blue-900/50 rounded-xl text-sm text-blue-700 dark:text-blue-300 leading-relaxed">
              {stageInstance.stage_details.description}
            </div>
          )}
          <WorkflowStageForm stageInstance={stageInstance} onSubmit={onSubmit} onCancel={onClose} submitting={submitting} error={error} />
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
//   MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════
export default function ProjectWorkflowView({ projectBoardId }) {
  const [selectedStage, setSelectedStage] = useState(null);
  const [error, setError] = useState('');
  const [workflow, setWorkflow] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    if (!projectBoardId) { setLoading(false); return; }
    setLoading(true);
    try {
      const res = await fetchProjectWorkflow(projectBoardId);
      setWorkflow(res.data);
      setError('');
    } catch (e) {
      setError(e.response?.data?.error || 'فشل تحميل سير العمل.');
      setWorkflow(null);
    } finally {
      setLoading(false);
    }
  }, [projectBoardId]);

  useEffect(() => { load(); }, [load]);

  const handleSubmit = async (formData) => {
    setError('');
    setSubmitting(true);
    try {
      const clean = {};
      Object.entries(formData).forEach(([k, v]) => {
        if (v == null) clean[k] = '';
        else if (v instanceof File) clean[k] = v.name;
        else if (typeof v === 'object' && !Array.isArray(v)) clean[k] = '';
        else clean[k] = String(v);
      });
      await submitWorkflowStage(selectedStage.id, { field_responses: clean });
      await load();
      setSelectedStage(null);
    } catch (e) {
      const d = e.response?.data;
      if (Array.isArray(d?.missing_fields)?.length) setError(`يرجى ملء: ${d.missing_fields.join('، ')}`);
      else if (d?.error) setError(d.error);
      else if (d && typeof d === 'object') setError(Object.values(d).flat().join(' '));
      else setError('فشل الإرسال. حاول مرة أخرى.');
    } finally {
      setSubmitting(false);
    }
  };

  // ── Loading ──
  if (loading) {
    return (
      <div className="w-full flex flex-col items-center justify-center py-20 gap-4">
        <div className="w-12 h-12 border-[3px] border-blue-100 border-t-blue-600 rounded-full animate-spin" />
        <span className="text-sm text-slate-500">جارٍ تحميل سير العمل...</span>
      </div>
    );
  }

  // ── Error ──
  if (error && !workflow) {
    return (
      <div className="w-full flex flex-col items-center justify-center py-20 gap-3 text-center">
        <div className="w-16 h-16 rounded-2xl bg-red-50 dark:bg-red-950/30 flex items-center justify-center">
          <AlertCircle size={28} className="text-red-500" />
        </div>
        <p className="text-sm text-slate-500 max-w-sm m-0">{error}</p>
        <button onClick={() => { setError(''); load(); }} className="mt-2 px-5 py-2.5 text-sm font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-xl transition-colors">
          إعادة المحاولة
        </button>
      </div>
    );
  }

  // ── Empty ──
  if (!workflow) {
    return (
      <div className="w-full flex flex-col items-center justify-center py-20 gap-3 text-center">
        <div className="w-16 h-16 rounded-2xl bg-blue-50 dark:bg-blue-950/30 flex items-center justify-center">
          <GitBranch size={28} className="text-blue-500" />
        </div>
        <p className="text-sm text-slate-500 max-w-sm m-0">لا يوجد سير عمل معيّن لهذا المشروع بعد.</p>
      </div>
    );
  }

  // ── تصنيف المراحل ──
  const stages = workflow?.stage_instances || [];
  const scheduled = stages.filter((s) => s?.status === 'scheduled');
  const active = stages.filter((s) => s?.status !== 'scheduled' && stageNeedsAction(s));
  const done = stages.filter((s) => s?.status !== 'scheduled' && !stageNeedsAction(s));
  const completedCount = stages.filter((s) => ['submitted', 'approved'].includes(s?.status)).length;

  const indexMap = {};
  stages.forEach((s, i) => { if (s?.id) indexMap[s.id] = i + 1; });

  return (
    <div className="w-full">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 space-y-2">
        {/* Header */}
        <ProjectHeader workflow={workflow} stages={stages} completedCount={completedCount} />

        {/* المراحل النشطة */}
        {active.length > 0 && (
          <>
            <SectionTitle icon={Zap} title="مراحل بحاجة لإجراءك" count={active.length} color="warning" />
            <div className="space-y-4">
              {active.map((s) => (
                <ActiveStageCard
                  key={s?.id}
                  stage={s}
                  index={indexMap[s?.id]}
                  total={stages.length}
                  onOpen={setSelectedStage}
                />
              ))}
            </div>
          </>
        )}

        {/* المراحل المنجزة */}
        {done.length > 0 && (
          <>
            <SectionTitle icon={CheckCircle2} title="المراحل المنجزة" count={done.length} color="success" />
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-700/60 divide-y divide-slate-100 dark:divide-slate-800 px-2">
              {done.map((s) => (
                <CompletedStageRow key={s?.id} stage={s} index={indexMap[s?.id]} />
              ))}
            </div>
          </>
        )}

        {/* المراحل المجدولة */}
        <ScheduledStages stages={scheduled} />

        {/* خطأ عام */}
        {error && workflow && (
          <div className="flex items-center gap-2.5 p-3.5 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-xl text-sm text-red-700 dark:text-red-300">
            <AlertCircle size={16} className="flex-shrink-0" /><span>{error}</span>
          </div>
        )}
      </div>

      {/* Drawer */}
      <StageDrawer
        stageInstance={selectedStage}
        onClose={() => { setSelectedStage(null); setError(''); }}
        onSubmit={handleSubmit}
        submitting={submitting}
        error={error}
      />
    </div>
  );
}
