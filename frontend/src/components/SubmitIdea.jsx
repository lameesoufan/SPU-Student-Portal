import React, { useState } from 'react';
import { submitProjectIdea } from '../api';
import { PROJECT_TYPES } from '../lib/constants';
import { ChevronLeft, Lightbulb, CheckCircle, Send, Loader2, Info, AlertCircle } from 'lucide-react';

const DEPARTMENTS = [
  { value: 'software_engineering',    label: 'Software Engineering' },
  { value: 'artificial_intelligence', label: 'Artificial Intelligence' },
  { value: 'information_security',    label: 'Information Security' },
  { value: 'communications',          label: 'Communications' },
  { value: 'control_robotics',        label: 'Control & Robotics' },
];

const EMPTY = { title: '', description: '', department: '', required_skills: '', max_team_size: 2, project_type: '' };

const inputCls = "w-full bg-[var(--input-bg)] text-[var(--text)] border border-[var(--border)] rounded-[var(--radius-sm)] px-4 py-2.5 text-sm outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] transition-colors placeholder:text-[var(--text-faint)]";

export default function SubmitIdea({ onBack }) {
  const [form, setForm]       = useState(EMPTY);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError]     = useState('');

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    e.stopPropagation();   // ← منع انتشار الحدث
    if (loading) return;   // ← حماية إضافية
    setError('');
    setLoading(true);
    try {
            await submitProjectIdea({ ...form, max_team_size: Number(form.max_team_size) });
      // تأخير بسيط لمنع الإرسال المتكرر من React StrictMode
      await new Promise(r => setTimeout(r, 300));
      setSuccess(true);
      setForm(EMPTY);
    } catch (err) {
      const data = err.response?.data;
      if (data && typeof data === 'object') {
        setError(Object.values(data).flat().join(' '));
      } else {
        setError('Something went wrong. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="flex flex-col gap-6 max-w-[800px] mx-auto px-6 py-8">
        {/* ── Header ── */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center text-amber-500">
            <Lightbulb size={20} />
          </div>
          <div>
            <h1 className="text-xl font-extrabold text-[var(--text)] leading-tight">Submit New Project Idea</h1>
            <p className="text-sm text-[var(--text-muted)]">Propose a graduation project</p>
          </div>
        </div>

        {/* ── Success Card ── */}
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] shadow-[var(--shadow)] overflow-hidden">
          <div className="p-12 text-center">
            <div className="w-[72px] h-[72px] mx-auto mb-5 flex items-center justify-center bg-emerald-500/10 rounded-full text-emerald-500">
              <CheckCircle size={40} />
            </div>
            <h3 className="text-[22px] font-extrabold text-[var(--text)] mb-2">Idea Submitted Successfully</h3>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-600 border border-amber-500/20">
              <Loader2 size={12} />
              Pending Review
            </span>
            <p className="text-[var(--text-muted)] text-[15px] mt-3">Your project idea has been received and is awaiting department review.</p>
            <div className="flex gap-3 mt-6 flex-wrap justify-center">
              <button
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-[var(--radius-sm)] bg-[var(--primary)] text-white font-semibold text-sm hover:bg-[var(--primary-hover)] transition-colors"
                onClick={() => setSuccess(false)}
              >
                Submit Another Idea
              </button>
              <button
                className="inline-flex items-center gap-2 bg-transparent border border-[var(--border)] text-[var(--text)] font-medium py-2.5 px-5 rounded-[var(--radius-sm)] hover:bg-[var(--bg-tertiary)] transition-colors text-sm"
                onClick={onBack}
              >
                View My Ideas
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 max-w-[800px] mx-auto px-6 py-8">
      {/* ── Header ── */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center text-amber-500">
          <Lightbulb size={20} />
        </div>
        <div className="flex-1">
          <h1 className="text-xl font-extrabold text-[var(--text)] leading-tight">Submit New Project Idea</h1>
          <p className="text-sm text-[var(--text-muted)]">Fill in the details below to propose a new graduation project.</p>
        </div>
        <button
          className="inline-flex items-center gap-1.5 text-sm font-medium text-[var(--text-muted)] hover:text-[var(--text)] transition-colors"
          onClick={onBack}
        >
          <ChevronLeft size={16} />
          Back
        </button>
      </div>

      {/* ── Info Banner ── */}
      <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-blue-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 text-sm">
        <Info size={16} className="shrink-0" />
        <span>Your idea will be saved as <strong>Pending Review</strong> and forwarded to the department for evaluation.</span>
      </div>

      {/* ── Form Card ── */}
      <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] shadow-[var(--shadow)] overflow-hidden">
        <div className="p-8">
          {error && (
            <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-sm mb-6" role="alert">
              <AlertCircle size={16} className="shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
            {/* Title */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="title" className="text-sm font-semibold text-[var(--text)]">
                Title <span className="text-red-500">*</span>
              </label>
              <input
                id="title" name="title" type="text"
                className={inputCls}
                value={form.title} onChange={handleChange}
                placeholder="e.g. AI-based Attendance System"
                required
              />
            </div>

            {/* Description */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="description" className="text-sm font-semibold text-[var(--text)]">
                Description <span className="text-red-500">*</span>
              </label>
              <textarea
                id="description" name="description" rows={4}
                className={`${inputCls} resize-none`}
                value={form.description} onChange={handleChange}
                placeholder="Describe the project goals and scope..."
                required
              />
            </div>

            {/* Department + Team Size + Project Type */}
            <div className="grid grid-cols-3 gap-5 max-[768px]:grid-cols-1">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="department" className="text-sm font-semibold text-[var(--text)]">
                  Department <span className="text-red-500">*</span>
                </label>
                <select
                  id="department" name="department"
                  className={inputCls}
                  value={form.department} onChange={handleChange}
                  required
                >
                  <option value="">Select department</option>
                  {DEPARTMENTS.map((d) => (
                    <option key={d.value} value={d.value}>{d.label}</option>
                  ))}
                </select>
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="max_team_size" className="text-sm font-semibold text-[var(--text)]">
                  Max Team Size <span className="text-red-500">*</span>
                </label>
                <select
                  id="max_team_size" name="max_team_size"
                  className={inputCls}
                  value={form.max_team_size} onChange={handleChange}
                >
                  <option value={2}>2 Students</option>
                  <option value={3}>3 Students</option>
                </select>
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="project_type" className="text-sm font-semibold text-[var(--text)]">
                  Project Type <span className="text-red-500">*</span>
                </label>
                <select
                  id="project_type" name="project_type"
                  className={inputCls}
                  value={form.project_type} onChange={handleChange}
                  required
                >
                  <option value="" disabled>Select project type</option>
                  {PROJECT_TYPES.map((pt) => (
                    <option key={pt.value} value={pt.value}>{pt.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Required Skills */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="required_skills" className="text-sm font-semibold text-[var(--text)]">
                Required Skills
              </label>
              <input
                id="required_skills" name="required_skills" type="text"
                className={inputCls}
                value={form.required_skills} onChange={handleChange}
                placeholder="e.g. Python, Machine Learning, React"
              />
              <span className="text-xs text-[var(--text-muted)] mt-1 font-medium">Comma-separated tags</span>
            </div>

            {/* Submit */}
            <button
              type="submit"
              className="inline-flex items-center justify-center gap-2 w-full py-3.5 text-[15px] font-bold rounded-[var(--radius-sm)] bg-[var(--primary)] text-white hover:bg-[var(--primary-hover)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-2"
              disabled={loading}
            >
              {loading ? <><Loader2 size={18} className="animate-spin" /> Submitting…</> : <><Send size={18} /> Submit Idea</>}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
