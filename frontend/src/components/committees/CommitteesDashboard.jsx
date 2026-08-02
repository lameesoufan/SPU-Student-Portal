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
  if (withdrawn) statusParts.push(`${withdrawn} withdrawn`);
  if (failed) statusParts.push(`${failed} failed`);

  const studentPart = total
    ? `${total} students excluded from distribution: ${statusParts.join(', ') || 'inactive status'}.`
    : '';
  const projectPart = zeroActiveProjects
    ? `${zeroActiveProjects} projects with zero active students skipped.`
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

  if (loading) {
    return (
      <div className="cmd-loading">
        <div className="cmd-spinner" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="cmd-page" dir="rtl">
        <div className="cmd-error">
          <AlertTriangle size={18} />
          {error}
        </div>
        <button className="cmd-btn cmd-btn-primary" onClick={load}>
          <RefreshCw size={14} /> إعادة المحاولة
        </button>
      </div>
    );
  }

  const stats      = data?.stats || {};
  const comps      = data?.compositions || [];
  const warnings   = data?.warnings || [];
  const workloads  = data?.doctor_workload || [];

  return (
    <div className="cmd-page" dir="rtl">
      {/* ── Hero ──────────────────────────────────────────────────────────── */}
      <div className="cmd-hero">
        <div className="cmd-hero-content">
          <div>
            <h1 className="cmd-hero-title">لوحة إدارة اللجان</h1>
            <p className="cmd-hero-sub">
              Welcome {user?.username || 'العميد'} — From here you can create compositions, distribute projects,
              and monitor faculty workload.
            </p>
          </div>
          <div className="cmd-hero-actions">
            <button
              className="cmd-hero-btn cmd-hero-btn-primary"
              onClick={() => onNavigate && onNavigate('committees-template-form')}
            >
              <Plus size={16} /> تشكيلة جديدة
            </button>
            <button
              className="cmd-hero-btn cmd-hero-btn-secondary"
              onClick={() => onNavigate && onNavigate('committees-list')}
            >
              <FolderKanban size={16} /> قائمة اللجان
            </button>
            <button
              className="cmd-hero-btn cmd-hero-btn-secondary"
              onClick={() => onNavigate && onNavigate('projects-assignment')}
            >
              <FileText size={16} /> جدول التوزيع
            </button>
          </div>
        </div>
      </div>

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
            Distribute Projects
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
                and {warnings.length - 30} more warnings…
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
        <div style={{
          position: 'fixed',
          bottom: 24,
          left: 24,
          right: 24,
          maxWidth: 480,
          margin: '0 auto',
          padding: '14px 18px',
          borderRadius: 12,
          background: toast.type === 'success' ? 'rgba(16, 185, 129, 0.95)' : 'rgba(239, 68, 68, 0.95)',
          color: '#fff',
          fontSize: 13,
          fontWeight: 600,
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.2)',
          zIndex: 9999,
          display: 'flex',
          alignItems: 'center',
          gap: 10,
        }}>
          {toast.type === 'success'
            ? <CheckCircle2 size={18} />
            : <AlertTriangle size={18} />}
          {toast.msg}
        </div>
      )}

      {/* ── Scheduling Mode Selection Dialog ─────────────────────────────── */}
      {showModeDialog && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
          backdropFilter: 'blur(4px)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', zIndex: 10000,
        }}>
          <div style={{
            background: '#fff', borderRadius: 16, padding: 28,
            maxWidth: 540, width: 'calc(100% - 32px)',
            boxShadow: '0 20px 50px rgba(0,0,0,0.3)',
            direction: 'rtl',
          }}>
            <h3 style={{ margin: '0 0 8px 0', fontSize: 20, fontWeight: 700, color: '#1e293b' }}>
              اختر طريقة التوزيع
            </h3>
            <p style={{ margin: '0 0 20px 0', fontSize: 14, color: '#64748b', lineHeight: 1.6 }}>
              هل نفس اللجنة تقيّم المشروع في كل الأنواع الأربعة (سيمينار 1، سيمينار 2، فنية، نهائية)،
              أم لجان مختلفة لكل نوع؟
            </p>

            {/* Option A: Single */}
            <div
              onClick={() => setSelectedMode('single')}
              style={{
                padding: 16, borderRadius: 12, cursor: 'pointer', marginBottom: 10,
                border: `2px solid ${selectedMode === 'single' ? '#667eea' : '#e2e8f0'}`,
                background: selectedMode === 'single' ? '#ede9fe' : '#fff',
                transition: 'all 0.2s',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                <div style={{
                  width: 20, height: 20, borderRadius: '50%',
                  border: `2px solid ${selectedMode === 'single' ? '#667eea' : '#cbd5e1'}`,
                  background: selectedMode === 'single' ? '#667eea' : '#fff',
                }} />
                <strong style={{ fontSize: 15, color: '#1e293b' }}>نفس اللجنة للأنواع الأربعة</strong>
              </div>
              <p style={{ margin: 0, fontSize: 13, color: '#64748b', lineHeight: 1.5, paddingLeft: 30 }}>
                نفس الأطباء يقيّمون المشروع في 4 جلسات بأنواع مختلفة.
                ينشئ النظام 4 لجان تلقائياً لكل مشروع بنفس الأطباء.
              </p>
            </div>

            {/* Option B: Multi */}
            <div
              onClick={() => setSelectedMode('multi')}
              style={{
                padding: 16, borderRadius: 12, cursor: 'pointer', marginBottom: 20,
                border: `2px solid ${selectedMode === 'multi' ? '#667eea' : '#e2e8f0'}`,
                background: selectedMode === 'multi' ? '#ede9fe' : '#fff',
                transition: 'all 0.2s',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                <div style={{
                  width: 20, height: 20, borderRadius: '50%',
                  border: `2px solid ${selectedMode === 'multi' ? '#667eea' : '#cbd5e1'}`,
                  background: selectedMode === 'multi' ? '#667eea' : '#fff',
                }} />
                <strong style={{ fontSize: 15, color: '#1e293b' }}>لجان مختلفة لكل نوع</strong>
              </div>
              <p style={{ margin: 0, fontSize: 13, color: '#64748b', lineHeight: 1.5, paddingLeft: 30 }}>
                كل نوع لجنة له تشكيلة منفصلة بأطباء قد يكونون مختلفين.
                التشكيلة تحدد نوع اللجنة (سيمينار 1، 2، فنية، نهائية).
              </p>
            </div>

            {/* Buttons */}
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowModeDialog(false)}
                style={{
                  padding: '11px 24px', borderRadius: 10,
                  border: '1.5px solid #e2e8f0', background: '#fff',
                  color: '#64748b', fontSize: 14, fontWeight: 600, cursor: 'pointer',
                }}
              >إلغاء</button>
              <button
                onClick={() => {
                  setShowModeDialog(false);
                  setShowConfirmDialog(true);  // proceed to confirmation
                }}
                style={{
                  padding: '11px 28px', borderRadius: 10, border: 'none',
                  background: 'linear-gradient(135deg, #667eea, #764ba2)',
                  color: '#fff', fontSize: 14, fontWeight: 600, cursor: 'pointer',
                  boxShadow: '0 4px 12px rgba(102,126,234,0.4)',
                }}
              >متابعة</button>
            </div>
          </div>
        </div>
      )}

      {/* ── Confirm Dialog ──────────────────────────────────────────────── */}
      {showConfirmDialog && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.5)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 10000,
          animation: 'fadeIn 0.2s ease',
        }}>
          <div style={{
            background: '#fff',
            borderRadius: 16,
            padding: 28,
            maxWidth: 480,
            width: 'calc(100% - 32px)',
            boxShadow: '0 20px 50px rgba(0, 0, 0, 0.3)',
            animation: 'scaleIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
          }}>
            {/* العنوان */}
            <div style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: 14,
              marginBottom: 18,
            }}>
              <div style={{
                width: 48,
                height: 48,
                borderRadius: 12,
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}>
                <RefreshCw size={24} color="#fff" />
              </div>
              <div style={{ flex: 1 }}>
                <h3 style={{
                  margin: 0,
                  fontSize: 20,
                  fontWeight: 700,
                  color: '#1e293b',
                  marginBottom: 6,
                }}>
                  تأكيد توزيع المشاريع
                </h3>
                <p style={{
                  margin: 0,
                  fontSize: 14,
                  color: '#64748b',
                  lineHeight: 1.6,
                }}>
                  سيتم تشغيل خوارزمية توزيع المشاريع على اللجان المُعدّة. هل تريد المتابعة؟
                </p>
              </div>
            </div>

            {/* Additional information */}
            <div style={{
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              borderRadius: 10,
              padding: 14,
              marginBottom: 20,
            }}>
              <div style={{
                fontSize: 13,
                color: '#475569',
                lineHeight: 1.5,
              }}>
                <div style={{ marginBottom: 6 }}>
                  ✓ سيتم توزيع المشاريع تلقائيًا
                </div>
                <div style={{ marginBottom: 6 }}>
                  ✓ سيتم إسناد المشاريع لكل لجنة بناءً على القسم ونوع المشروع
                </div>
                <div>
                  ✓ يمكنك تعديل التوزيع يدويًا لاحقًا
                </div>
              </div>
            </div>

            {/* Buttons */}
            <div style={{
              display: 'flex',
              gap: 10,
              justifyContent: 'flex-end',
            }}>
              <button
                onClick={() => setShowConfirmDialog(false)}
                style={{
                  padding: '11px 24px',
                  borderRadius: 10,
                  border: '1.5px solid #e2e8f0',
                  background: '#fff',
                  color: '#64748b',
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => {
                  e.target.style.background = '#f8fafc';
                  e.target.style.borderColor = '#cbd5e1';
                }}
                onMouseLeave={(e) => {
                  e.target.style.background = '#fff';
                  e.target.style.borderColor = '#e2e8f0';
                }}
              >
                إلغاء
              </button>
              <button
                onClick={confirmDistribute}
                style={{
                  padding: '11px 32px',
                  borderRadius: 10,
                  border: 'none',
                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  color: '#fff',
                  fontSize: 14,
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  transition: 'all 0.2s',
                  boxShadow: '0 4px 12px rgba(102, 126, 234, 0.4)',
                }}
                onMouseEnter={(e) => {
                  e.target.style.transform = 'translateY(-2px)';
                  e.target.style.boxShadow = '0 6px 20px rgba(102, 126, 234, 0.5)';
                }}
                onMouseLeave={(e) => {
                  e.target.style.transform = 'translateY(0)';
                  e.target.style.boxShadow = '0 4px 12px rgba(102, 126, 234, 0.4)';
                }}
              >
                <RefreshCw size={16} />
                تنفيذ التوزيع
              </button>
            </div>
          </div>

          <style>
            {`
              @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
              }
              @keyframes scaleIn {
                from {
                  opacity: 0;
                  transform: scale(0.9);
                }
                to {
                  opacity: 1;
                  transform: scale(1);
                }
              }
            `}
          </style>
        </div>
      )}

      {/* ── Draft-loss confirmation ───────────────────────────────────── */}
      {draftLossWarning && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 10020,
          background: 'rgba(15, 23, 42, 0.64)', backdropFilter: 'blur(5px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
        }}>
          <div dir="rtl" style={{
            width: 'min(560px, 100%)', background: '#fff', borderRadius: 18,
            boxShadow: '0 24px 70px rgba(15, 23, 42, 0.35)', overflow: 'hidden',
          }}>
            <div style={{ padding: '24px 26px 18px', borderBottom: '1px solid #fee2e2' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
                <div style={{
                  width: 46, height: 46, borderRadius: 13, flexShrink: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: '#fff1f2', color: '#e11d48',
                }}>
                  <AlertTriangle size={23} />
                </div>
                <div>
                  <h3 style={{ margin: 0, color: '#881337', fontSize: 19, fontWeight: 800 }}>
                    توجد مسودات علامات ستُحذف
                  </h3>
                  <p style={{ margin: '7px 0 0', color: '#64748b', fontSize: 14, lineHeight: 1.8 }}>
                    إعادة التوزيع ستنشئ لجانًا جديدة، ولذلك ستُحذف مسودات العلامات المرتبطة
                    باللجان الحالية. العلامات النهائية غير موجودة، لذا يمكنك المتابعة فقط بعد تأكيد صريح.
                  </p>
                </div>
              </div>
            </div>

            <div style={{ padding: '18px 26px' }}>
              <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
                gap: 10, marginBottom: 16,
              }}>
                <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 12, padding: 13 }}>
                  <div style={{ color: '#64748b', fontSize: 12 }}>اللجان المتأثرة</div>
                  <div style={{ color: '#0f172a', fontSize: 21, fontWeight: 800, marginTop: 3 }}>
                    {draftLossWarning.committees_count || 0}
                  </div>
                </div>
                <div style={{ background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 12, padding: 13 }}>
                  <div style={{ color: '#9a3412', fontSize: 12 }}>مسودات العلامات</div>
                  <div style={{ color: '#c2410c', fontSize: 21, fontWeight: 800, marginTop: 3 }}>
                    {draftLossWarning.draft_count || 0}
                  </div>
                </div>
              </div>

              <div style={{
                background: '#fff1f2', border: '1px solid #fecdd3', borderRadius: 12,
                padding: 13, color: '#9f1239', fontSize: 13, lineHeight: 1.7, marginBottom: 20,
              }}>
                لن يمكن استرجاع المسودات بعد تنفيذ التوزيع. سيتم تسجيل العملية باسم حساب العميد في سجل التدقيق.
              </div>

              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={() => setDraftLossWarning(null)}
                  style={{
                    border: '1px solid #cbd5e1', background: '#fff', color: '#475569',
                    borderRadius: 10, padding: '10px 18px', fontWeight: 700, cursor: 'pointer',
                  }}
                >
                  إلغاء وحماية المسودات
                </button>
                <button
                  type="button"
                  onClick={() => executeDistribution(true)}
                  disabled={busy}
                  style={{
                    border: 0, background: '#be123c', color: '#fff', borderRadius: 10,
                    padding: '10px 19px', fontWeight: 800,
                    cursor: busy ? 'not-allowed' : 'pointer', opacity: busy ? 0.65 : 1,
                    display: 'inline-flex', alignItems: 'center', gap: 8,
                  }}
                >
                  {busy ? <RefreshCw size={15} className="animate-spin" /> : <AlertTriangle size={15} />}
                  حذف المسودات وإعادة التوزيع
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
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
