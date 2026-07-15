import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  RotateCcw,
  Search,
  ShieldAlert,
  UserCheck,
  UserX,
  X,
} from 'lucide-react';
import {
  fetchStudentStatusManagement,
  markParticipationFailed,
  markParticipationWithdrawn,
  reverseParticipationToActive,
} from '../api';

const STATUS_OPTIONS = [
  { value: '', label: 'كل الحالات' },
  { value: 'active', label: 'نشط' },
  { value: 'failed', label: 'راسب' },
  { value: 'withdrawn', label: 'منسحب' },
];

const emptyStats = {
  active_students: 0,
  failed_students: 0,
  withdrawn_students: 0,
  partial_projects: 0,
  solo_projects: 0,
  fully_withdrawn_projects: 0,
  fully_failed_projects: 0,
  alerts: {},
};

function statusClass(status) {
  if (status === 'active') return 'bg-emerald-50 text-emerald-700 border-emerald-200';
  if (status === 'failed') return 'bg-rose-50 text-rose-700 border-rose-200';
  return 'bg-amber-50 text-amber-700 border-amber-200';
}

function projectStatusLabel(status) {
  return {
    active: 'نشط',
    partial_team: 'جزئي',
    solo: 'فردي',
    fully_withdrawn: 'منسحب كلياً',
    fully_failed: 'راسب كلياً',
    inactive: 'غير نشط',
  }[status] || status || 'نشط';
}

function studentLabel(student) {
  return `${student.name}${student.is_leader ? ' - قائد' : ''}${student.status !== 'active' ? ` - ${student.status}` : ''}`;
}

function StatCard({ label, value, tone = 'slate' }) {
  const toneClass = {
    emerald: 'border-emerald-200 bg-emerald-50 text-emerald-800',
    rose: 'border-rose-200 bg-rose-50 text-rose-800',
    amber: 'border-amber-200 bg-amber-50 text-amber-800',
    sky: 'border-sky-200 bg-sky-50 text-sky-800',
    slate: 'border-slate-200 bg-white text-slate-800',
  }[tone];

  return (
    <div className={`rounded-lg border px-4 py-3 ${toneClass}`}>
      <div className="text-xs font-medium uppercase tracking-wide opacity-80">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value ?? 0}</div>
    </div>
  );
}

