import React, { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Users, FileSpreadsheet, AlertTriangle, FolderKanban,
  Plus, FileText, RefreshCw, CheckCircle2, Clock,
  ChevronLeft, ChevronRight, Folder, Gavel, UserCheck, Inbox, BarChart3,
} from 'lucide-react';
import {
  fetchCommitteesDashboard, distributeProjects,
} from '../../api';
import {
  COMMITTEE_TYPE_COLORS, DEPARTMENT_COLORS, WORKLOAD_COLORS,
  WARNING_COLORS, DEPARTMENTS, COMMITTEE_TYPES, getCommitteeTypeLabel, getProjectTypeLabel, getDepartmentLabel,
} from './constants';
import {
  LoadingState,
  PageAlert,
  PageHeader,
  PageShell,
  primaryButtonClass,
  secondaryButtonClass,
} from '../ui/PagePrimitives';
import './CommitteesDashboard.css';

/* ────────────────────────────────────────────────────────────────────────── */
/* Committees Dashboard — matches mockup 01_dashboard_main.png                  */
/* Layout: hero → stat cards → toolbar → two-column (compositions + warnings)   */
/*         → doctor workload table                                              */
/* ────────────────────────────────────────────────────────────────────────── */

/* ── Helper: render chair full name ──────────────────────────────────────── */
/* chair is unified across all endpoints: object {id, username, full_name, ...} | null */
function renderChairName(chair) {
  if (!chair) return '—';
  return chair.full_name || chair.username || (chair.id ? `#${chair.id}` : '—');
}

function distributionExclusionMessage(exclusions) {
  const total = Number(exclusions?.excluded_students_total || 0);
  const failed = Number(exclusions?.excluded_failed_students || 0);
  const withdrawn = Number(exclusions?.excluded_withdrawn_students || 0);
  const zeroActiveProjects = Number(exclusions?.excluded_projects_zero_active || 0);

  if (!total && !zeroActiveProjects) return '';

  const statusParts = [];
  if (withdrawn) statusParts.push(`${withdrawn} منسحب`);
  if (failed) statusParts.push(`${failed} راسب`);

  const studentPart = total
    ? `تم استبعاد ${total} طالب من التوزيع: ${statusParts.join('، ') || 'حالة غير فعالة'}.`
    : '';
  const projectPart = zeroActiveProjects
    ? `تم تجاوز ${zeroActiveProjects} مشروع لعدم وجود طلاب فعّالين.`
    : '';

  return [studentPart, projectPart].filter(Boolean).join(' ');
}

