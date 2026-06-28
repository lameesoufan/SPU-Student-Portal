import React, { useState, useEffect, useCallback } from 'react';
import {
  Users, FileSpreadsheet, AlertTriangle, FolderKanban,
  Plus, FileText, RefreshCw, CheckCircle2, Clock,
  ChevronLeft, Gavel, UserCheck, Inbox, BarChart3,
} from 'lucide-react';
import {
  fetchCommitteesDashboard, distributeProjects,
} from '../../api';
import {
  COMMITTEE_TYPE_COLORS, DEPARTMENT_COLORS, WORKLOAD_COLORS,
  WARNING_COLORS, getCommitteeTypeLabel, getProjectTypeLabel, getDepartmentLabel,
} from './constants';
import './CommitteesDashboard.css';

/* ────────────────────────────────────────────────────────────────────────── */
/* Committees Dashboard — matches mockup 01_dashboard_main.png                  */
/* Layout: hero → stat cards → toolbar → two-column (compositions + warnings)   */
/*         → doctor workload table                                              */
/* ────────────────────────────────────────────────────────────────────────── */

/* ── Helper: safely render a chair value ─────────────────────────────────── */
/* chair can be either:
 *   - null/undefined            → return '—'
 *   - a string (from DashboardView compositions)
 *   - an object {full_name, username, ...} (from CommitteeSerializer)
 */
function renderChairName(chair) {
  if (!chair) return '—';
  if (typeof chair === 'string') return chair;
  if (typeof chair === 'object') {
    return chair.full_name || chair.username || `#${chair.id}` || '—';
  }
  return String(chair);
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

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetchCommitteesDashboard();
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'فشل تحميل لوحة اللجان.');
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
    setShowConfirmDialog(true);
  };

  const confirmDistribute = async () => {
    setShowConfirmDialog(false);
    setBusy(true);
    try {
      const res = await distributeProjects({ dry_run: false });
      const distributed    = res.data?.distributed_projects    ?? 0;
      const undistributed  = res.data?.undistributed_projects  ?? 0;
      const processed      = res.data?.processed_templates     ?? 0;
      const exclusionMsg   = distributionExclusionMessage(res.data?.exclusions);
      const msg = undistributed > 0
        ? `تم توزيع ${distributed} مشروع على ${processed} تركيبة. (${undistributed} مشروع بدون لجنة مناسبة — راجع التنبيهات.)`
        : `تم توزيع ${distributed} مشروع على ${processed} تركيبة بنجاح.`;
      setToast({ type: 'success', msg: [msg, exclusionMsg].filter(Boolean).join(' ') });
      await load();
    } catch (err) {
      setToast({
        type: 'error',
        msg: err.response?.data?.detail || 'فشل التوزيع. حاول لاحقاً.',
      });
    } finally { setBusy(false); }
  };

  if (loading) {
    return (
      <div className="cmd-loading">
        <div className="cmd-spinner" />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="cmd-page">
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
    <div className="cmd-page">
      {/* ── Hero ──────────────────────────────────────────────────────────── */}
      <div className="cmd-hero">
        <div className="cmd-hero-content">
          <div>
            <h1 className="cmd-hero-title">لوحة إدارة اللجان</h1>
            <p className="cmd-hero-sub">
              مرحباً {user?.username || 'د. عميد'} — من هنا يمكنك إنشاء التشكيلات، توزيع المشاريع،
              ومتابعة ضغط العمل على أعضاء هيئة التدريس.
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
        <StatCard icon={<Users size={22} />} value={stats.committees_count ?? 0} label="اللجان المنشأة" variant="is-blue" />
        <StatCard icon={<CheckCircle2 size={22} />} value={stats.projects_distributed ?? 0} label="مشاريع موزعة" variant="is-green" />
        <StatCard icon={<Inbox size={22} />} value={stats.projects_unassigned ?? 0} label="مشاريع بدون لجنة" variant="is-amber" />
        <StatCard icon={<AlertTriangle size={22} />} value={stats.warnings_count ?? 0} label="تنبيهات" variant="is-red" />
      </div>

      {/* ── Toolbar ───────────────────────────────────────────────────────── */}
      <div className="cmd-toolbar">
        <div className="cmd-toolbar-left">
          <button
            className="cmd-btn cmd-btn-success"
            onClick={handleDistribute}
            disabled={busy || comps.length === 0}
            title="تنفيذ خوارزمية التوزيع"
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
                <p>ابدأ بإنشاء أول تشكيلة لتحديد نوع اللجنة والقسم ونوع المشروع والأطباء.</p>
              </div>
            ) : (
              comps.map((c) => {
                const cTypeColor = COMMITTEE_TYPE_COLORS[c.committee_type] || {};
                const deptColor  = DEPARTMENT_COLORS[c.department] || {};
                /* ── FIX: safely render chair (string OR object) ──────── */
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
              })
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
                <h3>كل شيء على ما يرام</h3>
                <p>لا توجد تنبيهات حالياً.</p>
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
                و {warnings.length - 30} تنبيه آخر…
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
            ضغط عمل أعضاء هيئة التدريس
            <span className="cmd-section-count">{workloads.length}</span>
          </h2>
        </div>
        {workloads.length === 0 ? (
          <div className="cmd-empty">
            <div className="cmd-empty-icon"><Users size={28} /></div>
            <h3>لا يوجد أطباء مُعيَّنون بعد</h3>
            <p>عند إنشاء تشكيلات وإسناد أطباء، ستظهر إحصائيات ضغط العمل هنا.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="cmd-workload-table">
              <thead>
                <tr>
                  <th>الطبيب</th>
                  <th>القسم</th>
                  <th>رئاسة</th>
                  <th>عضوية</th>
                  <th>الإجمالي</th>
                  <th>مستوى الضغط</th>
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
                  سيتم تنفيذ خوارزمية توزيع المشاريع على اللجان المُعدّة. هل تريد المتابعة؟
                </p>
              </div>
            </div>

            {/* معلومات إضافية */}
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
                  ✓ سيتم توزيع المشاريع تلقائياً
                </div>
                <div style={{ marginBottom: 6 }}>
                  ✓ سيتم تخصيص مشروع لكل لجنة حسب القسم ونوع المشروع
                </div>
                <div>
                  ✓ يمكنك تعديل التوزيع يدوياً لاحقاً
                </div>
              </div>
            </div>

            {/* الأزرار */}
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
