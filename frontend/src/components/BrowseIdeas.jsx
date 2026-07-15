import React, { useState, useEffect } from 'react';
import { browseIdeas, applyOnIdea, fetchMyIdeaApplication, fetchMyProposal, fetchStudentForm, fetchMyBoard } from '../api';
import { PROJECT_TYPES, getProjectTypeLabel } from '../lib/constants';
import StudentSearch from './StudentSearch';
import DynamicCheckboxGroup from './DynamicCheckboxGroup';
import { Users, User, Award, Briefcase, Wrench, Search, Lock, Send, CheckCircle, Clock, BookOpen } from 'lucide-react';

const STATUS_META = {
  awaiting_members:             { label: 'بانتظار الأعضاء',             cls: 'badge-warning' },
  pending_review:              { label: 'قيد المراجعة',              cls: 'badge-warning' },
  pending_doctor:              { label: 'بانتظار الطبيب',              cls: 'badge-warning' },
  pending_hod:                 { label: 'بانتظار رئيس القسم',                 cls: 'badge-primary' },
  registered:                  { label: 'مسجل',                  cls: 'badge-success' },
  rejected:                    { label: 'مرفوض',                    cls: 'badge-danger' },
  rejected_insufficient_members: { label: 'Rejected (Insufficient Members)', cls: 'badge-danger' },
};

const EMPTY_APPLY = { team_size: 1, member_ids: [], team_size_reason: '', project_type: '' };

const emptyValueForField = (field) => field.field_type === 'checkbox' ? [] : '';

