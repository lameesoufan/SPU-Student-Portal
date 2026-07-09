import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  ArrowRight, Save, X, CheckCircle2, ChevronLeft, ChevronRight,
  Gavel, Building2, BookOpen, Users, Search, UserCheck,
  Plus, AlertTriangle, Info, Calendar,
} from 'lucide-react';
import {
  fetchDoctors, createCommitteeTemplate, updateCommitteeTemplate,
  fetchCommitteeTemplate,
} from '../../api';
import {
  COMMITTEE_TYPES, PROJECT_TYPES, DEPARTMENTS,
  COMMITTEE_TYPE_COLORS, DEPARTMENT_COLORS,
} from './constants';
import './TemplateForm.css';

/* ────────────────────────────────────────────────────────────────────────── */
/* TemplateForm — REVISED DESIGN (3-step wizard)                                */
/*   Step 1: classification (committee type, department, project type, sem)     */
/*   Step 2: doctors (chair + members)                                          */
/*   Step 3: review & submit                                                    */
/*                                                                              */
/* REVISED: `committees_count` and `max_projects_per_committee` have been       */
/* REMOVED. Each template now creates exactly ONE committee. The Dean creates   */
/* multiple templates for the same (committee_type × department × project_type) */
/* when more capacity is needed. The distribution algorithm balances projects   */
/* evenly across all matching committees (10 per committee by default).         */
/* ────────────────────────────────────────────────────────────────────────── */

const STEPS = [
  { id: 1, label: 'Committee Type',   icon: Gavel },
  { id: 2, label: 'Faculty',          icon: Users },
  { id: 3, label: 'Review',           icon: CheckCircle2 },
];

