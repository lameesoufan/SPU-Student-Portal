import React, { useEffect, useState } from 'react';
import { fetchSupervisorPending, supervisorReview, fetchResponseByProposal } from '../api';
import { getDepartmentLabel } from '../lib/constants';
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  FileText,
  GraduationCap,
  Loader2,
  MessageSquareText,
  ShieldCheck,
  UserRound,
  UsersRound,
  X,
  XCircle,
} from 'lucide-react';

const PROJECT_TYPE_LABELS = {
  seasonal: 'فصلي',
  graduation_1: 'تخرج 1',
  graduation_2: 'تخرج 2',
};

const INVITATION_STATUS = {
  accepted: {
    label: 'موافق',
    className: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-300',
  },
  rejected: {
    label: 'رافض',
    className: 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-300',
  },
  pending: {
    label: 'بانتظار الرد',
    className: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-300',
  },
};

const SUPERVISOR_STATUS = {
  approved: INVITATION_STATUS.accepted,
  rejected: INVITATION_STATUS.rejected,
  pending: INVITATION_STATUS.pending,
};

function renderResponseValue(value) {
  if (Array.isArray(value)) {
    return value.length ? (
      <div className="flex flex-wrap gap-1.5">
        {value.map((item) => (
          <span
            key={String(item)}
            className="inline-flex items-center rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-xs font-semibold text-violet-700 dark:border-violet-900/50 dark:bg-violet-950/30 dark:text-violet-300"
          >
            {String(item)}
          </span>
        ))}
      </div>
    ) : null;
  }

  if (value && typeof value === 'object') {
    return JSON.stringify(value);
  }

  return value || null;
}

