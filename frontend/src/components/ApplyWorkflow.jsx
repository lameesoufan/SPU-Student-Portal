import { useState, useEffect } from 'react';
import { fetchWorkflowTemplates, applyWorkflowBulk, fetchAvailableProjects } from '../api';

const TRIGGER_DOT_COLORS = {
  project_start: 'bg-emerald-400',
  after_days: 'bg-amber-400',
  date: 'bg-blue-400',
  milestone: 'bg-violet-400',
  manual: 'bg-rose-400',
};

const Icons = {
  ArrowLeft: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>,
  CheckCircle: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>,
  AlertCircle: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>,
  List: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>,
  Zap: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>,
  Folder: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>,
  Users: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>,
  Link: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>,
  Play: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>,
  Eye: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>,
  ChevronDown: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>,
};

// ── Mini Pipeline (same as WorkflowBuilder) ──────────────────────────────
function MiniPipeline({ stages }) {
  if (!stages || stages.length === 0) return null;
  return (
    <div className="flex items-center gap-0 overflow-x-auto py-2">
      {stages.map((s, i) => (
        <div key={i} className="flex items-center">
          <div className="flex flex-col items-center">
            <div
              className={`w-3 h-3 rounded-full ${
                s.is_required
                  ? TRIGGER_DOT_COLORS[s.trigger_type] || 'bg-emerald-400'
                  : 'bg-gray-300 dark:bg-gray-600'
              }`}
              title={s.name || `Stage ${i + 1}`}
            />
            <span className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5 max-w-[48px] truncate text-center">
              {s.name || i + 1}
            </span>
          </div>
          {i < stages.length - 1 && (
            <div className="w-4 h-0.5 bg-violet-300 dark:bg-violet-600 mx-0.5 mb-3" />
          )}
        </div>
      ))}
    </div>
  );
}