export default function StudentStatusManagement({ onBack }) {
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState(emptyStats);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [filters, setFilters] = useState({
    search: '',
    university_id: '',
    status: '',
    department: '',
    project: '',
    supervisor: '',
  });
  const [modal, setModal] = useState(null);
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const loadRows = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = Object.fromEntries(
        Object.entries(filters).filter(([, value]) => String(value || '').trim())
      );
      const response = await fetchStudentStatusManagement(params);
      setRows(response.data?.results || []);
      setStats(response.data?.stats || emptyStats);
    } catch (err) {
      setError(err.response?.data?.error || 'تعذر تحميل بيانات حالة الطلاب.');
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    loadRows();
  }, [loadRows]);

  const departments = useMemo(() => {
    const values = new Set(rows.map((row) => row.department).filter(Boolean));
    return Array.from(values).sort();
  }, [rows]);

  const alertProjects = useMemo(() => {
    const alerts = stats.alerts || {};
    return [
      ...(alerts.partial_projects || []).map((project) => ({ ...project, label: 'جزئي' })),
      ...(alerts.solo_projects || []).map((project) => ({ ...project, label: 'فردي' })),
      ...(alerts.fully_withdrawn_projects || []).map((project) => ({ ...project, label: 'منسحب كلياً' })),
      ...(alerts.fully_failed_projects || []).map((project) => ({ ...project, label: 'راسب كلياً' })),
    ].slice(0, 8);
  }, [stats]);

  const updateFilter = (key, value) => {
    setFilters((current) => ({ ...current, [key]: value }));
  };

  const clearFilters = () => {
    setFilters({
      search: '',
      university_id: '',
      status: '',
      department: '',
      project: '',
      supervisor: '',
    });
  };

  const openModal = (row, action) => {
    setModal({ row, action });
    setReason('');
    setError('');
    setSuccess('');
  };

  const closeModal = () => {
    setModal(null);
    setReason('');
    setSubmitting(false);
  };

  const submitAction = async () => {
    if (!modal) return;
    setSubmitting(true);
    setError('');
    setSuccess('');
    const payload = { reason };

    try {
      if (modal.action === 'failed') {
        await markParticipationFailed(modal.row.id, payload);
        setSuccess(`${modal.row.student_name} تم تحديده كراسب.`);
      } else if (modal.action === 'withdrawn') {
        await markParticipationWithdrawn(modal.row.id, payload);
        setSuccess(`${modal.row.student_name} تم تحديده كمنسحب.`);
      } else {
        await reverseParticipationToActive(modal.row.id, payload);
        setSuccess(`${modal.row.student_name} تمت إعادته كنشط.`);
      }
      closeModal();
      await loadRows();
    } catch (err) {
      setError(err.response?.data?.error || 'فشل تحديث الحالة.');
      setSubmitting(false);
    }
  };

  const modalTitle = modal?.action === 'failed'
    ? 'تحديد كراسب'
    : modal?.action === 'withdrawn'
      ? 'تحديد كمنسحب'
      : 'إعادة كنشط';

  const remainingActive = modal?.row?.team_members
    ?.filter((student) => student.id !== modal.row.student && student.status === 'active')
    ?.map((student) => student.name) || [];

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-6">
      <div className="mx-auto max-w-7xl space-y-5">
        <div className="flex flex-col gap-3 border-b border-slate-200 pb-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">إدارة حالة الطلاب</h1>
            <div className="mt-1 text-sm text-slate-500">{rows.length} records loaded</div>
          </div>
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="inline-flex items-center justify-center rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
            >
              Back
            </button>
          )}
        </div>

        <div className="grid gap-3 md:grid-cols-4 xl:grid-cols-7">
          <StatCard label="نشط" value={stats.active_students} tone="emerald" />
          <StatCard label="راسب" value={stats.failed_students} tone="rose" />
          <StatCard label="منسحب" value={stats.withdrawn_students} tone="amber" />
          <StatCard label="جزئي" value={stats.partial_projects} tone="sky" />
          <StatCard label="فردي" value={stats.solo_projects} tone="amber" />
          <StatCard label="منسحب كلياً" value={stats.fully_withdrawn_projects} tone="slate" />
          <StatCard label="راسب كلياً" value={stats.fully_failed_projects} tone="rose" />
        </div>

        {alertProjects.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-900">
              <AlertTriangle size={18} />
              Project Alerts
            </div>
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-4">
              {alertProjects.map((project) => (
                <div key={`${project.source}-${project.id}-${project.label}`} className="rounded-md border border-amber-200 bg-white px-3 py-2">
                  <div className="text-sm font-medium text-slate-900">{project.title}</div>
                  <div className="mt-1 text-xs text-amber-700">{project.label}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
            <label className="relative">
              <Search className="pointer-events-none absolute left-3 top-2.5 text-slate-400" size={16} />
              <input
                value={filters.search}
                onChange={(event) => updateFilter('search', event.target.value)}
                className="w-full rounded-md border border-slate-300 py-2 pl-9 pr-3 text-sm"
                placeholder="طالب أو مشروع"
              />
            </label>
            <input
              value={filters.university_id}
              onChange={(event) => updateFilter('university_id', event.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="الرقم الجامعي"
            />
            <select
              value={filters.status}
              onChange={(event) => updateFilter('status', event.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
            <select
              value={filters.department}
              onChange={(event) => updateFilter('department', event.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
            >
              <option value="">كل الأقسام</option>
              {departments.map((department) => (
                <option key={department} value={department}>{department}</option>
              ))}
            </select>
            <input
              value={filters.project}
              onChange={(event) => updateFilter('project', event.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="المشروع"
            />
            <input
              value={filters.supervisor}
              onChange={(event) => updateFilter('supervisor', event.target.value)}
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              placeholder="المشرف"
            />
          </div>
          <div className="mt-3 flex justify-end">
            <button
              type="button"
              onClick={clearFilters}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              مسح
            </button>
          </div>
        </div>

        {(error || success) && (
          <div className={`rounded-md border px-4 py-3 text-sm ${error ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>
            {error || success}
          </div>
        )}

        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-100 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                <tr>
                  <th className="px-4 py-3">الطالب</th>
                  <th className="px-4 py-3">الرقم الجامعي</th>
                  <th className="px-4 py-3">القسم</th>
                  <th className="px-4 py-3">مشروع مسجل</th>
                  <th className="px-4 py-3">المشرف</th>
                  <th className="px-4 py-3">حجم الفريق</th>
                  <th className="px-4 py-3">الحالة</th>
                  <th className="px-4 py-3">التصنيف</th>
                  <th className="px-4 py-3">السبب</th>
                  <th className="px-4 py-3">آخر تعديل بواسطة</th>
                  <th className="px-4 py-3">إجراءات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {loading ? (
                  <tr>
                    <td className="px-4 py-8 text-center text-slate-500" colSpan={11}>جاري التحميل...</td>
                  </tr>
                ) : rows.length === 0 ? (
                  <tr>
                    <td className="px-4 py-8 text-center text-slate-500" colSpan={11}>لا توجد سجلات</td>
                  </tr>
                ) : rows.map((row) => (
                  <tr key={row.id} className={row.current_status === 'active' ? 'bg-white' : 'bg-slate-50'}>
                    <td className="px-4 py-3 font-medium text-slate-900">{row.student_name}</td>
                    <td className="px-4 py-3 text-slate-700">{row.university_id}</td>
                    <td className="px-4 py-3 text-slate-700">{row.department || '-'}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900">{row.registered_project}</div>
                      <div className="text-xs text-slate-500">{projectStatusLabel(row.project_operational_status)}</div>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{row.supervisor?.name || '-'}</td>
                    <td className="px-4 py-3 font-medium text-slate-800">{row.team_size?.label || '-'}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold capitalize ${statusClass(row.current_status)}`}>
                        {row.current_status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-600">
                      {row.designation_date ? new Date(row.designation_date).toLocaleDateString() : '-'}
                    </td>
                    <td className="max-w-[220px] px-4 py-3 text-slate-600">
                      <span className="block max-h-10 overflow-hidden">{row.reason || '-'}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{row.last_changed_by?.name || '-'}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2">
                        {row.current_status === 'active' ? (
                          <>
                            <button
                              type="button"
                              onClick={() => openModal(row, 'failed')}
                              className="inline-flex items-center gap-1 rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-xs font-medium text-rose-700 hover:bg-rose-100"
                            >
                              <ShieldAlert size={14} />
                              Failed
                            </button>
                            <button
                              type="button"
                              onClick={() => openModal(row, 'withdrawn')}
                              className="inline-flex items-center gap-1 rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100"
                            >
                              <UserX size={14} />
                              Withdrawn
                            </button>
                          </>
                        ) : (
                          <button
                            type="button"
                            onClick={() => openModal(row, 'active')}
                            className="inline-flex items-center gap-1 rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100"
                          >
                            <RotateCcw size={14} />
                            Active
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {modal && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-slate-900/50 p-4" role="dialog" aria-modal="true">
          <div className="w-full max-w-2xl rounded-lg bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
              <div className="flex items-center gap-2">
                {modal.action === 'active' ? <UserCheck size={20} className="text-emerald-600" /> : <AlertTriangle size={20} className="text-amber-600" />}
                <h2 className="text-lg font-semibold text-slate-900">{modalTitle}</h2>
              </div>
              <button type="button" onClick={closeModal} className="rounded-md p-1 text-slate-500 hover:bg-slate-100">
                <X size={18} />
              </button>
            </div>

            <div className="space-y-4 px-5 py-4">
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <div className="text-xs font-medium uppercase tracking-wide text-slate-500">طالب</div>
                  <div className="mt-1 font-semibold text-slate-900">{modal.row.student_name}</div>
                </div>
                <div>
                  <div className="text-xs font-medium uppercase tracking-wide text-slate-500">المشروع</div>
                  <div className="mt-1 font-semibold text-slate-900">{modal.row.registered_project}</div>
                </div>
              </div>

              <div>
                <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">الفريق الحالي</div>
                <div className="flex flex-wrap gap-2">
                  {modal.row.team_members?.map((student) => (
                    <span key={student.id} className={`rounded-full border px-2 py-1 text-xs ${statusClass(student.status)}`}>
                      {studentLabel(student)}
                    </span>
                  ))}
                </div>
              </div>

              <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                {modal.action === 'active'
                  ? `${modal.row.student_name} سيظهر مجدداً في عمليات المشاريع النشطة وفحوصات الأهلية المستقبلية.`
                  : `${modal.row.student_name} سيُستبعد من عمليات المشاريع النشطة المستقبلية. ${remainingActive.length ? `الطلاب النشطون المتبقون: ${remainingActive.join('، ')}.` : 'لن يبقى أي طلاب نشطين آخرين.'}`}
              </div>

              <label className="block">
                <span className="mb-1 block text-sm font-medium text-slate-700">السبب</span>
                <textarea
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                  className="min-h-[96px] w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                  placeholder="سبب اختياري"
                />
              </label>
            </div>

            <div className="flex justify-end gap-2 border-t border-slate-200 px-5 py-4">
              <button
                type="button"
                onClick={closeModal}
                className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                إلغاء
              </button>
              <button
                type="button"
                onClick={submitAction}
                disabled={submitting}
                className="inline-flex items-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-60"
              >
                <CheckCircle2 size={16} />
                تأكيد
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