export default function SupervisorReview({ onBack }) {
  const [proposals, setProposals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reviewing, setReviewing] = useState(null);
  const [reason, setReason] = useState('');
  const [actionError, setActionError] = useState('');
  const [confirming, setConfirming] = useState(false);
  const [formResponses, setFormResponses] = useState({});
  const [expandedForm, setExpandedForm] = useState(null);

  useEffect(() => {
    let active = true;

    const load = async () => {
      setLoading(true);
      setError('');

      try {
        const response = await fetchSupervisorPending();
        if (!active) return;

        const items = Array.isArray(response.data) ? response.data : [];
        setProposals(items);

        const responses = await Promise.allSettled(
          items.map((proposal) => (
            fetchResponseByProposal(proposal.id).then((result) => [proposal.id, result.data])
          )),
        );

        if (!active) return;

        const next = {};
        responses.forEach((result) => {
          if (result.status === 'fulfilled') {
            next[result.value[0]] = result.value[1];
          }
        });
        setFormResponses(next);
      } catch (requestError) {
        if (!active) return;
        setError(requestError.response?.data?.error || 'تعذر تحميل مقترحات الطلاب. حاول مرة أخرى.');
      } finally {
        if (active) setLoading(false);
      }
    };

    load();
    return () => { active = false; };
  }, []);

  const openReview = (id, action) => {
    setReviewing({ id, action });
    setReason('');
    setActionError('');
  };

  const closeReview = () => {
    if (confirming) return;
    setReviewing(null);
    setReason('');
    setActionError('');
  };

  const handleConfirm = async () => {
    if (!reviewing || confirming) return;

    if (reviewing.action === 'reject' && !reason.trim()) {
      setActionError('يرجى كتابة سبب الرفض قبل المتابعة.');
      return;
    }

    setActionError('');
    setConfirming(true);

    try {
      await supervisorReview(reviewing.id, {
        action: reviewing.action,
        rejection_reason: reason.trim(),
      });
      setProposals((current) => current.filter((proposal) => proposal.id !== reviewing.id));
      setReviewing(null);
    } catch (requestError) {
      const data = requestError.response?.data;
      if (Array.isArray(data?.rejection_reason)) setActionError(data.rejection_reason[0]);
      else if (data?.rejection_reason) setActionError(data.rejection_reason);
      else if (data?.error) setActionError(data.error);
      else setActionError('تعذر تنفيذ العملية. حاول مرة أخرى.');
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 lg:px-8" dir="rtl">
      <div className="mb-6 flex flex-col gap-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 sm:flex-row sm:items-center sm:justify-between sm:p-6">
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-violet-50 text-violet-600 dark:bg-violet-950/30 dark:text-violet-300">
            <ShieldCheck size={23} />
          </div>
          <div>
            <h1 className="m-0 text-xl font-black text-slate-900 dark:text-white sm:text-2xl">مقترحات الطلاب</h1>
            <p className="m-0 mt-1 text-sm leading-6 text-slate-500 dark:text-slate-400">
              راجع المقترحات التي اختارك الطلاب للإشراف عليها، ثم سجّل قرارك.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {!loading && proposals.length > 0 && (
            <span className="inline-flex h-10 items-center gap-2 rounded-xl bg-violet-50 px-3.5 text-sm font-bold text-violet-700 dark:bg-violet-950/30 dark:text-violet-300">
              <FileText size={16} />
              {proposals.length} {proposals.length === 1 ? 'مقترح' : 'مقترحات'}
            </span>
          )}
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 text-sm font-bold text-slate-600 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
            >
              <ArrowRight size={16} />
              رجوع
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="mb-5 flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3.5 text-sm font-medium text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/20 dark:text-rose-300">
          <AlertCircle size={18} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading && (
        <div className="flex min-h-[360px] flex-col items-center justify-center gap-3 rounded-2xl border border-slate-200 bg-white text-sm font-medium text-slate-500 shadow-sm dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
          <Loader2 size={32} className="animate-spin text-violet-600 dark:text-violet-300" />
          جارٍ تحميل المقترحات...
        </div>
      )}

      {!loading && proposals.length === 0 && !error && (
        <div className="flex min-h-[360px] flex-col items-center justify-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 text-center shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-300">
            <ClipboardCheck size={31} />
          </div>
          <h2 className="m-0 text-lg font-black text-slate-900 dark:text-white">لا توجد طلبات بانتظارك</h2>
          <p className="m-0 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
            لا توجد مقترحات معلّقة للمراجعة حاليًا. ستظهر هنا أي فكرة جديدة يختارك الطالب للإشراف عليها.
          </p>
        </div>
      )}

      {!loading && proposals.length > 0 && (
        <div className="space-y-4">
          {proposals.map((proposal) => {
            const response = formResponses[proposal.id];
            const isExpanded = expandedForm === proposal.id;
            const supervisors = proposal.supervisors || [];
            const invitations = proposal.invitations || [];

            return (
              <article
                key={proposal.id}
                className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:border-violet-200 hover:shadow-md dark:border-slate-800 dark:bg-slate-900 dark:hover:border-violet-900/70"
              >
                <div className="p-5 sm:p-6">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center rounded-full bg-violet-50 px-2.5 py-1 text-xs font-bold text-violet-700 dark:bg-violet-950/30 dark:text-violet-300">
                          {PROJECT_TYPE_LABELS[proposal.project_type] || proposal.project_type || 'مشروع'}
                        </span>
                        <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                          {getDepartmentLabel(proposal.department)}
                        </span>
                      </div>

                      <h2 className="m-0 text-lg font-black leading-8 text-slate-900 dark:text-white sm:text-xl">
                        {proposal.title}
                      </h2>

                      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-500 dark:text-slate-400">
                        <span className="inline-flex items-center gap-1.5">
                          <GraduationCap size={16} />
                          صاحب المقترح: <strong className="font-bold text-slate-700 dark:text-slate-200">{proposal.student_name}</strong>
                        </span>
                        <span className="inline-flex items-center gap-1.5">
                          <UsersRound size={16} />
                          أعضاء الفريق: {invitations.length + 1}
                        </span>
                      </div>
                    </div>

                    <div className="flex shrink-0 gap-2">
                      <button
                        type="button"
                        onClick={() => openReview(proposal.id, 'approve')}
                        className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 text-sm font-bold text-white transition hover:bg-emerald-700 focus:outline-none focus:ring-4 focus:ring-emerald-500/15"
                      >
                        <CheckCircle2 size={17} />
                        موافقة
                      </button>
                      <button
                        type="button"
                        onClick={() => openReview(proposal.id, 'reject')}
                        className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-rose-200 bg-white px-4 text-sm font-bold text-rose-600 transition hover:bg-rose-50 focus:outline-none focus:ring-4 focus:ring-rose-500/10 dark:border-rose-900/60 dark:bg-slate-900 dark:text-rose-300 dark:hover:bg-rose-950/20"
                      >
                        <XCircle size={17} />
                        رفض
                      </button>
                    </div>
                  </div>

                  {proposal.description && (
                    <div className="mt-5 rounded-xl bg-slate-50 px-4 py-3.5 text-sm leading-7 text-slate-600 dark:bg-slate-800/60 dark:text-slate-300">
                      {proposal.description}
                    </div>
                  )}

                  {supervisors.length > 0 && (
                    <div className="mt-5">
                      <div className="mb-2 flex items-center gap-2 text-xs font-bold text-slate-500 dark:text-slate-400">
                        <UserRound size={14} />
                        المشرفون المختارون
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {supervisors.map((supervisor) => {
                          const status = SUPERVISOR_STATUS[supervisor.status] || SUPERVISOR_STATUS.pending;
                          return (
                            <span
                              key={supervisor.id}
                              title={supervisor.rejection_reason || ''}
                              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-bold ${status.className}`}
                            >
                              {supervisor.name}
                              <span className="opacity-70">•</span>
                              {status.label}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {invitations.length > 0 && (
                    <div className="mt-5">
                      <div className="mb-2 flex items-center gap-2 text-xs font-bold text-slate-500 dark:text-slate-400">
                        <UsersRound size={14} />
                        أعضاء الفريق
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {invitations.map((invitation) => {
                          const status = INVITATION_STATUS[invitation.status] || INVITATION_STATUS.pending;
                          return (
                            <span
                              key={invitation.id}
                              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-bold ${status.className}`}
                            >
                              {invitation.invitee_name}
                              <span className="opacity-70">•</span>
                              {status.label}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {response?.field_responses?.length > 0 && (
                  <div className="border-t border-slate-100 dark:border-slate-800">
                    <button
                      type="button"
                      onClick={() => setExpandedForm(isExpanded ? null : proposal.id)}
                      aria-expanded={isExpanded}
                      className="flex w-full items-center justify-between gap-3 bg-slate-50/70 px-5 py-3.5 text-right text-sm font-bold text-slate-700 transition hover:bg-slate-100 dark:bg-slate-800/40 dark:text-slate-200 dark:hover:bg-slate-800 sm:px-6"
                    >
                      <span className="inline-flex items-center gap-2">
                        <MessageSquareText size={17} className="text-violet-600 dark:text-violet-300" />
                        عرض إجابات نموذج القسم
                        <span className="rounded-full bg-white px-2 py-0.5 text-[11px] text-slate-500 shadow-sm dark:bg-slate-900 dark:text-slate-400">
                          {response.field_responses.length}
                        </span>
                      </span>
                      <ChevronDown size={18} className={`text-slate-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                    </button>

                    {isExpanded && (
                      <div className="divide-y divide-slate-100 border-t border-slate-100 dark:divide-slate-800 dark:border-slate-800">
                        {response.field_responses.map((fieldResponse, index) => (
                          <div key={`${fieldResponse.field_label}-${index}`} className="grid gap-2 px-5 py-3.5 sm:grid-cols-[190px_minmax(0,1fr)] sm:px-6">
                            <span className="text-sm font-bold text-slate-500 dark:text-slate-400">
                              {fieldResponse.field_label}
                            </span>
                            <div className="break-words text-sm leading-6 text-slate-800 dark:text-slate-200">
                              {renderResponseValue(fieldResponse.value) || <span className="text-slate-400">—</span>}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}

      {reviewing && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm" role="dialog" aria-modal="true">
          <button type="button" className="absolute inset-0" onClick={closeReview} aria-label="إغلاق" />

          <section className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-slate-900">
            <header className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4 dark:border-slate-800 sm:px-6">
              <div className="flex items-start gap-3">
                <div className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${reviewing.action === 'approve' ? 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-300' : 'bg-rose-50 text-rose-600 dark:bg-rose-950/30 dark:text-rose-300'}`}>
                  {reviewing.action === 'approve' ? <CheckCircle2 size={22} /> : <XCircle size={22} />}
                </div>
                <div>
                  <h3 className="m-0 text-lg font-black text-slate-900 dark:text-white">
                    {reviewing.action === 'approve' ? 'تأكيد الموافقة على المقترح' : 'رفض مقترح المشروع'}
                  </h3>
                  <p className="m-0 mt-1 text-sm text-slate-500 dark:text-slate-400">
                    {reviewing.action === 'approve' ? 'سيتم تسجيل موافقتك كمشرف على هذا المشروع.' : 'أدخل سببًا واضحًا ليتمكن الطالب من معالجة الملاحظات.'}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={closeReview}
                disabled={confirming}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-200 text-slate-500 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                aria-label="إغلاق"
              >
                <X size={17} />
              </button>
            </header>

            <div className="px-5 py-5 sm:px-6">
              {reviewing.action === 'approve' ? (
                <div className="rounded-xl border border-sky-200 bg-sky-50 px-4 py-3.5 text-sm leading-7 text-sky-800 dark:border-sky-900/50 dark:bg-sky-950/20 dark:text-sky-300">
                  ينتقل المقترح إلى رئيس القسم بعد اكتمال موافقات المشرفين النشطين، أو بعد اختيار الطالب المتابعة بمشرف واحد موافق.
                </div>
              ) : (
                <div>
                  <label htmlFor="supervisor-rejection-reason" className="mb-2 block text-sm font-bold text-slate-700 dark:text-slate-200">
                    سبب الرفض <span className="text-rose-500">*</span>
                  </label>
                  <textarea
                    id="supervisor-rejection-reason"
                    rows={4}
                    value={reason}
                    onChange={(event) => {
                      setReason(event.target.value);
                      if (actionError) setActionError('');
                    }}
                    placeholder="اكتب سبب الرفض أو التعديلات المطلوبة..."
                    className="w-full resize-y rounded-xl border border-slate-200 bg-white px-3.5 py-3 text-sm leading-6 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-violet-400 focus:ring-4 focus:ring-violet-500/10 dark:border-slate-700 dark:bg-slate-950 dark:text-white dark:focus:border-violet-700"
                  />
                </div>
              )}

              {actionError && (
                <div className="mt-4 flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-3 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/20 dark:text-rose-300">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  {actionError}
                </div>
              )}
            </div>

            <footer className="flex items-center justify-end gap-2 border-t border-slate-100 bg-slate-50/70 px-5 py-4 dark:border-slate-800 dark:bg-slate-800/30 sm:px-6">
              <button
                type="button"
                onClick={closeReview}
                disabled={confirming}
                className="h-10 rounded-xl border border-slate-200 bg-white px-4 text-sm font-bold text-slate-600 transition hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                إلغاء
              </button>
              <button
                type="button"
                onClick={handleConfirm}
                disabled={confirming}
                className={`inline-flex h-10 items-center justify-center gap-2 rounded-xl px-5 text-sm font-bold text-white transition disabled:cursor-not-allowed disabled:opacity-60 ${reviewing.action === 'approve' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-rose-600 hover:bg-rose-700'}`}
              >
                {confirming ? <Loader2 size={16} className="animate-spin" /> : reviewing.action === 'approve' ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                {confirming ? 'جارٍ الحفظ...' : reviewing.action === 'approve' ? 'تأكيد الموافقة' : 'تأكيد الرفض'}
              </button>
            </footer>
          </section>
        </div>
      )}
    </div>
  );
}
