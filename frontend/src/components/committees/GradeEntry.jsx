/**
 * GradeEntry — واجهة منظمة لإدخال علامات مشاريع اللجان.
 * في وضع التقييم الجماعي: كل عضو يحفظ مسودته، وتُحسب العلامة النهائية بعد اكتمال تقييم الجميع.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Award,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  Download,
  FileText,
  Filter,
  GraduationCap,
  Loader2,
  MessageSquareText,
  Save,
  Search,
  ShieldCheck,
  Star,
  UsersRound,
  X,
} from 'lucide-react';
import {
  downloadProjectReport,
  enterBulkGrades,
  fetchMyCommitteeGrades,
  submitGradeDraft,
} from '../../api';

const CTYPE_AR = {
  seminar_1: 'سيمينار 1',
  seminar_2: 'سيمينار 2',
  technical: 'اللجنة الفنية',
  final_discussion: 'المناقشة النهائية',
};

const MAX_MAIN = {
  seminar_1: 10,
  seminar_2: 10,
  technical: 20,
  final_discussion: 30,
};

const VIEW_FILTERS = [
  { value: 'all', label: 'الكل' },
  { value: 'pending', label: 'غير مكتملة' },
  { value: 'completed', label: 'مكتملة' },
];

function extractApiError(error, fallback = 'حدث خطأ غير متوقع.') {
  const data = error?.response?.data;
  if (!data) return fallback;
  if (typeof data === 'string') return data;
  if (data.detail) return data.detail;
  if (data.error) return data.error;
  if (data.message) return data.message;

  if (typeof data === 'object') {
    const messages = Object.entries(data).flatMap(([key, value]) => {
      const values = Array.isArray(value) ? value : [value];
      return values
        .filter((item) => item != null)
        .map((item) => (typeof item === 'object' ? JSON.stringify(item) : String(item)))
        .map((item) => (key === 'non_field_errors' ? item : `${key}: ${item}`));
    });
    if (messages.length) return messages.join(' — ');
  }

  return fallback;
}

function getInitialScores(project, collectiveMode) {
  const initial = {};
  (project.students || []).forEach((student) => {
    const source = collectiveMode ? student.my_draft : student.grade;
    initial[student.student_id] = {
      score_main: source?.score_main ?? '',
      score_report: source?.score_report ?? '',
      notes: source?.notes || '',
    };
  });
  return initial;
}

function projectMatchesSearch(project, query) {
  if (!query) return true;
  const normalized = query.trim().toLowerCase();
  if (!normalized) return true;

  const title = String(project.title || '').toLowerCase();
  const studentNames = (project.students || [])
    .map((student) => student.student_name || '')
    .join(' ')
    .toLowerCase();

  return title.includes(normalized) || studentNames.includes(normalized);
}

function Notice({ type = 'error', children, onClose }) {
  const styles = {
    success: 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-200',
    warning: 'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-200',
    error: 'border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900/60 dark:bg-rose-950/30 dark:text-rose-200',
  };

  const Icon = type === 'success' ? CheckCircle2 : AlertCircle;

  return (
    <div className={`flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm leading-6 ${styles[type] || styles.error}`}>
      <Icon size={18} className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">{children}</div>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg transition hover:bg-black/5 dark:hover:bg-white/10"
          aria-label="إغلاق"
        >
          <X size={15} />
        </button>
      )}
    </div>
  );
}

function ConfirmationNotice({ message, saving, onConfirm, onCancel }) {
  return (
    <div className="rounded-2xl border-2 border-amber-300 bg-amber-50 p-4 shadow-sm dark:border-amber-800 dark:bg-amber-950/30 sm:p-5">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-600 text-white shadow-sm dark:bg-amber-500 dark:text-amber-950">
          <AlertCircle size={20} />
        </div>

        <div className="min-w-0 flex-1">
          <h4 className="m-0 text-base font-black text-amber-950 dark:text-amber-100">
            تأكيد استبدال العلامات السابقة
          </h4>
          <p className="m-0 mt-1.5 text-sm font-semibold leading-6 text-amber-900 dark:text-amber-200">
            {message || 'توجد علامات محفوظة سابقًا لهذا المشروع.'}
          </p>

          <div className="mt-3 rounded-xl border border-amber-200 bg-white/80 px-3.5 py-2.5 text-xs font-bold leading-6 text-amber-900 dark:border-amber-800 dark:bg-slate-900/60 dark:text-amber-100">
            عند المتابعة سيتم استبدال العلامات القديمة بالقيم الموجودة حاليًا في الحقول. لا يمكن التراجع عن هذا الإجراء بعد الحفظ.
          </div>

          <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center">
            <button
              type="button"
              disabled={saving}
              onClick={onConfirm}
              className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-amber-700 px-5 py-2.5 text-sm font-black text-white shadow-sm transition hover:bg-amber-800 focus:outline-none focus:ring-4 focus:ring-amber-300/50 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-amber-500 dark:text-amber-950 dark:hover:bg-amber-400"
            >
              {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
              {saving ? 'جاري الاستبدال...' : 'استبدال العلامات وحفظها'}
            </button>
            <button
              type="button"
              disabled={saving}
              onClick={onCancel}
              className="inline-flex min-h-11 items-center justify-center rounded-xl border border-amber-300 bg-white px-5 py-2.5 text-sm font-black text-amber-900 transition hover:bg-amber-100 focus:outline-none focus:ring-4 focus:ring-amber-200/60 disabled:cursor-not-allowed disabled:opacity-60 dark:border-amber-800 dark:bg-slate-900 dark:text-amber-100 dark:hover:bg-amber-950/40"
            >
              العودة دون تغيير
            </button>
          </div>
        </div>

        <button
          type="button"
          disabled={saving}
          onClick={onCancel}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-amber-800 transition hover:bg-amber-200/70 disabled:opacity-60 dark:text-amber-200 dark:hover:bg-amber-900/50"
          aria-label="إلغاء التأكيد"
        >
          <X size={17} />
        </button>
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, helper }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-2xl font-black text-slate-900 dark:text-white">{value}</div>
          <div className="mt-1 text-sm font-bold text-slate-700 dark:text-slate-200">{label}</div>
          {helper && <div className="mt-1 text-xs text-slate-500 dark:text-slate-400">{helper}</div>}
        </div>
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-violet-50 text-violet-600 dark:bg-violet-950/40 dark:text-violet-300">
          <Icon size={21} />
        </div>
      </div>
    </div>
  );
}

export default function GradeEntry() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [committeeType, setCommitteeType] = useState('all');
  const [viewFilter, setViewFilter] = useState('all');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetchMyCommitteeGrades();
      setData(response.data);
    } catch (requestError) {
      setError(extractApiError(requestError, 'تعذّر تحميل اللجان والعلامات.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const committees = data?.committees || [];

  const totals = useMemo(() => {
    const projects = committees.flatMap((committee) => committee.projects || []);
    const completed = projects.filter((project) => project.all_graded).length;
    const students = projects.reduce((sum, project) => sum + (project.students?.length || 0), 0);
    return {
      committees: committees.length,
      projects: projects.length,
      completed,
      pending: Math.max(0, projects.length - completed),
      students,
    };
  }, [committees]);

  const visibleCommittees = useMemo(() => {
    return committees
      .filter((committee) => committeeType === 'all' || committee.committee_type === committeeType)
      .map((committee) => {
        const projects = (committee.projects || []).filter((project) => {
          const matchesSearch = projectMatchesSearch(project, search);
          const matchesStatus = viewFilter === 'all'
            || (viewFilter === 'completed' && project.all_graded)
            || (viewFilter === 'pending' && !project.all_graded);
          return matchesSearch && matchesStatus;
        });
        return { ...committee, projects };
      })
      .filter((committee) => committee.projects.length > 0);
  }, [committees, committeeType, search, viewFilter]);

  if (loading) {
    return (
      <div className="flex min-h-[440px] flex-col items-center justify-center gap-3" dir="rtl">
        <Loader2 size={32} className="animate-spin text-violet-600" />
        <div className="text-sm font-semibold text-slate-500 dark:text-slate-400">جاري تحميل لجانك ومشاريعك...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl p-5" dir="rtl">
        <Notice type="error">
          <div className="font-bold">تعذّر فتح صفحة العلامات</div>
          <div className="mt-1">{error}</div>
          <button
            type="button"
            onClick={load}
            className="mt-3 rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white transition hover:bg-rose-700"
          >
            إعادة المحاولة
          </button>
        </Notice>
      </div>
    );
  }

  if (!committees.length) {
    return (
      <div className="mx-auto flex min-h-[440px] max-w-2xl flex-col items-center justify-center px-5 text-center" dir="rtl">
        <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-300">
          <ClipboardCheck size={30} />
        </div>
        <h2 className="mt-4 text-xl font-black text-slate-900 dark:text-white">لا توجد لجان متاحة لإدخال العلامات</h2>
        <p className="mt-2 text-sm leading-7 text-slate-500 dark:text-slate-400">
          ستظهر هنا اللجان التي تشارك فيها عندما تصبح مشاريعها جاهزة للتقييم.
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-full bg-slate-50/70 px-3 py-5 dark:bg-slate-950/30 sm:px-5 lg:px-7" dir="rtl">
      <div className="mx-auto max-w-7xl space-y-5">
        <header className="overflow-hidden rounded-3xl border border-violet-100 bg-gradient-to-l from-violet-700 via-violet-600 to-indigo-600 px-5 py-6 text-white shadow-lg shadow-violet-900/10 sm:px-7 sm:py-7">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex items-start gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-white/15 ring-1 ring-white/20 backdrop-blur">
                <Award size={28} />
              </div>
              <div>
                <div className="mb-1 text-xs font-bold text-violet-100">نظام تقييم مشاريع التخرج</div>
                <h1 className="m-0 text-2xl font-black sm:text-3xl">إدخال العلامات</h1>
                <p className="m-0 mt-2 max-w-2xl text-sm leading-7 text-violet-100">
                  اختر اللجنة والمشروع، ثم أدخل علامة كل طالب واحفظ المشروع كاملًا من مكان واحد.
                </p>
              </div>
            </div>
            <div className="rounded-2xl bg-white/10 px-4 py-3 text-sm ring-1 ring-white/15 backdrop-blur">
              <div className="font-bold">{totals.pending} مشروع بانتظار التقييم</div>
              <div className="mt-1 text-xs text-violet-100">تم إنجاز {totals.completed} من أصل {totals.projects}</div>
            </div>
          </div>
        </header>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard icon={ShieldCheck} label="اللجان" value={totals.committees} helper="اللجان المسندة إليك" />
          <StatCard icon={GraduationCap} label="المشاريع" value={totals.projects} helper="إجمالي المشاريع المتاحة" />
          <StatCard icon={UsersRound} label="الطلاب" value={totals.students} helper="ضمن المشاريع الحالية" />
          <StatCard icon={CheckCircle2} label="المكتملة" value={totals.completed} helper={`${totals.pending} ما زالت غير مكتملة`} />
        </section>

        <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:p-5">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center">
            <div className="relative min-w-0 flex-1">
              <Search size={18} className="pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="ابحث باسم المشروع أو الطالب..."
                className="w-full rounded-2xl border border-slate-200 bg-slate-50 py-3.5 pl-4 pr-11 text-sm font-medium text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-violet-300 focus:bg-white focus:ring-4 focus:ring-violet-500/10 dark:border-slate-700 dark:bg-slate-800 dark:text-white dark:focus:border-violet-700 dark:focus:bg-slate-900"
              />
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:w-auto">
              <label className="relative block">
                <Filter size={16} className="pointer-events-none absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <select
                  value={committeeType}
                  onChange={(event) => setCommitteeType(event.target.value)}
                  className="h-[50px] w-full min-w-[190px] appearance-none rounded-2xl border border-slate-200 bg-white pl-9 pr-10 text-sm font-bold text-slate-700 outline-none transition focus:border-violet-300 focus:ring-4 focus:ring-violet-500/10 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
                >
                  <option value="all">جميع أنواع اللجان</option>
                  {Object.entries(CTYPE_AR).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
                <ChevronDown size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
              </label>

              <div className="flex h-[50px] items-center rounded-2xl border border-slate-200 bg-slate-50 p-1 dark:border-slate-700 dark:bg-slate-800">
                {VIEW_FILTERS.map((filter) => (
                  <button
                    key={filter.value}
                    type="button"
                    onClick={() => setViewFilter(filter.value)}
                    className={`h-full flex-1 whitespace-nowrap rounded-xl px-3 text-xs font-bold transition ${
                      viewFilter === filter.value
                        ? 'bg-white text-violet-700 shadow-sm dark:bg-slate-900 dark:text-violet-300'
                        : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-white'
                    }`}
                  >
                    {filter.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>

        {visibleCommittees.length > 0 ? (
          <div className="space-y-5">
            {visibleCommittees.map((committee) => (
              <CommitteeSection
                key={committee.committee_id}
                committee={committee}
                onReload={load}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-3xl border border-dashed border-slate-300 bg-white px-5 py-16 text-center dark:border-slate-700 dark:bg-slate-900">
            <Search size={30} className="mx-auto text-slate-300 dark:text-slate-600" />
            <div className="mt-4 text-base font-black text-slate-800 dark:text-slate-100">لا توجد نتائج مطابقة</div>
            <div className="mt-2 text-sm text-slate-500 dark:text-slate-400">غيّر كلمات البحث أو الفلاتر لعرض المشاريع.</div>
          </div>
        )}
      </div>
    </div>
  );
}

function CommitteeSection({ committee, onReload }) {
  const isFinal = committee.committee_type === 'final_discussion';
  const collective = committee.collective_mode;
  const projects = committee.projects || [];
  const completedCount = projects.filter((project) => project.all_graded).length;
  const firstPendingIndex = projects.findIndex((project) => !project.all_graded);
  const [expanded, setExpanded] = useState(true);

  return (
    <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm dark:border-slate-800 dark:bg-slate-900">
      <button
        type="button"
        onClick={() => setExpanded((current) => !current)}
        className="flex w-full flex-col gap-4 border-b border-slate-100 bg-gradient-to-l from-slate-50 to-white px-5 py-5 text-right transition hover:bg-slate-50 dark:border-slate-800 dark:from-slate-900 dark:to-slate-900 sm:flex-row sm:items-center sm:justify-between sm:px-6"
      >
        <div className="flex min-w-0 items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-violet-100 text-violet-700 dark:bg-violet-950/50 dark:text-violet-300">
            <ShieldCheck size={23} />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="m-0 text-lg font-black text-slate-900 dark:text-white">
                {CTYPE_AR[committee.committee_type] || committee.committee_type}
              </h2>
              {collective && (
                <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-[11px] font-bold text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300">
                  تقييم جماعي
                </span>
              )}
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs font-medium text-slate-500 dark:text-slate-400">
              <span>{committee.department_ar || 'القسم غير محدد'}</span>
              {committee.semester && <span>• {committee.semester}</span>}
              <span>• {projects.length} مشاريع</span>
              <span>• العلامة من {MAX_MAIN[committee.committee_type]}{isFinal ? ' + 30 للتقرير' : ''}</span>
            </div>
          </div>
        </div>

        <div className="flex w-full items-center gap-3 sm:w-auto">
          <div className="min-w-[150px] flex-1 sm:flex-none">
            <div className="mb-1.5 flex items-center justify-between text-[11px] font-bold text-slate-500 dark:text-slate-400">
              <span>تقدم اللجنة</span>
              <span>{completedCount}/{projects.length}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
              <div
                className="h-full rounded-full bg-violet-600 transition-all"
                style={{ width: `${projects.length ? Math.round((completedCount / projects.length) * 100) : 0}%` }}
              />
            </div>
          </div>
          <ChevronDown size={20} className={`shrink-0 text-slate-400 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </div>
      </button>

      {expanded && (
        <div className="space-y-3 bg-slate-50/60 p-2.5 dark:bg-slate-950/20 sm:p-4">
          {projects.map((project, index) => (
            <ProjectSection
              key={`${project.source}-${project.id}`}
              project={project}
              committee={committee}
              onReload={onReload}
              defaultOpen={index === (firstPendingIndex >= 0 ? firstPendingIndex : 0)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function ProjectSection({ project, committee, onReload, defaultOpen }) {
  const isFinal = committee.committee_type === 'final_discussion';
  const maxMain = MAX_MAIN[committee.committee_type];
  const [open, setOpen] = useState(defaultOpen);
  const [scores, setScores] = useState(() => getInitialScores(project, committee.collective_mode));
  const [fieldErrors, setFieldErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);
  const [downloading, setDownloading] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);

  useEffect(() => {
    setScores(getInitialScores(project, committee.collective_mode));
  }, [project, committee.collective_mode]);

  const gradedStudents = (project.students || []).filter((student) => {
    if (committee.collective_mode) return Boolean(student.my_draft);
    return Boolean(student.grade);
  }).length;

  const setField = (studentId, field, value) => {
    setScores((current) => ({
      ...current,
      [studentId]: {
        ...current[studentId],
        [field]: value,
      },
    }));

    setFieldErrors((current) => {
      const key = `${studentId}.${field}`;
      if (!current[key]) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  };

  const validate = () => {
    const errors = {};

    (project.students || []).forEach((student) => {
      const values = scores[student.student_id] || {};
      const main = values.score_main;
      const report = values.score_report;

      if (main === '' || main == null) {
        errors[`${student.student_id}.score_main`] = 'مطلوبة';
      } else if (Number.isNaN(Number(main)) || Number(main) < 0 || Number(main) > maxMain) {
        errors[`${student.student_id}.score_main`] = `0–${maxMain}`;
      }

      if (isFinal && report !== '' && report != null) {
        if (Number.isNaN(Number(report)) || Number(report) < 0 || Number(report) > 30) {
          errors[`${student.student_id}.score_report`] = '0–30';
        }
      }
    });

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSave = async ({ confirmUpdate = false } = {}) => {
    setMessage(null);
    setShowConfirmation(false);

    if (!validate()) {
      setMessage({
        type: 'error',
        text: 'راجع الحقول المميزة بالأحمر؛ توجد علامات ناقصة أو خارج المجال المسموح.',
      });
      return;
    }

    const grades = (project.students || []).map((student) => {
      const values = scores[student.student_id] || {};
      const item = {
        student_id: student.student_id,
        score_main: Number(values.score_main),
        notes: String(values.notes || '').trim(),
      };

      if (isFinal) {
        item.score_report = values.score_report === '' || values.score_report == null
          ? null
          : Number(values.score_report);
      }

      return item;
    });

    setSaving(true);
    try {
      if (committee.collective_mode) {
        await submitGradeDraft({
          committee_id: committee.committee_id,
          project_source: project.source,
          project_id: project.id,
          committee_type: committee.committee_type,
          semester: committee.semester,
          grades,
        });
        setMessage({
          type: 'success',
          text: 'تم حفظ تقييمك، وستظهر النتيجة النهائية بعد اكتمال تقييم جميع الأعضاء.',
        });
      } else {
        await enterBulkGrades({
          project_source: project.source,
          project_id: project.id,
          committee_type: committee.committee_type,
          committee_id: committee.committee_id,
          semester: committee.semester,
          grades,
          confirm_update: confirmUpdate,
        });
        setMessage({
          type: 'success',
          text: 'تم حفظ علامات المشروع بنجاح.',
        });
      }

      await onReload();
    } catch (requestError) {
      const responseData = requestError?.response?.data;
      if (requestError?.response?.status === 409 && responseData?.requires_confirmation) {
        setShowConfirmation(true);
        setMessage({
          type: 'warning',
          text: responseData.message || 'توجد علامات محفوظة سابقًا. هل تريد استبدالها؟',
        });
      } else {
        setMessage({
          type: 'error',
          text: extractApiError(requestError, 'فشل حفظ العلامات. حاول مرة أخرى.'),
        });
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDownload = async () => {
    setDownloading(true);
    setMessage(null);
    try {
      const response = await downloadProjectReport(project.source, project.id);
      const url = URL.createObjectURL(new Blob([response.data]));
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = project.report?.original_name || `project-${project.id}-report`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (requestError) {
      setMessage({
        type: 'error',
        text: extractApiError(requestError, 'فشل تحميل تقرير المشروع.'),
      });
    } finally {
      setDownloading(false);
    }
  };

  return (
    <article className={`overflow-hidden rounded-xl border bg-white shadow-sm transition dark:bg-slate-900 ${
      project.all_graded
        ? 'border-emerald-200 dark:border-emerald-900/60'
        : 'border-slate-200 dark:border-slate-800'
    }`}>
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center gap-3 px-3 py-2.5 text-right transition hover:bg-slate-50/80 dark:hover:bg-slate-800/40 sm:px-4"
      >
        <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
          project.all_graded
            ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/40 dark:text-emerald-300'
            : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
        }`}>
          {project.all_graded ? <CheckCircle2 size={17} /> : <FileText size={17} />}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="m-0 truncate text-sm font-black text-slate-900 dark:text-white sm:text-base">
              {project.title || `مشروع رقم ${project.id}`}
            </h3>
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
              project.all_graded
                ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300'
                : 'bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300'
            }`}>
              {project.all_graded ? 'مكتملة' : 'قيد الإدخال'}
            </span>
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11px] font-medium text-slate-500 dark:text-slate-400">
            <span>{project.students?.length || 0} طلاب</span>
            <span>• {gradedStudents}/{project.students?.length || 0} مدخل</span>
            {isFinal && (
              <span className={project.report_uploaded ? 'text-emerald-600 dark:text-emerald-300' : 'text-amber-600 dark:text-amber-300'}>
                • {project.report_uploaded ? 'التقرير مرفوع' : 'التقرير غير مرفوع'}
              </span>
            )}
          </div>
        </div>

        <span className="hidden rounded-lg bg-slate-100 px-2.5 py-1.5 text-[11px] font-black text-slate-600 dark:bg-slate-800 dark:text-slate-300 sm:inline-flex">
          /{maxMain}{isFinal ? ' + 30' : ''}
        </span>
        <ChevronDown size={18} className={`shrink-0 text-slate-400 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="border-t border-slate-100 dark:border-slate-800">
          <div className="flex flex-col gap-2 border-b border-slate-100 bg-slate-50/70 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/20 sm:flex-row sm:items-center sm:justify-between sm:px-4">
            <div className="text-xs text-slate-600 dark:text-slate-300">
              {committee.collective_mode
                ? 'أدخل تقييمك لكل طالب؛ يحسب النظام المتوسط بعد اكتمال تقييم أعضاء اللجنة.'
                : 'أدخل العلامات في الجدول ثم احفظ المشروع دفعة واحدة.'}
            </div>

            {isFinal && project.report_uploaded && (
              <button
                type="button"
                onClick={handleDownload}
                disabled={downloading}
                className="inline-flex h-8 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-sky-200 bg-sky-50 px-3 text-[11px] font-bold text-sky-700 transition hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-sky-900/60 dark:bg-sky-950/30 dark:text-sky-300"
              >
                {downloading ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
                {downloading ? 'تحميل...' : 'تحميل التقرير'}
              </button>
            )}
          </div>

          {!project.report_uploaded && isFinal && (
            <div className="border-b border-amber-100 bg-amber-50 px-3 py-2 text-[11px] font-semibold text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-200 sm:px-4">
              التقرير غير مرفوع إلكترونيًا، لكن يمكن إدخال علامة التقرير وحفظها بشكل طبيعي.
            </div>
          )}

          {showConfirmation ? (
            <div className="px-3 pt-3 sm:px-4">
              <ConfirmationNotice
                message={message?.text}
                saving={saving}
                onConfirm={() => handleSave({ confirmUpdate: true })}
                onCancel={() => {
                  setMessage(null);
                  setShowConfirmation(false);
                }}
              />
            </div>
          ) : message ? (
            <div className="px-3 pt-3 sm:px-4">
              <Notice type={message.type} onClose={() => setMessage(null)}>
                <div className="font-bold">{message.text}</div>
              </Notice>
            </div>
          ) : null}

          <div className="overflow-x-auto">
            <table className={`w-full border-collapse text-right ${isFinal ? 'min-w-[920px]' : 'min-w-[760px]'}`}>
              <thead className="bg-slate-100/90 text-[11px] font-black text-slate-600 dark:bg-slate-800/80 dark:text-slate-300">
                <tr>
                  <th className="w-12 border-b border-slate-200 px-3 py-2 text-center dark:border-slate-700">#</th>
                  <th className="min-w-[210px] border-b border-slate-200 px-3 py-2 dark:border-slate-700">الطالب</th>
                  <th className="w-32 border-b border-slate-200 px-3 py-2 text-center dark:border-slate-700">علامة التقييم / {maxMain}</th>
                  {isFinal && (
                    <th className="w-32 border-b border-slate-200 px-3 py-2 text-center dark:border-slate-700">علامة التقرير / 30</th>
                  )}
                  <th className="min-w-[170px] border-b border-slate-200 px-3 py-2 dark:border-slate-700">العلامة السابقة</th>
                  <th className="min-w-[240px] border-b border-slate-200 px-3 py-2 dark:border-slate-700">
                    <span className="inline-flex items-center gap-1.5"><MessageSquareText size={13} />ملاحظة</span>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {(project.students || []).map((student, index) => (
                  <StudentGradeRow
                    key={student.student_id}
                    student={student}
                    index={index}
                    values={scores[student.student_id] || {}}
                    maxMain={maxMain}
                    isFinal={isFinal}
                    collectiveMode={committee.collective_mode}
                    errors={{
                      main: fieldErrors[`${student.student_id}.score_main`],
                      report: fieldErrors[`${student.student_id}.score_report`],
                    }}
                    onChange={(field, value) => setField(student.student_id, field, value)}
                  />
                ))}
              </tbody>
            </table>
          </div>

          <footer className="flex flex-col gap-2 border-t border-slate-100 bg-slate-50/70 px-3 py-2.5 dark:border-slate-800 dark:bg-slate-950/20 sm:flex-row sm:items-center sm:justify-between sm:px-4">
            <div className="text-[11px] text-slate-500 dark:text-slate-400">
              الحقول الفارغة لا تُسجل كصفر. تحقق من القيم قبل الحفظ.
            </div>
            <button
              type="button"
              onClick={() => handleSave()}
              disabled={saving || showConfirmation}
              className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-violet-600 px-4 text-xs font-black text-white shadow-sm transition hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
              {saving
                ? 'جاري الحفظ...'
                : committee.collective_mode
                  ? 'حفظ تقييمي'
                  : 'حفظ العلامات'}
            </button>
          </footer>
        </div>
      )}
    </article>
  );
}

function StudentGradeRow({
  student,
  index,
  values,
  maxMain,
  isFinal,
  collectiveMode,
  errors,
  onChange,
}) {
  const previousParts = [];
  if (collectiveMode && student.my_draft) {
    previousParts.push(`تقييمي: ${student.my_draft.score_main ?? '—'}`);
  }
  if (student.grade?.score_main != null) {
    previousParts.push(
      `${collectiveMode ? 'المتوسط' : 'المحفوظة'}: ${student.grade.score_main}${
        isFinal ? ` + ${student.grade.score_report ?? '—'}` : ''
      }`,
    );
  }

  return (
    <tr className="bg-white transition hover:bg-violet-50/30 dark:bg-slate-900 dark:hover:bg-slate-800/40">
      <td className="px-3 py-2 text-center align-middle">
        <span className="inline-flex h-7 w-7 items-center justify-center rounded-lg bg-slate-100 text-[11px] font-black text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          {index + 1}
        </span>
      </td>
      <td className="px-3 py-2 align-middle">
        <div className="flex min-w-0 items-center gap-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-black text-slate-900 dark:text-white">{student.student_name}</span>
              {student.is_leader && (
                <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-50 px-1.5 py-0.5 text-[9px] font-bold text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
                  <Star size={9} className="fill-current" /> قائد
                </span>
              )}
            </div>
            {student.student_number && (
              <div className="mt-0.5 text-[10px] text-slate-400">{student.student_number}</div>
            )}
          </div>
        </div>
      </td>
      <td className="px-3 py-2 align-top">
        <ScoreInput
          value={values.score_main ?? ''}
          max={maxMain}
          error={errors.main}
          onChange={(value) => onChange('score_main', value)}
        />
      </td>
      {isFinal && (
        <td className="px-3 py-2 align-top">
          <ScoreInput
            value={values.score_report ?? ''}
            max={30}
            error={errors.report}
            onChange={(value) => onChange('score_report', value)}
          />
        </td>
      )}
      <td className="px-3 py-2 align-middle text-[11px] font-semibold text-slate-500 dark:text-slate-400">
        {previousParts.length ? previousParts.join(' • ') : '—'}
      </td>
      <td className="px-3 py-2 align-middle">
        <input
          type="text"
          value={values.notes || ''}
          onChange={(event) => onChange('notes', event.target.value)}
          placeholder="ملاحظة اختيارية..."
          className="h-9 w-full rounded-lg border border-slate-200 bg-white px-3 text-xs text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-violet-300 focus:ring-2 focus:ring-violet-500/10 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:focus:border-violet-700"
        />
      </td>
    </tr>
  );
}

function ScoreInput({ value, max, disabled = false, error, onChange }) {
  return (
    <div className="min-w-0">
      <div className="relative">
        <input
          type="number"
          min={0}
          max={max}
          step="0.01"
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          placeholder="—"
          className={`h-9 w-full rounded-lg border bg-white px-2 pl-9 text-center text-sm font-black text-slate-900 outline-none transition disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400 dark:bg-slate-900 dark:text-white dark:disabled:bg-slate-800 ${
            error
              ? 'border-rose-400 ring-2 ring-rose-500/10 dark:border-rose-700'
              : 'border-slate-200 focus:border-violet-300 focus:ring-2 focus:ring-violet-500/10 dark:border-slate-700 dark:focus:border-violet-700'
          }`}
        />
        <span className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-[9px] font-black text-slate-400 dark:text-slate-500">
          /{max}
        </span>
      </div>
      {error && (
        <span className="mt-1 flex items-center justify-center gap-1 text-[9px] font-bold text-rose-600 dark:text-rose-300">
          <AlertCircle size={9} /> {error}
        </span>
      )}
    </div>
  );
}
