import React, { useState, useEffect } from 'react';
import { fetchSupervisorPending, supervisorReview, fetchResponseByProposal } from '../api';
import { getProjectTypeLabel } from '../lib/constants';


const renderResponseValue = (value) => {
  if (Array.isArray(value)) return value.length ? <div className="sv-choice-pills">{value.map((item) => <span key={item}>{item}</span>)}</div> : null;
  return value || null;
};

export default function SupervisorReview({ onBack }) {
  const [proposals, setProposals]     = useState([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState('');
  const [reviewing, setReviewing]     = useState(null); // { id, action }
  const [reason, setReason]           = useState('');
  const [actionError, setActionError] = useState('');
  const [confirming, setConfirming]   = useState(false);
  // form responses keyed by proposal id
  const [formResponses, setFormResponses] = useState({});
  const [expandedForm, setExpandedForm]   = useState(null); // proposal id

  useEffect(() => {
    let active = true;
    fetchSupervisorPending()
      .then(async (res) => {
        if (!active) return;
        setProposals(res.data);
        const responses = await Promise.allSettled(
          res.data.map((p) => fetchResponseByProposal(p.id).then((r) => [p.id, r.data]))
        );
        if (!active) return;
        const next = {};
        responses.forEach((result) => {
          if (result.status === 'fulfilled') next[result.value[0]] = result.value[1];
        });
        setFormResponses(next);
      })
      .catch(() => { if (active) setError('Failed to load proposals.'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const openReview = (id, action) => {
    setReviewing({ id, action });
    setReason('');
    setActionError('');
  };

  const handleConfirm = async () => {
    if (!reviewing || confirming) return;
    setActionError('');
    setConfirming(true);
    try {
      await supervisorReview(reviewing.id, {
        action: reviewing.action,
        rejection_reason: reason,
      });
      setProposals((prev) => prev.filter((p) => p.id !== reviewing.id));
      setReviewing(null);
    } catch (err) {
      const data = err.response?.data;
      if (data?.rejection_reason) setActionError(data.rejection_reason[0]);
      else if (data?.error) setActionError(data.error);
      else setActionError('Something went wrong.');
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div className="sv-wrap">
      <div className="page-header">
        <button className="back-btn" onClick={onBack}>← Back</button>
        <h2>Student Proposals — Pending Your Review</h2>
      </div>

      {error && <div className="alert">{error}</div>}
      {loading && <div className="spinner spinner-dark"></div>}

      {!loading && proposals.length === 0 && !error && (
        <div className="empty-state">
          <span aria-hidden="true">✅</span>
          <p>No pending proposals at the moment.</p>
        </div>
      )}

      <div className="sv-list">
        {proposals.map((p) => {
          const resp = formResponses[p.id];
          const isExpanded = expandedForm === p.id;

          return (
            <div key={p.id} className="card">
              <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div className="sv-card-top">
                  <div>
                    <h3 className="sv-card-title">{p.title}</h3>
                    <span className="sv-card-student">👤 {p.student_name}</span>
                  </div>
                  <div>
                    <span className="badge badge-neutral">🏛 {p.department.replace(/_/g, ' ')}</span>
                    {p.project_type && (
                      <span className="badge badge-primary" style={{ marginLeft: '8px' }}>
                        {getProjectTypeLabel(p.project_type)}
                      </span>
                    )}
                  </div>
                </div>
                <p className="sv-card-desc">{p.description}</p>

                {/* Team info */}
                {p.invitations && p.invitations.length > 0 && (
                  <div className="sv-team-row">
                    <span className="sv-team-label">Team:</span>
                    {p.invitations.map((inv) => (
                      <span key={inv.id} className={`sv-team-member sv-team-member--${inv.status}`}>
                        {inv.invitee_name}
                      </span>
                    ))}
                  </div>
                )}

                {/* Dynamic form response */}
                {resp && resp.field_responses && resp.field_responses.length > 0 && (
                  <div className="sv-form-section">
                    <button
                      className="sv-form-toggle"
                      onClick={() => setExpandedForm(isExpanded ? null : p.id)}
                      aria-expanded={isExpanded}
                    >
                      📋 Department Form Responses
                      <span className="sv-form-toggle-arrow">{isExpanded ? '▲' : '▼'}</span>
                    </button>

                    {isExpanded && (
                      <div className="sv-form-responses">
                        {resp.field_responses.map((fr, idx) => (
                          <div key={idx} className="sv-form-field">
                            <span className="sv-form-field-label">{fr.field_label}</span>
                            <span className="sv-form-field-value">
                              {renderResponseValue(fr.value) || <em className="sv-form-empty">—</em>}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="card-footer" style={{ display: 'flex', gap: 12 }}>
                <button className="btn btn-primary btn-sm" onClick={() => openReview(p.id, 'approve')}>
                  ✅ Approve
                </button>
                <button className="btn btn-danger btn-sm" onClick={() => openReview(p.id, 'reject')}>
                  ❌ Reject
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Confirm modal */}
      {reviewing && (
        <div className="sv-modal-overlay" role="dialog" aria-modal="true">
          <div className="sv-modal">
            <h3>{reviewing.action === 'approve' ? '✅ Approve Proposal' : '❌ Reject Proposal'}</h3>

            {reviewing.action === 'reject' && (
              <div className="form-group" style={{ marginTop: 16 }}>
                <label htmlFor="sv-reason">Rejection Reason <span aria-hidden="true">*</span></label>
                <textarea
                  id="sv-reason"
                  className="form-control"
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Explain why this proposal is being rejected…"
                />
              </div>
            )}

            {reviewing.action === 'approve' && (
              <p className="sv-modal-note">
                This will forward the proposal to the HoD for final review.
              </p>
            )}

            {actionError && <div className="alert">{actionError}</div>}

            <div className="sv-modal-actions">
              <button
                className={`btn ${reviewing.action === 'approve' ? 'btn-primary' : 'btn-danger'}`}
                onClick={handleConfirm}
                disabled={confirming}
              >
                {confirming ? 'Processing...' : 'Confirm'}
              </button>
              <button className="btn btn-outline" onClick={() => setReviewing(null)} disabled={confirming}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
