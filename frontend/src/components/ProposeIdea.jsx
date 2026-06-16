import React, { useState, useEffect } from 'react';
import { submitStudentProposal, fetchMyProposal, fetchDoctorsList, fetchStudentForm } from '../api';
import StudentSearch from './StudentSearch';
import DynamicCheckboxGroup from './DynamicCheckboxGroup';
import {
  Send, Users, Clock, RefreshCw, CheckCircle, XCircle, Info,
  Lightbulb, UserPlus, Building2, Clipboard, ChevronRight, ChevronDown, ChevronLeft,
  Loader2, User, Check
} from 'lucide-react';

const DEPARTMENTS = [
  { value: 'software_engineering',    label: 'Software Engineering' },
  { value: 'artificial_intelligence', label: 'Artificial Intelligence' },
  { value: 'information_security',    label: 'Information Security' },
  { value: 'communications',          label: 'Communications' },
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
  awaiting_members:   { label: 'Awaiting Members',    Icon: Users,     color: 'amber' },
  pending_supervisor: { label: 'Pending Supervisor',   Icon: Clock,     color: 'blue' },
  pending_hod:        { label: 'Pending HoD Review',   Icon: RefreshCw, color: 'purple' },
  assigned:           { label: 'Approved & Assigned',   Icon: CheckCircle, color: 'green' },
  rejected:           { label: 'Rejected',              Icon: XCircle,   color: 'red' },
};

const STATUS_STEPS = {
  awaiting_members:   1,
  pending_supervisor: 2,
  pending_hod:        3,
  assigned:           4,
  rejected:           0,
};

const EMPTY = { title: '', description: '', department: '', supervisor: '', team_size: 2, team_size_reason: '', member_ids: [''] };
const emptyValueForField = (field) => field.field_type === 'checkbox' ? [] : '';

