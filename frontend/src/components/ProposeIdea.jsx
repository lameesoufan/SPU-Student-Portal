import React, { useState, useEffect } from 'react';

import StudentSearch from './StudentSearch';
import DynamicCheckboxGroup from './DynamicCheckboxGroup';
import {
  Send, Users, Clock, RefreshCw, CheckCircle, XCircle, Info,
  Lightbulb, UserPlus, Building2, Clipboard, ChevronRight, ChevronDown, ChevronLeft,
  Loader2, User, Check, UserMinus, UserCheck, UserX
} from 'lucide-react';
import {
  submitStudentProposal,
  fetchMyProposal,
  fetchDoctorsList,
  fetchStudentForm,
  replaceProposalMember,
  removeRejectedProposalMember,
  replaceRejectedSupervisor,
  continueWithApprovedSupervisor,
  reviseStudentProposal,
} from '../api';
import { PROJECT_TYPES } from '../lib/constants';

const DEPARTMENTS = [
  { value: 'software_engineering',    label: 'برمجيات' },
  { value: 'artificial_intelligence', label: 'ذكاء اصطناعي' },
  { value: 'information_security',    label: 'أمن سيبراني' },
  { value: 'communications',          label: 'اتصالات' },
  { value: 'control_robotics',        label: 'Control & Robotics' },
];

const BADGE_STYLES = {
  amber:  'bg-amber-500/10 text-amber-600 border-amber-500/20',
  blue:   'bg-blue-500/10 text-blue-600 border-blue-500/20',
  purple: 'bg-purple-500/10 text-purple-600 border-purple-500/20',
  green:  'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
  red:    'bg-red-500/10 text-red-600 border-red-500/20',
};

const STATUS_META = {
  awaiting_members:   { label: 'بانتظار الأعضاء',    Icon: Users,     color: 'amber' },
  pending_supervisor: { label: 'بانتظار المشرفين',   Icon: Clock,     color: 'blue' },
  supervisor_action_required: { label: 'مطلوب تعديل المشرفين', Icon: UserX, color: 'red' },
  pending_hod:        { label: 'بانتظار مراجعة رئيس القسم',   Icon: RefreshCw, color: 'purple' },
  assigned:           { label: 'Approved & Assigned',   Icon: CheckCircle, color: 'green' },
  rejected:           { label: 'مرفوض',              Icon: XCircle,   color: 'red' },
};

const STATUS_STEPS = {
  awaiting_members:   1,
  pending_supervisor: 2,
  supervisor_action_required: 2,
  pending_hod:        3,
  assigned:           4,
  rejected:           0,
};

const EMPTY = { title: '', description: '', department: '', supervisor: '', co_supervisor: '', team_size: 2, member_ids: [''], team_size_reason: '', project_type: '' };
const emptyValueForField = (field) => field.field_type === 'checkbox' ? [] : '';

const flattenApiDetails = (details) => {
  if (!details) return '';
  if (typeof details === 'string') return details;
  if (Array.isArray(details)) return details.map(flattenApiDetails).filter(Boolean).join(' ');
  if (typeof details === 'object') return Object.values(details).map(flattenApiDetails).filter(Boolean).join(' ');
  return String(details);
};

const getProposalErrorMessage = (data) => {
  if (!data) return 'تعذر إرسال المقترح. حاول مرة أخرى.';
  if (data.message && data.message !== 'Validation failed.') return data.message;
  if (data.error && data.error !== 'Validation failed.') return data.error;
  return flattenApiDetails(data.details) || 'بيانات المقترح غير صالحة. يرجى مراجعة الحقول.';
};

const STEPS = [
  { id: 'idea',    label: 'فكرة مشروع',   Icon: Lightbulb },
  { id: 'dept',    label: 'القسم',     Icon: Building2 },
  { id: 'team',    label: 'Team',           Icon: UserPlus },
  { id: 'dynamic', label: 'المتطلبات',   Icon: Clipboard },
];

const inputCls = "w-full bg-[var(--input-bg)] text-[var(--text)] border border-[var(--border)] rounded-[var(--radius-sm)] px-4 py-2.5 text-sm outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] transition-colors placeholder:text-[var(--text-faint)]";

export default function ProposeIdea({ onBack }) {
  const [existing, setExisting]     = useState(undefined);
  const [doctors, setDoctors]       = useState([]);
  const [form, setForm]             = useState(EMPTY);
  const [loading, setLoading]       = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]           = useState('');
  const [currentStep, setCurrentStep] = useState(0);
  const [dynForm, setDynForm]       = useState(null);
  const [dynValues, setDynValues]   = useState({});
  const [replacingId, setReplacingId]     = useState(null);   // username of member being replaced
  const [replaceLoading, setReplaceLoading] = useState(false);
  const [replaceError, setReplaceError]   = useState('');
  const [replacingSupervisorId, setReplacingSupervisorId] = useState(null);
  const [supervisorActionLoading, setSupervisorActionLoading] = useState(false);
  const [supervisorActionError, setSupervisorActionError] = useState('');
  const [editingRevision, setEditingRevision] = useState(false);
  const [revisionForm, setRevisionForm] = useState({ title: '', description: '' });
  const [revisionLoading, setRevisionLoading] = useState(false);
  const [revisionError, setRevisionError] = useState('');
  useEffect(() => {
    setLoading(true);
    Promise.allSettled([fetchMyProposal(), fetchDoctorsList()])
      .then(([propRes, docRes]) => {
        if (propRes.status === 'fulfilled') {
          setExisting(propRes.value.data || null);
        } else {
          setExisting(null);
        }
        if (docRes.status === 'fulfilled') {
          const data = docRes.value.data;
          setDoctors(Array.isArray(data) ? data : []);
        } else {
          setDoctors([]);
          setError('Could not load supervisors list. Please refresh the page.');
        }
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!form.department) { setDynForm(null); return; }
    fetchStudentForm(form.department, 'propose')
      .then(res => {
        setDynForm(res.data?.fields?.length ? res.data : null);
        const init = {};
        (res.data?.fields || []).forEach(f => { init[f.id] = emptyValueForField(f); });
        setDynValues(init);
      })
      .catch(() => setDynForm(null));
  }, [form.department]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => {
      const next = { ...prev, [name]: value };
      if (name === 'supervisor' && value === prev.co_supervisor) next.co_supervisor = '';
      return next;
    });
  };