export default function CommitteesDashboard({ onNavigate, user }) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [busy, setBusy]       = useState(false);
  const [toast, setToast]     = useState(null);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [draftLossWarning, setDraftLossWarning] = useState(null);
  const [showModeDialog, setShowModeDialog] = useState(false);
  const [selectedMode, setSelectedMode] = useState('multi');  // 'single' | 'multi'
  const [selectedDepartment, setSelectedDepartment] = useState(null);
  const [selectedCommitteeType, setSelectedCommitteeType] = useState(null);

  const groupedCompositions = useMemo(() => {
    const compositions = data?.compositions || [];

    return DEPARTMENTS.map((department) => {
      const departmentItems = compositions.filter(
        (composition) => composition.department === department.value,
      );

      return {
        department: department.value,
        label: department.label_ar,
        items: departmentItems,
        committeeTypes: COMMITTEE_TYPES.map((committeeType) => ({
          committeeType: committeeType.value,
          label: committeeType.label_ar,
          items: departmentItems
            .filter((composition) => composition.committee_type === committeeType.value)
            .sort((a, b) =>
              String(a.project_type_ar || a.project_type || '').localeCompare(
                String(b.project_type_ar || b.project_type || ''),
                'ar',
              ) || String(a.name || '').localeCompare(String(b.name || ''), 'ar')
            ),
        })),
      };
    });
  }, [data]);

  const selectedDepartmentGroup = useMemo(
    () => groupedCompositions.find((group) => group.department === selectedDepartment) || null,
    [groupedCompositions, selectedDepartment],
  );

  const selectedTypeGroup = useMemo(
    () => selectedDepartmentGroup?.committeeTypes.find(
      (group) => group.committeeType === selectedCommitteeType,
    ) || null,
    [selectedDepartmentGroup, selectedCommitteeType],
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetchCommitteesDashboard();
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'تعذر تحميل لوحة اللجان.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  /* ── Actions ─────────────────────────────────────────────────────────── */
  const handleDistribute = async () => {
    if (busy) return;
    setShowModeDialog(true);  // first ask the dean for scheduling mode
  };

  const executeDistribution = async (confirmDraftLoss = false) => {
    setShowConfirmDialog(false);
    if (confirmDraftLoss) setDraftLossWarning(null);
    setBusy(true);
    try {
      const res = await distributeProjects({
        dry_run: false,
        scheduling_mode: selectedMode,
        confirm_draft_loss: confirmDraftLoss,
      });
      const distributed    = res.data?.distributed_projects    ?? 0;
      const undistributed  = res.data?.undistributed_projects  ?? 0;
      const processed      = res.data?.processed_templates     ?? 0;
      const exclusionMsg   = distributionExclusionMessage(res.data?.exclusions);
      const modeLabel = selectedMode === 'single' ? 'نفس اللجنة للأنواع الأربعة' : 'لجان مستقلة';
      const singleCreated = res.data?.single_mode_committees_created || 0;
      const msg = undistributed > 0
        ? `تم توزيع ${distributed} مشروع على ${processed} تركيب (${modeLabel}). (${undistributed} مشروع بدون لجنة مناسبة)`
        : `تم توزيع ${distributed} مشروع بنجاح (${modeLabel})${singleCreated ? ' · ' + singleCreated + ' لجنة منشأة للوضع الموحّد' : ''}`;
      setToast({ type: 'success', msg: [msg, exclusionMsg].filter(Boolean).join(' ') });
      setDraftLossWarning(null);
      await load();
    } catch (err) {
      const response = err.response?.data;
      if (response?.code === 'redistribution_confirmation_required') {
        setDraftLossWarning(response.safety || {});
        return;
      }
      setToast({
        type: 'error',
        msg: response?.detail || 'فشل التوزيع. حاول مرة أخرى لاحقًا.',
      });
    } finally { setBusy(false); }
  };

  const confirmDistribute = async () => executeDistribution(false);

  if (loading) return <LoadingState label="جاري تحميل التشكيلات واللجان..." />;

  if (error && !data) {
    return (
      <PageShell>
        <PageAlert>{error}</PageAlert>
        <div className="mt-4">
          <button type="button" className={primaryButtonClass} onClick={load}>
            <RefreshCw size={15} /> إعادة المحاولة
          </button>
        </div>
      </PageShell>
    );
  }

  const stats      = data?.stats || {};
  const comps      = data?.compositions || [];
  const warnings   = data?.warnings || [];
  const workloads  = data?.doctor_workload || [];

  return (
    <PageShell>
      <PageHeader
        icon={FolderKanban}
        title="التشكيلات والتوزيع"
        description={`إدارة تشكيلات اللجان وتوزيع المشاريع ومتابعة العبء التدريسي${user?.username ? ` — ${user.username}` : ''}.`}
        badge={`${comps.length} تشكيلة`}
        actions={(
          <>
            <button
              type="button"
              className={primaryButtonClass}
              onClick={() => onNavigate && onNavigate('committees-template-form')}
            >
              <Plus size={15} /> تشكيلة جديدة
            </button>
            <button
              type="button"
              className={secondaryButtonClass}
              onClick={() => onNavigate && onNavigate('committees-list')}
            >
              <FolderKanban size={15} /> قائمة اللجان
            </button>
            <button
              type="button"
              className={secondaryButtonClass}
              onClick={() => onNavigate && onNavigate('projects-assignment')}
            >
              <FileText size={15} /> جدول توزيع المشاريع
            </button>
          </>
        )}
      />
      <div className="cmd-page" dir="rtl">

      {/* ── Stat Cards ────────────────────────────────────────────────────── */}
      <div className="cmd-stats">
        <StatCard icon={<FileSpreadsheet size={22} />} value={stats.templates_count ?? 0} label="التشكيلات" variant="is-purple" />
        <StatCard icon={<Users size={22} />} value={stats.committees_count ?? 0} label="اللجان" variant="is-blue" />
        <StatCard icon={<CheckCircle2 size={22} />} value={stats.projects_distributed ?? 0} label="المشاريع الموزعة" variant="is-green" />
        <StatCard icon={<Inbox size={22} />} value={stats.projects_unassigned ?? 0} label="المشاريع غير المسندة" variant="is-amber" />
        <StatCard icon={<AlertTriangle size={22} />} value={stats.warnings_count ?? 0} label="التنبيهات" variant="is-red" />
      </div>

      {/* ── Toolbar ───────────────────────────────────────────────────────── */}
      <div className="cmd-toolbar">
        <div className="cmd-toolbar-left">
          <button
            className="cmd-btn cmd-btn-success"
            onClick={handleDistribute}
            disabled={busy || comps.length === 0}
            title="تشغيل خوارزمية التوزيع"
          >
            {busy ? <RefreshCw size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            توزيع المشاريع
          </button>
        </div>
        <div className="cmd-toolbar-right">
          <button className="cmd-btn cmd-btn-sm" onClick={load} disabled={loading}>
            <RefreshCw size={13} /> تحديث
          </button>
        </div>
      </div>

      {/* ── Two columns: compositions + warnings ─────────────────────────── */}
      <div className="cmd-two-col">
        {/* Compositions list */}
        <div className="cmd-section">
          <div className="cmd-section-header">
            <h2 className="cmd-section-title">
              <span className="cmd-section-title-icon"><FolderKanban size={16} /></span>
              التشكيلات
              <span className="cmd-section-count">{comps.length}</span>
            </h2>
            <button
              className="cmd-btn cmd-btn-sm cmd-btn-primary"
              onClick={() => onNavigate && onNavigate('committees-template-form')}
            >
              <Plus size={13} /> إضافة
            </button>
          </div>
          <div className="cmd-section-body">
            {comps.length === 0 ? (
              <div className="cmd-empty">
                <div className="cmd-empty-icon"><FolderKanban size={28} /></div>
                <h3>لا توجد تشكيلات بعد</h3>
                <p>ابدأ بإنشاء أول تشكيلة لتحديد نوع اللجنة والقسم ونوع المشروع وأعضاء الهيئة التدريسية.</p>
              </div>
            ) : (
              <div className="cmd-folder-browser" dir="rtl">
                <div className="cmd-folder-breadcrumbs">
                  <button
                    type="button"
                    className={`cmd-folder-crumb ${!selectedDepartment ? 'is-current' : ''}`}
                    onClick={() => {
                      setSelectedDepartment(null);
                      setSelectedCommitteeType(null);
                    }}
                  >
                    الاختصاصات
                  </button>
                  {selectedDepartmentGroup && (
                    <>
                      <ChevronLeft size={14} />
                      <button
                        type="button"
                        className={`cmd-folder-crumb ${!selectedCommitteeType ? 'is-current' : ''}`}
                        onClick={() => setSelectedCommitteeType(null)}
                      >
                        {selectedDepartmentGroup.label}
                      </button>
                    </>
                  )}
                  {selectedTypeGroup && (
                    <>
                      <ChevronLeft size={14} />
                      <span className="cmd-folder-crumb is-current">{selectedTypeGroup.label}</span>
                    </>
                  )}
                </div>

                {!selectedDepartment ? (
                  <div className="cmd-folder-grid cmd-department-folders">
                    {groupedCompositions.map((group) => {
                      const deptColor = DEPARTMENT_COLORS[group.department] || {};
                      return (
                        <button
                          type="button"
                          key={group.department}
                          className="cmd-folder-card"
                          style={{
                            '--folder-bg': deptColor.bg || 'var(--bg-tertiary)',
                            '--folder-border': deptColor.border || 'var(--border)',
                            '--folder-color': deptColor.text || 'var(--primary)',
                          }}
                          onClick={() => {
                            setSelectedDepartment(group.department);
                            setSelectedCommitteeType(null);
                          }}
                        >
                          <Folder size={48} className="cmd-folder-icon" />
                          <strong>{group.label}</strong>
                          <span>{group.items.length} تشكيلات</span>
                          <ChevronLeft size={17} className="cmd-folder-open-icon" />
                        </button>
                      );
                    })}
                  </div>
                ) : !selectedCommitteeType ? (
                  <>
                    <button
                      type="button"
                      className="cmd-folder-back"
                      onClick={() => setSelectedDepartment(null)}
                    >
                      <ChevronRight size={15} /> العودة إلى الاختصاصات
                    </button>
                    <div className="cmd-folder-grid cmd-type-folders">
                      {selectedDepartmentGroup.committeeTypes.map((typeGroup) => {
                        const typeColor = COMMITTEE_TYPE_COLORS[typeGroup.committeeType] || {};
                        return (
                          <button
                            type="button"
                            key={typeGroup.committeeType}
                            className="cmd-folder-card"
                            style={{
                              '--folder-bg': typeColor.bg || 'var(--bg-tertiary)',
                              '--folder-border': typeColor.border || 'var(--border)',
                              '--folder-color': typeColor.text || 'var(--primary)',
                            }}
                            onClick={() => setSelectedCommitteeType(typeGroup.committeeType)}
                          >
                            <Folder size={48} className="cmd-folder-icon" />
                            <strong>{typeGroup.label}</strong>
                            <span>{typeGroup.items.length} تشكيلات</span>
                            <ChevronLeft size={17} className="cmd-folder-open-icon" />
                          </button>
                        );
                      })}
                    </div>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      className="cmd-folder-back"
                      onClick={() => setSelectedCommitteeType(null)}
                    >
                      <ChevronRight size={15} /> العودة إلى أنواع اللجان
                    </button>
                    {selectedTypeGroup.items.length === 0 ? (
                      <div className="cmd-empty cmd-folder-empty">
                        <div className="cmd-empty-icon"><Inbox size={28} /></div>
                        <h3>لا توجد تشكيلات</h3>
                        <p>لا توجد تشكيلات من نوع {selectedTypeGroup.label} ضمن اختصاص {selectedDepartmentGroup.label}.</p>
                      </div>
                    ) : (
                      <div className="cmd-committee-type-list">
                        {selectedTypeGroup.items.map((c) => {
                          const cTypeColor = COMMITTEE_TYPE_COLORS[c.committee_type] || {};
                          const deptColor = DEPARTMENT_COLORS[c.department] || {};
                          const chairName = renderChairName(c.chair);
                          return (
                            <div
                              key={c.id}
                              className={`cmd-comp-card ${c.is_approved ? 'is-approved' : 'is-draft'}`}
                              onClick={() => onNavigate && onNavigate('committees-list', { templateId: c.id })}
                            >
                              <div className="cmd-comp-main">
                                <div className="cmd-comp-title-row">
                                  <h3 className="cmd-comp-title">{c.name}</h3>
                                  {c.is_approved ? (
                                    <span className="cmd-badge" style={{
                                      background: 'rgba(16, 185, 129, 0.12)',
                                      color: '#34d399',
                                      borderColor: 'rgba(16, 185, 129, 0.25)',
                                    }}>
                                      <CheckCircle2 size={11} /> معتمدة
                                    </span>
                                  ) : (
                                    <span className="cmd-badge" style={{
                                      background: 'rgba(245, 158, 11, 0.12)',
                                      color: '#fbbf24',
                                      borderColor: 'rgba(245, 158, 11, 0.25)',
                                    }}>
                                      <Clock size={11} /> مسودة
                                    </span>
                                  )}
                                </div>
                                <div className="cmd-comp-badges">
                                  <span className="cmd-badge" style={{
                                    background: cTypeColor.bg,
                                    color: cTypeColor.text,
                                    borderColor: cTypeColor.border,
                                  }}>
                                    <Gavel size={11} /> {c.committee_type_ar}
                                  </span>
                                  <span className="cmd-badge" style={{
                                    background: deptColor.bg,
                                    color: deptColor.text,
                                    borderColor: deptColor.border,
                                  }}>
                                    {c.department_ar}
                                  </span>
                                  <span className="cmd-badge" style={{
                                    background: 'rgba(99, 102, 241, 0.12)',
                                    color: '#818cf8',
                                    borderColor: 'rgba(99, 102, 241, 0.25)',
                                  }}>
                                    {c.project_type_ar}
                                  </span>
                                </div>
                                <div className="cmd-comp-meta">
                                  <span className="cmd-comp-meta-item">
                                    <UserCheck size={13} /> الرئيس: <strong>{chairName}</strong>
                                  </span>
                                  <span className="cmd-comp-meta-item">
                                    <Users size={13} /> الأعضاء: <strong>{c.members_count ?? 0}</strong>
                                  </span>
                                  <span className="cmd-comp-meta-item">
                                    <FolderKanban size={13} /> اللجان: <strong>{c.committees_count ?? c.committees_total ?? 0}</strong>
                                  </span>
                                  <span className="cmd-comp-meta-item">
                                    <CheckCircle2 size={13} /> المشاريع: <strong>{c.total_projects_assigned ?? 0}</strong>
                                  </span>
                                </div>
                              </div>
                              <div className="cmd-comp-actions">
                                <button
                                  className="cmd-btn cmd-btn-sm"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    onNavigate && onNavigate('committees-list', { templateId: c.id });
                                  }}
                                >
                                  عرض اللجان <ChevronLeft size={12} />
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Warnings panel */}
        <div className="cmd-section">
          <div className="cmd-section-header">
            <h2 className="cmd-section-title">
              <span className="cmd-section-title-icon" style={{
                background: 'rgba(245, 158, 11, 0.12)',
                color: '#fbbf24',
              }}>
                <AlertTriangle size={16} />
              </span>
              التنبيهات
              <span className="cmd-section-count" style={{
                background: 'rgba(239, 68, 68, 0.12)',
                color: '#f87171',
              }}>{warnings.length}</span>
            </h2>
          </div>
          <div className="cmd-section-body" style={{ maxHeight: '460px', overflowY: 'auto' }}>
            {warnings.length === 0 ? (
              <div className="cmd-empty">
                <div className="cmd-empty-icon"><CheckCircle2 size={28} /></div>
                <h3>كل البيانات صحيحة</h3>
                <p>لا توجد تنبيهات حاليًا.</p>
              </div>
            ) : (
              warnings.slice(0, 30).map((w, i) => {
                const color = WARNING_COLORS[w.level] || WARNING_COLORS.info;
                return (
                  <div
                    key={i}
                    className="cmd-warning-item"
                    style={{
                      background: color.bg,
                      borderColor: color.border,
                      color: color.text,
                    }}
                  >
                    <div className="cmd-warning-icon" style={{ background: color.bg, color: color.text }}>
                      {w.level === 'warn' ? <AlertTriangle size={14} /> : <BarChart3 size={14} />}
                    </div>
                    <div className="cmd-warning-content">
                      <span className="cmd-warning-text">{w.message}</span>
                      <span className="cmd-warning-code">{w.code}</span>
                    </div>
                  </div>
                );
              })
            )}
            {warnings.length > 30 && (
              <div style={{ textAlign: 'center', padding: '8px', fontSize: 12, color: 'var(--text-muted)' }}>
                ويوجد {warnings.length - 30} تنبيهًا إضافيًا…
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Doctor Workload Table ─────────────────────────────────────────── */}
      <div className="cmd-section">
        <div className="cmd-section-header">
          <h2 className="cmd-section-title">
            <span className="cmd-section-title-icon" style={{
              background: 'rgba(16, 185, 129, 0.12)',
              color: '#34d399',
            }}>
              <BarChart3 size={16} />
            </span>
            عبء أعضاء الهيئة التدريسية
            <span className="cmd-section-count">{workloads.length}</span>
          </h2>
        </div>
        {workloads.length === 0 ? (
          <div className="cmd-empty">
            <div className="cmd-empty-icon"><Users size={28} /></div>
            <h3>لم يتم تعيين أعضاء هيئة تدريس بعد</h3>
            <p>عند إنشاء التشكيلات وتعيين أعضاء الهيئة التدريسية ستظهر إحصاءات العبء هنا.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="cmd-workload-table">
              <thead>
                <tr>
                  <th>عضو هيئة التدريس</th>
                  <th>القسم</th>
                  <th>الرئيس</th>
                  <th>عضو</th>
                  <th>الإجمالي</th>
                  <th>مستوى العبء</th>
                </tr>
              </thead>
              <tbody>
                {workloads.map((w) => {
                  const level = WORKLOAD_COLORS[w.workload_level] || WORKLOAD_COLORS.med;
                  const initial = (w.doctor_name || '?').charAt(0);
                  return (
                    <tr key={w.doctor_id}>
                      <td>
                        <div className="cmd-doctor-cell">
                          <div className="cmd-doctor-avatar">{initial}</div>
                          <div>
                            <div className="cmd-doctor-name">{w.doctor_name}</div>
                            <div className="cmd-doctor-dept">#{w.doctor_id}</div>
                          </div>
                        </div>
                      </td>
                      <td>{w.department_ar}</td>
                      <td><strong>{w.chaired_count}</strong></td>
                      <td><strong>{w.member_count}</strong></td>
                      <td><strong>{w.total_committees}</strong></td>
                      <td>
                        <span className="cmd-badge" style={{
                          background: level.bg,
                          color: level.text,
                          borderColor: 'transparent',
                        }}>
                          {level.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Toast ────────────────────────────────────────────────────────── */}
      {toast && (
        <div className={`fixed bottom-6 left-1/2 z-[9999] flex mx-4 w-full max-w-[480px] -translate-x-1/2 items-center gap-2 rounded-xl px-4 py-3 text-sm font-bold text-white shadow-2xl ${toast.type === 'success' ? 'bg-emerald-600' : 'bg-rose-600'}`}>
          {toast.type === 'success' ? <CheckCircle2 size={17} /> : <AlertTriangle size={17} />}
          <span>{toast.msg}</span>
        </div>
      )}

      {/* ── Scheduling Mode Selection Dialog ─────────────────────────────── */}
      {showModeDialog && (
        <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-slate-950/55 p-4 backdrop-blur-sm">
          <section className="w-full max-w-xl rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-2xl sm:p-6" dir="rtl">
            <h3 className="m-0 text-xl font-black text-[var(--text)]">اختر طريقة التوزيع</h3>
            <p className="m-0 mt-2 text-sm leading-7 text-[var(--text-muted)]">
              حدّد هل تعتمد المشاريع لجنة موحّدة للأنواع الأربعة، أم تشكيلات مستقلة لكل نوع لجنة.
            </p>

            <div className="mt-5 space-y-3">
              {[
                {
                  value: 'single',
                  title: 'نفس اللجنة للأنواع الأربعة',
                  description: 'نفس الأطباء يقيّمون المشروع في سيمينار 1 وسيمينار 2 واللجنة الفنية والمناقشة النهائية.',
                },
                {
                  value: 'multi',
                  title: 'لجان مختلفة لكل نوع',
                  description: 'كل نوع لجنة يعتمد تشكيلته الخاصة، ويمكن أن تختلف الهيئة التدريسية بين الأنواع.',
                },
              ].map((option) => {
                const selected = selectedMode === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setSelectedMode(option.value)}
                    className={`w-full rounded-xl border p-4 text-right transition ${
                      selected
                        ? 'border-[var(--primary)] bg-[var(--primary-light)] ring-2 ring-[var(--primary-light)]'
                        : 'border-[var(--border)] bg-[var(--bg-secondary)] hover:border-[var(--border-dark)] hover:bg-[var(--bg-hover)]'
                    }`}
                  >
                    <span className="flex items-start gap-3">
                      <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 ${selected ? 'border-[var(--primary)]' : 'border-[var(--border-dark)]'}`}>
                        {selected && <span className="h-2.5 w-2.5 rounded-full bg-[var(--primary)]" />}
                      </span>
                      <span>
                        <strong className="block text-sm font-black text-[var(--text)]">{option.title}</strong>
                        <span className="mt-1 block text-xs leading-6 text-[var(--text-muted)]">{option.description}</span>
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>

            <div className="mt-6 flex flex-wrap justify-end gap-2">
              <button type="button" onClick={() => setShowModeDialog(false)} className={secondaryButtonClass}>إلغاء</button>
              <button
                type="button"
                className={primaryButtonClass}
                onClick={() => {
                  setShowModeDialog(false);
                  setShowConfirmDialog(true);
                }}
              >
                متابعة
              </button>
            </div>
          </section>
        </div>
      )}

      {/* ── Confirm Dialog ──────────────────────────────────────────────── */}
      {showConfirmDialog && (
        <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-slate-950/55 p-4 backdrop-blur-sm">
          <section className="w-full max-w-lg rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-2xl sm:p-6" dir="rtl">
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--primary-light)] text-[var(--primary)]">
                <RefreshCw size={20} />
              </div>
              <div>
                <h3 className="m-0 text-lg font-black text-[var(--text)]">تأكيد توزيع المشاريع</h3>
                <p className="m-0 mt-1 text-sm leading-7 text-[var(--text-muted)]">
                  سيتم تشغيل خوارزمية التوزيع على التشكيلات المعتمدة وفق القسم ونوع المشروع.
                </p>
              </div>
            </div>

            <div className="mt-5 rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-4 text-sm leading-7 text-[var(--text-secondary)]">
              <div>• سيتم توزيع المشاريع تلقائيًا على اللجان المناسبة.</div>
              <div>• ستتمكن من مراجعة النتائج وتعديلها يدويًا لاحقًا.</div>
              <div>• يحمي النظام العلامات النهائية ويطلب تأكيدًا عند وجود مسودات.</div>
            </div>

            <div className="mt-6 flex flex-wrap justify-end gap-2">
              <button type="button" onClick={() => setShowConfirmDialog(false)} className={secondaryButtonClass}>إلغاء</button>
              <button type="button" onClick={confirmDistribute} className={primaryButtonClass}>
                <RefreshCw size={15} /> تنفيذ التوزيع
              </button>
            </div>
          </section>
        </div>
      )}

      {/* ── Draft-loss confirmation ───────────────────────────────────── */}
      {draftLossWarning && (
        <div className="fixed inset-0 z-[10020] flex items-center justify-center bg-slate-950/65 p-4 backdrop-blur-sm">
          <section className="w-full max-w-xl overflow-hidden rounded-2xl border border-[var(--danger-border)] bg-[var(--card)] shadow-2xl" dir="rtl">
            <div className="border-b border-[var(--danger-border)] p-5 sm:p-6">
              <div className="flex items-start gap-3">
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--danger-bg)] text-[var(--danger-text)]">
                  <AlertTriangle size={21} />
                </div>
                <div>
                  <h3 className="m-0 text-lg font-black text-[var(--danger-text)]">توجد مسودات علامات ستُحذف</h3>
                  <p className="m-0 mt-1 text-sm leading-7 text-[var(--text-muted)]">
                    إعادة التوزيع تنشئ لجانًا جديدة، ولذلك ستُحذف مسودات العلامات المرتبطة باللجان الحالية.
                  </p>
                </div>
              </div>
            </div>

            <div className="p-5 sm:p-6">
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
                  <div className="text-xs font-medium text-[var(--text-muted)]">اللجان المتأثرة</div>
                  <div className="mt-1 text-2xl font-black text-[var(--text)]">{draftLossWarning.committees_count || 0}</div>
                </div>
                <div className="rounded-xl border border-[var(--warning-border)] bg-[var(--warning-bg)] p-4">
                  <div className="text-xs font-medium text-[var(--warning-text)]">مسودات العلامات</div>
                  <div className="mt-1 text-2xl font-black text-[var(--warning-text)]">{draftLossWarning.draft_count || 0}</div>
                </div>
              </div>

              <div className="mt-4 rounded-xl border border-[var(--danger-border)] bg-[var(--danger-bg)] p-4 text-sm leading-7 text-[var(--danger-text)]">
                لن يمكن استرجاع المسودات بعد التنفيذ، وسيُسجل الإجراء في سجل التدقيق باسم حساب العميد.
              </div>

              <div className="mt-6 flex flex-wrap justify-end gap-2">
                <button type="button" onClick={() => setDraftLossWarning(null)} className={secondaryButtonClass}>
                  إلغاء وحماية المسودات
                </button>
                <button
                  type="button"
                  onClick={() => executeDistribution(true)}
                  disabled={busy}
                  className="btn border-0 bg-[var(--danger)] text-white hover:opacity-90"
                >
                  {busy ? <RefreshCw size={15} className="animate-spin" /> : <AlertTriangle size={15} />}
                  حذف المسودات وإعادة التوزيع
                </button>
              </div>
            </div>
          </section>
        </div>
      )}
      </div>
    </PageShell>
  );
}

/* ── Sub-component: Stat Card ────────────────────────────────────────────── */
function StatCard({ icon, value, label, variant = '' }) {
  return (
    <div className={`cmd-stat-card ${variant}`}>
      <div className="cmd-stat-icon">{icon}</div>
      <div className="cmd-stat-info">
        <span className="cmd-stat-value">{value}</span>
        <span className="cmd-stat-label">{label}</span>
      </div>
    </div>
  );
}
