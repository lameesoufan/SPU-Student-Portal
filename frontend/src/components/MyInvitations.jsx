import React, { useState, useEffect } from 'react';
import {
  fetchMyInvitations, respondToInvitation,
  fetchMyProposalInvitations, respondToProposalInvitation,
} from '../api';
import { Inbox, Check, X, User, Briefcase, Info, Mail } from 'lucide-react';

export default function MyInvitations({ onBack }) {
  const [ideaInvs, setIdeaInvs]       = useState([]);
  const [propInvs, setPropInvs]       = useState([]);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState('');
  const [acting, setActing]           = useState(null);

  useEffect(() => {
    Promise.all([fetchMyInvitations(), fetchMyProposalInvitations()])
      .then(([ideaRes, propRes]) => {
        setIdeaInvs(ideaRes.data);
        setPropInvs(propRes.data);
      })
      .catch(() => setError('Failed to load invitations.'))
      .finally(() => setLoading(false));
  }, []);

  const handleIdeaRespond = async (invId, action) => {
    setActing(invId);
    try {
      await respondToInvitation(invId, action);
      setIdeaInvs((prev) => prev.filter((i) => i.id !== invId));
    } catch (err) {
      setError(err.response?.data?.error || 'Something went wrong.');
    } finally {
      setActing(null);
    }
  };

  const handlePropRespond = async (invId, action) => {
    let rejectionReason = '';
    if (action === 'reject') {
      rejectionReason = window.prompt('يمكنك كتابة سبب رفض الانضمام إلى الفريق (اختياري):') || '';
    }
    setActing(invId);
    try {
      await respondToProposalInvitation(invId, action, rejectionReason);
      setPropInvs((prev) => prev.filter((i) => i.id !== invId));
    } catch (err) {
      setError(err.response?.data?.error || 'Something went wrong.');
    } finally {
      setActing(null);
    }
  };

  const total = ideaInvs.length + propInvs.length;

  return (
    <div className="flex flex-col gap-6 max-w-[1080px] mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-500">
          <Mail size={20} />
        </div>
        <div>
          <h1 className="text-xl font-extrabold text-[var(--text)] leading-tight">دعوات الفريق</h1>
          <p className="text-sm text-[var(--text-muted)]">راجع ورد على طلبات تشكيل الفريق المعلقة.</p>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-sm">
          <Info size={16} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="spinner-dark w-8 h-8"></div>
        </div>
      )}

      {/* Empty State */}
      {!loading && total === 0 && !error && (
        <div className="flex flex-col items-center justify-center py-20">
          <div className="w-16 h-16 flex items-center justify-center rounded-full bg-[var(--bg-tertiary)] text-[var(--text-muted)] mb-4">
            <Inbox size={28} />
          </div>
          <h3 className="text-lg font-bold text-[var(--text)]">لا توجد دعوات معلقة</h3>
          <p className="text-sm text-[var(--text-muted)] mt-1">You're all caught up!</p>
        </div>
      )}

      {/* Doctor Idea Application Invitations */}
      {ideaInvs.length > 0 && (
        <div className="flex flex-col gap-3">
          <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">
            Doctor Idea Applications
          </span>
          <div className="flex flex-col gap-3">
            {ideaInvs.map((inv) => (
              <div
                key={inv.id}
                className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] shadow-[var(--shadow)] overflow-hidden"
              >
                {/* Card Body */}
                <div className="p-5">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20">
                      <User size={12} />
                      {inv.doctor_name}
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-[var(--text)] mb-3 leading-snug">{inv.idea_title}</h3>
                  <div className="flex items-center gap-3 p-3 bg-[var(--bg-tertiary)] rounded-[var(--radius-sm)] border border-[var(--border-light)]">
                    <div className="w-8 h-8 rounded-full bg-[var(--primary)]/10 flex items-center justify-center text-[var(--primary)] shrink-0">
                      <User size={14} />
                    </div>
                    <div>
                      <span className="text-[11px] text-[var(--text-muted)] uppercase tracking-wide font-medium block">دعوة من قائد الفريق</span>
                      <span className="text-sm font-semibold text-[var(--text)]">{inv.leader_name}</span>
                    </div>
                  </div>
                </div>

                {/* Notice Bar */}
                <div className="flex items-start gap-2.5 px-5 py-3 bg-blue-500/5 border-l-[3px] border-l-blue-500 text-sm text-[var(--text-secondary)]">
                  <Briefcase size={16} className="text-blue-500 shrink-0 mt-0.5" />
                  <span>قبول الدعوة يعني أنك لن تتمكن من التقدم لمكان آخر حتى يُبت في هذا الطلب. وفي حال الرفض، ستصبح حراً مرة أخرى.</span>
                </div>

                {/* Actions */}
                <div className="flex gap-3 px-5 py-4 border-t border-[var(--border-light)] bg-[var(--bg-tertiary)]">
                  <button
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-[var(--radius-sm)] bg-emerald-500 text-white font-semibold text-sm hover:bg-emerald-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    onClick={() => handleIdeaRespond(inv.id, 'accept')}
                    disabled={acting === inv.id}
                  >
                    <Check size={16} /> قبول
                  </button>
                  <button
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-[var(--radius-sm)] bg-transparent border-2 border-red-400 text-red-500 font-semibold text-sm hover:bg-red-500/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    onClick={() => handleIdeaRespond(inv.id, 'reject')}
                    disabled={acting === inv.id}
                  >
                    <X size={16} /> رفض
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Student Proposal Invitations */}
      {propInvs.length > 0 && (
        <div className="flex flex-col gap-3">
          <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">
            Student Proposal Teams
          </span>
          <div className="flex flex-col gap-3">
            {propInvs.map((inv) => (
              <div
                key={inv.id}
                className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] shadow-[var(--shadow)] overflow-hidden"
              >
                {/* Card Body */}
                <div className="p-5">
                  <h3 className="text-base font-bold text-[var(--text)] mb-3 leading-snug">{inv.idea_title}</h3>
                  <div className="flex items-center gap-3 p-3 bg-[var(--bg-tertiary)] rounded-[var(--radius-sm)] border border-[var(--border-light)]">
                    <div className="w-8 h-8 rounded-full bg-[var(--primary)]/10 flex items-center justify-center text-[var(--primary)] shrink-0">
                      <User size={14} />
                    </div>
                    <div>
                      <span className="text-[11px] text-[var(--text-muted)] uppercase tracking-wide font-medium block">مقترحة من قائد الفريق</span>
                      <span className="text-sm font-semibold text-[var(--text)]">{inv.leader_name}</span>
                    </div>
                  </div>
                </div>

                {/* Notice Bar */}
                <div className="flex items-start gap-2.5 px-5 py-3 bg-blue-500/5 border-l-[3px] border-l-blue-500 text-sm text-[var(--text-secondary)]">
                  <Briefcase size={16} className="text-blue-500 shrink-0 mt-0.5" />
                  <span>قبول الدعوة يعني أنك لن تتمكن من التقدم لمكان آخر حتى يُبت في هذا المقترح. وفي حال الرفض، ستصبح حراً مرة أخرى.</span>
                </div>

                {/* Actions */}
                <div className="flex gap-3 px-5 py-4 border-t border-[var(--border-light)] bg-[var(--bg-tertiary)]">
                  <button
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-[var(--radius-sm)] bg-emerald-500 text-white font-semibold text-sm hover:bg-emerald-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    onClick={() => handlePropRespond(inv.id, 'accept')}
                    disabled={acting === inv.id}
                  >
                    <Check size={16} /> قبول
                  </button>
                  <button
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-[var(--radius-sm)] bg-transparent border-2 border-red-400 text-red-500 font-semibold text-sm hover:bg-red-500/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    onClick={() => handlePropRespond(inv.id, 'reject')}
                    disabled={acting === inv.id}
                  >
                    <X size={16} /> رفض
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}