const handleTeamSizeChange = (size) => {
    const s = Number(size);
    setForm((prev) => ({
      ...prev,
      team_size: s,
      member_ids: Array(s - 1).fill(''),
      // Clear reason if team_size is normal (2 or 3)
      team_size_reason: (s === 2 || s === 3) ? '' : prev.team_size_reason,
    }));
  };

  const handleMemberChange = (idx, val) => {
    setForm((prev) => {
      const ids = [...prev.member_ids];
      ids[idx] = val;
      return { ...prev, member_ids: ids };
    });
  };

  const hasDynamicFields = dynForm && (dynForm.fields || []).length > 0;
  const totalSteps = hasDynamicFields ? 4 : 3;

  const goNext = () => {
    if (currentStep < totalSteps - 1) setCurrentStep(prev => prev + 1);
  };

  const goPrev = () => {
    if (currentStep > 0) setCurrentStep(prev => prev - 1);
  };

  const goToStep = (idx) => {
    setCurrentStep(idx);
  };

  const isStepValid = (step) => {
    if (step === 0) return form.title.trim() !== '' && form.description.trim() !== '';
    if (step === 1) return form.department !== '' && form.supervisor !== '' && form.project_type !== '';
    if (step === 2) return true;
    if (step === 3) return true;
    return false;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const res = await submitStudentProposal({
        title:            form.title,
        description:      form.description,
        department:       form.department,
        supervisor:       Number(form.supervisor),
        supervisor_ids:   [form.supervisor, form.co_supervisor].filter(Boolean).map(Number),
        team_size:        Number(form.team_size),
        team_size_reason: (Number(form.team_size) === 1 || Number(form.team_size) > 3) ? form.team_size_reason.trim() : '',
        project_type:     form.project_type,
        member_ids:       form.member_ids.filter(Boolean),
        form_id:          dynForm?.id || null,
        field_responses:  dynForm
          ? (dynForm.fields || []).map(f => ({ field: f.id, value: dynValues[f.id] ?? emptyValueForField(f) }))
          : [],
      });
      setExisting(res.data.proposal);
    } catch (err) {
      const data = err.response?.data;
      setError(getProposalErrorMessage(data));
    } finally {
      setSubmitting(false);
    }
  };
    const handleReplaceMember = async (oldMemberId, newMemberUsername) => {
    if (!newMemberUsername.trim()) return;
    setReplaceLoading(true);
    setReplaceError('');
    try {
      await replaceProposalMember(existing.id, oldMemberId, newMemberUsername);
      // Refresh proposal data
      const res = await fetchMyProposal();
      setExisting(res.data || null);
      setReplacingId(null);
    } catch (err) {
      const data = err.response?.data;
      setReplaceError(data?.error || 'Failed to replace member. Please try again.');
    } finally {
      setReplaceLoading(false);
    }
  };

  const refreshExisting = async () => {
    const res = await fetchMyProposal();
    setExisting(res.data || null);
  };

  const handleRemoveRejectedMember = async (memberId) => {
    const nextSize = Math.max(1, Number(existing?.team_size || 1) - 1);
    let reason = '';
    if (nextSize === 1 && !existing?.team_size_reason) {
      reason = window.prompt('أدخل سبب الاستمرار بالمشروع بشكل فردي:') || '';
      if (!reason.trim()) return;
    }
    setReplaceLoading(true);
    setReplaceError('');
    try {
      await removeRejectedProposalMember(existing.id, memberId, reason);
      await refreshExisting();
    } catch (err) {
      setReplaceError(err.response?.data?.error || 'تعذر حذف العضو المرفوض.');
    } finally {
      setReplaceLoading(false);
    }
  };

  const handleReplaceSupervisor = async (oldSupervisorId, newSupervisorId) => {
    if (!newSupervisorId) return;
    setSupervisorActionLoading(true);
    setSupervisorActionError('');
    try {
      await replaceRejectedSupervisor(existing.id, oldSupervisorId, Number(newSupervisorId));
      await refreshExisting();
      setReplacingSupervisorId(null);
    } catch (err) {
      setSupervisorActionError(err.response?.data?.error || 'تعذر استبدال المشرف.');
    } finally {
      setSupervisorActionLoading(false);
    }
  };

  const handleContinueWithOne = async (approvedSupervisorId) => {
    setSupervisorActionLoading(true);
    setSupervisorActionError('');
    try {
      await continueWithApprovedSupervisor(existing.id, approvedSupervisorId);
      await refreshExisting();
    } catch (err) {
      setSupervisorActionError(err.response?.data?.error || 'تعذر المتابعة بالمشرف الموافق.');
    } finally {
      setSupervisorActionLoading(false);
    }
  };
  const openRevision = () => {
    setRevisionForm({
      title: existing?.title || '',
      description: existing?.description || '',
    });
    setRevisionError('');
    setEditingRevision(true);
  };

  const handleRevisionSubmit = async () => {
    if (!revisionForm.title.trim() || !revisionForm.description.trim()) {
      setRevisionError('العنوان والوصف مطلوبان.');
      return;
    }
    setRevisionLoading(true);
    setRevisionError('');
    try {
      await reviseStudentProposal(existing.id, {
        title: revisionForm.title.trim(),
        description: revisionForm.description.trim(),
      });
      await refreshExisting();
      setEditingRevision(false);
    } catch (err) {
      setRevisionError(err.response?.data?.error || 'تعذر تعديل الفكرة وإعادة إرسالها.');
    } finally {
      setRevisionLoading(false);
    }
  };

  /* ── Loading State ── */
  if (loading) {
    return (
      <div className="flex flex-col gap-6 max-w-[1080px] mx-auto px-6 py-8">
        <div className="flex flex-col items-center justify-center py-20">
          <div className="spinner-dark w-8 h-8"></div>
          <p className="text-[var(--text-muted)] mt-3 text-sm">Loading proposal data…</p>
        </div>
      </div>
    );
  }

  /* ── Existing Proposal Status ── */
  if (existing) {
    const meta = STATUS_META[existing.status] || STATUS_META.pending_supervisor;
    const StatusIcon = meta.Icon;
    const stepProgress = STATUS_STEPS[existing.status] || 0;
    const isRejected = existing.status === 'rejected';
    const isApproved = existing.status === 'assigned';

    return (
      <div className="flex flex-col gap-6 max-w-[1080px] mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center text-emerald-500">
            <Clipboard size={20} />
          </div>
          <div>
            <h1 className="text-xl font-extrabold text-[var(--text)] leading-tight">مقترحك</h1>
            <p className="text-sm text-[var(--text-muted)]">تابع حالة مقترح مشروعك المُرسل</p>
          </div>
        </div>

        {/* Status Card */}
        <div className={`bg-[var(--card)] border rounded-[var(--radius)] shadow-[var(--shadow)] overflow-hidden ${isRejected ? 'border-red-500/30' : isApproved ? 'border-emerald-500/30' : 'border-[var(--border)]'}`}>
          <div className="p-6 flex flex-col gap-5">
            {/* Top: Title + Badge */}
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <h3 className="text-lg font-extrabold text-[var(--text)]">{existing.title}</h3>
              <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border ${BADGE_STYLES[meta.color]}`}>
                <StatusIcon size={14} />
                {meta.label}
              </span>
            </div>

            <p className="text-sm text-[var(--text-muted)] leading-relaxed">{existing.description}</p>

            {/* Progress Tracker */}
            {!isRejected && (
              <div className="flex items-center justify-between relative my-4">
                <div className="absolute top-5 left-0 right-0 h-0.5 bg-[var(--border)]" />
                <div className="absolute top-5 left-0 h-0.5 bg-emerald-500 transition-all duration-500" style={{ width: `${(stepProgress / 4) * 100}%` }} />
                {['الأعضاء', 'المشرفون', 'رئيس القسم', 'مقبول'].map((label, i) => (
                  <div key={label} className="flex flex-col items-center gap-2 z-10">
                    <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-colors ${
                      i + 1 <= stepProgress
                        ? 'bg-emerald-500 text-white'
                        : 'bg-[var(--bg-tertiary)] text-[var(--text-muted)] border border-[var(--border)]'
                    }`}>
                      {i + 1 <= stepProgress ? <Check size={14} /> : i + 1}
                    </div>
                    <span className="text-xs text-[var(--text-muted)] font-medium">{label}</span>
                  </div>
                ))}
              </div>
            )}

            {/* Meta Info */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { label: 'القسم', value: existing.department.replace(/_/g, ' ') },
                { label: 'المشرفون', value: (existing.supervisors || []).map((item) => item.name).join('، ') || existing.supervisor_name || '—' },
                { label: 'حجم الفريق', value: `${existing.team_size} student${existing.team_size > 1 ? 's' : ''}` },
                { label: 'مُرسل', value: new Date(existing.created_at).toLocaleDateString() },
              ].map(item => (
                <div key={item.label} className="bg-[var(--bg-tertiary)] p-3 rounded-[var(--radius-sm)] border border-[var(--border-light)]">
                  <span className="text-xs text-[var(--text-muted)] uppercase tracking-wide font-semibold">{item.label}</span>
                  <span className="text-sm text-[var(--text)] font-medium mt-1 block">{item.value}</span>
                </div>
              ))}
            </div>

            {(existing.supervisors || []).length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="text-xs text-[var(--text-muted)] uppercase tracking-wide font-semibold">حالة موافقة المشرفين</span>
                {(existing.supervisors || []).map((supervisor) => {
                  const statusStyle = supervisor.status === 'approved'
                    ? BADGE_STYLES.green
                    : supervisor.status === 'rejected'
                      ? BADGE_STYLES.red
                      : BADGE_STYLES.blue;
                  const statusLabel = supervisor.status === 'approved'
                    ? 'موافق'
                    : supervisor.status === 'rejected'
                      ? 'رافض'
                      : 'بانتظار الرد';
                  return (
                    <div key={supervisor.id} className="rounded-[var(--radius-sm)] border border-[var(--border-light)] bg-[var(--bg-tertiary)] p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-[var(--card)] flex items-center justify-center text-[var(--primary)]">
                          <UserCheck size={16} />
                        </div>
                        <span className="flex-1 text-sm font-semibold text-[var(--text)]">
                          {supervisor.name}{supervisor.is_primary ? ' — المشرف الأساسي' : ' — المشرف المشارك'}
                        </span>
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full border text-xs font-medium ${statusStyle}`}>
                          {statusLabel}
                        </span>
                      </div>

                      {supervisor.rejection_reason && (
                        <p className="mt-2 text-xs leading-5 text-red-600 dark:text-red-400">
                          سبب الرفض: {supervisor.rejection_reason}
                        </p>
                      )}

                      {existing.status === 'supervisor_action_required' && supervisor.status === 'rejected' && (
                        <div className="mt-3">
                          {replacingSupervisorId === supervisor.id ? (
                            <div className="flex flex-col gap-2">
                              <select
                                className={inputCls}
                                defaultValue=""
                                disabled={supervisorActionLoading}
                                onChange={(event) => handleReplaceSupervisor(supervisor.id, event.target.value)}
                              >
                                <option value="">اختر مشرفاً بديلاً</option>
                                {doctors
                                  .filter((doctor) => !(existing.supervisors || []).some((item) => item.id === doctor.id))
                                  .map((doctor) => (
                                    <option key={doctor.id} value={doctor.id}>{doctor.name}</option>
                                  ))}
                              </select>
                              <button
                                type="button"
                                onClick={() => setReplacingSupervisorId(null)}
                                className="self-start text-xs text-[var(--text-muted)] hover:text-[var(--text)]"
                              >
                                إلغاء
                              </button>
                            </div>
                          ) : (
                            <button
                              type="button"
                              onClick={() => setReplacingSupervisorId(supervisor.id)}
                              className="inline-flex items-center gap-1.5 rounded-[var(--radius-sm)] border border-amber-500/20 bg-amber-500/10 px-3 py-1.5 text-xs font-semibold text-amber-600"
                            >
                              <RefreshCw size={13} /> استبدال المشرف
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}

                {existing.can_continue_with_one && (
                  <button
                    type="button"
                    disabled={supervisorActionLoading}
                    onClick={() => {
                      const approved = (existing.supervisors || []).find((item) => item.status === 'approved');
                      if (approved) handleContinueWithOne(approved.id);
                    }}
                    className="inline-flex w-fit items-center gap-2 rounded-[var(--radius-sm)] bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
                  >
                    {supervisorActionLoading ? <Loader2 size={15} className="animate-spin" /> : <CheckCircle size={15} />}
                    المتابعة بالمشرف الموافق فقط
                  </button>
                )}

                {supervisorActionError && (
                  <div className="text-xs text-red-500">{supervisorActionError}</div>
                )}
              </div>
            )}
            {existing.status === 'supervisor_action_required' && (
              <div className="rounded-[var(--radius-sm)] border border-purple-500/20 bg-purple-500/5 p-4">
                {!editingRevision ? (
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="text-sm font-bold text-[var(--text)]">تعديل الفكرة وإعادة طلب الموافقات</div>
                      <p className="mt-1 text-xs leading-5 text-[var(--text-muted)]">
                        عند تعديل العنوان أو الوصف ستُعاد موافقة أعضاء الفريق والمشرفين لأن النسخة الجديدة تختلف عن النسخة السابقة.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={openRevision}
                      className="inline-flex shrink-0 items-center justify-center gap-2 rounded-[var(--radius-sm)] border border-purple-500/20 bg-purple-500/10 px-4 py-2 text-sm font-semibold text-purple-600 hover:bg-purple-500/20"
                    >
                      <RefreshCw size={15} /> تعديل وإعادة الإرسال
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col gap-3">
                    <div>
                      <label className="mb-1.5 block text-sm font-semibold text-[var(--text)]">عنوان الفكرة</label>
                      <input
                        className={inputCls}
                        value={revisionForm.title}
                        onChange={(event) => setRevisionForm((current) => ({ ...current, title: event.target.value }))}
                      />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-sm font-semibold text-[var(--text)]">وصف الفكرة</label>
                      <textarea
                        className={`${inputCls} min-h-[120px] resize-y`}
                        value={revisionForm.description}
                        onChange={(event) => setRevisionForm((current) => ({ ...current, description: event.target.value }))}
                      />
                    </div>
                    <div className="rounded-[var(--radius-sm)] border border-amber-500/20 bg-amber-500/10 p-3 text-xs leading-5 text-amber-700 dark:text-amber-300">
                      سيُطلب من أعضاء الفريق تأكيد مشاركتهم من جديد، وبعد موافقتهم سيصل المقترح المعدّل إلى المشرف أو المشرفين مرة أخرى.
                    </div>
                    {revisionError && <div className="text-xs font-medium text-red-500">{revisionError}</div>}
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        disabled={revisionLoading}
                        onClick={handleRevisionSubmit}
                        className="inline-flex items-center gap-2 rounded-[var(--radius-sm)] bg-purple-600 px-4 py-2 text-sm font-semibold text-white hover:bg-purple-700 disabled:opacity-50"
                      >
                        {revisionLoading ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
                        حفظ وإعادة الإرسال
                      </button>
                      <button
                        type="button"
                        disabled={revisionLoading}
                        onClick={() => { setEditingRevision(false); setRevisionError(''); }}
                        className="rounded-[var(--radius-sm)] border border-[var(--border)] px-4 py-2 text-sm font-semibold text-[var(--text-muted)] hover:bg-[var(--bg-tertiary)]"
                      >
                        إلغاء
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Team Size Reason */}
{existing.team_size_reason && (
  <div className="bg-amber-500/5 p-3.5 rounded-[var(--radius-sm)] border border-amber-500/20">
    <span className="text-xs text-amber-600 dark:text-amber-400 uppercase tracking-wide font-semibold flex items-center gap-1.5">
      <Info size={12} /> Team Size Justification
    </span>
    <p className="text-sm text-[var(--text)] mt-1.5">{existing.team_size_reason}</p>
  </div>
)}
            {/* Team Members */}
            {existing.invitations && existing.invitations.length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="text-xs text-[var(--text-muted)] uppercase tracking-wide font-semibold">أعضاء الفريق</span>
                {existing.invitations.map((inv) => {
                  const InvIcon = inv.status === 'accepted' ? CheckCircle : inv.status === 'rejected' ? XCircle : Clock;
                  const invColor = inv.status === 'accepted' ? 'green' : inv.status === 'rejected' ? 'red' : 'blue';
                  const canReplace = inv.status === 'rejected' && existing.status === 'awaiting_members';
                  const isReplacing = replacingId === inv.invitee_id;

                  return (
                    <div key={inv.id} className="flex flex-col gap-2">
                      <div className="flex items-center gap-3 py-2 border-b border-[var(--border-light)] last:border-0">
                        <div className="w-8 h-8 rounded-full bg-[var(--bg-tertiary)] flex items-center justify-center text-[var(--text-muted)]">
                          <User size={18} />
                        </div>
                        <span className="text-sm text-[var(--text)] font-medium flex-1">{inv.invitee_name}</span>
                        <span className="text-xs text-[var(--text-muted)]">{inv.invitee_id}</span>
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${BADGE_STYLES[invColor]}`}>
                          <InvIcon size={12} />
                          {inv.status.charAt(0).toUpperCase() + inv.status.slice(1)}
                        </span>
                        {canReplace && !isReplacing && (
                          <div className="flex flex-wrap gap-1.5">
                            <button
                              type="button"
                              onClick={() => { setReplacingId(inv.invitee_id); setReplaceError(''); }}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-[var(--radius-sm)] text-xs font-medium bg-amber-500/10 text-amber-600 border border-amber-500/20 hover:bg-amber-500/20 transition-colors"
                            >
                              <RefreshCw size={12} />
                              استبدال
                            </button>
                            <button
                              type="button"
                              disabled={replaceLoading}
                              onClick={() => handleRemoveRejectedMember(inv.invitee_id)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-[var(--radius-sm)] text-xs font-medium bg-red-500/10 text-red-600 border border-red-500/20 hover:bg-red-500/20 transition-colors disabled:opacity-50"
                            >
                              <UserMinus size={12} />
                              حذف والمتابعة بفريق أصغر
                            </button>
                          </div>
                        )}
                      </div>
                      {/* Replace member search */}
                      {isReplacing && (
                        <div className="ml-11 flex flex-col gap-2 p-3 rounded-[var(--radius-sm)] bg-amber-500/5 border border-amber-500/15">
                          <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">
                            Choose a replacement for <strong>{inv.invitee_name}</strong>:
                          </span>
                          <StudentSearch
                            value=""
                            onChange={(username) => handleReplaceMember(inv.invitee_id, username)}
                            placeholder="ابحث عن عضو جديد في الفريق…"
                          />
                          {replaceLoading && (
                            <span className="text-xs text-[var(--text-muted)] flex items-center gap-1">
                              <Loader2 size={12} className="animate-spin" /> جاري الاستبدال…
                            </span>
                          )}
                          {replaceError && (
                            <span className="text-xs text-red-500">{replaceError}</span>
                          )}
                          <button
                            type="button"
                            onClick={() => { setReplacingId(null); setReplaceError(''); }}
                            className="text-xs text-[var(--text-muted)] hover:text-[var(--text)] transition-colors self-start"
                          >
                            إلغاء
                          </button>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* Status Alerts */}
            {existing.status === 'awaiting_members' && (
              <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-blue-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 text-sm">
                <Info size={16} className="shrink-0" />
                <span>بانتظار تأكيد أعضاء الفريق لمشاركتهم.</span>
              </div>
            )}
            {existing.status === 'assigned' && (
              <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-sm">
                <CheckCircle size={16} className="shrink-0" />
                <span>Your idea has been approved and assigned to you. Go to "My Project" to start working!</span>
              </div>
            )}
            {existing.status === 'rejected' && existing.rejection_reason && (
              <div className="flex items-start gap-2 p-3 rounded-[var(--radius-sm)] bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-sm">
                <XCircle size={16} className="shrink-0 mt-0.5" />
                <span><strong>Rejection reason:</strong> {existing.rejection_reason}</span>
              </div>
            )}
            {existing.status === 'pending_supervisor' && (
              <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-blue-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 text-sm">
                <Info size={16} className="shrink-0" />
                <span>
                  بانتظار مراجعة المشرفين الذين لم يردّوا بعد:
                  {' '}
                  <strong>{(existing.supervisors || []).filter((item) => item.status === 'pending').map((item) => item.name).join('، ') || existing.supervisor_name}</strong>
                </span>
              </div>
            )}
            {existing.status === 'supervisor_action_required' && (
              <div className="flex items-start gap-2 p-3 rounded-[var(--radius-sm)] bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-300 text-sm">
                <Info size={16} className="shrink-0 mt-0.5" />
                <span>
                  رفض مشرف واحد أو أكثر المقترح. يمكنك استبدال المشرف الرافض، أو المتابعة بالمشرف الموافق فقط بعد اكتمال الردود.
                </span>
              </div>
            )}
            {existing.status === 'pending_hod' && (
              <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-blue-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 text-sm">
                <Info size={16} className="shrink-0" />
                <span>Approved by supervisor — now awaiting HoD review.</span>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  /* ── New Proposal Form ── */
  return (
    <div className="flex flex-col gap-6 max-w-[1080px] mx-auto px-6 py-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[var(--primary)]/10 flex items-center justify-center text-[var(--primary)]">
          <Lightbulb size={20} />
        </div>
        <div>
          <h1 className="text-xl font-extrabold text-[var(--text)] leading-tight">مقترح مشروع</h1>
          <p className="text-sm text-[var(--text-muted)]">Submit a new idea for approval — fill in each step below</p>
        </div>
      </div>

      {/* Step Indicator */}
      <div className="flex items-center justify-between bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] shadow-[var(--shadow)] p-5">
        {STEPS.slice(0, totalSteps).map((step, i) => {
          const StepIcon = step.Icon;
          const isActive = i === currentStep;
          const isDone = i < currentStep;
          return (
            <div key={step.id} className="flex items-center flex-1 last:flex-none">
              <button
                className={`flex flex-col items-center gap-2 ${isDone ? 'cursor-pointer' : 'cursor-default'}`}
                onClick={() => isDone && goToStep(i)}
                type="button"
              >
                <div className={`w-10 h-10 rounded-full flex items-center justify-center transition-all duration-300 ${
                  isActive ? 'bg-[var(--primary)] text-white shadow-md scale-110' :
                  isDone ? 'bg-emerald-500 text-white' :
                  'bg-[var(--bg-tertiary)] text-[var(--text-muted)] border border-[var(--border)]'
                }`}>
                  {isDone ? <Check size={16} /> : <StepIcon size={16} />}
                </div>
                <span className={`text-xs font-medium whitespace-nowrap ${
                  isActive ? 'text-[var(--primary)]' :
                  isDone ? 'text-emerald-500' :
                  'text-[var(--text-muted)]'
                }`}>{step.label}</span>
              </button>
              {i < totalSteps - 1 && (
                <div className={`flex-1 h-0.5 mx-3 rounded transition-colors ${
                  i < currentStep ? 'bg-emerald-500' : 'bg-[var(--border)]'
                }`} />
              )}
            </div>
          );
        })}
      </div>

      {/* Form Card */}
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] shadow-[var(--shadow)] p-6">
        {error && (
          <div className="flex items-center gap-2 mb-6 p-3 rounded-[var(--radius-sm)] bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-sm">
            <XCircle size={16} className="shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate>
          {/* Step 0: Project Idea */}
          {currentStep === 0 && (
            <div className="flex flex-col gap-5">
              <div className="flex items-center gap-3 pb-4 border-b border-[var(--border)]">
                <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center text-amber-500">
                  <Lightbulb size={20} />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-[var(--text)]">فكرة مشروع</h2>
                  <p className="text-sm text-[var(--text-muted)]">صف فكرة وأهداف مشروع تخرجك</p>
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="p-title" className="text-sm font-semibold text-[var(--text)]">
                  Project Title <span className="text-[var(--danger)]">*</span>
                </label>
                <input
                  id="p-title" name="title" type="text"
                  className={inputCls}
                  value={form.title} onChange={handleChange}
                  placeholder="e.g. Smart Campus Navigation App" required autoFocus
                />
                <span className="text-xs text-[var(--text-muted)]">اختر عنواناً واضحاً ووصفياً لمشروعك</span>
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="p-desc" className="text-sm font-semibold text-[var(--text)]">
                  Project Description <span className="text-[var(--danger)]">*</span>
                </label>
                <textarea
                  id="p-desc" name="description" rows={5}
                  className={`${inputCls} resize-none`}
                  value={form.description} onChange={handleChange}
                  placeholder="صف فكرة مشروعك بالتفصيل — الأهداف، المنهجية، النتائج المتوقعة، والتقنيات التي تخطط لاستخدامها…" required
                />
                <span className="text-xs text-[var(--text-muted)]">كن محدداً: اذكر الأهداف، المنهجية، والمخرجات المتوقعة</span>
              </div>
            </div>
          )}

          {/* Step 1: Department & Supervisor */}
          {currentStep === 1 && (
            <div className="flex flex-col gap-5">
              <div className="flex items-center gap-3 pb-4 border-b border-[var(--border)]">
                <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-500">
                  <Building2 size={20} />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-[var(--text)]">القسم والمشرف</h2>
                  <p className="text-sm text-[var(--text-muted)]">اختر قسمك ومشرفاً واحداً أو مشرفين اثنين</p>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="p-dept" className="text-sm font-semibold text-[var(--text)]">
                    Department <span className="text-[var(--danger)]">*</span>
                  </label>
                  <div className="relative">
                    <select
                      id="p-dept" name="department"
                      className={`${inputCls} appearance-none pr-10`}
                      value={form.department} onChange={handleChange} required
                    >
                      <option value="">اختر القسم</option>
                      {DEPARTMENTS.map((d) => (
                        <option key={d.value} value={d.value}>{d.label}</option>
                      ))}
                    </select>
                    <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none" />
                  </div>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="p-sup" className="text-sm font-semibold text-[var(--text)]">
                    Preferred Supervisor <span className="text-[var(--danger)]">*</span>
                  </label>
                  <div className="relative">
                    <select
                      id="p-sup" name="supervisor"
                      className={`${inputCls} appearance-none pr-10`}
                      value={form.supervisor} onChange={handleChange}
                      required disabled={doctors.length === 0}
                    >
                      <option value="">
                        {doctors.length === 0 ? 'لا يوجد مشرفون متاحون' : 'اختر المشرف'}
                      </option>
                      {doctors.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name}{d.department ? ` (${d.department.replace(/_/g, ' ')})` : ''}
                        </option>
                      ))}
                    </select>
                    <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none" />
                  </div>
                  {doctors.length === 0 && (
                    <span className="text-xs text-amber-500 mt-1">
                      No doctors found in the system. Please contact your department or try refreshing.
                    </span>
                  )}
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="p-co-sup" className="text-sm font-semibold text-[var(--text)]">
                    المشرف الثاني <span className="text-xs font-normal text-[var(--text-muted)]">(اختياري)</span>
                  </label>
                  <div className="relative">
                    <select
                      id="p-co-sup"
                      name="co_supervisor"
                      className={`${inputCls} appearance-none pr-10`}
                      value={form.co_supervisor}
                      onChange={handleChange}
                      disabled={!form.supervisor || doctors.length < 2}
                    >
                      <option value="">المتابعة بمشرف واحد</option>
                      {doctors
                        .filter((doctor) => doctor.id !== Number(form.supervisor))
                        .map((doctor) => (
                          <option key={doctor.id} value={doctor.id}>
                            {doctor.name}{doctor.department ? ` (${doctor.department.replace(/_/g, ' ')})` : ''}
                          </option>
                        ))}
                    </select>
                    <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none" />
                  </div>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="p-type" className="text-sm font-semibold text-[var(--text)]">
                    Project Type <span className="text-[var(--danger)]">*</span>
                  </label>
                  <div className="relative">
                    <select
                      id="p-type" name="project_type"
                      className={`${inputCls} appearance-none pr-10`}
                      value={form.project_type} onChange={handleChange} required
                    >
                      <option value="" disabled>اختر النوع</option>
                      {PROJECT_TYPES.map((pt) => (
                        <option key={pt.value} value={pt.value}>{pt.label}</option>
                      ))}
                    </select>
                    <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none" />
                  </div>
                </div>
              </div>
              <div className="flex items-start gap-2 p-3 rounded-[var(--radius-sm)] bg-blue-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 text-sm">
                <Info size={16} className="shrink-0 mt-0.5" />
                <span>يمكنك اختيار مشرف واحد أو إضافة مشرف ثانٍ. بعد موافقة أعضاء الفريق، يراجع كل مشرف المقترح بشكل مستقل قبل انتقاله إلى رئيس القسم.</span>
              </div>
            </div>
          )}

          {/* Step 2: Team */}
          {currentStep === 2 && (
            <div className="flex flex-col gap-5">
              <div className="flex items-center gap-3 pb-4 border-b border-[var(--border)]">
                <div className="w-10 h-10 rounded-xl bg-[var(--primary)]/10 flex items-center justify-center text-[var(--primary)]">
                  <UserPlus size={20} />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-[var(--text)]">إعداد الفريق</h2>
                  <p className="text-sm text-[var(--text-muted)]">اختر حجم فريقك وادعُ الأعضاء</p>
                </div>
              </div>
              <div className="flex flex-col gap-1.5" style={{ maxWidth: 400 }}>
<label className="text-sm font-semibold text-[var(--text)]">حجم الفريق</label>
<div className="flex gap-3">
  {[1, 2, 3].map((n) => (
    <button
      key={n} type="button"
      className={`flex flex-col items-center px-6 py-3 rounded-xl border-2 transition-all ${
        form.team_size === n
          ? 'border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]'
          : 'border-[var(--border)] bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:border-[var(--primary)]/50'
      }`}
      onClick={() => handleTeamSizeChange(n)}
    >
      <span className="text-2xl font-bold">{n}</span>
      <span className="text-xs mt-1">{n === 1 ? 'فردي' : 'أعضاء'}</span>
    </button>
  ))}
</div>
</div>

{/* Team Size Reason - shown when team_size is 1 or > 3 */}
{(Number(form.team_size) === 1 || Number(form.team_size) > 3) && (
  <div className="flex flex-col gap-1.5">
    <label htmlFor="team-size-reason" className="text-sm font-semibold text-[var(--text)]">
      Justification for team size
      <span className="text-[var(--danger)] ml-0.5">*</span>
      <span className="text-xs text-[var(--text-muted)] font-normal ml-2">
        {Number(form.team_size) === 1 ? 'Why are you working alone?' : 'Why do you need more than 3 members?'}
      </span>
    </label>
    <textarea
      id="team-size-reason"
      name="team_size_reason"
      className={inputCls + ' resize-none'}
      rows={3}
      value={form.team_size_reason}
      onChange={handleChange}
      placeholder={Number(form.team_size) === 1
        ? 'Explain why you are submitting this proposal without team members…'
        : 'Explain why your team needs more than 3 members…'}
      required
    />
  </div>
)}


                            {form.member_ids.map((val, idx) => (
                <div key={idx} className="flex flex-col gap-1.5">
                  <label htmlFor={`p-member-${idx}`} className="text-sm font-semibold text-[var(--text)]">
                    عضو الفريق {idx + 2}
                    <span className="text-xs text-[var(--text-muted)] font-normal ml-2">ابحث بالاسم أو الرقم الجامعي</span>
                  </label>
                  <StudentSearch
                    id={`p-member-${idx}`}
                    value={val}
                    onChange={(username) => handleMemberChange(idx, username)}
                    placeholder="اكتب للبحث عن الطلاب…"
                  />
                </div>
              ))}
              <div className="flex items-start gap-2 p-3 rounded-[var(--radius-sm)] bg-blue-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 text-sm">
                <Info size={16} className="shrink-0 mt-0.5" />
                <span>حجم الفريق <strong>1–4 طلاب</strong>. أنت مُضمّن تلقائياً كقائد للفريق.{(form.team_size === 1 || form.team_size === 4) && ' مطلوب تبرير.'}</span>
              </div>
            </div>
          )}

          {/* Step 3: Dynamic Fields */}
          {currentStep === 3 && hasDynamicFields && (
            <div className="flex flex-col gap-5">
              <div className="flex items-center gap-3 pb-4 border-b border-[var(--border)]">
                <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center text-purple-500">
                  <Clipboard size={20} />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-[var(--text)]">{dynForm.title || 'متطلبات القسم'}</h2>
                  <p className="text-sm text-[var(--text-muted)]">{dynForm.description || 'املأ الحقول الإضافية المطلوبة من قبل قسمك'}</p>
                </div>
              </div>
              {(dynForm.fields || []).map(field => (
                <ProposeDynField key={field.id} field={field}
                  value={dynValues[field.id] ?? emptyValueForField(field)}
                  onChange={val => setDynValues(prev => ({ ...prev, [field.id]: val }))} />
              ))}
            </div>
          )}

          {/* Step 3 (no dynamic): Review */}
          {currentStep === 3 && !hasDynamicFields && (
            <div className="flex flex-col gap-5">
              <div className="flex items-center gap-3 pb-4 border-b border-[var(--border)]">
                <div className="w-10 h-10 rounded-xl bg-purple-500/10 flex items-center justify-center text-purple-500">
                  <Clipboard size={20} />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-[var(--text)]">المراجعة والإرسال</h2>
                  <p className="text-sm text-[var(--text-muted)]">راجع تفاصيل المقترح قبل التقديم</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: 'العنوان', value: form.title || '—' },
                  { label: 'القسم', value: DEPARTMENTS.find(d => d.value === form.department)?.label || '—' },
                  {
                    label: 'المشرفون',
                    value: [form.supervisor, form.co_supervisor]
                      .filter(Boolean)
                      .map((id) => doctors.find((doctor) => doctor.id === Number(id))?.name)
                      .filter(Boolean)
                      .join('، ') || '—',
                  },
                  { label: 'حجم الفريق', value: `${form.team_size} طالب` },
                ].map(item => (
                  <div key={item.label} className="bg-[var(--bg-tertiary)] p-3 rounded-[var(--radius-sm)] border border-[var(--border-light)]">
                    <span className="text-xs text-[var(--text-muted)] uppercase tracking-wide font-semibold">{item.label}</span>
                    <span className="text-sm text-[var(--text)] font-medium mt-1 block">{item.value}</span>
                  </div>
                ))}
              </div>
  <div className="bg-[var(--bg-tertiary)] p-3 rounded-[var(--radius-sm)] border border-[var(--border-light)]">
  <span className="text-xs text-[var(--text-muted)] uppercase tracking-wide font-semibold">الوصف</span>
  <p className="text-sm text-[var(--text)] mt-1">{form.description || '—'}</p>
</div>
{form.team_size_reason && (
  <div className="bg-[var(--bg-tertiary)] p-3 rounded-[var(--radius-sm)] border border-[var(--border-light)]">
    <span className="text-xs text-[var(--text-muted)] uppercase tracking-wide font-semibold">تبرير حجم الفريق</span>
    <p className="text-sm text-[var(--text)] mt-1">{form.team_size_reason}</p>
  </div>
)}
</div>
          )}

          {/* Navigation Buttons */}
          <div className="flex items-center justify-between mt-8 pt-6 border-t border-[var(--border)]">
            {currentStep > 0 ? (
              <button
                type="button"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-[var(--radius-sm)] border border-[var(--border)] text-[var(--text)] font-medium hover:bg-[var(--bg-tertiary)] transition-colors"
                onClick={goPrev}
              >
                <ChevronLeft size={16} />
                السابق
              </button>
            ) : <div />}
            {currentStep < totalSteps - 1 ? (
              <button
                type="button"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-[var(--radius-sm)] bg-[var(--primary)] text-white font-semibold hover:bg-[var(--primary-hover)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={goNext}
                disabled={!isStepValid(currentStep)}
              >
                متابعة
                <ChevronRight size={16} />
              </button>
            ) : (
              <button
                type="submit"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-[var(--radius-sm)] bg-[var(--primary)] text-white font-semibold hover:bg-[var(--primary-hover)] transition-colors hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={submitting}
              >
                {submitting ? (
                  <><Loader2 size={16} className="animate-spin" /> جاري الإرسال…</>
                ) : (
                  <><Send size={16} /> إرسال المقترح</>
                )}
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}

/* ── Dynamic Field Renderer ── */
function ProposeDynField({ field, value, onChange }) {
  const { label, field_type, required, options } = field;
  const lbl = (
    <label className="block text-sm font-semibold text-[var(--text)] mb-1.5">
      {label}
      {required && <span className="text-[var(--danger)] ml-0.5">*</span>}
    </label>
  );

  if (field_type === 'text')
    return <div>{lbl}<input className={inputCls} type="text" value={value} required={required} onChange={e => onChange(e.target.value)} /></div>;
  if (field_type === 'textarea')
    return <div>{lbl}<textarea className={`${inputCls} resize-none`} rows={3} value={value} required={required} onChange={e => onChange(e.target.value)} /></div>;
  if (field_type === 'number')
    return <div>{lbl}<input className={`${inputCls} max-w-[160px]`} type="number" value={value} required={required} min="0" step="any" onChange={e => onChange(e.target.value)} /></div>;
  if (field_type === 'date')
    return <div>{lbl}<input className={inputCls} type="date" value={value} required={required} onChange={e => onChange(e.target.value)} /></div>;
  if (field_type === 'select')
    return (
      <div>{lbl}
        <div className="relative">
          <select className={`${inputCls} appearance-none pr-10`} value={value} required={required} onChange={e => onChange(e.target.value)}>
            <option value="">Select…</option>
            {(options || []).map(o => <option key={o} value={o}>{o}</option>)}
          </select>
          <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none" />
        </div>
      </div>
    );
  if (field_type === 'radio')
    return (
      <div>{lbl}
        <div className="flex flex-col gap-2">
          {(options || []).map(o => (
            <label key={o} className={`flex items-center gap-3 px-4 py-2.5 rounded-[var(--radius-sm)] border cursor-pointer transition-colors ${
              value === o
                ? 'border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]'
                : 'border-[var(--border)] text-[var(--text)] hover:border-[var(--primary)]/50'
            }`}>
              <input type="radio" name={`dyn-${field.id}`} value={o}
                checked={value === o} onChange={() => onChange(o)} required={required}
                className="accent-[var(--primary)]" />
              <span className="text-sm font-medium">{o}</span>
            </label>
          ))}
        </div>
      </div>
    );
  if (field_type === 'checkbox')
    return <div>{lbl}<DynamicCheckboxGroup field={field} value={value} onChange={onChange} /></div>;
  if (field_type === 'file')
    return (
      <div>{lbl}
        <input className={inputCls} type="file" required={required}
          accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.gif"
          onChange={e => { const f = e.target.files?.[0]; if (f) onChange(f.name); }} />
        <span className="text-xs text-[var(--text-muted)] mt-1 block">Accepted: PDF, DOC, DOCX, JPG, PNG</span>
      </div>
    );
  return null;
}