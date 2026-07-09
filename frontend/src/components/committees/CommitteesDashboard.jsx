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
  const [showModeDialog, setShowModeDialog] = useState(false);
  const [selectedMode, setSelectedMode] = useState('multi');  // 'single' | 'multi'

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetchCommitteesDashboard();
      setData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load committees dashboard.');
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

  const confirmDistribute = async () => {
    setShowConfirmDialog(false);
    setBusy(true);
    try {
      const res = await distributeProjects({ dry_run: false, scheduling_mode: selectedMode });
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
      await load();
    } catch (err) {
      setToast({
        type: 'error',
        msg: err.response?.data?.detail || 'Distribution failed. Try again later.',
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
          <RefreshCw size={14} /> Retry
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
            <h1 className="cmd-hero-title">Committees Management Dashboard</h1>
            <p className="cmd-hero-sub">
              Welcome {user?.username || 'Dean'} — From here you can create compositions, distribute projects,
              and monitor faculty workload.
            </p>
          </div>
          <div className="cmd-hero-actions">
            <button
              className="cmd-hero-btn cmd-hero-btn-primary"
              onClick={() => onNavigate && onNavigate('committees-template-form')}
            >
              <Plus size={16} /> New Composition
            </button>
            <button
              className="cmd-hero-btn cmd-hero-btn-secondary"
              onClick={() => onNavigate && onNavigate('committees-list')}
            >
              <FolderKanban size={16} /> Committees List
            </button>
            <button
              className="cmd-hero-btn cmd-hero-btn-secondary"
              onClick={() => onNavigate && onNavigate('projects-assignment')}
            >
              <FileText size={16} /> Distribution Table
            </button>
          </div>
        </div>
      </div>

      {/* ── Stat Cards ────────────────────────────────────────────────────── */}
      <div className="cmd-stats">
        <StatCard icon={<FileSpreadsheet size={22} />} value={stats.templates_count ?? 0} label="Compositions" variant="is-purple" />
        <StatCard icon={<Users size={22} />} value={stats.committees_count ?? 0} label="Committees" variant="is-blue" />
        <StatCard icon={<CheckCircle2 size={22} />} value={stats.projects_distributed ?? 0} label="Distributed Projects" variant="is-green" />
        <StatCard icon={<Inbox size={22} />} value={stats.projects_unassigned ?? 0} label="Unassigned Projects" variant="is-amber" />
        <StatCard icon={<AlertTriangle size={22} />} value={stats.warnings_count ?? 0} label="Warnings" variant="is-red" />
      </div>

      {/* ── Toolbar ───────────────────────────────────────────────────────── */}
      <div className="cmd-toolbar">
        <div className="cmd-toolbar-left">
          <button
            className="cmd-btn cmd-btn-success"
            onClick={handleDistribute}
            disabled={busy || comps.length === 0}
            title="Execute distribution algorithm"
          >
            {busy ? <RefreshCw size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            Distribute Projects
          </button>
        </div>
        <div className="cmd-toolbar-right">
          <button className="cmd-btn cmd-btn-sm" onClick={load} disabled={loading}>
            <RefreshCw size={13} /> Refresh
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
              Compositions
              <span className="cmd-section-count">{comps.length}</span>
            </h2>
            <button
              className="cmd-btn cmd-btn-sm cmd-btn-primary"
              onClick={() => onNavigate && onNavigate('committees-template-form')}
            >
              <Plus size={13} /> Add
            </button>
          </div>
          <div className="cmd-section-body">
            {comps.length === 0 ? (
              <div className="cmd-empty">
                <div className="cmd-empty-icon"><FolderKanban size={28} /></div>
                <h3>No compositions yet</h3>
                <p>Start by creating your first composition to define committee type, department, project type, and faculty members.</p>
              </div>
            ) : (
              comps.map((c) => {
                const cTypeColor = COMMITTEE_TYPE_COLORS[c.committee_type] || {};
                const deptColor  = DEPARTMENT_COLORS[c.department] || {};
                /* ── render chair (unified object shape) ──────────────── */
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
                            <CheckCircle2 size={11} /> Approved
                          </span>
                        ) : (
                          <span className="cmd-badge" style={{
                            background: 'rgba(245, 158, 11, 0.12)',
                            color: '#fbbf24',
                            borderColor: 'rgba(245, 158, 11, 0.25)',
                          }}>
                            <Clock size={11} /> Draft
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
                          <UserCheck size={13} /> Chair: <strong>{chairName}</strong>
                        </span>
                        <span className="cmd-comp-meta-item">
                          <Users size={13} /> Members: <strong>{c.members_count ?? 0}</strong>
                        </span>
                        <span className="cmd-comp-meta-item">
                          <FolderKanban size={13} /> Committees: <strong>{c.committees_count ?? c.committees_total ?? 0}</strong>
                        </span>
                        <span className="cmd-comp-meta-item">
                          <CheckCircle2 size={13} /> Projects: <strong>{c.total_projects_assigned ?? 0}</strong>
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
                        View Committees <ChevronLeft size={12} />
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
              Warnings
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
                <h3>Everything looks good</h3>
                <p>No warnings at this time.</p>
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
            Faculty Workload
            <span className="cmd-section-count">{workloads.length}</span>
          </h2>
        </div>
        {workloads.length === 0 ? (
          <div className="cmd-empty">
            <div className="cmd-empty-icon"><Users size={28} /></div>
            <h3>No faculty assigned yet</h3>
            <p>When you create compositions and assign faculty members, their workload stats will appear here.</p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="cmd-workload-table">
              <thead>
                <tr>
                  <th>Faculty Member</th>
                  <th>Department</th>
                  <th>Chair</th>
                  <th>Member</th>
                  <th>Total</th>
                  <th>Workload Level</th>
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
                  Confirm Project Distribution
                </h3>
                <p style={{
                  margin: 0,
                  fontSize: 14,
                  color: '#64748b',
                  lineHeight: 1.6,
                }}>
                  The project distribution algorithm will be executed on the prepared committees. Do you want to proceed?
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
                  ✓ Projects will be distributed automatically
                </div>
                <div style={{ marginBottom: 6 }}>
                  ✓ Each committee will be assigned projects based on department and project type
                </div>
                <div>
                  ✓ You can manually adjust the distribution later
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
                Cancel
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
                Execute Distribution
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
