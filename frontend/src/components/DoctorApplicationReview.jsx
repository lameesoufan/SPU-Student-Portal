import React, { useState, useEffect } from 'react';
import { fetchDoctorPendingApplications, doctorReviewApplication, fetchResponseByApplication } from '../api';
import { ClipboardCheck, User, Users, Calendar, CheckCircle, XCircle, Loader2, Info, ChevronDown } from 'lucide-react';

/* ── Status colour pills for team members ── */
const TEAM_STATUS_STYLES = {
  accepted: 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20',
  rejected: 'bg-red-500/10 text-red-600 border border-red-500/20',
  pending:  'bg-amber-500/10 text-amber-600 border border-amber-500/20',
};

/* ── Helper: render dynamic-form field values (arrays, strings, etc.) ── */
const renderResponseValue = (value, fieldType) => {
  if (fieldType === 'file' && value && typeof value === 'object' && value.url) {
    return (
      <a href={value.url} target="_blank" rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 text-[var(--primary)] hover:underline font-medium">
        📎 {value.name || 'Download file'}
      </a>
    );
  }
  if (Array.isArray(value))
    return value.length ? (
      <div className="flex flex-wrap gap-1.5">
        {value.map((item) => (
          <span key={item} className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-violet-500/10 text-violet-600 dark:text-violet-400 border border-violet-500/20 text-xs font-semibold">
            {item}
          </span>
        ))}
      </div>
    ) : null;
  return value || null;
};