export default function ApplyWorkflow({ onBack }) {
  const [templates, setTemplates] = useState([]);
  const [projects, setProjects] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [selectedProjects, setSelectedProjects] = useState([]);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [templatesRes, projectsRes] = await Promise.all([
        fetchWorkflowTemplates(),
        fetchAvailableProjects()
      ]);
      setTemplates(templatesRes.data.filter(t => t.status === 'active'));
      setProjects(projectsRes.data);
    } catch {
      setError('Failed to load workflow data. Refresh the page or try again later.');
    } finally {
      setLoading(false);
    }
  };

  const availableProjects = projects.filter((project) => !project.has_own_workflow);
  const allAvailableSelected =
    availableProjects.length > 0 &&
    availableProjects.every((project) => selectedProjects.includes(project.id));

  const toggleProject = (projectId) => {
    setSelectedProjects((current) =>
      current.includes(projectId)
        ? current.filter((id) => id !== projectId)
        : [...current, projectId]
    );
    setError('');
  };

  const toggleSelectAll = () => {
    setSelectedProjects(
      allAvailableSelected ? [] : availableProjects.map((project) => project.id)
    );
    setError('');
  };

  const handleApply = async () => {
    if (!selectedTemplate || selectedProjects.length === 0) {
      setError('يرجى اختيار قالب سير العمل ومشروع واحد على الأقل.');
      return;
    }

    setApplying(true);
    setError('');
    setSuccess(false);

    try {
      const response = await applyWorkflowBulk({
        template_id: Number(selectedTemplate),
        project_ids: selectedProjects,
        replace_existing: false,
      });

      const applied = response.data?.applied_count || 0;
      const skipped = response.data?.skipped_count || 0;
      const errors = response.data?.error_count || 0;
      setSuccess(`تم إسناد سير العمل إلى ${applied} مشروع${skipped ? `، وتم تجاوز ${skipped}` : ''}${errors ? `، وتعذر إسناد ${errors}` : ''}.`);
      setSelectedProjects([]);
      await loadData();
      setTimeout(() => setSuccess(false), 5000);
    } catch (err) {
      const msg = err.response?.data?.error || 'تعذر إسناد سير العمل. حاول مرة أخرى.';
      setError(msg);
    } finally {
      setApplying(false);
    }
  };

  // ── Loading ──
  if (loading) {
    return (
      <div className="w-full overflow-x-hidden flex items-center justify-center min-h-[280px]">
        <div className="flex items-center gap-3 text-gray-500 dark:text-gray-400">
          <div className="w-7 h-7 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Loading workflow configuration...</span>
        </div>
      </div>
    );
  }

  const selectedTemplateData = templates.find(t => t.id === Number(selectedTemplate));
  const selectedProjectData = selectedProjects.length === 1
    ? projects.find((project) => project.id === selectedProjects[0])
    : null;
  const canApply = selectedTemplate && selectedProjects.length > 0 && !applying;

  return (
    <div className="w-full overflow-x-hidden">
      <div className="max-w-5xl mx-auto p-2 sm:p-4 space-y-5">
        {/* Header */}
        <div className="flex items-center gap-3 flex-wrap">
          <button
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-violet-600 dark:hover:text-violet-400 hover:bg-violet-50 dark:hover:bg-violet-900/20 rounded-lg transition-colors duration-200"
            onClick={onBack}
          >
            {Icons.ArrowLeft} Back
          </button>
          <div>
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">
              Assign Workflow
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
              Pick a workflow template and assign it to the correct project board.
            </p>
          </div>
        </div>

        {/* Two-Column Selection */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {/* Left — Template Selection */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 bg-violet-50/50 dark:bg-violet-900/10">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300">
                <span className="p-1.5 rounded-lg bg-violet-100 dark:bg-violet-900/30 text-violet-600 dark:text-violet-400">
                  {Icons.Zap}
                </span>
                Workflow Template
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-8">
                Only active templates are shown
              </p>
            </div>

            <div className="p-4 space-y-3">
              <div>
                <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                  Select Template
                </label>
                <select
                  className="w-full mt-1 px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200"
                  value={selectedTemplate}
                  onChange={e => { setSelectedTemplate(e.target.value); setError(''); }}
                >
                  <option value="">Choose a template...</option>
                  {templates.map(t => (
                    <option key={t.id} value={t.id}>
                      {t.name} ({t.stages?.length || 0} stages)
                    </option>
                  ))}
                </select>
              </div>

              {/* Template Preview */}
              {selectedTemplateData ? (
                <div className="p-3 rounded-xl border border-violet-200 dark:border-violet-700 bg-violet-50/30 dark:bg-violet-900/10 space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-gray-900 dark:text-white text-sm">
                      {selectedTemplateData.name}
                    </span>
                    <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold bg-violet-100 dark:bg-violet-900/40 text-violet-700 dark:text-violet-300">
                      {selectedTemplateData.stages?.length || 0} stages
                    </span>
                  </div>

                  {selectedTemplateData.description && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                      {selectedTemplateData.description}
                    </p>
                  )}

                  {/* Mini Pipeline */}
                  {selectedTemplateData.stages?.length > 0 && (
                    <div className="pt-2 border-t border-violet-100 dark:border-violet-800">
                      <MiniPipeline stages={selectedTemplateData.stages} />
                    </div>
                  )}

                  {/* Stage List */}
                  <div className="space-y-1.5">
                    {selectedTemplateData.stages?.map((stage, idx) => (
                      <div
                        key={stage.id ?? `${stage.name || 'stage'}-${idx}`}
                        className="flex items-center gap-2.5 py-2 px-3 rounded-lg bg-white dark:bg-gray-800 border border-gray-100 dark:border-gray-700"
                      >
                        <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                          TRIGGER_DOT_COLORS[stage.trigger_type] || 'bg-emerald-400'
                        }`} />
                        <span className="text-sm text-gray-800 dark:text-gray-200 font-medium flex-1 truncate">
                          {stage.name || `Stage ${idx + 1}`}
                        </span>
                        <span className="text-[11px] text-gray-400 dark:text-gray-500 capitalize">
                          {stage.trigger_type?.replace('_', ' ')}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="py-8 text-center rounded-xl bg-gray-50 dark:bg-gray-800/50 border-2 border-dashed border-gray-200 dark:border-gray-700">
                  <div className="text-gray-300 dark:text-gray-600 mb-2">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mx-auto">
                      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
                    </svg>
                  </div>
                  <p className="text-xs text-gray-400 dark:text-gray-500">
                    Select a template to preview its stages
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Right — Project Selection */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-700 bg-emerald-50/50 dark:bg-emerald-900/10">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-gray-700 dark:text-gray-300">
                <span className="p-1.5 rounded-lg bg-emerald-100 dark:bg-emerald-900/30 text-emerald-600 dark:text-emerald-400">
                  {Icons.Folder}
                </span>
                Target Project
              </h3>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 ml-8">
                يمكنك إضافة سير عمل حتى لو أضاف مشرف آخر سيراً لهذا المشروع
              </p>
            </div>

            <div className="p-4 space-y-3">
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                    اختيار المشاريع
                  </label>
                  <span className="text-xs font-semibold text-violet-600 dark:text-violet-400">
                    تم اختيار {selectedProjects.length}
                  </span>
                </div>

                <button
                  type="button"
                  onClick={toggleSelectAll}
                  disabled={availableProjects.length === 0}
                  className={`w-full flex items-center justify-between gap-3 rounded-xl border px-4 py-3 text-sm font-semibold transition-all ${
                    allAvailableSelected
                      ? 'border-violet-300 bg-violet-50 text-violet-700 dark:border-violet-700 dark:bg-violet-900/20 dark:text-violet-300'
                      : 'border-gray-200 bg-gray-50 text-gray-700 hover:border-violet-300 hover:bg-violet-50/60 dark:border-gray-700 dark:bg-gray-900/30 dark:text-gray-200'
                  } disabled:cursor-not-allowed disabled:opacity-50`}
                >
                  <span className="flex items-center gap-2">
                    <span className={`flex h-5 w-5 items-center justify-center rounded border ${
                      allAvailableSelected
                        ? 'border-violet-600 bg-violet-600 text-white'
                        : 'border-gray-300 bg-white dark:border-gray-600 dark:bg-gray-800'
                    }`}>
                      {allAvailableSelected && '✓'}
                    </span>
                    {allAvailableSelected ? 'إلغاء اختيار الكل' : 'اختيار كل المشاريع'}
                  </span>
                  <span className="rounded-full bg-white px-2.5 py-1 text-xs text-gray-500 shadow-sm dark:bg-gray-800 dark:text-gray-400">
                    {availableProjects.length} متاح
                  </span>
                </button>

                <div className="max-h-80 space-y-2 overflow-y-auto rounded-xl border border-gray-200 p-2 dark:border-gray-700">
                  {projects.map((project) => {
                    const disabled = project.has_own_workflow;
                    const checked = selectedProjects.includes(project.id);
                    return (
                      <label
                        key={project.id}
                        className={`flex items-start gap-3 rounded-lg border p-3 transition-colors ${
                          disabled
                            ? 'cursor-not-allowed border-gray-100 bg-gray-50 opacity-60 dark:border-gray-800 dark:bg-gray-900/30'
                            : checked
                              ? 'cursor-pointer border-violet-300 bg-violet-50/70 dark:border-violet-700 dark:bg-violet-900/20'
                              : 'cursor-pointer border-transparent hover:border-gray-200 hover:bg-gray-50 dark:hover:border-gray-700 dark:hover:bg-gray-900/30'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={disabled}
                          onChange={() => toggleProject(project.id)}
                          className="mt-0.5 h-4 w-4 rounded border-gray-300 text-violet-600 focus:ring-violet-500"
                        />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-semibold text-gray-900 dark:text-white">
                            {project.title}
                          </span>
                          <span className="mt-1 block text-xs text-gray-500 dark:text-gray-400">
                            {disabled
                              ? 'سبق أن أسندت سير عمل لهذا المشروع'
                              : project.has_workflow
                                ? `يوجد ${project.workflow_count || 1} سير عمل من جهة أخرى ويمكنك إضافة مسارك`
                                : 'متاح لإسناد سير العمل'}
                          </span>
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Project Preview */}
              {selectedProjectData ? (
                <div className={`p-3 rounded-xl border ${
                  selectedProjectData.has_own_workflow
                    ? 'border-amber-200 dark:border-amber-700 bg-amber-50/30 dark:bg-amber-900/10'
                    : 'border-emerald-200 dark:border-emerald-700 bg-emerald-50/30 dark:bg-emerald-900/10'
                } space-y-3`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-gray-900 dark:text-white text-sm">
                      {selectedProjectData.title}
                    </span>
                    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold ${
                      selectedProjectData.has_own_workflow
                        ? 'bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300'
                        : 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300'
                    }`}>
                      {selectedProjectData.has_own_workflow ? 'أضفته مسبقاً' : 'متاح للإسناد'}
                    </span>
                  </div>

                  {/* Team Members */}
                  <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                    {Icons.Users}
                    {selectedProjectData.team_members?.length > 0 ? (
                      <span>{selectedProjectData.team_members.map(m => m.name).join(', ')}</span>
                    ) : (
                      <span>No team members assigned yet</span>
                    )}
                  </div>

                  {/* Warning if already assigned */}
                  {selectedProjectData.has_own_workflow ? (
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
                      <span className="text-amber-500 flex-shrink-0 mt-0.5">{Icons.AlertCircle}</span>
                      <p className="text-xs text-amber-700 dark:text-amber-300 leading-relaxed">
                        لقد أسندت أنت سير عمل فعالاً لهذا المشروع مسبقاً.
                      </p>
                    </div>
                  ) : selectedProjectData.has_workflow ? (
                    <div className="flex items-start gap-2 p-3 rounded-lg bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800">
                      <span className="text-blue-500 flex-shrink-0 mt-0.5">{Icons.AlertCircle}</span>
                      <p className="text-xs text-blue-700 dark:text-blue-300 leading-relaxed">
                        يوجد حالياً {selectedProjectData.workflow_count || 1} سير عمل من مشرف أو جهة أخرى، ويمكنك إضافة سير عمل مستقل باسمك.
                      </p>
                    </div>
                  ) : null}
                </div>
              ) : (
                <div className="py-8 text-center rounded-xl bg-gray-50 dark:bg-gray-800/50 border-2 border-dashed border-gray-200 dark:border-gray-700">
                  <div className="text-gray-300 dark:text-gray-600 mb-2">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mx-auto">
                      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
                    </svg>
                  </div>
                  <p className="text-xs text-gray-400 dark:text-gray-500">
                    Select a project to inspect its status
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Connection Visual — Template → Project */}
        {selectedTemplateData && selectedProjects.length > 0 && (
          <div className="flex items-center justify-center gap-3 py-2">
            <span className="text-xs text-gray-400 dark:text-gray-500 font-medium">Workflow</span>
            <div className="flex-1 h-px bg-violet-200 dark:bg-violet-700 max-w-[120px]" />
            <span className="text-violet-500">{Icons.Link}</span>
            <div className="flex-1 h-px bg-emerald-200 dark:bg-emerald-700 max-w-[120px]" />
            <span className="text-xs text-gray-400 dark:text-gray-500 font-medium">Project</span>
          </div>
        )}

        {/* Alerts */}
        {error && (
          <div className="flex items-center gap-2.5 px-4 py-3 text-sm text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
            {Icons.AlertCircle}
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="flex items-center gap-2.5 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-200 dark:border-emerald-800 rounded-lg">
            {Icons.CheckCircle}
            <span>{success}</span>
          </div>
        )}

        {/* Apply Button */}
        <div className="flex justify-end pt-1">
          <button
            className={`flex items-center gap-2 px-6 py-2.5 text-sm font-medium rounded-lg shadow-sm transition-all duration-200 ${
              canApply
                ? 'text-white bg-violet-600 dark:bg-violet-500 hover:bg-violet-700 dark:hover:bg-violet-600 hover:shadow-md'
                : 'text-gray-400 dark:text-gray-500 bg-gray-100 dark:bg-gray-800 cursor-not-allowed'
            }`}
            onClick={handleApply}
            disabled={!canApply}
          >
            {Icons.Play}
            {applying ? 'جارٍ الإسناد...' : `إسناد إلى ${selectedProjects.length || 0} مشروع`}
          </button>
        </div>
      </div>
    </div>
  );
}