export default function BrowseIdeas({ onBack }) {
  const [ideas, setIdeas]           = useState([]);
  const [myApp, setMyApp]           = useState(undefined);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [applyModal, setApplyModal] = useState(null);
  const [applyForm, setApplyForm]   = useState(EMPTY_APPLY);
  const [applying, setApplying]     = useState(false);
  const [applyError, setApplyError] = useState('');
  const [search, setSearch]         = useState('');
  const [deptFilter, setDeptFilter] = useState('');
  const [dynForm, setDynForm]       = useState(null);
  const [dynValues, setDynValues]   = useState({});
  const [loadingDynForm, setLoadingDynForm] = useState(false);

  useEffect(() => {
    Promise.allSettled([browseIdeas(), fetchMyIdeaApplication(), fetchMyProposal(), fetchMyBoard()])
      .then(([ideasRes, appRes, propRes, boardRes]) => {
        if (ideasRes.status === 'fulfilled') {
          setIdeas(ideasRes.value.data);
        } else {
          setError('Failed to load ideas.');
        }

        const boardData = boardRes.status === 'fulfilled' ? boardRes.value.data : null;
        const appData = appRes.status === 'fulfilled' ? appRes.value.data : null;
        const propData = propRes.status === 'fulfilled' ? propRes.value.data : null;
        if (boardData && boardData.has_project) {
          setMyApp({ _type: 'board', status: 'registered', idea_title: boardData.board?.title || 'مشروعك' });
        } else if (appData && ['awaiting_members', 'pending_doctor', 'pending_hod', 'registered'].includes(appData.status)) {
          setMyApp(appData);
        } else if (propData && ['pending_supervisor', 'pending_hod', 'assigned'].includes(propData.status)) {
          setMyApp({ _type: 'proposal', status: propData.status });
        } else {
          setMyApp(null);
        }
      })
      .catch(() => setError('Failed to load ideas.'))
      .finally(() => setLoading(false));
  }, []);

  const openApply = (idea) => {
    setApplyModal(idea);
    setApplyForm({ team_size: 1, member_ids: [], team_size_reason: '', project_type: '' });
    // باقي الكود نفسو...
    setApplyError('');
    setDynForm(null);
    setDynValues({});
    setLoadingDynForm(true);
    fetchStudentForm(idea.department, 'browse')
      .then(res => {
        if (res.data?.fields?.length) {
          setDynForm(res.data);
          const init = {};
          res.data.fields.forEach(f => { init[f.id] = emptyValueForField(f); });
          setDynValues(init);
        }
      })
      .catch(() => {})
      .finally(() => setLoadingDynForm(false));
  };

const handleTeamSizeChange = (size) => {
    const s = Number(size);
    setApplyForm(prev => ({
      team_size: s,
      member_ids: Array(s - 1).fill(''),
      team_size_reason: (s === 2 || s === 3) ? '' : prev.team_size_reason || '',
    }));
  };

  const handleMemberChange = (idx, val) => {
    setApplyForm((prev) => {
      const ids = [...prev.member_ids];
      ids[idx] = val;
      return { ...prev, member_ids: ids };
    });
  };

  const handleApplySubmit = async () => {
    if (applying || loadingDynForm) return;
    setApplyError('');
    setApplying(true);
    try {
      const fd = new FormData();

      // الحقول العادية
      fd.append('team_size', applyForm.team_size);
      applyForm.member_ids.filter(Boolean).forEach(id => fd.append('member_ids', id));
      if (dynForm?.id) fd.append('form_id', dynForm.id);

      // field_responses — نفصل الملفات عن النصوص
      const fieldResponses = dynForm
        ? (dynForm.fields || []).map(f => {
            const val = dynValues[f.id] ?? emptyValueForField(f);
            return { field: f.id, value: f.field_type === 'file' ? val?.name || '' : val };
          })
        : [];
      fd.append('field_responses', JSON.stringify(fieldResponses));

      // إضافة الملفات الفعلية
      if (dynForm) {
        (dynForm.fields || []).forEach(f => {
          if (f.field_type === 'file' && dynValues[f.id] instanceof File) {
            fd.append(`field_file_${f.id}`, dynValues[f.id]);
          }
        });
      }

      fd.append('team_size_reason', (Number(applyForm.team_size) === 1 || Number(applyForm.team_size) > 3) ? applyForm.team_size_reason.trim() : '');
      fd.append('team_size', applyForm.team_size);
      fd.append('project_type', applyForm.project_type);
      const res = await applyOnIdea(applyModal.id, fd);
      setMyApp(res.data);
      setApplyModal(null);
    } catch (err) {
      const data = err.response?.data;
      setApplyError(data?.error || 'Failed to apply. Please try again.');
    } finally {
      setApplying(false);
    }
  };

  const filtered = ideas.filter((i) => {
    const matchSearch = !search ||
      i.title.toLowerCase().includes(search.toLowerCase()) ||
      i.doctor_name.toLowerCase().includes(search.toLowerCase()) ||
      (i.required_skills || '').toLowerCase().includes(search.toLowerCase());
    const matchDept = !deptFilter || i.department === deptFilter;
    return matchSearch && matchDept;
  });

  const departments = [...new Set(ideas.map((i) => i.department))];

  return (
    <div className="flex flex-col gap-6 max-w-[1080px] mx-auto px-6 py-8">
      {/* ── Header ── */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[var(--primary)]/10 flex items-center justify-center text-[var(--primary)]">
          <BookOpen size={20} />
        </div>
        <div>
          <h1 className="text-xl font-extrabold text-[var(--text)] leading-tight">تصفح أفكار المشاريع</h1>
          <p className="text-sm text-[var(--text-muted)]">اكتشف وتقدم لمشاريع التخرج المقترحة من أعضاء الهيئة التدريسية.</p>
        </div>
      </div>

      <div className="flex flex-col gap-5">
        {/* ── Alerts ── */}
        {myApp && myApp.idea_title && (
          <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-blue-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 text-sm">
            <CheckCircle size={16} />
            <span>
              You have an active application on <strong>"{myApp.idea_title}"</strong>{' '}
              <span className={`badge ${(STATUS_META[myApp.status] || STATUS_META.rejected).cls}`}>
                {(STATUS_META[myApp.status] || STATUS_META.rejected).label}
              </span>
            </span>
          </div>
        )}
        {myApp && myApp._type === 'proposal' && (
          <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-amber-500/10 border border-amber-500/20 text-amber-600 dark:text-amber-400 text-sm">
            <Briefcase size={16} />
            <span>لديك مقترح فكرة نشط بالفعل. لا يمكنك التقدم لفكرة أخرى.</span>
          </div>
        )}
        {myApp && myApp._type === 'board' && (
          <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-blue-500/10 border border-blue-500/20 text-blue-600 dark:text-blue-400 text-sm">
            <CheckCircle size={16} />
            <span>لديك مشروع مسجل بالفعل. لا يمكنك التقدم لفكرة أخرى.</span>
          </div>
        )}
        {error && (
          <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-sm">
            <Lock size={16} />
            <span>{error}</span>
          </div>
        )}

        {/* ── Filters ── */}
        <div className="flex gap-3 flex-wrap items-center">
          <div className="flex-1 min-w-[250px] relative flex items-center">
            <span className="absolute left-3.5 text-[var(--text-faint)] pointer-events-none flex">
              <Search size={16} />
            </span>
            <input
              type="text"
              className="w-full pl-[42px] mb-0 bg-[var(--input-bg)] text-[var(--text)] border border-[var(--border)] rounded-[var(--radius-sm)] px-4 py-2.5 text-sm outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] transition-colors placeholder:text-[var(--text-faint)]"
              placeholder="ابحث بالعنوان، الطبيب، أو المهارات…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select
            className="min-w-[180px] mb-0 bg-[var(--input-bg)] text-[var(--text)] border border-[var(--border)] rounded-[var(--radius-sm)] px-4 py-2.5 text-sm outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] transition-colors"
            value={deptFilter}
            onChange={(e) => setDeptFilter(e.target.value)}
          >
            <option value="">كل الأقسام</option>
            {departments.map((d) => (
              <option key={d} value={d}>{d.replace(/_/g, ' ')}</option>
            ))}
          </select>
        </div>

        {/* ── Loading ── */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-12">
            <div className="spinner-dark w-6 h-6"></div>
            <p className="text-[var(--text-muted)] mt-3 text-sm">جاري تحميل المشاريع…</p>
          </div>
        )}

        {/* ── Empty State ── */}
        {!loading && filtered.length === 0 && !error && (
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] shadow-[var(--shadow)]">
            <div className="flex flex-col items-center justify-center py-12">
              <div className="w-16 h-16 flex items-center justify-center rounded-full bg-[var(--bg-tertiary)] text-[var(--text-muted)] mx-auto mb-4">
                <Search size={24} />
              </div>
              <h3 className="text-lg font-bold text-[var(--text)]">لا توجد مشاريع</h3>
              <p className="text-sm text-[var(--text-muted)] text-center mt-1">لا توجد أفكار مشاريع تطابق الفلاتر الحالية. حاول تعديل البحث أو فلتر القسم.</p>
            </div>
          </div>
        )}

        {/* ── Idea Cards Grid ── */}
        <div className="grid grid-cols-1 md:grid-cols-[repeat(auto-fill,minmax(340px,1fr))] gap-5">
          {filtered.map((idea) => {
            const isApplied  = myApp && myApp.idea === idea.id;
            const isTaken    = idea.is_taken;
            const canApply   = !myApp && !isTaken;
            const hasProject = !!myApp;
            const team       = idea.registered_team;

            return (
              <div
                key={idea.id}
                className={`bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)  ${(isTaken || hasProject) ? 'opacity-75 hover:translate-y-0 hover:shadow-[var(--shadow)] hover:border-[var(--border)]' : ''}`}
              >
                <div className="p-6 flex flex-col gap-[18px]">
                  {/* Card header */}
                  <div className="flex flex-col gap-2.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20">
                        <BookOpen size={12} />
                        {idea.department.replace(/_/g, ' ')}
                      </span>
                      {idea.project_type && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-500/10 text-purple-600 border border-purple-500/20">
                          {getProjectTypeLabel(idea.project_type)}
                        </span>
                      )}
                      {isTaken && (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-500/10 text-red-500 border border-red-500/20">
                          <Lock size={12} />
                          Taken
                        </span>
                      )}
                    </div>
                    <h3 className="text-lg font-extrabold text-[var(--text)] leading-snug m-0">{idea.title}</h3>
                    <p className="text-sm text-[var(--text-muted)] leading-relaxed m-0 line-clamp-3">{idea.description}</p>
                  </div>

                  {/* Card info with icon circles */}
                  <div className="grid grid-cols-2 gap-3 bg-[var(--bg-tertiary)] p-3.5 rounded-[var(--radius-sm)] border border-[var(--border-light)]">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-full bg-[var(--primary)]/10 flex items-center justify-center text-[var(--primary)]">
                        <User size={14} />
                      </div>
                      <div className="flex flex-col gap-0.5">
                        <span className="text-[var(--text-muted)] text-xs">المشرف</span>
                        <span className="text-sm text-[var(--text)] font-semibold">{idea.doctor_name}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-500">
                        <Users size={14} />
                      </div>
                      <div className="flex flex-col gap-0.5">
                        <span className="text-[var(--text-muted)] text-xs">حجم الفريق</span>
                        <span className="text-sm text-[var(--text)] font-semibold">Max {idea.max_team_size}</span>
                      </div>
                    </div>
                  </div>

                  {/* Skills as tags */}
                  {idea.required_skills && (
                    <div className="flex items-center gap-2 flex-wrap">
                      <Wrench size={14} className="text-[var(--primary)] shrink-0" />
                      {idea.required_skills.split(',').map((skill, i) => (
                        <span
                          key={i}
                          className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-[var(--primary)]/10 text-[var(--primary)] border border-[var(--primary)]/20"
                        >
                          {skill.trim()}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Registered team */}
                  {isTaken && team && (
                    <div className="bg-[var(--bg-tertiary)] px-3.5 py-3 rounded-[var(--radius-sm)] border border-[var(--border-light)]">
                      <span className="text-[var(--text-muted)] text-xs mb-1.5 block">الفريق المسجل</span>
                      <div className="flex flex-col gap-1.5">
                        <span className="text-[13px] flex items-center gap-2 font-bold text-[var(--primary)]">
                          <Award size={16} /> {team.leader.name}
                        </span>
                        {team.members.map((m) => (
                          <span key={m.username} className="text-[13px] text-[var(--text)] flex items-center gap-2 font-medium">
                            <User size={16} /> {m.name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Card footer */}
                  <div className="mt-auto pt-4 border-t border-[var(--border)]">
                    {isApplied ? (
                      <div className="flex items-center justify-center gap-2">
                        <span className={`badge ${(STATUS_META[myApp.status] || STATUS_META.rejected).cls}`}>
                          {(STATUS_META[myApp.status] || STATUS_META.rejected).label}
                        </span>
                      </div>
                    ) : isTaken || hasProject ? (
                      <button className="w-full inline-flex items-center justify-center gap-2 opacity-60 bg-transparent text-[var(--text-muted)] py-2.5 px-4 rounded-[var(--radius-sm)] cursor-not-allowed" disabled>
                        <Lock size={16} /> {hasProject ? 'لديك مشروع بالفعل' : 'غير متاح'}
                      </button>
                    ) : (
                      <button
                        className="w-full inline-flex items-center justify-center gap-2 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white font-semibold py-2.5 px-4 rounded-[var(--radius-sm)] transition-all duration-200 hover:shadow-md"
                        onClick={() => openApply(idea)}
                      >
                        <Send size={16} />
                        Apply for Project
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ── Apply Modal ── */}
      {applyModal && (
        <div className="fixed inset-0 bg-[var(--overlay)] flex items-center justify-center z-[1000] p-4" role="dialog" aria-modal="true">
          <div className="bg-[var(--card)] rounded-[var(--radius-lg)] shadow-[var(--shadow-lg)] p-4 md:p-8 w-full max-w-[520px] max-h-[90vh] overflow-y-auto border border-[var(--border)]">
            <div className="flex items-start justify-between gap-3">
              <h3 className="text-xl font-extrabold text-[var(--text)] flex items-center gap-2 m-0">
                <Send size={16} /> Apply: {applyModal.title}
              </h3>
              <button
                className="inline-flex items-center justify-center w-8 h-8 rounded-full hover:bg-[var(--bg-tertiary)] text-[var(--text-muted)] transition-colors"
                onClick={() => setApplyModal(null)}
                disabled={applying}
              >✕</button>
            </div>
            <p className="text-sm text-[var(--text-muted)] mt-1">
              Max team size for this project: <strong className="text-[var(--text-secondary)]">{applyModal.max_team_size}</strong>
            </p>

            <form className="mt-5">
              <div className="mb-4">
                <label htmlFor="team-size" className="block text-sm font-semibold text-[var(--text-muted)] mb-1.5">حجم فريقك</label>
                <select
                  id="team-size"
                  className="w-full bg-[var(--input-bg)] text-[var(--text)] border border-[var(--border)] rounded-[var(--radius-sm)] px-4 py-2.5 text-sm outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] transition-colors"
                  value={applyForm.team_size}
                  onChange={(e) => handleTeamSizeChange(e.target.value)}
                >
                  {Array.from({ length: applyModal.max_team_size }, (_, i) => i + 1).map((n) => (
                    <option key={n} value={n}>{n} student{n > 1 ? 's' : ''}</option>
                  ))}
                </select>
              </div>

              <div className="mb-4">
                <label htmlFor="project_type" className="block text-sm font-semibold text-[var(--text-muted)] mb-1.5">نوع المشروع <span className="text-[var(--danger)]">*</span></label>
                <select
                  id="project_type"
                  className="w-full bg-[var(--input-bg)] text-[var(--text)] border border-[var(--border)] rounded-[var(--radius-sm)] px-4 py-2.5 text-sm outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] transition-colors"
                  value={applyForm.project_type}
                  onChange={(e) => setApplyForm(prev => ({ ...prev, project_type: e.target.value }))}
                  required
                >
                  <option value="" disabled>اختر نوع المشروع</option>
                  {PROJECT_TYPES.map((pt) => (
                    <option key={pt.value} value={pt.value}>{pt.label}</option>
                  ))}
                </select>
              </div>

              {(Number(applyForm.team_size) === 1 || Number(applyForm.team_size) > 3) && (
                <div className="mb-4">
                  <label htmlFor="team-size-reason" className="block text-sm font-semibold text-[var(--text-muted)] mb-1.5">
                    Justification for team size
                    <span className="text-[var(--danger)] ml-0.5">*</span>
                    <span className="text-xs text-[var(--text-muted)] font-normal ml-2">
                      {Number(applyForm.team_size) === 1 ? 'Why are you working alone?' : 'Why do you need more than 3 members?'}
                    </span>
                  </label>
                  <textarea
                    id="team-size-reason"
                    className="w-full bg-[var(--input-bg)] text-[var(--text)] border border-[var(--border)] rounded-[var(--radius-sm)] px-4 py-2.5 text-sm outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] transition-colors resize-none"
                    rows={3}
                    value={applyForm.team_size_reason}
                    onChange={(e) => setApplyForm(prev => ({ ...prev, team_size_reason: e.target.value }))}
                    placeholder={Number(applyForm.team_size) === 1
                      ? 'Explain why you are applying without team members…'
                      : 'Explain why your team needs more than 3 members…'}
                    required
                  />
                </div>
              )}

{applyForm.member_ids.map((val, idx) => (
  <div className="mb-4" key={idx}>
    <label htmlFor={`member-${idx}`} className="block text-sm font-semibold text-[var(--text-muted)] mb-1.5">Team Member {idx + 2}</label>
    <StudentSearch
      id={`member-${idx}`}
      value={val}
      onChange={(username) => handleMemberChange(idx, username)}
      placeholder="ابحث باسم الطالب أو الرقم الجامعي…"
    />
  </div>
))}


              {loadingDynForm && (
                <div className="py-2 flex items-center gap-2">
                  <div className="spinner-dark w-4 h-4"></div>
                  <span className="text-sm text-[var(--text-muted)]">جاري تحميل نموذج القسم…</span>
                </div>
              )}
              {dynForm && (dynForm.fields || []).length > 0 && (
                <div className="mt-4 p-4 bg-[var(--bg-tertiary)] rounded-[var(--radius)] border border-[var(--border-light)] flex flex-col gap-3.5">
                  <div className="text-sm font-bold text-[var(--primary)] uppercase tracking-wide pb-2 border-b border-[var(--border)]">
                    {dynForm.title || 'متطلبات إضافية'}
                  </div>
                  {dynForm.fields.map(field => (
                    <BrowseDynField
                      key={field.id}
                      field={field}
                      value={dynValues[field.id] ?? emptyValueForField(field)}
                      onChange={val => setDynValues(prev => ({ ...prev, [field.id]: val }))}
                    />
                  ))}
                </div>
              )}
            </form>

            {applyError && (
              <div className="flex items-center gap-2 mt-4 p-3 rounded-[var(--radius-sm)] bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-sm">
                <Lock size={16} />
                <span>{applyError}</span>
              </div>
            )}

            <div className="flex gap-3 mt-6 justify-end">
              <button
                className="inline-flex items-center justify-center gap-2 bg-[var(--primary)] hover:bg-[var(--primary-hover)] text-white font-semibold py-2.5 px-5 rounded-[var(--radius-sm)] transition-all duration-200 hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={handleApplySubmit}
                disabled={applying || loadingDynForm}
              >
                {applying ? 'Submitting…' : loadingDynForm ? 'Loading form…' : 'تأكيد الطلب'}
              </button>
              <button
                className="inline-flex items-center justify-center gap-2 bg-transparent border border-[var(--border)] text-[var(--text)] font-medium py-2.5 px-5 rounded-[var(--radius-sm)] hover:bg-[var(--bg-tertiary)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => setApplyModal(null)}
                disabled={applying}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Inline dynamic field renderer for BrowseIdeas modal ──────────────────────
function BrowseDynField({ field, value, onChange }) {
  const { label, field_type, required, options } = field;
  const inputCls = "w-full bg-[var(--input-bg)] text-[var(--text)] border border-[var(--border)] rounded-[var(--radius-sm)] px-4 py-2.5 text-sm outline-none focus:border-[var(--primary)] focus:ring-1 focus:ring-[var(--primary)] transition-colors";
  const lbl = (
    <label className="block text-[13px] font-bold text-[var(--text-muted)] mb-1.5 uppercase tracking-wide">
      {label}{required && <span className="text-[var(--danger)] ml-0.5">*</span>}
    </label>
  );

  if (field_type === 'text')
    return <div>{lbl}<input className={inputCls} type="text" value={value} required={required} onChange={e => onChange(e.target.value)} /></div>;
  if (field_type === 'textarea')
    return <div>{lbl}<textarea className={inputCls} rows={3} value={value} required={required} onChange={e => onChange(e.target.value)} /></div>;
  if (field_type === 'number')
    return <div>{lbl}<input className={`${inputCls} max-w-[120px]`} type="number" value={value} required={required} min="0" step="any" onChange={e => onChange(e.target.value)} /></div>;
  if (field_type === 'date')
    return <div>{lbl}<input className={inputCls} type="date" value={value} required={required} onChange={e => onChange(e.target.value)} /></div>;
  if (field_type === 'select')
    return <div>{lbl}<select className={inputCls} value={value} required={required} onChange={e => onChange(e.target.value)}><option value="">اختر...</option>{(options||[]).map(o=><option key={o} value={o}>{o}</option>)}</select></div>;
  if (field_type === 'radio')
    return <div>{lbl}<div className="flex flex-col gap-2">{(options||[]).map(o=><label key={o} className="flex items-center gap-2 text-sm text-[var(--text)] cursor-pointer font-medium"><input type="radio" name={`bdyn-${field.id}`} value={o} checked={value===o} onChange={()=>onChange(o)} required={required} className="accent-[var(--primary)]" /><span>{o}</span></label>)}</div></div>;
  if (field_type === 'checkbox')
    return <div>{lbl}<DynamicCheckboxGroup field={field} value={value} onChange={onChange} /></div>;
 if (field_type === 'file')
    return (
      <div>
        {lbl}
        <input
          className={inputCls}
          type="file"
          required={required}
          accept=".pdf,.doc,.docx,.jpg,.jpeg,.png,.gif"
          onChange={e => {
            const file = e.target.files?.[0];
            if (file) onChange(file);  // ← تخزين File object بدل file.name
          }}
        />
        {value instanceof File && (
          <span className="text-xs text-[var(--text-muted)] mt-1 block">
            Selected: {value.name}
          </span>
        )}
      </div>
    );
  return null;
}