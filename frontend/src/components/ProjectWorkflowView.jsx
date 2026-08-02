import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchProjectWorkflow, submitWorkflowStage } from '../api';
import {
  AlertCircle,
  ArrowLeft,
  Calendar,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Clock3,
  FileText,
  FolderKanban,
  Layers3,
  Loader2,
  Lock,
  MessageSquare,
  RotateCcw,
  Search,
  Send,
  ShieldCheck,
  Timer,
  UserRound,
  X,
  XCircle,
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

function getWorkflowFileUrl(response) {
  if (response?.file_url) return response.file_url;
  if (!response?.value) return '';
  const path = String(response.value).replace(/^\/?media\//, '');
  return `${API_BASE}/media/${path}`;
}

const STATUS = {
  scheduled: {
    label: 'مجدولة',
    icon: Lock,
    badge: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
    dot: 'bg-slate-400',
  },
  pending: {
    label: 'بانتظار البدء',
    icon: CircleDot,
    badge: 'bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-300',
    dot: 'bg-amber-500',
  },
  in_progress: {
    label: 'قيد التنفيذ',
    icon: Timer,
    badge: 'bg-sky-50 text-sky-700 dark:bg-sky-950/30 dark:text-sky-300',
    dot: 'bg-sky-500',
  },
  submitted: {
    label: 'تم الإرسال',
    icon: Send,
    badge: 'bg-blue-50 text-blue-700 dark:bg-blue-950/30 dark:text-blue-300',
    dot: 'bg-blue-500',
  },
  approved: {
    label: 'تمت الموافقة',
    icon: CheckCircle2,
    badge: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300',
    dot: 'bg-emerald-500',
  },
  rejected: {
    label: 'مرفوضة',
    icon: XCircle,
    badge: 'bg-rose-50 text-rose-700 dark:bg-rose-950/30 dark:text-rose-300',
    dot: 'bg-rose-500',
  },
  overdue: {
    label: 'متأخرة',
    icon: AlertCircle,
    badge: 'bg-rose-50 text-rose-700 dark:bg-rose-950/30 dark:text-rose-300',
    dot: 'bg-rose-500',
  },
};

function getStatus(status) {
  return STATUS[status] || STATUS.pending;
}

function roleLabel(role) {
  if (role === 'hod') return 'رئيس القسم';
  if (role === 'doctor') return 'المشرف الأكاديمي';
  return 'المكلّف بالمسار';
}

function getDaysLeft(date) {
  if (!date) return null;
  return Math.ceil((new Date(date) - new Date()) / 86400000);
}

function deadlineLabel(date) {
  const days = getDaysLeft(date);
  if (days === null) return null;
  if (days < 0) return { text: `متأخرة ${Math.abs(days)} يوم`, className: 'text-rose-600 dark:text-rose-300' };
  if (days === 0) return { text: 'الموعد اليوم', className: 'text-amber-600 dark:text-amber-300' };
  if (days <= 7) return { text: `${days} أيام متبقية`, className: 'text-amber-600 dark:text-amber-300' };
  return { text: `${days} يوم متبقٍ`, className: 'text-slate-500 dark:text-slate-400' };
}

function stageNeedsAction(stage) {
  const status = stage?.status;
  const fields = stage?.stage_details?.fields || [];
  const answered = new Set(
    (stage?.field_responses || [])
      .filter((response) => response.value)
      .map((response) => response.field),
  );
  const hasMissingRequired = fields.some((field) => field.required && !answered.has(field.id));

  return ['pending', 'in_progress', 'rejected', 'overdue'].includes(status)
    || (hasMissingRequired && ['submitted', 'approved'].includes(status));
}

function workflowProgress(workflow) {
  const stages = workflow?.stage_instances || [];
  if (!stages.length) return 0;
  const completed = stages.filter((stage) => ['submitted', 'approved'].includes(stage.status)).length;
  return Math.round((completed / stages.length) * 100);
}

function ProgressBar({ value }) {
  return (
    <div className="h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
      <div
        className="h-full rounded-full bg-indigo-500 transition-[width] duration-500"
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}

function WorkflowSelector({ workflows, selectedId, onSelect, search, setSearch }) {
  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return workflows;
    return workflows.filter((workflow) => {
      const creator = workflow.assigned_by_name || workflow.template_details?.created_by_name || '';
      const name = workflow.template_details?.name || '';
      return name.toLowerCase().includes(query) || creator.toLowerCase().includes(query);
    });
  }, [search, workflows]);

  return (
    <aside className="rounded-2xl border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900 lg:sticky lg:top-5 lg:self-start">
      <div className="px-2 pb-3 pt-1">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="m-0 text-sm font-bold text-slate-900 dark:text-white">مسارات المشروع</p>
            <p className="m-0 mt-1 text-xs text-slate-500 dark:text-slate-400">اختر المسار الذي تريد متابعته</p>
          </div>
          <span className="rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            {workflows.length}
          </span>
        </div>
      </div>

      {workflows.length > 4 && (
        <div className="relative mb-3">
          <Search size={15} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="بحث عن مسار أو مشرف..."
            className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-3 pr-9 text-xs text-slate-800 outline-none transition focus:border-indigo-300 focus:bg-white focus:ring-4 focus:ring-indigo-500/5 dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:focus:border-indigo-700 dark:focus:bg-slate-900"
          />
        </div>
      )}

      <div className="flex gap-2 overflow-x-auto pb-1 lg:flex-col lg:overflow-visible">
        {filtered.map((workflow) => {
          const selected = workflow.id === selectedId;
          const progress = workflowProgress(workflow);
          const creator = workflow.assigned_by_name || workflow.template_details?.created_by_name || 'غير محدد';
          const stages = workflow.stage_instances || [];
          const required = stages.filter(stageNeedsAction).length;

          return (
            <button
              key={workflow.id}
              type="button"
              onClick={() => onSelect(workflow.id)}
              className={`min-w-[260px] rounded-xl border p-3 text-right transition lg:min-w-0 ${
                selected
                  ? 'border-indigo-200 bg-indigo-50/70 ring-1 ring-indigo-100 dark:border-indigo-800 dark:bg-indigo-950/20 dark:ring-indigo-900/40'
                  : 'border-transparent bg-slate-50 hover:border-slate-200 hover:bg-white dark:bg-slate-800/50 dark:hover:border-slate-700 dark:hover:bg-slate-800'
              }`}
            >
              <div className="flex items-start gap-3">
                <div className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${selected ? 'bg-indigo-600 text-white' : 'bg-white text-slate-500 ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-700'}`}>
                  <Layers3 size={17} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-bold text-slate-900 dark:text-white">
                    {workflow.template_details?.name || 'سير عمل'}
                  </div>
                  <div className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-500 dark:text-slate-400">
                    <UserRound size={11} />
                    <span className="truncate">{roleLabel(workflow.assigned_by_role)}: {creator}</span>
                  </div>
                </div>
                <span className="text-xs font-extrabold text-slate-700 dark:text-slate-200">{progress}%</span>
              </div>

              <div className="mt-3">
                <ProgressBar value={progress} />
              </div>
              <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400">
                <span>{stages.length} مراحل</span>
                <span>{required > 0 ? `${required} بحاجة لإجراء` : 'لا توجد إجراءات'}</span>
              </div>
            </button>
          );
        })}
      </div>

      {!filtered.length && (
        <div className="rounded-xl bg-slate-50 px-4 py-8 text-center text-xs text-slate-500 dark:bg-slate-800/50 dark:text-slate-400">
          لا توجد نتائج مطابقة.
        </div>
      )}
    </aside>
  );
}

function WorkflowSummary({ workflow, stages }) {
  const progress = workflowProgress(workflow);
  const completed = stages.filter((stage) => ['submitted', 'approved'].includes(stage.status)).length;
  const actionRequired = stages.filter(stageNeedsAction).length;
  const creator = workflow.assigned_by_name || workflow.template_details?.created_by_name || 'غير محدد';

  const stats = [
    { label: 'نسبة الإنجاز', value: `${progress}%` },
    { label: 'مراحل مكتملة', value: completed },
    { label: 'بحاجة لإجراء', value: actionRequired },
    { label: 'إجمالي المراحل', value: stages.length },
  ];

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900 sm:p-6">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600 dark:bg-indigo-950/30 dark:text-indigo-300">
            <ShieldCheck size={22} />
          </div>
          <div className="min-w-0">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-[11px] font-bold text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-300">
                {roleLabel(workflow.assigned_by_role)}
              </span>
              <span className="text-xs text-slate-400">مسار مستقل</span>
            </div>
            <h1 className="m-0 text-xl font-black text-slate-900 dark:text-white sm:text-2xl">
              {workflow.template_details?.name || 'سير عمل المشروع'}
            </h1>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-slate-500 dark:text-slate-400">
              <span className="inline-flex items-center gap-1.5"><UserRound size={13} />أنشأه: <strong className="text-slate-700 dark:text-slate-200">{creator}</strong></span>
              {workflow.started_at && (
                <span className="inline-flex items-center gap-1.5"><Calendar size={13} />{new Date(workflow.started_at).toLocaleDateString('ar-SY')}</span>
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:min-w-[430px]">
          {stats.map((item) => (
            <div key={item.label} className="rounded-xl bg-slate-50 px-3 py-3 text-center dark:bg-slate-800/60">
              <div className="text-lg font-black text-slate-900 dark:text-white">{item.value}</div>
              <div className="mt-0.5 text-[10px] font-medium text-slate-500 dark:text-slate-400">{item.label}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-5">
        <div className="mb-2 flex items-center justify-between text-xs text-slate-500 dark:text-slate-400">
          <span>التقدم العام</span>
          <span className="font-bold text-slate-700 dark:text-slate-200">{completed} من {stages.length}</span>
        </div>
        <ProgressBar value={progress} />
      </div>
    </section>
  );
}

function StageCard({ stage, index, onOpen }) {
  const status = getStatus(stage.status);
  const StatusIcon = status.icon;
  const fields = stage.stage_details?.fields || [];
  const answered = new Set(
    (stage.field_responses || [])
      .filter((response) => response.value)
      .map((response) => response.field),
  );
  const completedFields = fields.filter((field) => answered.has(field.id)).length;
  const percentage = fields.length ? Math.round((completedFields / fields.length) * 100) : 0;
  const deadline = deadlineLabel(stage.due_date);
  const rejected = stage.status === 'rejected';

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 transition hover:border-slate-300 hover:shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:hover:border-slate-700 sm:p-5">
      <div className="flex items-start gap-4">
        <div className="relative shrink-0">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
            <StatusIcon size={18} />
          </div>
          <span className="absolute -right-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-slate-900 px-1 text-[9px] font-bold text-white dark:bg-white dark:text-slate-900">
            {index}
          </span>
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="m-0 text-base font-extrabold text-slate-900 dark:text-white">
                {stage.stage_details?.name || `المرحلة ${index}`}
              </h3>
              {stage.stage_details?.description && (
                <p className="m-0 mt-1 line-clamp-2 text-xs leading-6 text-slate-500 dark:text-slate-400">
                  {stage.stage_details.description}
                </p>
              )}
            </div>
            <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold ${status.badge}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${status.dot}`} />
              {status.label}
            </span>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-center">
            <div>
              <div className="mb-2 flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
                <span>{fields.length ? `${completedFields} من ${fields.length} حقول` : 'لا توجد حقول'}</span>
                <span>{percentage}%</span>
              </div>
              <ProgressBar value={percentage} />
            </div>

            {deadline && (
              <div className={`inline-flex items-center gap-1.5 text-xs font-semibold ${deadline.className}`}>
                <Clock3 size={13} />
                {deadline.text}
              </div>
            )}
          </div>

          {stage.feedback && (
            <div className="mt-4 rounded-xl border border-amber-100 bg-amber-50/70 px-3.5 py-3 text-xs leading-6 text-amber-800 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200">
              <div className="mb-1 flex items-center gap-1.5 font-bold"><MessageSquare size={13} />ملاحظة المشرف</div>
              {stage.feedback}
            </div>
          )}

          <div className="mt-4 flex justify-end">
            <button
              type="button"
              onClick={() => onOpen(stage)}
              disabled={!fields.length}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-xs font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100"
            >
              {rejected ? <RotateCcw size={14} /> : <ArrowLeft size={14} />}
              {rejected ? 'تعديل وإعادة الإرسال' : stage.status === 'in_progress' ? 'متابعة التعبئة' : 'فتح المرحلة'}
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}

function CompletedStages({ stages, indexMap }) {
  const [expanded, setExpanded] = useState(true);
  if (!stages.length) return null;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-center justify-between gap-3 px-4 py-4 text-right sm:px-5"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-300">
            <CheckCircle2 size={17} />
          </div>
          <div>
            <div className="text-sm font-bold text-slate-900 dark:text-white">المراحل المكتملة</div>
            <div className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">{stages.length} مراحل محفوظة للمراجعة</div>
          </div>
        </div>
        <ChevronDown size={18} className={`text-slate-400 transition ${expanded ? 'rotate-180' : ''}`} />
      </button>

      {expanded && (
        <div className="border-t border-slate-100 px-3 py-2 dark:border-slate-800 sm:px-4">
          {stages.map((stage) => {
            const status = getStatus(stage.status);
            const StatusIcon = status.icon;
            return (
              <div key={stage.id} className="flex items-center gap-3 border-b border-slate-100 px-2 py-3 last:border-0 dark:border-slate-800">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[10px] font-bold text-slate-500 dark:bg-slate-800 dark:text-slate-300">
                  {indexMap[stage.id]}
                </span>
                <StatusIcon size={15} className="shrink-0 text-emerald-500" />
                <span className="min-w-0 flex-1 truncate text-sm font-medium text-slate-700 dark:text-slate-300">
                  {stage.stage_details?.name || 'مرحلة'}
                </span>
                {stage.submitted_at && (
                  <span className="hidden text-[11px] text-slate-400 sm:block">
                    {new Date(stage.submitted_at).toLocaleDateString('ar-SY')}
                  </span>
                )}
                <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${status.badge}`}>{status.label}</span>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function ScheduledStages({ stages, indexMap }) {
  const [expanded, setExpanded] = useState(false);
  if (!stages.length) return null;

  return (
    <section className="rounded-2xl border border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-center justify-between gap-3 px-4 py-4 text-right sm:px-5"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-300">
            <Lock size={16} />
          </div>
          <div>
            <div className="text-sm font-bold text-slate-900 dark:text-white">المراحل القادمة</div>
            <div className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">{stages.length} مراحل ستتاح لاحقاً</div>
          </div>
        </div>
        <ChevronDown size={18} className={`text-slate-400 transition ${expanded ? 'rotate-180' : ''}`} />
      </button>

      {expanded && (
        <div className="border-t border-slate-100 px-3 py-2 dark:border-slate-800 sm:px-4">
          {stages.map((stage) => {
            const deadline = deadlineLabel(stage.due_date);
            return (
              <div key={stage.id} className="flex items-center gap-3 border-b border-slate-100 px-2 py-3 last:border-0 dark:border-slate-800">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[10px] font-bold text-slate-500 dark:bg-slate-800 dark:text-slate-300">
                  {indexMap[stage.id]}
                </span>
                <Calendar size={14} className="shrink-0 text-slate-400" />
                <span className="min-w-0 flex-1 truncate text-sm text-slate-600 dark:text-slate-400">
                  {stage.stage_details?.name || 'مرحلة'}
                </span>
                {deadline && <span className={`text-[11px] font-medium ${deadline.className}`}>{deadline.text}</span>}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function WorkflowStageForm({ stageInstance, onSubmit, onCancel, submitting, error }) {
  const fields = useMemo(() => stageInstance?.stage_details?.fields || [], [stageInstance]);
  const [formData, setFormData] = useState({});
  const [validationErrors, setValidationErrors] = useState({});

  useEffect(() => {
    const initial = {};
    fields.forEach((field) => { initial[field.id] = ''; });
    (stageInstance?.field_responses || []).forEach((response) => {
      const field = fields.find((item) => item.id === response.field);
      if (field?.field_type === 'file') {
        const hasExistingFile = Boolean(response.file_url || response.value);
        initial[response.field] = hasExistingFile
          ? {
              existing: true,
              name: response.file_name || String(response.value || '').split('/').pop(),
              url: getWorkflowFileUrl(response),
              value: response.value || '',
            }
          : null;
      } else {
        initial[response.field] = response.value || '';
      }
    });
    setFormData(initial);
    setValidationErrors({});
  }, [fields, stageInstance]);

  const change = (id, value) => {
    setFormData((current) => ({ ...current, [id]: value }));
    setValidationErrors((current) => {
      if (!current[id]) return current;
      const next = { ...current };
      delete next[id];
      return next;
    });
  };

  const toggleCheckbox = (id, option, checked) => {
    const current = String(formData[id] || '').split(',').filter(Boolean);
    const next = checked ? [...new Set([...current, option])] : current.filter((item) => item !== option);
    change(id, next.join(','));
  };

  const validate = () => {
    const nextErrors = {};
    fields.forEach((field) => {
      const value = formData[field.id];
      if (!field.required) return;

      if (field.field_type === 'file') {
        const hasFile = value instanceof File || Boolean(value?.existing);
        if (!hasFile) nextErrors[field.id] = 'هذا الملف مطلوب';
        return;
      }

      if (!String(value || '').trim()) nextErrors[field.id] = 'هذا الحقل مطلوب';
    });
    return nextErrors;
  };

  const submit = () => {
    const nextErrors = validate();
    if (Object.keys(nextErrors).length) {
      setValidationErrors(nextErrors);
      document.querySelector(`[data-field-id="${Object.keys(nextErrors)[0]}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    onSubmit(formData);
  };

  const inputClass = (hasError) => `w-full rounded-xl border bg-white px-3.5 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:ring-4 dark:bg-slate-950 dark:text-white ${
    hasError
      ? 'border-rose-300 focus:border-rose-400 focus:ring-rose-500/5 dark:border-rose-800'
      : 'border-slate-200 focus:border-indigo-300 focus:ring-indigo-500/5 dark:border-slate-700 dark:focus:border-indigo-700'
  }`;

  return (
    <div className="space-y-5">
      {fields.map((field) => {
        const value = formData[field.id] ?? (field.field_type === 'file' ? null : '');
        const fieldError = validationErrors[field.id];
        const hasError = Boolean(fieldError);

        return (
          <div key={field.id} data-field-id={field.id} className="space-y-2">
            <label className="block text-sm font-bold text-slate-700 dark:text-slate-200">
              {field.label}
              {field.required && <span className="mr-1 text-rose-500">*</span>}
            </label>

            {field.field_type === 'text' && (
              <input className={inputClass(hasError)} value={value} onChange={(event) => change(field.id, event.target.value)} placeholder={`أدخل ${field.label}...`} />
            )}
            {field.field_type === 'textarea' && (
              <textarea className={`${inputClass(hasError)} min-h-[120px] resize-y`} value={value} onChange={(event) => change(field.id, event.target.value)} placeholder={`أدخل ${field.label}...`} />
            )}
            {field.field_type === 'number' && (
              <input type="number" className={inputClass(hasError)} value={value} onChange={(event) => change(field.id, event.target.value)} />
            )}
            {field.field_type === 'date' && (
              <input type="date" className={inputClass(hasError)} value={value} onChange={(event) => change(field.id, event.target.value)} />
            )}
            {field.field_type === 'select' && (
              <select className={inputClass(hasError)} value={value} onChange={(event) => change(field.id, event.target.value)}>
                <option value="">اختر...</option>
                {(field.options || []).map((option) => <option key={option} value={option}>{option}</option>)}
              </select>
            )}
            {field.field_type === 'radio' && (
              <div className="grid gap-2 sm:grid-cols-2">
                {(field.options || []).map((option) => (
                  <label key={option} className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-slate-200 px-3.5 py-3 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800/60">
                    <input type="radio" name={`field-${field.id}`} checked={value === option} onChange={() => change(field.id, option)} className="accent-indigo-600" />
                    {option}
                  </label>
                ))}
              </div>
            )}
            {field.field_type === 'checkbox' && (
              <div className="grid gap-2 sm:grid-cols-2">
                {(field.options || []).map((option) => {
                  const selected = String(value).split(',').filter(Boolean).includes(option);
                  return (
                    <label key={option} className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-slate-200 px-3.5 py-3 text-sm text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-800/60">
                      <input type="checkbox" checked={selected} onChange={(event) => toggleCheckbox(field.id, option, event.target.checked)} className="accent-indigo-600" />
                      {option}
                    </label>
                  );
                })}
              </div>
            )}
            {field.field_type === 'file' && (
              <div className={`rounded-xl border bg-white p-3.5 dark:bg-slate-950 ${hasError ? 'border-rose-300 dark:border-rose-800' : 'border-slate-200 dark:border-slate-700'}`}>
                <input
                  type="file"
                  className="block w-full text-sm text-slate-600 file:ml-3 file:rounded-lg file:border-0 file:bg-indigo-50 file:px-3.5 file:py-2 file:text-xs file:font-bold file:text-indigo-700 hover:file:bg-indigo-100 dark:text-slate-300 dark:file:bg-indigo-950/40 dark:file:text-indigo-300"
                  onChange={(event) => change(field.id, event.target.files?.[0] || null)}
                  accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.gif"
                />

                {value instanceof File && (
                  <div className="mt-3 flex items-center gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700 dark:bg-emerald-950/25 dark:text-emerald-300">
                    <FileText size={14} />
                    <span className="min-w-0 flex-1 truncate">{value.name}</span>
                    <span className="shrink-0 font-normal opacity-70">{(value.size / 1024 / 1024).toFixed(2)} MB</span>
                  </div>
                )}

                {(!(value instanceof File) && value?.existing) && (
                  <div className="mt-3 flex items-center gap-2 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:bg-slate-800/60 dark:text-slate-300">
                    <FileText size={14} />
                    {value.url ? (
                      <a href={value.url} target="_blank" rel="noopener noreferrer" className="min-w-0 flex-1 truncate font-semibold text-indigo-600 hover:underline dark:text-indigo-300">
                        {value.name || 'الملف المرفوع'}
                      </a>
                    ) : (
                      <span className="min-w-0 flex-1 truncate font-semibold">{value.name || 'الملف المرفوع'}</span>
                    )}
                    <span className="shrink-0 text-[10px] text-slate-400">سيبقى محفوظاً ما لم تختر ملفاً جديداً</span>
                  </div>
                )}

                <p className="m-0 mt-2 text-[11px] text-slate-400">PDF أو Word أو صورة، وبحجم أقصى 10 MB.</p>
              </div>
            )}

            {hasError && (
              <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-600 dark:text-rose-300">
                <AlertCircle size={12} />
                {fieldError}
              </div>
            )}
          </div>
        );
      })}

      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-3 text-xs leading-6 text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/20 dark:text-rose-200">
          <AlertCircle size={15} className="mt-0.5 shrink-0" />
          {error}
        </div>
      )}

      <div className="flex items-center justify-end gap-2 border-t border-slate-100 pt-5 dark:border-slate-800">
        <button type="button" onClick={onCancel} className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800">
          إلغاء
        </button>
        <button type="button" disabled={submitting} onClick={submit} className="inline-flex items-center gap-2 rounded-xl bg-slate-900 px-5 py-2.5 text-xs font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100">
          {submitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          {submitting ? 'جاري الإرسال...' : 'إرسال المرحلة'}
        </button>
      </div>
    </div>
  );
}

function StageModal({ stage, onClose, onSubmit, submitting, error }) {
  useEffect(() => {
    if (!stage) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const keyHandler = (event) => { if (event.key === 'Escape') onClose(); };
    document.addEventListener('keydown', keyHandler);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', keyHandler);
    };
  }, [onClose, stage]);

  if (!stage) return null;
  const status = getStatus(stage.status);
  const StatusIcon = status.icon;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-3 sm:p-6" dir="rtl">
      <button type="button" className="absolute inset-0 bg-slate-950/40 backdrop-blur-[2px]" onClick={onClose} aria-label="إغلاق" />
      <section className="relative flex max-h-[92vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900">
        <header className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4 dark:border-slate-800 sm:px-6 sm:py-5">
          <div className="flex min-w-0 items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              <StatusIcon size={18} />
            </div>
            <div className="min-w-0">
              <div className="mb-1 flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${status.badge}`}>{status.label}</span>
                <span className="text-[11px] text-slate-400">{stage.stage_details?.fields?.length || 0} حقول</span>
              </div>
              <h2 className="m-0 truncate text-lg font-black text-slate-900 dark:text-white sm:text-xl">
                {stage.stage_details?.name || 'تعبئة المرحلة'}
              </h2>
            </div>
          </div>
          <button type="button" onClick={onClose} className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-200 text-slate-500 transition hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800" aria-label="إغلاق">
            <X size={17} />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-5 sm:px-6 sm:py-6">
          {stage.stage_details?.description && (
            <div className="mb-5 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-xs leading-6 text-slate-600 dark:border-slate-700 dark:bg-slate-800/50 dark:text-slate-300">
              <div className="mb-1 flex items-center gap-1.5 font-bold text-slate-800 dark:text-slate-100"><FileText size={13} />تعليمات المرحلة</div>
              {stage.stage_details.description}
            </div>
          )}
          <WorkflowStageForm stageInstance={stage} onSubmit={onSubmit} onCancel={onClose} submitting={submitting} error={error} />
        </div>
      </section>
    </div>
  );
}

export default function ProjectWorkflowView({ projectBoardId }) {
  const [workflows, setWorkflows] = useState([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState(null);
  const [selectedStage, setSelectedStage] = useState(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!projectBoardId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const response = await fetchProjectWorkflow(projectBoardId);
      const items = Array.isArray(response.data) ? response.data : response.data ? [response.data] : [];
      setWorkflows(items);
      setSelectedWorkflowId((current) => (
        current && items.some((workflow) => workflow.id === current)
          ? current
          : items[0]?.id || null
      ));
      setError('');
    } catch (requestError) {
      setWorkflows([]);
      setError(requestError.response?.data?.error || 'فشل تحميل مسارات العمل.');
    } finally {
      setLoading(false);
    }
  }, [projectBoardId]);

  useEffect(() => { load(); }, [load]);

  const workflow = workflows.find((item) => item.id === selectedWorkflowId) || workflows[0] || null;

  const handleSubmit = async (formData) => {
    setError('');
    setSubmitting(true);
    try {
      const payload = new FormData();
      const clean = {};
      Object.entries(formData).forEach(([key, value]) => {
        if (value instanceof File) {
          payload.append(`field_file_${key}`, value, value.name);
          clean[key] = '';
        } else if (value?.existing) {
          clean[key] = value.value || value.name || '';
        } else {
          clean[key] = value == null ? '' : String(value);
        }
      });
      payload.append('field_responses', JSON.stringify(clean));
      await submitWorkflowStage(selectedStage.id, payload);
      await load();
      setSelectedStage(null);
    } catch (requestError) {
      const data = requestError.response?.data;
      if (Array.isArray(data?.missing_fields)?.length) setError(`يرجى ملء: ${data.missing_fields.join('، ')}`);
      else if (data?.error) setError(data.error);
      else if (data && typeof data === 'object') setError(Object.values(data).flat().join(' '));
      else setError('فشل الإرسال. حاول مرة أخرى.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-[420px] w-full flex-col items-center justify-center gap-3" dir="rtl">
        <Loader2 size={28} className="animate-spin text-indigo-500" />
        <span className="text-sm text-slate-500">جارٍ تحميل مسارات العمل...</span>
      </div>
    );
  }

  if (error && !workflows.length) {
    return (
      <div className="flex min-h-[420px] w-full flex-col items-center justify-center gap-3 text-center" dir="rtl">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-rose-50 text-rose-500 dark:bg-rose-950/30">
          <AlertCircle size={25} />
        </div>
        <p className="m-0 max-w-md text-sm text-slate-500">{error}</p>
        <button type="button" onClick={load} className="rounded-xl bg-slate-900 px-4 py-2.5 text-xs font-bold text-white dark:bg-white dark:text-slate-900">إعادة المحاولة</button>
      </div>
    );
  }

  if (!workflow) {
    return (
      <div className="flex min-h-[420px] w-full flex-col items-center justify-center gap-3 text-center" dir="rtl">
        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-500 dark:bg-slate-800">
          <FolderKanban size={25} />
        </div>
        <p className="m-0 text-sm text-slate-500">لا يوجد سير عمل معيّن لهذا المشروع بعد.</p>
      </div>
    );
  }

  const stages = workflow.stage_instances || [];
  const indexMap = {};
  stages.forEach((stage, index) => { indexMap[stage.id] = index + 1; });

  const actionStages = stages.filter((stage) => stage.status !== 'scheduled' && stageNeedsAction(stage));
  const completedStages = stages.filter((stage) => stage.status !== 'scheduled' && !stageNeedsAction(stage));
  const scheduledStages = stages.filter((stage) => stage.status === 'scheduled');

  return (
    <div className="w-full bg-slate-50/50 dark:bg-slate-950/20" dir="rtl">
      <div className="mx-auto max-w-7xl px-3 py-5 sm:px-5 lg:px-6">
        <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="mb-2 inline-flex items-center gap-2 rounded-lg bg-indigo-50 px-2.5 py-1 text-xs font-bold text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-300">
              <Layers3 size={13} />
              سير العمل
            </div>
            <h1 className="m-0 text-2xl font-black tracking-tight text-slate-900 dark:text-white">متابعة متطلبات المشروع</h1>
            <p className="m-0 mt-1 text-sm text-slate-500 dark:text-slate-400">كل مسار مستقل ويظهر اسم الجهة التي أضافته.</p>
          </div>
          <div className="inline-flex w-fit items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-500 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
            <FolderKanban size={14} />
            {workflows.length} {workflows.length === 1 ? 'مسار' : 'مسارات'}
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-[300px_minmax(0,1fr)]">
          <WorkflowSelector
            workflows={workflows}
            selectedId={workflow.id}
            onSelect={(id) => {
              setSelectedWorkflowId(id);
              setSelectedStage(null);
              setError('');
            }}
            search={search}
            setSearch={setSearch}
          />

          <main className="min-w-0 space-y-5">
            <WorkflowSummary workflow={workflow} stages={stages} />

            {actionStages.length > 0 && (
              <section>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <div>
                    <h2 className="m-0 text-base font-black text-slate-900 dark:text-white">بانتظار إجراء منك</h2>
                    <p className="m-0 mt-1 text-xs text-slate-500 dark:text-slate-400">ابدأ بالمراحل الأقرب للموعد النهائي.</p>
                  </div>
                  <span className="rounded-lg bg-amber-50 px-2.5 py-1 text-xs font-bold text-amber-700 dark:bg-amber-950/30 dark:text-amber-300">{actionStages.length}</span>
                </div>
                <div className="space-y-3">
                  {actionStages.map((stage) => (
                    <StageCard key={stage.id} stage={stage} index={indexMap[stage.id]} onOpen={setSelectedStage} />
                  ))}
                </div>
              </section>
            )}

            {actionStages.length === 0 && (
              <div className="rounded-2xl border border-emerald-100 bg-emerald-50/70 px-5 py-4 dark:border-emerald-900/40 dark:bg-emerald-950/20">
                <div className="flex items-center gap-3">
                  <CheckCircle2 size={19} className="text-emerald-600 dark:text-emerald-300" />
                  <div>
                    <div className="text-sm font-bold text-emerald-800 dark:text-emerald-200">لا توجد إجراءات مطلوبة حالياً</div>
                    <div className="mt-0.5 text-xs text-emerald-700/70 dark:text-emerald-300/70">ستظهر هنا أي مرحلة جديدة تحتاج إلى تعبئة أو تعديل.</div>
                  </div>
                </div>
              </div>
            )}

            <CompletedStages stages={completedStages} indexMap={indexMap} />
            <ScheduledStages stages={scheduledStages} indexMap={indexMap} />

            {error && (
              <div className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-xs leading-6 text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/20 dark:text-rose-200">
                <AlertCircle size={15} className="mt-0.5 shrink-0" />
                {error}
              </div>
            )}
          </main>
        </div>
      </div>

      <StageModal
        stage={selectedStage}
        onClose={() => {
          setSelectedStage(null);
          setError('');
        }}
        onSubmit={handleSubmit}
        submitting={submitting}
        error={error}
      />
    </div>
  );
}