export default function TemplateForm({ onBack, editId, onSaved }) {
  const [step, setStep]             = useState(1);
  const [doctors, setDoctors]       = useState([]);
  const [doctorsLoading, setDoctorsLoading] = useState(true);
  const [search, setSearch]         = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]           = useState('');
  const [success, setSuccess]       = useState('');

  // Form state — REVISED: removed committees_count & max_projects_per_committee
  const [form, setForm] = useState({
    committee_type: '',
    department: '',
    project_type: '',
    semester: `Fall ${new Date().getFullYear()}`,
    chair: null,
    members: [],
    name: '',
    discussion_duration: '',   // minutes — required for solver
  });

  /* ── Load doctors list ───────────────────────────────────────────────── */
  useEffect(() => {
    let active = true;
    setDoctorsLoading(true);
    fetchDoctors()
      .then((res) => { if (active) setDoctors(res.data); })
      .catch(()    => { if (active) setDoctors([]); })
      .finally(()  => { if (active) setDoctorsLoading(false); });
    return () => { active = false; };
  }, []);

  /* ── Load template if editing ────────────────────────────────────────── */
  useEffect(() => {
    if (!editId) return;
    let active = true;
    fetchCommitteeTemplate(editId)
      .then((res) => {
        if (!active) return;
        const t = res.data;
        setForm({
          committee_type: t.committee_type || '',
          department: t.department || '',
          project_type: t.project_type || '',
          semester: t.semester || '',
          chair: t.chair || null,
          members: Array.isArray(t.members) ? t.members : [],
          name: t.name || '',
          discussion_duration: t.discussion_duration || '',
        });
      })
      .catch((err) => {
        if (active) setError(err.response?.data?.detail || 'Failed to load composition.');
      });
    return () => { active = false; };
  }, [editId]);

  /* ── Filtered doctors by search ──────────────────────────────────────── */
  const filteredDoctors = useMemo(() => {
    if (!search.trim()) return doctors;
    const q = search.toLowerCase();
    return doctors.filter((d) => {
      const fullName = `${d.first_name || ''} ${d.last_name || ''} ${d.username || ''}`.toLowerCase();
      return fullName.includes(q);
    });
  }, [doctors, search]);

  /* ── Doctor selection handlers ───────────────────────────────────────── */
  const setChair = (doctorId) => {
    setForm((f) => {
      const members = f.members.filter((id) => id !== doctorId);
      return { ...f, chair: doctorId, members };
    });
  };

  const toggleMember = (doctorId) => {
    setForm((f) => {
      if (f.chair === doctorId) return f;
      const exists = f.members.includes(doctorId);
      return {
        ...f,
        members: exists
          ? f.members.filter((id) => id !== doctorId)
          : [...f.members, doctorId],
      };
    });
  };

  const removeDoctor = (doctorId) => {
    setForm((f) => ({
      ...f,
      chair: f.chair === doctorId ? null : f.chair,
      members: f.members.filter((id) => id !== doctorId),
    }));
  };

  /* ── Doctor helpers ──────────────────────────────────────────────────── */
  const getDoctor = (id) => doctors.find((d) => d.id === id);
  const doctorName = (id) => {
    if (!id) return '—';
    const d = getDoctor(id);
    if (!d) return `#${id}`;
    return ((d.first_name || '') + ' ' + (d.last_name || '')).trim() || d.username;
  };

  /* ── Validation per step ─────────────────────────────────────────────── */
  const stepValid = useMemo(() => {
    if (step === 1) {
      return !!(form.committee_type && form.department && form.project_type && form.semester && form.discussion_duration);
    }
    if (step === 2) return !!form.chair;  // chair required; members optional
    if (step === 3) return true;
    return false;
  }, [step, form]);

  const canSubmit = useMemo(() => {
    return !!(form.committee_type && form.department && form.project_type
          && form.semester && form.chair && form.discussion_duration);
  }, [form]);

  /* ── Navigation ──────────────────────────────────────────────────────── */
  const nextStep = () => { if (stepValid && step < 3) { setError(''); setStep(step + 1); } };
  const prevStep = () => { if (step > 1) { setError(''); setStep(step - 1); } };

  /* ── Submit ──────────────────────────────────────────────────────────── */
  const handleSubmit = async () => {
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    setError('');
    setSuccess('');
    try {
      const payload = {
        committee_type: form.committee_type,
        department:     form.department,
        project_type:   form.project_type,
        semester:       form.semester,
        chair:          form.chair,
        members:        form.members,
        name: form.name || '',
        discussion_duration: parseInt(form.discussion_duration) || 15,
      };
      let result;
      if (editId) {
        result = await updateCommitteeTemplate(editId, payload);
        setSuccess('Composition updated successfully.');
      } else {
        result = await createCommitteeTemplate(payload);
        setSuccess('Composition created and committee generated successfully.');
      }
      setTimeout(() => {
        if (onSaved) onSaved(result.data);
        else if (onBack) onBack();
      }, 1200);
    } catch (err) {
      const data = err.response?.data || {};
      const msg = typeof data === 'object'
        ? Object.entries(data).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`).join(' · ')
        : String(data);
      setError(msg || 'Save failed. Check data and try again.');
    } finally {
      setSubmitting(false);
    }
  };

  /* ── Render ──────────────────────────────────────────────────────────── */
  return (
    <div className="ctf-page">
      {/* Header */}
      <div className="ctf-header">
        <div className="ctf-header-left">
          <div className="ctf-header-icon">
            <Plus size={22} />
          </div>
          <div>
            <h1 className="ctf-header-title">
              {editId ? 'Edit Composition' : 'New Committee Composition'}
            </h1>
            <p className="ctf-header-sub">
              Select committee type, department, project type, then choose faculty. One committee will be generated per composition — create multiple compositions when more capacity is needed.
            </p>
          </div>
        </div>
        <button className="ctf-back" onClick={onBack}>
          <ArrowRight size={14} /> Back
        </button>
      </div>

      {/* Alerts */}
      {error && (
        <div className="ctf-alert ctf-alert-error">
          <AlertTriangle size={16} />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="ctf-alert ctf-alert-success">
          <CheckCircle2 size={16} />
          <span>{success}</span>
        </div>
      )}

      {/* Stepper */}
      <div className="ctf-stepper">
        {STEPS.map((s) => {
          const isActive   = step === s.id;
          const isComplete = step > s.id;
          const Icon       = s.icon;
          return (
            <div
              key={s.id}
              className={`ctf-step ${isActive ? 'is-active' : ''} ${isComplete ? 'is-complete' : ''}`}
              onClick={() => { if (s.id < step) setStep(s.id); }}
            >
              <div className="ctf-step-circle">
                {isComplete ? <CheckCircle2 size={18} /> : (isActive ? <Icon size={16} /> : s.id)}
              </div>
              <span className="ctf-step-label">{s.label}</span>
            </div>
          );
        })}
      </div>

      {/* Step 1: Classification ───────────────────────────────────────── */}
      {step === 1 && (
        <div className="ctf-section">
          <div className="ctf-section-header">
            <span className="ctf-section-num">1</span>
            <h2 className="ctf-section-title">Composition Classification</h2>
          </div>
          <div className="ctf-section-body">

            {/* Committee Type */}
            <div className="ctf-field">
              <label className="ctf-label">
                Committee Type <span className="ctf-label-required">*</span>
              </label>
              <div className="ctf-options">
                {COMMITTEE_TYPES.map((ct) => {
                  const color = COMMITTEE_TYPE_COLORS[ct.value] || {};
                  const sel = form.committee_type === ct.value;
                  return (
                    <div
                      key={ct.value}
                      className={`ctf-option ${sel ? 'is-selected' : ''}`}
                      onClick={() => setForm((f) => ({ ...f, committee_type: ct.value }))}
                    >
                      <div className="ctf-option-icon" style={sel ? {
                        background: color.text,
                        color: '#fff',
                      } : {}}>
                        <Gavel size={16} />
                      </div>
                      <div className="ctf-option-text">
                        <span className="ctf-option-label">{ct.label_ar}</span>
                        <span className="ctf-option-desc">{ct.label_en}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Department */}
            <div className="ctf-field">
              <label className="ctf-label">
                Department <span className="ctf-label-required">*</span>
              </label>
              <div className="ctf-options">
                {DEPARTMENTS.map((d) => {
                  const color = DEPARTMENT_COLORS[d.value] || {};
                  const sel = form.department === d.value;
                  return (
                    <div
                      key={d.value}
                      className={`ctf-option ${sel ? 'is-selected' : ''}`}
                      onClick={() => setForm((f) => ({ ...f, department: d.value }))}
                    >
                      <div className="ctf-option-icon" style={sel ? {
                        background: color.text,
                        color: '#fff',
                      } : {}}>
                        <Building2 size={16} />
                      </div>
                      <div className="ctf-option-text">
                        <span className="ctf-option-label">{d.label_ar}</span>
                        <span className="ctf-option-desc">{d.label_en}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Project Type + Semester */}
            <div className="ctf-grid-2">
              <div className="ctf-field">
                <label className="ctf-label">
                  Project Type <span className="ctf-label-required">*</span>
                </label>
                <div className="ctf-options">
                  {PROJECT_TYPES.map((pt) => {
                    const sel = form.project_type === pt.value;
                    return (
                      <div
                        key={pt.value}
                        className={`ctf-option ${sel ? 'is-selected' : ''}`}
                        onClick={() => setForm((f) => ({ ...f, project_type: pt.value }))}
                      >
                        <div className="ctf-option-icon">
                          <BookOpen size={16} />
                        </div>
                        <div className="ctf-option-text">
                          <span className="ctf-option-label">{pt.label_ar}</span>
                          <span className="ctf-option-desc">{pt.label_en}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="ctf-field">
                <label className="ctf-label">
                  Semester <span className="ctf-label-required">*</span>
                </label>
                <input
                  type="text"
                  className="ctf-input"
                  value={form.semester}
                  onChange={(e) => setForm((f) => ({ ...f, semester: e.target.value }))}
                  placeholder="Example: Fall 2025"
                />
                <span className="ctf-hint">Used to filter projects and committees later.</span>
              </div>
            </div>

            {/* Discussion duration — REQUIRED for solver */}
            <div className="ctf-field">
              <label className="ctf-label">
                Discussion Duration per Project (minutes) <span className="ctf-label-required">*</span>
              </label>
              <input
                type="number"
                className="ctf-input"
                min="5"
                step="5"
                value={form.discussion_duration}
                onChange={(e) => setForm((f) => ({ ...f, discussion_duration: e.target.value }))}
                placeholder={
                  form.committee_type === 'final_discussion' ? 'مثال: 30' :
                  form.committee_type === 'technical' ? 'مثال: 20' : 'مثال: 15'
                }
              />
              <span className="ctf-hint">
                مدة المناقشة لكل مشروع بالدقائق — تُستخدم من قبل الـ Solver لحساب مدة اللجنة الكلية.
              </span>
            </div>

            {/* Optional name */}
            <div className="ctf-field">
              <label className="ctf-label">
                Custom Composition Name
                <span className="ctf-section-optional" style={{ marginRight: 8 }}>Optional</span>
              </label>
              <input
                type="text"
                className="ctf-input"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="Leave blank to auto-generate from type, department, and project"
              />
            </div>

            {/* Info banner — explain the new design */}
            <div className="ctf-alert ctf-alert-info">
              <Info size={16} />
              <span>
                Each composition creates only one committee. If you need more capacity for the same type (e.g., Seminar 2 - Software - Graduation 2),
                create multiple compositions with the same classification — the distribution algorithm will evenly redistribute projects across all matching committees.
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Step 2: Doctors ──────────────────────────────────────────────── */}
      {step === 2 && (
        <div className="ctf-section">
          <div className="ctf-section-header">
            <span className="ctf-section-num">2</span>
            <h2 className="ctf-section-title">Faculty</h2>
            <span className="ctf-section-optional">Chair + Members</span>
          </div>
          <div className="ctf-section-body">

            {/* Selected doctors summary */}
            <div className="ctf-field">
              <label className="ctf-label">Currently Selected</label>
              <div className="ctf-selected-summary">
                {!form.chair && form.members.length === 0 && (
                  <span className="ctf-selected-empty">
                    No faculty selected yet — choose the chair and members from the list below.
                  </span>
                )}
                {form.chair && (
                  <span className="ctf-chip is-chair" title="Committee Chair">
                    <span className="ctf-chip-avatar">
                      {doctorName(form.chair).charAt(0)}
                    </span>
                    <span>{doctorName(form.chair)}</span>
                    <span className="ctf-doctor-role is-chair" style={{ margin: '0 4px' }}>Chair</span>
                    <button
                      className="ctf-chip-remove"
                      onClick={() => removeDoctor(form.chair)}
                      title="Remove"
                    >
                      <X size={11} />
                    </button>
                  </span>
                )}
                {form.members.map((mid) => (
                  <span key={mid} className="ctf-chip" title="Member">
                    <span className="ctf-chip-avatar">
                      {doctorName(mid).charAt(0)}
                    </span>
                    <span>{doctorName(mid)}</span>
                    <span className="ctf-doctor-role is-member" style={{ margin: '0 4px' }}>Member</span>
                    <button
                      className="ctf-chip-remove"
                      onClick={() => removeDoctor(mid)}
                      title="Remove"
                    >
                      <X size={11} />
                    </button>
                  </span>
                ))}
              </div>
            </div>

            {/* Search */}
            <div className="ctf-field">
              <label className="ctf-label">Search for Faculty</label>
              <div className="ctf-doctor-search">
                <input
                  type="search"
                  className="ctf-input"
                  placeholder="Search by name or ID..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <Search size={16} className="ctf-doctor-search-icon" />
              </div>
            </div>

            {/* Doctor list */}
            <div className="ctf-field">
              <label className="ctf-label">
                Faculty List
                <span className="ctf-section-optional" style={{ marginRight: 8 }}>
                  Click "Set as Chair" to select committee chair, or check the box to add as member
                </span>
              </label>

              {doctorsLoading ? (
                <div className="ctf-loading">
                  <div className="ctf-spinner" /> Loading faculty…
                </div>
              ) : filteredDoctors.length === 0 ? (
                <div className="ctf-alert ctf-alert-info">
                  <Info size={16} />
                  <span>No faculty matching the search.</span>
                </div>
              ) : (
                <div className="ctf-doctor-list">
                  {filteredDoctors.map((d) => {
                    const fullName = ((d.first_name || '') + ' ' + (d.last_name || '')).trim() || d.username;
                    const initial  = fullName.charAt(0).toUpperCase();
                    const isChair  = form.chair === d.id;
                    const isMember = form.members.includes(d.id);
                    return (
                      <div
                        key={d.id}
                        className={`ctf-doctor-row ${isMember ? 'is-selected' : ''}`}
                      >
                        <div
                          className="ctf-doctor-checkbox"
                          onClick={() => toggleMember(d.id)}
                          role="checkbox"
                          aria-checked={isMember}
                        >
                          {isMember && <CheckCircle2 size={12} />}
                        </div>
                        <div className="ctf-doctor-avatar">{initial}</div>
                        <div className="ctf-doctor-info">
                          <span className="ctf-doctor-name">{fullName}</span>
                          <span className="ctf-doctor-meta">#{d.username} · {d.department}</span>
                        </div>
                        <button
                          className={`ctf-doctor-role ${isChair ? 'is-chair' : 'is-member'}`}
                          onClick={() => isChair ? removeDoctor(d.id) : setChair(d.id)}
                          style={{
                            cursor: 'pointer',
                            background: isChair ? 'rgba(245, 158, 11, 0.12)' : 'transparent',
                            color: isChair ? '#fbbf24' : 'var(--text-muted)',
                            border: isChair ? '1px solid rgba(245, 158, 11, 0.25)' : '1px solid var(--border)',
                            padding: '4px 10px',
                            borderRadius: 999,
                            fontSize: 10,
                            fontWeight: 700,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                          }}
                        >
                          <UserCheck size={11} />
                          {isChair ? 'Chair' : 'Set as Chair'}
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Step 3: Review ───────────────────────────────────────────────── */}
      {step === 3 && (
        <div className="ctf-section">
          <div className="ctf-section-header">
            <span className="ctf-section-num">3</span>
            <h2 className="ctf-section-title">Review & Save</h2>
          </div>
          <div className="ctf-section-body">

            <div className="ctf-review-grid">
              <ReviewItem icon={<Gavel size={16} />} label="Committee Type">
                {COMMITTEE_TYPES.find(c => c.value === form.committee_type)?.label_ar || '—'}
              </ReviewItem>
              <ReviewItem icon={<Building2 size={16} />} label="Department">
                {DEPARTMENTS.find(d => d.value === form.department)?.label_ar || '—'}
              </ReviewItem>
              <ReviewItem icon={<BookOpen size={16} />} label="Project Type">
                {PROJECT_TYPES.find(p => p.value === form.project_type)?.label_ar || '—'}
              </ReviewItem>
              <ReviewItem icon={<Calendar size={16} />} label="Semester">
                {form.semester || '—'}
              </ReviewItem>
              <ReviewItem icon={<UserCheck size={16} />} label="Committee Chair">
                {doctorName(form.chair)}
              </ReviewItem>
              <ReviewItem icon={<Users size={16} />} label="Members Count">
                {form.members.length} faculty
              </ReviewItem>
            </div>

            {/* Members list */}
            {form.members.length > 0 && (
              <div className="ctf-field">
                <label className="ctf-label">Selected Members</label>
                <div className="ctf-selected-summary">
                  {form.members.map((mid) => (
                    <span key={mid} className="ctf-chip">
                      <span className="ctf-chip-avatar">{doctorName(mid).charAt(0)}</span>
                      <span>{doctorName(mid)}</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="ctf-alert ctf-alert-info">
              <Info size={16} />
              <span>
                Upon saving, only one committee will be generated from this composition. You can later edit the committee
                (change faculty, scheduling, swap projects). If you need more capacity, create another composition with the same classification.
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Action bar */}
      <div className="ctf-actions">
        <div className="ctf-actions-left">
          <button className="ctf-btn ctf-btn-ghost" onClick={onBack} disabled={submitting}>
            <X size={14} /> Cancel
          </button>
        </div>
        <div className="ctf-actions-right">
          {step > 1 && (
            <button className="ctf-btn" onClick={prevStep} disabled={submitting}>
              <ChevronRight size={14} /> Previous
            </button>
          )}
          {step < 3 ? (
            <button
              className="ctf-btn ctf-btn-primary"
              onClick={nextStep}
              disabled={!stepValid}
            >
              Next <ChevronLeft size={14} />
            </button>
          ) : (
            <button
              className="ctf-btn ctf-btn-success"
              onClick={handleSubmit}
              disabled={!canSubmit || submitting}
            >
              {submitting
                ? (<><div className="ctf-spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Saving…</>)
                : (<><Save size={14} /> {editId ? 'Update Composition' : 'Save Composition'}</>)}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Sub-component: Review Item ──────────────────────────────────────────── */
function ReviewItem({ icon, label, children }) {
  return (
    <div className="ctf-review-item">
      <div className="ctf-review-icon">{icon}</div>
      <div style={{ flex: 1 }}>
        <div className="ctf-review-label">{label}</div>
        <div className="ctf-review-value">{children}</div>
      </div>
    </div>
  );
}