export default function DoctorApplicationReview({ onBack }) {
  const [apps, setApps]           = useState([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [reviewing, setReviewing] = useState(null);
  const [reason, setReason]       = useState('');
  const [actionError, setActionError] = useState('');
  const [confirming, setConfirming]   = useState(false);
  /* ── NEW: form responses state ── */
  const [formResponses, setFormResponses] = useState({});
  const [expandedForm, setExpandedForm]   = useState(null);

  useEffect(() => {
    let active = true;
    fetchDoctorPendingApplications()
      .then(async (res) => {
        if (!active) return;
        setApps(res.data);
        /* ── NEW: fetch dynamic-form responses for each application ── */
        const responses = await Promise.allSettled(
          res.data.map((app) =>
            fetchResponseByApplication(app.id).then((r) => [app.id, r.data])
          )
        );
        if (!active) return;
        const next = {};
        responses.forEach((result) => {
          if (result.status === 'fulfilled') next[result.value[0]] = result.value[1];
        });
        setFormResponses(next);
      })
      .catch(() => { if (active) setError('Failed to load applications.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const openReview = (id, action) => { setReviewing({ id, action }); setReason(''); setActionError(''); };

  const handleConfirm = async () => {
    if (!reviewing || confirming) return;
    setActionError('');
    setConfirming(true);
    try {
      await doctorReviewApplication(reviewing.id, { action: reviewing.action, rejection_reason: reason });
      setApps((prev) => prev.filter((a) => a.id !== reviewing.id));
      setReviewing(null);
    } catch (err) {
      const data = err.response?.data;
      setActionError(data?.rejection_reason?.[0] || data?.error || 'Something went wrong.');
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 max-w-[1080px] mx-auto px-6 py-8">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center text-amber-500">
          <ClipboardCheck size={20} />
        </div>
        <div>
          <h1 className="text-xl font-extrabold text-[var(--text)] leading-tight">Student Applications</h1>
          <p className="text-sm text-[var(--text-muted)]">Pending your approval</p>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-sm">
          <Info size={16} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading && (
        <div className="flex flex-col items-center justify-center py-16">
          <div className="spinner-dark w-8 h-8"></div>
        </div>
      )}

      {!loading && apps.length === 0 && !error && (
        <div className="flex flex-col items-center justify-center py-20">
          <div className="w-16 h-16 flex items-center justify-center rounded-full bg-emerald-500/10 text-emerald-500 mb-4">
            <CheckCircle size={28} />
          </div>
          <h3 className="text-lg font-bold text-[var(--text)]">No pending applications</h3>
          <p className="text-sm text-[var(--text-muted)] mt-1">All caught up!</p>
        </div>
      )}

      <div className="flex flex-col gap-3">
        {apps.map((app) => {
          const resp = formResponses[app.id];
          const isExpanded = expandedForm === app.id;

          return (
            <div key={app.id} className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] shadow-[var(--shadow)] overflow-hidden">
              {/* ── Card Header ── */}
              <div className="p-5">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="flex flex-col gap-2">
                    <h3 className="text-base font-bold text-[var(--text)] leading-snug">{app.idea_title}</h3>
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-[var(--primary)]/10 flex items-center justify-center text-[var(--primary)]">
                        <User size={12} />
                      </div>
                      <span className="text-sm font-medium text-[var(--text-secondary)]">{app.student_name}</span>
                    </div>
                  </div>

                  {/* ── NEW: team_size badge + date ── */}
                  <div className="flex gap-1.5 flex-wrap">
                    {app.team_size && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-violet-500/10 text-violet-600 tracking-wide">
                        <Users size={11} />
                        {app.team_size} student{app.team_size > 1 ? 's' : ''}
                      </span>
                    )}
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-[var(--bg-tertiary)] text-[var(--text-muted)] border border-[var(--border-light)]">
                      <Calendar size={12} />
                      {new Date(app.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </div>

              {/* ── NEW: Card Body — Team Members + Form Responses ── */}
              <div className="px-5 pb-4 flex flex-col gap-3.5">
                {/* Team Members */}
                {app.invitations && app.invitations.length > 0 && (
                  <div className="flex items-center flex-wrap gap-1.5">
                    <span className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wide flex items-center gap-1 mr-1">
                      <Users size={12} />
                      Team:
                    </span>
                    {app.invitations.map((inv) => (
                      <span
                        key={inv.id}
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${TEAM_STATUS_STYLES[inv.status] || 'bg-[var(--bg-tertiary)] text-[var(--text-muted)] border border-[var(--border-light)]'}`}
                      >
                        {inv.invitee_name}
                      </span>
                    ))}
                  </div>
                )}

                {/* Dynamic Form Responses (collapsible) */}
                {resp && resp.field_responses && resp.field_responses.length > 0 && (
                  <div className="border border-[var(--border-light)] rounded-[var(--radius-sm)] overflow-hidden">
                    <button
                      className="w-full flex items-center justify-between px-4 py-3 bg-[var(--bg-tertiary)] border-none cursor-pointer text-[13px] font-semibold text-[var(--text-muted)] text-left transition-colors hover:bg-[var(--bg-tertiary)]/80 hover:text-[var(--text)]"
                      onClick={() => setExpandedForm(isExpanded ? null : app.id)}
                      aria-expanded={isExpanded}
                    >
                      Department Form Responses
                      <ChevronDown size={14} className={`text-[var(--text-muted)] transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} />
                    </button>
                    {isExpanded && (
                      <div className="border-t border-[var(--border-light)]">
                        {resp.field_responses.map((fr, idx) => (
                          <div key={idx} className={`flex gap-3 px-4 py-2.5 text-[13px] transition-colors hover:bg-[var(--bg-tertiary)]/50 ${idx % 2 === 0 ? 'bg-transparent' : 'bg-[var(--bg-tertiary)]/30'}`}>
                            <span className="font-semibold text-[var(--text-muted)] min-w-[160px] flex-shrink-0 pt-px">{fr.field_label}</span>
                            <span className="text-[var(--text)] break-words leading-relaxed">
                              {renderResponseValue(fr.value , fr.field_type) || <em className="text-[var(--text-muted)] italic">—</em>}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* ── Card Footer ── */}
              <div className="flex gap-3 px-5 py-4 border-t border-[var(--border-light)] bg-[var(--bg-tertiary)]">
                <button className="inline-flex items-center gap-2 px-4 py-2 rounded-[var(--radius-sm)] bg-emerald-500 text-white font-semibold text-sm hover:bg-emerald-600 transition-colors" onClick={() => openReview(app.id, 'approve')}>
                  <CheckCircle size={16} /> Approve
                </button>
                <button className="inline-flex items-center gap-2 px-4 py-2 rounded-[var(--radius-sm)] bg-transparent border-2 border-red-400 text-red-500 font-semibold text-sm hover:bg-red-500/10 transition-colors" onClick={() => openReview(app.id, 'reject')}>
                  <XCircle size={16} /> Reject
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {reviewing && (
        <div className="fixed inset-0 bg-[var(--overlay)] flex items-center justify-center z-[1000] p-4" role="dialog" aria-modal="true">
          <div className="bg-[var(--card)] rounded-[var(--radius-lg)] shadow-[var(--shadow-lg)] p-4 md:p-8 w-full max-w-[480px] border border-[var(--border)]">
            <div className="flex items-center gap-3 mb-4">
              {reviewing.action === 'approve' ? (
                <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center text-emerald-500">
                  <CheckCircle size={20} />
                </div>
              ) : (
                <div className="w-10 h-10 rounded-xl bg-red-500/10 flex items-center justify-center text-red-500">
                  <XCircle size={20} />
                </div>
              )}
              <h3 className="text-lg font-extrabold text-[var(--text)]">
                {reviewing.action === 'approve' ? 'Approve Application' : 'Reject Application'}
              </h3>
            </div>

            {reviewing.action === 'approve' && (
              <div className="flex items-start gap-2 p-3 rounded-[var(--radius-sm)] bg-blue-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 text-sm mb-4">
                <Info size={16} className="shrink-0 mt-0.5" />
                <span>This will forward the application to the HoD for final approval.</span>
              </div>
            )}

            {reviewing.action === 'reject' && (
              <div className="mb-4">
                <label htmlFor="dr-reason" className="block text-sm font-semibold text-[var(--text)] mb-1.5">
                  Rejection Reason <span className="text-[var(--danger)]">*</span>
                </label>
                <textarea id="dr-reason" className="w-full bg-[var(--input-bg)] text-[var(--text)] border border-[var(--border)] rounded-[var(--radius-sm)] px-4 py-2.5 text-sm outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] transition-colors resize-none" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Explain why…" />
              </div>
            )}

            {actionError && (
              <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-sm mb-4">
                <Info size={16} className="shrink-0" />
                <span>{actionError}</span>
              </div>
            )}

            <div className="flex gap-3 justify-end">
              <button className={`inline-flex items-center gap-2 px-5 py-2.5 rounded-[var(--radius-sm)] font-semibold text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${reviewing.action === 'approve' ? 'bg-emerald-500 text-white hover:bg-emerald-600' : 'bg-red-500 text-white hover:bg-red-600'}`} onClick={handleConfirm} disabled={confirming}>
                {confirming ? <><Loader2 size={16} className="animate-spin" /> Processing…</> : 'Confirm'}
              </button>
              <button className="inline-flex items-center justify-center gap-2 bg-transparent border border-[var(--border)] text-[var(--text)] font-medium py-2.5 px-5 rounded-[var(--radius-sm)] hover:bg-[var(--bg-tertiary)] transition-colors text-sm disabled:opacity-50 disabled:cursor-not-allowed" onClick={() => setReviewing(null)} disabled={confirming}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
