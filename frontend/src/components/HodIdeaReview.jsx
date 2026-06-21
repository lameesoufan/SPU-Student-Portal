import React, { useState, useEffect } from 'react';
import { fetchHodPendingDoctorIdeas, hodReviewDoctorIdea } from '../api';
import { FileCheck2, Loader2, ClipboardCheck, CheckCircle2, XCircle, User, Users, ChevronDown, GraduationCap, Calendar, Stethoscope, Info, Lightbulb, Wrench } from 'lucide-react';

export default function HodIdeaReview({ onBack }) {
  const [ideas, setIdeas]         = useState([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [reviewing, setReviewing] = useState(null);
  const [reason, setReason]       = useState('');
  const [actionError, setActionError] = useState('');
  const [confirming, setConfirming]   = useState(false);

  useEffect(() => {
    fetchHodPendingDoctorIdeas()
      .then((res) => setIdeas(res.data))
      .catch(() => setError('Failed to load ideas.'))
      .finally(() => setLoading(false));
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
      await hodReviewDoctorIdea(reviewing.id, {
        action: reviewing.action,
        rejection_reason: reason,
      });
      setIdeas((prev) => prev.filter((i) => i.id !== reviewing.id));
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
          <Lightbulb size={20} />
        </div>
        <div className="flex flex-col gap-1">
          <h1 className="text-xl font-bold tracking-tight text-gray-900 dark:text-white m-0">Doctor Project Ideas</h1>
          <p className="text-[13px] font-medium text-gray-500 dark:text-gray-400 m-0">Review and approve ideas submitted by doctors in your department</p>
        </div>
        {ideas.length > 0 && (
          <div className="ml-auto flex items-center justify-center min-w-[36px] h-9 bg-violet-500/10 text-violet-600 dark:text-violet-400 rounded-lg text-sm font-bold px-3">
            {ideas.length}
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
          <Loader2 size={32} className="animate-spin text-violet-600" />
          Loading ideas…
        </div>
      )}

      {/* ── Empty State ── */}
      {!loading && ideas.length === 0 && !error && (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-emerald-500/10 text-emerald-500">
            <ClipboardCheck size={32} />
          </div>
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">All caught up</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-sm">No pending doctor ideas at the moment. New submissions will appear here for your review.</p>
        </div>
      )}

      {/* ── Idea Cards ── */}
      <div className="flex flex-col gap-4">
        {ideas.map((idea) => (
          <div key={idea.id} className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-sm flex flex-col transition-shadow hover:shadow-md">
            {/* Card Header */}
            <div className="pt-5 px-6 flex items-start justify-between gap-4">
              <div className="flex flex-col gap-1.5 min-w-0 flex-1">
                <h3 className="text-base font-bold text-gray-900 dark:text-white m-0 leading-snug">{idea.title}</h3>
                <span className="inline-flex items-center gap-1.5 text-[13px] text-gray-500 dark:text-gray-400 font-medium">
                  <span className="w-7 h-7 rounded-full bg-violet-600/10 text-violet-600 flex items-center justify-center text-[13px] flex-shrink-0">
                    <User size={14} />
                  </span>
                  {idea.doctor_name}
                </span>
              </div>
              <div className="flex gap-1.5 flex-wrap flex-shrink-0">
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-violet-500/10 text-violet-600 dark:text-violet-400 tracking-wide">
                  {idea.department.replace(/_/g, ' ')}
                </span>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 tracking-wide">
                  <Users size={11} />
                  {idea.max_team_size} students
                </span>
              </div>
            </div>

            {/* Card Body */}
            <div className="px-6 py-4 flex flex-col gap-3">
              <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed m-0 line-clamp-3">{idea.description}</p>
              {idea.required_skills && (
                <div className="flex items-center gap-1.5 flex-wrap">
                  <span className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide flex items-center gap-1">
                    <Wrench size={12} />
                    Skills:
                  </span>
                  {idea.required_skills.split(',').map((skill, i) => (
                    <span key={i} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-gray-50 dark:bg-gray-700/50 text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-600">
                      {skill.trim()}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Card Footer */}
            <div className="px-6 py-4 border-t border-gray-200/50 dark:border-gray-700/50 bg-gray-50 dark:bg-gray-800/30 flex gap-2.5 rounded-b-xl">
              <button
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
                onClick={() => openReview(idea.id, 'approve')}
              >
                <CheckCircle2 size={15} />
                Approve
              </button>
              <button
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold rounded-lg border border-red-300 text-red-600 hover:bg-red-50 transition-colors"
                onClick={() => openReview(idea.id, 'reject')}
              >
                <XCircle size={15} />
                Reject
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* ── Modal ── */}
      {reviewing && (
        <div
          className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center z-50 p-6"
          role="dialog"
          aria-modal="true"
        >
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl p-8 w-full max-w-md border border-gray-200 dark:border-gray-700">
            {/* Modal Header */}
            <div className="flex items-center gap-3 mb-2">
              <div className={`w-11 h-11 rounded-lg flex items-center justify-center flex-shrink-0 ${
                reviewing.action === 'approve' ? 'bg-emerald-500/10 text-emerald-600' : 'bg-red-500/10 text-red-600'
              }`}>
                {reviewing.action === 'approve' ? <CheckCircle2 size={22} /> : <XCircle size={22} />}
              </div>
              <h3 className="text-lg font-bold text-gray-900 dark:text-white m-0">
                {reviewing.action === 'approve' ? 'Approve Idea' : 'Reject Idea'}
              </h3>
            </div>

            {/* Approve Note */}
            {reviewing.action === 'approve' && (
              <p className="text-sm leading-relaxed mt-3 p-3 px-4 bg-sky-500/10 rounded-lg border border-sky-500/20 text-sky-700 dark:text-sky-400">
                This idea will be marked as <strong>Approved</strong> and become available for student applications.
              </p>
            )}

            {/* Reject Form */}
            {reviewing.action === 'reject' && (
              <div className="mt-5">
                <label htmlFor="hod-idea-reason" className="block text-[13px] font-semibold text-gray-500 dark:text-gray-400 mb-1.5">
                  Rejection Reason <span className="text-red-500">*</span>
                </label>
                <textarea
                  id="hod-idea-reason"
                  className="w-full py-2.5 px-3.5 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white transition-all placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none resize-none"
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Explain why this idea is being rejected…"
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
                className="px-4 py-2 text-sm font-semibold rounded-lg border border-gray-200 dark:border-gray-600 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
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
                {confirming ? 'Processing…' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}