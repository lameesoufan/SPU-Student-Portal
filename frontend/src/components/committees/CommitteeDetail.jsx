import React, { useState, useEffect, useCallback } from 'react';
import {
  ArrowRight, Calendar, Clock, MapPin, Users, FolderKanban,
  CheckCircle2, AlertTriangle, Gavel, FileText, FileDown,
  Edit3, X, UserCheck, Trash2, Inbox,
} from 'lucide-react';
import {
  fetchCommittee,
} from '../../api';
import {
  COMMITTEE_STATUSES, COMMITTEE_TYPE_COLORS, DEPARTMENT_COLORS, STATUS_COLORS,
  getCommitteeTypeLabel, getProjectTypeLabel, getDepartmentLabel,
  getCommitteeStatusLabel,
} from './constants';
import './CommitteeDetail.css';

/* ────────────────────────────────────────────────────────────────────────── */
/* CommitteeDetail — matches mockup 04_committee_detail.png                    */
/* Layout: back btn → purple banner with badges → stat cards row →             */
/*         two-column: main (projects list) + sidebar (team, schedule, files)  */
/* ────────────────────────────────────────────────────────────────────────── */

export default function CommitteeDetail({ onBack, committeeId, onNavigate }) {
  const [committee, setCommittee]       = useState(null);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState('');
  const [busy, setBusy]                 = useState(false);
  const [toast, setToast]               = useState(null);

  // Scheduling is now read-only on this page — it is done only on the
  // dedicated Committee Scheduling page (CP-SAT solver).

  /* ── Load committee ──────────────────────────────────────────────────── */
  const load = useCallback(async () => {
    if (!committeeId) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetchCommittee(committeeId);
      setCommittee(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'تعذر تحميل تفاصيل اللجنة.');
    } finally {
      setLoading(false);
    }
  }, [committeeId]);

  useEffect(() => { load(); }, [load]);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  /* ── Helpers ─────────────────────────────────────────────────────────── */
  const getProjects = () => {
    if (!committee?.projects) return [];
    return committee.projects;
  };

  /* ── Export ──────────────────────────────────────────────────────────── */
  const handleExport = async (format) => {
    // Placeholder for export functionality
    setToast({ type: 'info', msg: `Export as ${format.toUpperCase()} coming soon` });
  };

  /* ── Render ──────────────────────────────────────────────────────────── */
  if (loading) {
    return (
      <div className="ccd-loading">
        <div className="ccd-spinner" /> جارٍ تحميل تفاصيل اللجنة…
      </div>
    );
  }

  if (error && !committee) {
    return (
      <div className="ccd-page" dir="rtl">
        <button className="ccd-back" onClick={onBack}>
          <ArrowRight size={14} /> العودة إلى القائمة
        </button>
        <div className="ccd-error">
          <AlertTriangle size={16} /> {error}
        </div>
      </div>
    );
  }

  if (!committee) return null;

  const cTypeColor   = COMMITTEE_TYPE_COLORS[committee.committee_type] || {};
  const deptColor    = DEPARTMENT_COLORS[committee.department] || {};
  const statusColor  = STATUS_COLORS[committee.status] || {};
  const chair        = committee.chair;
  const members      = committee.members || [];
  const allDoctors   = committee.doctors || [];
  const projects     = getProjects();
  const seqLabel     = `#${String(committee.sequence_number || '').padStart(3, '0')}`;

  return (
    <div className="ccd-page" dir="rtl">
      {/* Back */}
      <button className="ccd-back" onClick={onBack}>
        <ArrowRight size={14} /> العودة إلى قائمة اللجان
      </button>

      {/* Banner */}
      <div className="ccd-banner">
        <div className="ccd-banner-content">
          <div className="ccd-banner-left">
            <div className="ccd-banner-icon">
              <Gavel size={26} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <h1 className="ccd-banner-title">
                {committee.committee_type_ar} — {committee.department_ar}
              </h1>
              <p className="ccd-banner-sub">
                Committee {seqLabel} · {committee.project_type_ar} · {committee.semester || '—'}
              </p>
              <div className="ccd-banner-badges">
                <span className="ccd-banner-badge">
                  <span className="ccd-badge-dot" style={{
                    display: 'inline-block',
                    width: 7,
                    height: 7,
                    borderRadius: '50%',
                    background: statusColor.text || '#fff',
                  }} />
                  {getCommitteeStatusLabel(committee.status)}
                </span>
                <span className="ccd-banner-badge">
                  <Users size={11} /> {allDoctors.length} faculty
                </span>
                <span className="ccd-banner-badge">
                  <FolderKanban size={11} /> {projects.length} projects
                </span>
                {committee.is_scheduled && (
                  <span className="ccd-banner-badge">
                    <Calendar size={11} /> مجدولة
                  </span>
                )}
              </div>
            </div>
          </div>
          {/* Edit Schedule button removed - functionality not available */}
        </div>
      </div>

      {/* Stat cards */}
      <div className="ccd-stats">
        <div className="ccd-stat-card">
          <div className="ccd-stat-icon is-purple"><Users size={20} /></div>
          <div>
            <div className="ccd-stat-value">{allDoctors.length}</div>
            <div className="ccd-stat-label">الهيئة التدريسية</div>
          </div>
        </div>
        <div className="ccd-stat-card">
          <div className="ccd-stat-icon is-blue"><FolderKanban size={20} /></div>
          <div>
            <div className="ccd-stat-value">{projects.length}</div>
            <div className="ccd-stat-label">المشاريع</div>
          </div>
        </div>
        <div className="ccd-stat-card">
          <div className="ccd-stat-icon is-amber"><Calendar size={20} /></div>
          <div>
            <div className="ccd-stat-value">{committee.date || '—'}</div>
            <div className="ccd-stat-label">التاريخ</div>
          </div>
        </div>
        <div className="ccd-stat-card">
          <div className="ccd-stat-icon is-green"><CheckCircle2 size={20} /></div>
          <div>
            <div className="ccd-stat-value">{getCommitteeStatusLabel(committee.status)}</div>
            <div className="ccd-stat-label">الحالة</div>
          </div>
        </div>
      </div>

      {/* Two columns */}
      <div className="ccd-two-col">

        {/* Main column: projects list */}
        <div>
          <div className="ccd-section">
            <div className="ccd-section-header">
              <h2 className="ccd-section-title">
                <span className="ccd-section-icon"><FolderKanban size={15} /></span>
                المشاريع المسندة إلى اللجنة
                <span className="ccd-section-count">{projects.length}</span>
              </h2>
            </div>
            <div className="ccd-section-body">
              {projects.length === 0 ? (
                <div className="ccd-empty">
                  <div className="ccd-empty-icon"><Inbox size={24} /></div>
                  <h4>لا توجد مشاريع بعد</h4>
                  <p>شغّل خوارزمية التوزيع من لوحة اللجان لإسناد المشاريع إلى هذه اللجنة.</p>
                </div>
              ) : (
                projects.map((p, idx) => {
                  const isApp   = p.source === 'طلب فكرة';
                  const tagText = p.source || (isApp ? 'طلب فكرة' : 'مقترح فكرة طالب');
                  const tagClass = isApp ? 'is-application' : 'is-proposal';
                  return (
                    <div key={`${p.source}-${p.id}-${idx}`} className="ccd-project-card">
                      <div className="ccd-project-icon">
                        <FileText size={18} />
                      </div>
                      <div className="ccd-project-main">
                        <h3 className="ccd-project-title">{p.title || `Project #${p.id}`}</h3>
                        <div className="ccd-project-meta">
                          <span className={`ccd-project-tag ${tagClass}`}>{tagText}</span>
                          <span className="ccd-project-meta-item">
                            <UserCheck size={11} /> {p.supervisor || '—'}
                          </span>
                          {p.students && p.students.length > 0 && (
                            <span className="ccd-project-meta-item">
                              <Users size={11} /> {p.students.join('، ')}
                            </span>
                          )}
                          {p.scheduled_start && p.scheduled_end && (
                            <span className="ccd-project-meta-item" style={{ color: '#667EEA', fontWeight: 500 }}>
                              <Clock size={11} /> {p.scheduled_start} - {p.scheduled_end}
                            </span>
                          )}
                          <span className="ccd-project-meta-item">
                            #{p.id}
                          </span>
                        </div>
                      </div>
                      <div className="ccd-project-actions">
                        <button
                          className="ccd-btn ccd-btn-sm ccd-btn-danger"
                          title="إزالة من اللجنة"
                          disabled={busy}
                          onClick={async () => {
                            // Simple removal: use swap_project to send back to "no committee"
                            // For now, just show a toast (full swap UI is on the table view)
                            setToast({ type: 'info', msg: 'استخدم زر «تبديل» من جدول اللجان لنقل المشاريع.' });
                          }}
                        >
                          <X size={11} />
                        </button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Sidebar column: team + schedule + files */}
        <div>
          {/* Team */}
          <div className="ccd-section">
            <div className="ccd-section-header">
              <h2 className="ccd-section-title">
                <span className="ccd-section-icon"><Users size={15} /></span>
                الفريق
              </h2>
              <button
                className="ccd-btn ccd-btn-sm"
                onClick={() => setToast({ type: 'info', msg: 'لتعديل أعضاء اللجنة، عدّل التشكيلة الأصلية ثم أعد توليدها.' })}
              >
                <Edit3 size={11} /> تعديل
              </button>
            </div>
            <div className="ccd-section-body">
              {allDoctors.length === 0 ? (
                <div className="ccd-empty">
                  <div className="ccd-empty-icon"><Users size={22} /></div>
                  <h4>لا يوجد أعضاء هيئة تدريس</h4>
                  <p>اختر رئيسًا وأعضاء عند إنشاء التشكيلة.</p>
                </div>
              ) : (
                allDoctors.map((d) => {
                  const name    = d.full_name || d.username || `#${d.id}`;
                  const initial = (name || '?').charAt(0).toUpperCase();
                  const isChair = d.role === 'chair';
                  return (
                    <div
                      key={d.id}
                      className={`ccd-doctor-row ${isChair ? 'is-chair' : ''}`}
                    >
                      <div className="ccd-doctor-avatar">{initial}</div>
                      <div className="ccd-doctor-info">
                        <div className="ccd-doctor-name">{name}</div>
                        <div className="ccd-doctor-dept">{d.department_ar || d.department || '—'}</div>
                      </div>
                      <span className={`ccd-doctor-role ${isChair ? 'is-chair' : 'is-member'}`}>
                        {isChair ? 'الرئيس' : 'عضو'}
                      </span>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Schedule Info (read-only) — scheduling is now done only on the
              Committee Scheduling page using CP-SAT solver */}
          <div className="ccd-section">
            <div className="ccd-section-header">
              <h2 className="ccd-section-title">
                <span className="ccd-section-icon"><Calendar size={15} /></span>
                مواعيد الجلسة
              </h2>
            </div>
            <div className="ccd-section-body">
              {committee.scheduled_start ? (
                <div className="ccd-schedule-block">
                  <div className="ccd-schedule-row" style={{ color: '#0369a1', fontWeight: 600 }}>
                    <Calendar size={14} className="ccd-schedule-row-icon" />
                    <span>التاريخ</span>
                    <span className="ccd-schedule-row-label">
                      {new Date(committee.scheduled_start).toLocaleDateString('ar-IQ', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' })}
                    </span>
                  </div>
                  <div className="ccd-schedule-row" style={{ color: '#0369a1', fontWeight: 600 }}>
                    <Clock size={14} className="ccd-schedule-row-icon" />
                    <span>الوقت</span>
                    <span className="ccd-schedule-row-label">
                      {new Date(committee.scheduled_start).toLocaleTimeString('ar-IQ', { hour: '2-digit', minute: '2-digit' })} - {new Date(committee.scheduled_end).toLocaleTimeString('ar-IQ', { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  {committee.room_detail && (
                    <div className="ccd-schedule-row">
                      <MapPin size={14} className="ccd-schedule-row-icon" />
                      <span>القاعة</span>
                      <span className="ccd-schedule-row-label">{committee.room_detail.name}</span>
                    </div>
                  )}
                  {committee.discussion_duration && (
                    <div className="ccd-schedule-row">
                      <Clock size={14} className="ccd-schedule-row-icon" />
                      <span>مدة المناقشة</span>
                      <span className="ccd-schedule-row-label">{committee.discussion_duration} دقيقة لكل مشروع</span>
                    </div>
                  )}
                </div>
              ) : (
                <div className="ccd-schedule-row is-empty" style={{ flexDirection: 'column', alignItems: 'flex-start', gap: 6 }}>
                  <div><Calendar size={14} style={{ marginLeft: 6 }} /> لم تُجدوَل بعد</div>
                  <div style={{ fontSize: '0.82em', color: '#888' }}>⚠️ الجدولة تتم فقط من صفحة «جدولة اللجان» باستخدام CP-SAT Solver</div>
                </div>
              )}
            </div>
          </div>

          {/* Files / Export */}
          <div className="ccd-section">
            <div className="ccd-section-header">
              <h2 className="ccd-section-title">
                <span className="ccd-section-icon"><FileText size={15} /></span>
                تصدير
              </h2>
            </div>
            <div className="ccd-section-body">
              <button
                className="ccd-file-btn"
                onClick={() => handleExport('pdf')}
                disabled={busy}
              >
                <div className="ccd-file-btn-icon is-pdf"><FileText size={16} /></div>
                <div className="ccd-file-btn-text">
                  <span className="ccd-file-btn-title">تصدير PDF</span>
                  <span className="ccd-file-btn-sub">قائمة اللجان والمشاريع</span>
                </div>
              </button>
              <button
                className="ccd-file-btn"
                onClick={() => handleExport('xlsx')}
                disabled={busy}
              >
                <div className="ccd-file-btn-icon is-excel"><FileDown size={16} /></div>
                <div className="ccd-file-btn-text">
                  <span className="ccd-file-btn-title">تصدير Excel</span>
                  <span className="ccd-file-btn-sub">جدول بيانات قابل للتعديل</span>
                </div>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div
          className={`ccd-toast ${toast.type === 'success' ? 'is-success' : (toast.type === 'error' ? 'is-error' : '')}`}
          style={toast.type === 'info' ? { background: 'rgba(59, 130, 246, 0.95)' } : {}}
        >
          {toast.type === 'success'
            ? <CheckCircle2 size={18} />
            : (toast.type === 'error' ? <AlertTriangle size={18} /> : <FileText size={18} />)}
          {toast.msg}
        </div>
      )}
    </div>
  );
}
