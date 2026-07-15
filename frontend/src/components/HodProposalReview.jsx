import React, { useState, useEffect } from 'react';
import { fetchHodPending, hodReview, fetchResponseByProposal } from '../api';
import {
  FileCheck, Loader2, ClipboardCheck, CheckCircle2, XCircle,
  User, Users, ChevronDown, GraduationCap,
} from 'lucide-react';

const TEAM_STATUS_STYLES = {
  accepted: 'bg-emerald-500/10 text-emerald-600 border border-emerald-500/20',
  rejected: 'bg-red-500/10 text-red-600 border border-red-500/20',
  pending:  'bg-amber-500/10 text-amber-600 border border-amber-500/20',
};

const renderResponseValue = (value) => {
  if (Array.isArray(value)) return value.length
    ? (
      <div className="flex flex-wrap gap-1.5">
        {value.map((item) => (
          <span key={item} className="inline-flex items-center px-2.5 py-0.5 rounded-full bg-violet-500/10 text-violet-600 dark:text-violet-400 border border-violet-500/20 text-xs font-semibold">
            {item}
          </span>
        ))}
      </div>
    )
    : null;
  return value || null;
};

export default function HodProposalReview({ onBack }) {
  const [proposals, setProposals]     = useState([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState('');
  const [reviewing, setReviewing]     = useState(null);
  const [reason, setReason]           = useState('');
  const [actionError, setActionError] = useState('');
  const [confirming, setConfirming]   = useState(false);
  const [formResponses, setFormResponses] = useState({});
  const [expandedForm, setExpandedForm]   = useState(null);

  useEffect(() => {
    let active = true;
    fetchHodPending()
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
      await hodReview(reviewing.id, {
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
    <div className="max-w-4xl mx-auto py-8 px-6 flex flex-col gap-6">
      {/* ── Header ── */}
      <div className="flex items-center gap-4 p-5 px-6 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-sm">
        <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-violet-600/10 text-violet-600">
          <FileCheck size={20} />
        </div>
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-bold tracking-tight text-gray-900 dark:text-white m-0">مقترحات الطلاب</h1>
          <p className="text-[13px] font-medium text-gray-500 dark:text-gray-400 m-0">مراجعة والموافقة على مقترحات المشاريع من الطلاب</p>
        </div>
        {proposals.length > 0 && (
          <div className="ml-auto flex items-center justify-center min-w-[36px] h-9 bg-violet-500/10 text-violet-600 dark:text-violet-400 rounded-lg text-sm font-bold px-3">
            {proposals.length}
          </div>
        )}
      </div>

      {/* ── Error Alert ── */}
      {error && (
        <div className="border border-red-300 dark:border-red-700/50 rounded-lg py-3.5 px-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 font-medium text-sm">
          {error}
        </div>
      )}

      {/* ── Loading ── */}
      {loading && (
        <div className="flex flex-col items-center gap-3 py-16 px-6 text-gray-500 dark:text-gray-400 text-sm font-medium">
          <Loader2 size={32} className="animate-spin text-violet-600 dark:text-violet-400" />
          Loading proposals…
        </div>
      )}

      {/* ── Empty State ── */}
      {!loading && proposals.length === 0 && !error && (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-emerald-500/10 text-emerald-500">
            <ClipboardCheck size={32} />
          </div>
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">تمت المراجعة</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-sm">لا توجد مقترحات معلقة للمراجعة. الطلبات الجديدة ستظهر هنا.</p>
        </div>
      )}

      {/* ── Proposal Cards ── */}
      <div className="flex flex-col gap-4">
        {proposals.map((p) => {
          const resp = formResponses[p.id];
          const isExpanded = expandedForm === p.id;

          return (
            <div key={p.id} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-sm flex flex-col transition-shadow hover:shadow-md">
              {/* Card Header */}
              <div className="pt-5 px-6 flex items-start justify-between gap-4">
                <div className="flex flex-col gap-1.5 min-w-0 flex-1">
                  <h3 className="text-base font-bold text-gray-900 dark:text-white m-0 leading-snug">{p.title}</h3>
                  <span className="inline-flex items-center gap-1.5 text-[13px] text-gray-500 dark:text-gray-400 font-medium">
                    <span className="w-7 h-7 rounded-full bg-amber-500/10 text-amber-600 flex items-center justify-center flex-shrink-0">
                      <GraduationCap size={14} />
                    </span>
                    {p.student_name}
                  </span>
                </div>
                <div className="flex gap-1.5 flex-wrap flex-shrink-0">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-violet-500/10 text-violet-600 dark:text-violet-400 tracking-wide">
                    {p.department.replace(/_/g, ' ')}
                  </span>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 tracking-wide">
                    <User size={11} />
                    {p.supervisor_name}
                  </span>
                </div>
              </div>

              {/* Card Body */}
              <div className="px-6 py-4 flex flex-col gap-3.5">
                <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed m-0 line-clamp-3">{p.description}</p>

                {/* Team Members */}
                {p.invitations && p.invitations.length > 0 && (
                  <div className="flex items-center flex-wrap gap-1.5">
                    <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide flex items-center gap-1 mr-1">
                      <Users size={12} />
                      Team:
                    </span>
                    {p.invitations.map((inv) => (
                      <span key={inv.id} className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${TEAM_STATUS_STYLES[inv.status] || 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-700'}`}>
                        {inv.invitee_name}
                      </span>
                    ))}
                  </div>
                )}

                {/* Dynamic Form Responses */}
                {resp && resp.field_responses && resp.field_responses.length > 0 && (
                  <div className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden mt-0.5">
                    <button
                      className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800/30 border-none cursor-pointer text-[13px] font-semibold text-gray-500 dark:text-gray-400 text-left transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/50 hover:text-gray-900 dark:hover:text-white"
                      onClick={() => setExpandedForm(isExpanded ? null : p.id)}
                      aria-expanded={isExpanded}
                    >
                      Department Form Responses
                      <ChevronDown size={14} className={`text-gray-500 dark:text-gray-400 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`} />
                    </button>
                    {isExpanded && (
                      <div className="border-t border-gray-200 dark:border-gray-700">
                        {resp.field_responses.map((fr, idx) => (
                          <div key={idx} className={`flex gap-3 px-4 py-2.5 text-[13px] transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/30 ${idx % 2 === 0 ? 'bg-transparent' : 'bg-gray-50/50 dark:bg-gray-800/15'}`}>
                            <span className="font-semibold text-gray-500 dark:text-gray-400 min-w-[160px] flex-shrink-0 pt-px">{fr.field_label}</span>
                            <span className="text-gray-900 dark:text-white break-words leading-relaxed">
                              {renderResponseValue(fr.value) || <em className="text-gray-500 dark:text-gray-400 italic">—</em>}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Card Footer */}
              <div className="px-6 py-4 border-t border-gray-200/50 dark:border-gray-700/50 bg-gray-50 dark:bg-gray-800/30 flex gap-2.5 rounded-b-xl">
                <button
                  className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
                  onClick={() => openReview(p.id, 'approve')}
                >
                  <CheckCircle2 size={15} />
                  Approve &amp; Assign
                </button>
                <button
                  className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold rounded-lg border border-red-300 text-red-600 hover:bg-red-50 transition-colors"
                  onClick={() => openReview(p.id, 'reject')}
                >
                  <XCircle size={15} />
                  Reject
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Modal ── */}
      {reviewing && (
        <div
          className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-6"
          role="dialog"
          aria-modal="true"
        >
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl p-8 w-full max-w-lg border border-gray-200 dark:border-gray-700">
            {/* Modal Header */}
            <div className="flex items-center gap-3 mb-2">
              <div className={`w-11 h-11 rounded-lg flex items-center justify-center flex-shrink-0 ${
                reviewing.action === 'approve' ? 'bg-emerald-500/10 text-emerald-600' : 'bg-red-500/10 text-red-600'
              }`}>
                {reviewing.action === 'approve' ? <CheckCircle2 size={22} /> : <XCircle size={22} />}
              </div>
              <h3 className="text-lg font-bold text-gray-900 dark:text-white m-0">
                {reviewing.action === 'approve' ? 'Approve & Assign' : 'رفض المقترح'}
              </h3>
            </div>

            {/* Approve Note */}
            {reviewing.action === 'approve' && (
              <p className="text-sm leading-relaxed mt-3 p-3 px-4 bg-sky-500/10 rounded-lg border border-sky-500/20 text-sky-700 dark:text-sky-400">
                Approving will assign this project to the student and automatically create a project application with status <strong>مقبول</strong>.
              </p>
            )}

            {/* Reject Form */}
            {reviewing.action === 'reject' && (
              <div className="mt-5">
                <label htmlFor="hod-reason" className="block text-[13px] font-semibold text-gray-500 dark:text-gray-400 mb-1.5">
                  Rejection Reason <span className="text-red-500">*</span>
                </label>
                <textarea
                  id="hod-reason"
                  className="w-full py-2.5 px-3.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white transition-all placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none resize-none"
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="اشرح سبب رفض هذا المقترح…"
                />
              </div>
            )}

            {/* Action Error */}
            {actionError && (
              <div className="border border-red-300 dark:border-red-700/50 rounded-lg py-3 px-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 font-medium text-sm mt-4">
                {actionError}
              </div>
            )}

            {/* Modal Actions */}
            <div className="flex gap-2.5 mt-7 justify-end">
              <button
                className="px-4 py-2 text-sm font-semibold rounded-lg border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                onClick={() => setReviewing(null)}
                disabled={confirming}
              >
                Cancel
              </button>
              <button
                className={`inline-flex items-center gap-1.5 px-5 py-2 text-sm font-semibold rounded-lg transition-colors disabled:opacity-60 disabled:cursor-not-allowed ${
                  reviewing.action === 'approve'
                    ? 'bg-emerald-600 text-white hover:bg-emerald-700'
                    : 'bg-red-600 text-white hover:bg-red-700'
                }`}
                onClick={handleConfirm}
                disabled={confirming}
              >
                {confirming && <Loader2 size={14} className="animate-spin" />}
                {confirming ? 'Processing…' : 'تأكيد'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}