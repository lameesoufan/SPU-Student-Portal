import React, { useState, useEffect, useCallback } from 'react';
import {
  ArrowRight, Calendar, Clock, MapPin, Users, FolderKanban,
  CheckCircle2, AlertTriangle, Gavel, FileText, FileDown,
  Edit3, Save, X, UserCheck, Trash2, Inbox,
} from 'lucide-react';
import {
  fetchCommittee, updateCommittee,
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

  // Inline editing for schedule
  const [editingSchedule, setEditingSchedule] = useState(false);
  const [scheduleDraft, setScheduleDraft] = useState({ date: '', time: '', location: '', status: 'draft' });

  /* ── Load committee ──────────────────────────────────────────────────── */
  const load = useCallback(async () => {
    if (!committeeId) return;
    setLoading(true);
    setError('');
    try {
      const res = await fetchCommittee(committeeId);
      setCommittee(res.data);
      setScheduleDraft({
        date: res.data.date || '',
        time: res.data.time || '',
        location: res.data.location || '',
        status: res.data.status || 'draft',
      });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load committee details.');
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

  /* ── Save schedule ───────────────────────────────────────────────────── */
  const saveSchedule = async () => {
    if (busy || !committee) return;
    setBusy(true);
    try {
      const res = await updateCommittee(committee.id, scheduleDraft);
      setCommittee(res.data);
      setEditingSchedule(false);
      setToast({ type: 'success', msg: 'Schedule saved successfully.' });
    } catch (err) {
      setToast({ type: 'error', msg: err.response?.data?.detail || 'Failed to save schedule.' });
    } finally { setBusy(false); }
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
        <div className="ccd-spinner" /> Loading committee details…
      </div>
    );
  }

  if (error && !committee) {
    return (
      <div className="ccd-page">
        <button className="ccd-back" onClick={onBack}>
          <ArrowRight size={14} /> Back to List
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
    <div className="ccd-page">
      {/* Back */}
      <button className="ccd-back" onClick={onBack}>
        <ArrowRight size={14} /> Back to Committees List
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
                    <Calendar size={11} /> Scheduled
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
            <div className="ccd-stat-label">Faculty</div>
          </div>
        </div>
        <div className="ccd-stat-card">
          <div className="ccd-stat-icon is-blue"><FolderKanban size={20} /></div>
          <div>
            <div className="ccd-stat-value">{projects.length}</div>
            <div className="ccd-stat-label">Projects</div>
          </div>
        </div>
        <div className="ccd-stat-card">
          <div className="ccd-stat-icon is-amber"><Calendar size={20} /></div>
          <div>
            <div className="ccd-stat-value">{committee.date || '—'}</div>
            <div className="ccd-stat-label">Date</div>
          </div>
        </div>
        <div className="ccd-stat-card">
          <div className="ccd-stat-icon is-green"><CheckCircle2 size={20} /></div>
          <div>
            <div className="ccd-stat-value">{getCommitteeStatusLabel(committee.status)}</div>
            <div className="ccd-stat-label">Status</div>
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
                Projects Assigned to Committee
                <span className="ccd-section-count">{projects.length}</span>
              </h2>
            </div>
            <div className="ccd-section-body">
              {projects.length === 0 ? (
                <div className="ccd-empty">
                  <div className="ccd-empty-icon"><Inbox size={24} /></div>
                  <h4>No projects yet</h4>
                  <p>Run the distribution algorithm from the committees dashboard to assign projects to this committee.</p>
                </div>
              ) : (
                projects.map((p, idx) => {
                  const isApp   = p.source === 'IdeaApplication';
                  const tagText = p.source || (isApp ? 'IdeaApplication' : 'StudentIdeaProposal');
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
                          <span className="ccd-project-meta-item">
                            #{p.id}
                          </span>
                        </div>
                      </div>
                      <div className="ccd-project-actions">
                        <button
                          className="ccd-btn ccd-btn-sm ccd-btn-danger"
                          title="Remove from committee"
                          disabled={busy}
                          onClick={async () => {
                            // Simple removal: use swap_project to send back to "no committee"
                            // For now, just show a toast (full swap UI is on the table view)
                            setToast({ type: 'info', msg: 'Use "Swap" button from committees table to move projects.' });
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
                Team
              </h2>
              <button
                className="ccd-btn ccd-btn-sm"
                onClick={() => setToast({ type: 'info', msg: 'To edit committee faculty, edit the original composition then regenerate.' })}
              >
                <Edit3 size={11} /> Edit
              </button>
            </div>
            <div className="ccd-section-body">
              {allDoctors.length === 0 ? (
                <div className="ccd-empty">
                  <div className="ccd-empty-icon"><Users size={22} /></div>
                  <h4>No faculty</h4>
                  <p>Select a chair and members when creating the composition.</p>
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
                        {isChair ? 'Chair' : 'Member'}
                      </span>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Schedule */}
          <div className="ccd-section">
            <div className="ccd-section-header">
              <h2 className="ccd-section-title">
                <span className="ccd-section-icon"><Calendar size={15} /></span>
                Schedule
              </h2>
              {!editingSchedule && (
                <button
                  className="ccd-btn ccd-btn-sm"
                  onClick={() => setEditingSchedule(true)}
                  disabled={busy}
                >
                  <Edit3 size={11} /> Edit
                </button>
              )}
            </div>
            <div className="ccd-section-body">
              {editingSchedule ? (
                <>
                  <div className="ccd-edit-field">
                    <label>Date</label>
                    <input
                      type="date"
                      className="ccd-edit-input"
                      value={scheduleDraft.date}
                      onChange={(e) => setScheduleDraft({ ...scheduleDraft, date: e.target.value })}
                    />
                  </div>
                  <div className="ccd-edit-field">
                    <label>Time</label>
                    <input
                      type="time"
                      className="ccd-edit-input"
                      value={scheduleDraft.time}
                      onChange={(e) => setScheduleDraft({ ...scheduleDraft, time: e.target.value })}
                    />
                  </div>
                  <div className="ccd-edit-field">
                    <label>Room / Location</label>
                    <input
                      type="text"
                      className="ccd-edit-input"
                      value={scheduleDraft.location}
                      placeholder="Example: Room A-201"
                      onChange={(e) => setScheduleDraft({ ...scheduleDraft, location: e.target.value })}
                    />
                  </div>
                  <div className="ccd-edit-field">
                    <label>Status</label>
                    <select
                      className="ccd-status-select"
                      value={scheduleDraft.status}
                      onChange={(e) => setScheduleDraft({ ...scheduleDraft, status: e.target.value })}
                    >
                      {COMMITTEE_STATUSES.map((s) => (
                        <option key={s.value} value={s.value}>{s.label}</option>
                      ))}
                    </select>
                  </div>
                  <div style={{ display: 'flex', gap: 6, marginTop: 6 }}>
                    <button
                      className="ccd-btn ccd-btn-primary ccd-btn-sm"
                      onClick={saveSchedule}
                      disabled={busy}
                    >
                      {busy ? (<><div className="ccd-spinner" style={{ width: 12, height: 12, borderWidth: 2 }} /> Saving…</>) : (<><Save size={11} /> Save</>)}
                    </button>
                    <button
                      className="ccd-btn ccd-btn-sm"
                      onClick={() => {
                        setEditingSchedule(false);
                        setScheduleDraft({
                          date: committee.date || '',
                          time: committee.time || '',
                          location: committee.location || '',
                          status: committee.status || 'draft',
                        });
                      }}
                      disabled={busy}
                    >
                      <X size={11} /> Cancel
                    </button>
                  </div>
                </>
              ) : (
                <div className="ccd-schedule-block">
                  {committee.date ? (
                    <div className="ccd-schedule-row">
                      <Calendar size={14} className="ccd-schedule-row-icon" />
                      <span>Date</span>
                      <span className="ccd-schedule-row-label">{committee.date}</span>
                    </div>
                  ) : (
                    <div className="ccd-schedule-row is-empty">
                      <Calendar size={14} /> No date
                    </div>
                  )}
                  {committee.time && (
                    <div className="ccd-schedule-row">
                      <Clock size={14} className="ccd-schedule-row-icon" />
                      <span>Time</span>
                      <span className="ccd-schedule-row-label">{committee.time}</span>
                    </div>
                  )}
                  {committee.location ? (
                    <div className="ccd-schedule-row">
                      <MapPin size={14} className="ccd-schedule-row-icon" />
                      <span>Room</span>
                      <span className="ccd-schedule-row-label">{committee.location}</span>
                    </div>
                  ) : (
                    <div className="ccd-schedule-row is-empty">
                      <MapPin size={14} /> No room
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Files / Export */}
          <div className="ccd-section">
            <div className="ccd-section-header">
              <h2 className="ccd-section-title">
                <span className="ccd-section-icon"><FileText size={15} /></span>
                Export
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
                  <span className="ccd-file-btn-title">Export PDF</span>
                  <span className="ccd-file-btn-sub">Committees and projects list</span>
                </div>
              </button>
              <button
                className="ccd-file-btn"
                onClick={() => handleExport('xlsx')}
                disabled={busy}
              >
                <div className="ccd-file-btn-icon is-excel"><FileDown size={16} /></div>
                <div className="ccd-file-btn-text">
                  <span className="ccd-file-btn-title">Export Excel</span>
                  <span className="ccd-file-btn-sub">Editable spreadsheet</span>
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