const STEPS = [
  { id: 'idea',    label: 'Project Idea',   Icon: Lightbulb },
  { id: 'dept',    label: 'Department',     Icon: Building2 },
  { id: 'team',    label: 'Team',           Icon: UserPlus },
  { id: 'dynamic', label: 'Requirements',   Icon: Clipboard },
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
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleTeamSizeChange = (size) => {
    const s = Number(size);
    setForm((prev) => ({
      ...prev,
      team_size: s,
      member_ids: Array(s - 1).fill(''),
      team_size_reason: (s === 1 || s === 4) ? prev.team_size_reason : '',
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
    if (step === 1) return form.department !== '' && form.supervisor !== '';
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
        team_size:        Number(form.team_size),
        team_size_reason: form.team_size_reason || '',
        member_ids:       form.member_ids.filter(Boolean),
        form_id:          dynForm?.id || null,
        field_responses:  dynForm
          ? (dynForm.fields || []).map(f => ({ field: f.id, value: dynValues[f.id] ?? emptyValueForField(f) }))
          : [],
      });
      setExisting(res.data.proposal);
    } catch (err) {
      const data = err.response?.data;
      if (data?.error) setError(data.error);
      else if (data && typeof data === 'object') setError(Object.values(data).flat().join(' '));
      else setError('Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
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
            <h1 className="text-xl font-extrabold text-[var(--text)] leading-tight">Your Proposal</h1>
            <p className="text-sm text-[var(--text-muted)]">Track your submitted project proposal status</p>
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
                {['Members', 'Supervisor', 'HoD', 'Approved'].map((label, i) => (
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
                { label: 'Department', value: existing.department.replace(/_/g, ' ') },
                { label: 'Supervisor', value: existing.supervisor_name || '—' },
                { label: 'Team Size', value: `${existing.team_size} student${existing.team_size > 1 ? 's' : ''}` },
                { label: 'Submitted', value: new Date(existing.created_at).toLocaleDateString() },
              ].map(item => (
                <div key={item.label} className="bg-[var(--bg-tertiary)] p-3 rounded-[var(--radius-sm)] border border-[var(--border-light)]">
                  <span className="text-xs text-[var(--text-muted)] uppercase tracking-wide font-semibold">{item.label}</span>
                  <span className="text-sm text-[var(--text)] font-medium mt-1 block">{item.value}</span>
                </div>
              ))}
            </div>

            {/* Team Members */}
            {existing.invitations && existing.invitations.length > 0 && (
              <div className="flex flex-col gap-2">
                <span className="text-xs text-[var(--text-muted)] uppercase tracking-wide font-semibold">Team Members</span>
                {existing.invitations.map((inv) => {
                  const InvIcon = inv.status === 'accepted' ? CheckCircle : inv.status === 'rejected' ? XCircle : Clock;
                  const invColor = inv.status === 'accepted' ? 'green' : inv.status === 'rejected' ? 'red' : 'blue';
                  return (
                    <div key={inv.id} className="flex items-center gap-3 py-2 border-b border-[var(--border-light)] last:border-0">
                      <div className="w-8 h-8 rounded-full bg-[var(--bg-tertiary)] flex items-center justify-center text-[var(--text-muted)]">
                        <User size={18} />
                      </div>
                      <span className="text-sm text-[var(--text)] font-medium flex-1">{inv.invitee_name}</span>
                      <span className="text-xs text-[var(--text-muted)]">{inv.invitee_id}</span>
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${BADGE_STYLES[invColor]}`}>
                        <InvIcon size={12} />
                        {inv.status.charAt(0).toUpperCase() + inv.status.slice(1)}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Status Alerts */}
            {existing.status === 'awaiting_members' && (
              <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-blue-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 text-sm">
                <Info size={16} className="shrink-0" />
                <span>Waiting for team members to confirm their participation.</span>
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
                <span>Waiting for <strong>{existing.supervisor_name}</strong> to review your proposal.</span>
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
          <h1 className="text-xl font-extrabold text-[var(--text)] leading-tight">Project Proposal</h1>
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
                  <h2 className="text-lg font-bold text-[var(--text)]">Project Idea</h2>
                  <p className="text-sm text-[var(--text-muted)]">Describe your graduation project concept and objectives</p>
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
                <span className="text-xs text-[var(--text-muted)]">Choose a clear, descriptive title for your project</span>
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="p-desc" className="text-sm font-semibold text-[var(--text)]">
                  Project Description <span className="text-[var(--danger)]">*</span>
                </label>
                <textarea
                  id="p-desc" name="description" rows={5}
                  className={`${inputCls} resize-none`}
                  value={form.description} onChange={handleChange}
                  placeholder="Describe your project idea in detail — goals, methodology, expected outcomes, and technologies you plan to use…" required
                />
                <span className="text-xs text-[var(--text-muted)]">Be specific: include objectives, methodology, and expected deliverables</span>
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
                  <h2 className="text-lg font-bold text-[var(--text)]">Department & Supervisor</h2>
                  <p className="text-sm text-[var(--text-muted)]">Select your department and preferred supervisor</p>
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                      <option value="">Select Department</option>
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
                        {doctors.length === 0 ? 'No supervisors available' : 'Select Supervisor'}
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
              </div>
              <div className="flex items-start gap-2 p-3 rounded-[var(--radius-sm)] bg-blue-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 text-sm">
                <Info size={16} className="shrink-0 mt-0.5" />
                <span>The supervisor you select will review and approve your proposal before it goes to the Head of Department.</span>
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
                  <h2 className="text-lg font-bold text-[var(--text)]">Team Setup</h2>
                  <p className="text-sm text-[var(--text-muted)]">Choose your team size and invite members</p>
                </div>
              </div>
              <div className="flex flex-col gap-1.5" style={{ maxWidth: 400 }}>
                <label className="text-sm font-semibold text-[var(--text)]">Team Size</label>
                <div className="flex gap-3">
                  {[1, 2, 3, 4].map((n) => (
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
                      <span className="text-xs mt-1">{n === 1 ? 'Solo' : 'Members'}</span>
                    </button>
                  ))}
                </div>
                              </div>
              {(form.team_size === 1 || form.team_size === 4) && (
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="team_size_reason" className="text-sm font-semibold text-[var(--text)]">
                    Justification for {form.team_size === 1 ? 'Solo Project' : '4-Member Team'} <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    id="team_size_reason"
                    name="team_size_reason"
                    value={form.team_size_reason}
                    onChange={handleChange}
                    placeholder={form.team_size === 1 ? 'Explain why this project should be done individually...' : 'Explain why this project requires 4 team members...'}
                    rows={3}
                    required
                    className={inputCls}
                  />
                  <span className="text-xs text-[var(--text-muted)]">Required: please provide a justification for this team size.</span>
                </div>
              )}
                            {form.member_ids.map((val, idx) => (
                <div key={idx} className="flex flex-col gap-1.5">
                  <label htmlFor={`p-member-${idx}`} className="text-sm font-semibold text-[var(--text)]">
                    Team Member {idx + 2}
                    <span className="text-xs text-[var(--text-muted)] font-normal ml-2">Search by name or university ID</span>
                  </label>
                  <StudentSearch
                    id={`p-member-${idx}`}
                    value={val}
                    onChange={(username) => handleMemberChange(idx, username)}
                    placeholder="Type to search students…"
                  />
                </div>
              ))}
              <div className="flex items-start gap-2 p-3 rounded-[var(--radius-sm)] bg-blue-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 text-sm">
                <Info size={16} className="shrink-0 mt-0.5" />
                <span>Team size is <strong>1–4 students</strong>. You are automatically included as the team leader.{(form.team_size === 1 || form.team_size === 4) && ' A justification is required.'}</span>
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
                  <h2 className="text-lg font-bold text-[var(--text)]">{dynForm.title || 'Department Requirements'}</h2>
                  <p className="text-sm text-[var(--text-muted)]">{dynForm.description || 'Fill in the additional fields required by your department'}</p>
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
                  <h2 className="text-lg font-bold text-[var(--text)]">Review & Submit</h2>
                  <p className="text-sm text-[var(--text-muted)]">Review your proposal details before submitting</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: 'Title', value: form.title || '—' },
                  { label: 'Department', value: DEPARTMENTS.find(d => d.value === form.department)?.label || '—' },
                  { label: 'Supervisor', value: doctors.find(d => d.id === Number(form.supervisor))?.name || '—' },
                  { label: 'Team Size', value: `${form.team_size} students` },
                ].map(item => (
                  <div key={item.label} className="bg-[var(--bg-tertiary)] p-3 rounded-[var(--radius-sm)] border border-[var(--border-light)]">
                    <span className="text-xs text-[var(--text-muted)] uppercase tracking-wide font-semibold">{item.label}</span>
                    <span className="text-sm text-[var(--text)] font-medium mt-1 block">{item.value}</span>
                  </div>
                ))}
              </div>
              <div className="bg-[var(--bg-tertiary)] p-3 rounded-[var(--radius-sm)] border border-[var(--border-light)]">
                <span className="text-xs text-[var(--text-muted)] uppercase tracking-wide font-semibold">Description</span>
                <p className="text-sm text-[var(--text)] mt-1">{form.description || '—'}</p>
              </div>
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
                Previous
              </button>
            ) : <div />}
            {currentStep < totalSteps - 1 ? (
              <button
                type="button"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-[var(--radius-sm)] bg-[var(--primary)] text-white font-semibold hover:bg-[var(--primary-hover)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={goNext}
                disabled={!isStepValid(currentStep)}
              >
                Continue
                <ChevronRight size={16} />
              </button>
            ) : (
              <button
                type="submit"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-[var(--radius-sm)] bg-[var(--primary)] text-white font-semibold hover:bg-[var(--primary-hover)] transition-colors hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={submitting}
              >
                {submitting ? (
                  <><Loader2 size={16} className="animate-spin" /> Submitting…</>
                ) : (
                  <><Send size={16} /> Submit Proposal</>
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