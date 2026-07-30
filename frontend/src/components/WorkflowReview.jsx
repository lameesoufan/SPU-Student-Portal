import { useState, useEffect } from 'react';
import {
  fetchReviewableProjects, fetchProjectWorkflow, reviewWorkflowStage
} from '../api';

const TRIGGER_DOT_COLORS = {
  project_start: 'bg-emerald-400',
  after_days: 'bg-amber-400',
  date: 'bg-blue-400',
  milestone: 'bg-violet-400',
  manual: 'bg-rose-400',
};

const Icons = {
  ArrowLeft: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>,
  Clock: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>,
  CheckCircle: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>,
  XCircle: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>,
  AlertCircle: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>,
  ThumbsUp: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>,
  ThumbsDown: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>,
  Eye: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>,
  Users: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>,
  Folder: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>,
  MessageSquare: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>,
  FileText: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>,
  ChevronRight: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>,
  Clipboard: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg>,
  X: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>,
  Zap: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>,
};

const STATUS_META = {
  pending:   { label: 'معلق',   icon: Icons.Clock,      cls: 'bg-amber-100 dark:bg-amber-900/20 text-amber-700 dark:text-amber-300' },
  submitted: { label: 'مُرسل', icon: Icons.CheckCircle, cls: 'bg-violet-100 dark:bg-violet-900/20 text-violet-700 dark:text-violet-300' },
  approved:  { label: 'مقبول',  icon: Icons.CheckCircle, cls: 'bg-emerald-100 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300' },
  rejected:  { label: 'مرفوض',  icon: Icons.XCircle,     cls: 'bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-300' },
  overdue:   { label: 'متأخر',   icon: Icons.AlertCircle, cls: 'bg-red-100 dark:bg-red-900/20 text-red-700 dark:text-red-300' },
};

// ── Pipeline Progress Bar ────────────────────────────────────────────────
function PipelineProgress({ stages, selectedIndex, onSelect }) {
  return (
    <div className="flex items-center gap-0 py-2 overflow-x-auto">
      {stages.map((s, i) => (
        <div key={s.id} className="flex items-center cursor-pointer" onClick={() => onSelect(i)}>
          <div className="flex flex-col items-center">
            <div
              className={`w-4 h-4 rounded-full border-2 transition-all duration-200 ${
                i === selectedIndex
                  ? 'bg-violet-500 border-violet-400 ring-2 ring-violet-200 dark:ring-violet-700'
                  : s.status === 'approved'
                  ? 'bg-emerald-400 border-emerald-300'
                  : s.status === 'rejected'
                  ? 'bg-red-400 border-red-300'
                  : s.status === 'submitted'
                  ? 'bg-violet-300 dark:bg-violet-500 border-violet-200 dark:border-violet-400'
                  : 'bg-gray-200 dark:bg-gray-600 border-gray-300 dark:border-gray-500'
              }`}
            />
            <span className={`text-[9px] mt-1 max-w-[52px] truncate text-center ${
              i === selectedIndex
                ? 'text-violet-600 dark:text-violet-400 font-bold'
                : 'text-gray-400 dark:text-gray-500'
            }`}>
              {s.stage_details?.name || i + 1}
            </span>
          </div>
          {i < stages.length - 1 && (
            <div className={`w-4 h-0.5 mx-0.5 mb-3 ${
              s.status === 'approved' ? 'bg-emerald-300' : 'bg-gray-200 dark:bg-gray-600'
            }`} />
          )}
        </div>
      ))}
    </div>
  );
}

export default function WorkflowReview({ onBack }) {
  const [projects, setProjects] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [workflow, setWorkflow] = useState(null);
  const [selectedStage, setSelectedStage] = useState(null);
  const [activeStageIdx, setActiveStageIdx] = useState(null);
  const [feedback, setFeedback] = useState('');
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadProjects();
  }, []);

  const loadProjects = async () => {
    setLoading(true);
    try {
      const res = await fetchReviewableProjects();
      setProjects(res.data);
    } catch {
      setError('فشل تحميل المشاريع');
    } finally {
      setLoading(false);
    }
  };

  const loadProjectWorkflow = async (projectId) => {
    setLoading(true);
    setError('');
    try {
      const res = await fetchProjectWorkflow(projectId);
      setWorkflow(Array.isArray(res.data) ? (res.data[0] || null) : res.data);
      setSelectedProject(projects.find(p => p.id === projectId));
      setActiveStageIdx(null);
    } catch {
      setError('فشل تحميل سير العمل');
    } finally {
      setLoading(false);
    }
  };

  const handleReview = async (stageInstanceId, action) => {
    if (action === 'reject' && !feedback.trim()) {
      setError('يرجى تقديم ملاحظات للرفض');
      return;
    }

    setReviewing(true);
    setError('');
    try {
      await reviewWorkflowStage(stageInstanceId, {
        action,
        feedback: feedback.trim()
      });
      await loadProjectWorkflow(selectedProject.id);
      setSelectedStage(null);
      setFeedback('');
    } catch {
      setError('فشل مراجعة المرحلة');
    } finally {
      setReviewing(false);
    }
  };

  // ── Loading ──
  if (loading && !workflow && !selectedStage) {
    return (
      <div className="w-full overflow-x-hidden flex items-center justify-center min-h-[280px]">
        <div className="flex items-center gap-3 text-gray-500 dark:text-gray-400">
          <div className="w-7 h-7 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">جاري التحميل...</span>
        </div>
      </div>
    );
  }

  // ── Review Modal (Overlay) ──
  if (selectedStage) {
    const meta = STATUS_META[selectedStage.status] || STATUS_META.pending;

    return (
      <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
        <div className="w-full max-w-[640px] max-h-[90vh] overflow-y-auto bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 shadow-2xl">
          {/* Modal Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-gray-700 bg-violet-50/50 dark:bg-violet-900/10 rounded-t-2xl">
            <div className="flex items-center gap-3">
              <span className="p-1.5 rounded-lg bg-violet-100 dark:bg-violet-900/30 text-violet-600 dark:text-violet-400">
                {Icons.Eye}
              </span>
              <div>
                <h3 className="text-base font-semibold text-gray-900 dark:text-gray-100 m-0">
                  {selectedStage.stage_details?.name || 'مراجعة المرحلة'}
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">مراجعة طلب الطالب</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold ${meta.cls}`}>
                {meta.icon}
                {meta.label}
              </span>
              <button
                className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                onClick={() => { setSelectedStage(null); setFeedback(''); setError(''); }}
              >
                {Icons.X}
              </button>
            </div>
          </div>

          {/* Modal Body */}
          <div className="p-5 space-y-4">
            {selectedStage.stage_details?.description && (
              <div className="px-3 py-2.5 bg-gray-50 dark:bg-gray-700/50 rounded-lg text-sm text-gray-500 dark:text-gray-400 leading-relaxed">
                {selectedStage.stage_details.description}
              </div>
            )}

            {/* Submission Info */}
            <div className="grid grid-cols-2 gap-3">
              {selectedStage.submitted_at && (
                <div className="px-3 py-2.5 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <div className="text-[10px] font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wide">مُرسل</div>
                  <div className="text-sm text-gray-700 dark:text-gray-300 mt-0.5">
                    {new Date(selectedStage.submitted_at).toLocaleString()}
                  </div>
                </div>
              )}
              {selectedStage.due_date && (
                <div className="px-3 py-2.5 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                  <div className="text-[10px] font-medium text-gray-400 dark:text-gray-500 uppercase tracking-wide">تاريخ الاستحقاق</div>
                  <div className="text-sm text-gray-700 dark:text-gray-300 mt-0.5">
                    {new Date(selectedStage.due_date).toLocaleDateString()}
                  </div>
                </div>
              )}
            </div>

            {/* Student Responses */}
            {selectedStage.field_responses && selectedStage.field_responses.length > 0 ? (
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide flex items-center gap-1.5">
                  {Icons.FileText} Student Responses
                </h4>
                {selectedStage.field_responses.map((response, idx) => (
                  <div key={idx} className="flex gap-3 px-3 py-2.5 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300 min-w-[140px] max-w-[140px] truncate" title={response.field_label}>
                      {response.field_label}:
                    </span>
                    <span className="text-sm text-gray-500 dark:text-gray-400 flex-1 break-all">
                      {response.value && response.field_type === 'file' ? (
                        <a href={`http://localhost:8000/media/${response.value}`}
                           target="_blank" rel="noopener noreferrer"
                           className="text-violet-600 dark:text-violet-400 no-underline font-medium hover:underline">
                          {response.value}
                        </a>
                      ) : (
                        response.value || '—'
                      )}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-6 text-center text-sm text-gray-400 dark:text-gray-500 bg-gray-50 dark:bg-gray-700/30 rounded-lg">
                No responses submitted yet.
              </div>
            )}

            {/* Previous Feedback */}
            {selectedStage.feedback && (
              <div className="flex items-start gap-2.5 px-3 py-2.5 bg-amber-50 dark:bg-amber-900/10 border-l-[3px] border-l-amber-400 rounded-r-lg">
                {Icons.MessageSquare}
                <div>
                  <div className="text-xs font-semibold text-amber-600 dark:text-amber-400">الملاحظات السابقة</div>
                  <p className="text-sm text-gray-700 dark:text-gray-300 m-0 mt-0.5">{selectedStage.feedback}</p>
                </div>
              </div>
            )}

            {/* Feedback Input */}
            {selectedStage.status === 'submitted' && (
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                  Feedback <span className="text-amber-500 normal-case">(required for rejection)</span>
                </label>
                <textarea
                  className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500 dark:focus:ring-violet-400 transition-all duration-200 resize-y"
                  rows={3}
                  value={feedback}
                  onChange={e => setFeedback(e.target.value)}
                  placeholder="قدم ملاحظات للطالب..."
                />
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="flex items-center gap-2.5 px-4 py-2.5 text-sm text-red-700 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                {Icons.AlertCircle}
                <span>{error}</span>
              </div>
            )}
          </div>

          {/* Modal Footer */}
          {selectedStage.status === 'submitted' && (
            <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-gray-100 dark:border-gray-700">
              <button
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-700 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/30 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => handleReview(selectedStage.id, 'reject')}
                disabled={reviewing}
              >
                {Icons.ThumbsDown}
                {reviewing ? 'Rejecting...' : 'رفض'}
              </button>
              <button
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-emerald-600 dark:bg-emerald-500 rounded-lg hover:bg-emerald-700 dark:hover:bg-emerald-600 shadow-sm transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                onClick={() => handleReview(selectedStage.id, 'approve')}
                disabled={reviewing}
              >
                {Icons.ThumbsUp}
                {reviewing ? 'Approving...' : 'موافقة'}
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ── Project Workflow View ──
  if (workflow) {
    const stages = workflow.stage_instances || [];
    const submittedCount = stages.filter(s => s.status === 'submitted').length;

    return (
      <div className="w-full overflow-x-hidden">
        <div className="max-w-5xl mx-auto p-2 sm:p-4 space-y-5">
          {/* Header */}
          <div className="flex items-center gap-3 flex-wrap">
            <button
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 hover:text-violet-600 dark:hover:text-violet-400 hover:bg-violet-50 dark:hover:bg-violet-900/20 rounded-lg transition-colors duration-200"
              onClick={() => { setWorkflow(null); setSelectedProject(null); setActiveStageIdx(null); }}
            >
              {Icons.ArrowLeft} Back to Projects
            </button>
            <div>
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-gray-100">
                {selectedProject?.title}
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                {workflow.template_details?.name}
              </p>
            </div>
          </div>

          {/* Submitted Alert */}
          {submittedCount > 0 && (
            <div className="flex items-center gap-2.5 px-4 py-3 text-sm text-violet-700 dark:text-violet-300 bg-violet-50 dark:bg-violet-900/20 border border-violet-200 dark:border-violet-800 rounded-lg">
              {Icons.AlertCircle}
              <span><strong>{submittedCount}</strong> stage{submittedCount !== 1 ? 's' : ''} awaiting your review</span>
            </div>
          )}

          {/* Pipeline Progress */}
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
            <h3 className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-violet-500" />
              Pipeline Progress
            </h3>
            <PipelineProgress
              stages={stages}
              selectedIndex={activeStageIdx}
              onSelect={setActiveStageIdx}
            />
          </div>

          {/* Stages List */}
          <div className="space-y-3">
            {stages.map((stage, idx) => {
              const meta = STATUS_META[stage.status] || STATUS_META.pending;
              const isSubmitted = stage.status === 'submitted';

              return (
                <div
                  key={stage.id}
                  className={`bg-white dark:bg-gray-800 rounded-xl border transition-all duration-200 overflow-hidden ${
                    isSubmitted
                      ? 'border-violet-300 dark:border-violet-600 shadow-md ring-1 ring-violet-100 dark:ring-violet-900/30'
                      : 'border-gray-200 dark:border-gray-700'
                  }`}
                >
                  {/* Stage Header */}
                  <div className="flex items-center gap-3 px-4 py-3">
                    {/* Number Circle */}
                    <div className={`w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0 ${
                      stage.status === 'approved'
                        ? 'bg-emerald-500 text-white'
                        : stage.status === 'rejected'
                        ? 'bg-red-500 text-white'
                        : isSubmitted
                        ? 'bg-violet-600 text-white'
                        : 'bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300'
                    }`}>
                      {idx + 1}
                    </div>

                    {/* Stage Info */}
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-gray-900 dark:text-gray-100 truncate">
                        {stage.stage_details?.name || `Stage ${idx + 1}`}
                      </div>
                      <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                        {stage.stage_details?.trigger_type && (
                          <>
                            <span className="flex items-center gap-1">
                              <div className={`w-2 h-2 rounded-full ${TRIGGER_DOT_COLORS[stage.stage_details.trigger_type] || 'bg-gray-400'}`} />
                              {stage.stage_details.trigger_type.replace('_', ' ')}
                            </span>
                            <span className="text-gray-300 dark:text-gray-600">|</span>
                          </>
                        )}
                        {stage.submitted_at && (
                          <span>Submitted {new Date(stage.submitted_at).toLocaleDateString()}</span>
                        )}
                      </div>
                    </div>

                    {/* Status Badge */}
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold flex-shrink-0 ${meta.cls}`}>
                      {meta.icon}
                      {meta.label}
                    </span>
                  </div>

                  {/* Stage Body — Review button or Feedback */}
                  {(isSubmitted || stage.feedback) && (
                    <div className="px-4 pb-3 ml-10">
                      {isSubmitted && (
                        <button
                          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-violet-600 dark:bg-violet-500 rounded-lg hover:bg-violet-700 dark:hover:bg-violet-600 shadow-sm transition-colors duration-200"
                          onClick={() => setSelectedStage(stage)}
                        >
                          {Icons.Eye} Review Submission
                        </button>
                      )}
                      {stage.feedback && !isSubmitted && (
                        <div className="flex items-start gap-2 px-3 py-2 bg-gray-50 dark:bg-gray-700/50 rounded-lg text-xs">
                          {Icons.MessageSquare}
                          <div>
                            <span className="font-semibold text-gray-600 dark:text-gray-300">Feedback:</span>
                            <span className="text-gray-500 dark:text-gray-400 ml-1">{stage.feedback}</span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  // ── Projects List View ──
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
              Review Workflow Submissions
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
              Select a project to review its workflow stages
            </p>
          </div>
        </div>

        {projects.length === 0 ? (
          <div className="py-16 text-center bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
            <div className="text-gray-300 dark:text-gray-600 mb-3">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mx-auto">
                <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
              </svg>
            </div>
            <p className="text-gray-500 dark:text-gray-400 font-medium">لا توجد مشاريع بسير عمل موجودة.</p>
            <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">طبّق سير العمل على المشاريع أولاً.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {projects.map(project => {
              const pendingCount = project.pending_reviews || 0;
              return (
                <div
                  key={project.id}
                  className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 hover:border-violet-300 dark:hover:border-violet-600 hover:shadow-md transition-all duration-200 cursor-pointer overflow-hidden group"
                  onClick={() => loadProjectWorkflow(project.id)}
                >
                  {/* Card Color Accent */}
                  <div className="h-1 bg-gradient-to-r from-violet-500 to-violet-400 opacity-0 group-hover:opacity-100 transition-opacity duration-200" />

                  <div className="p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="p-2 rounded-lg bg-violet-50 dark:bg-violet-900/20 text-violet-600 dark:text-violet-400 flex-shrink-0">
                          {Icons.Folder}
                        </div>
                        <div className="min-w-0">
                          <h3 className="font-semibold text-gray-900 dark:text-gray-100 truncate m-0">
                            {project.title}
                          </h3>
                          <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 mt-1">
                            {Icons.Users}
                            <span className="truncate">
                              {project.team_members?.map(m => m.name).join(', ') || 'بدون فريق'}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-1 text-gray-400 dark:text-gray-500 group-hover:text-violet-500 transition-colors flex-shrink-0">
                        {Icons.ChevronRight}
                      </div>
                    </div>

                    {/* Supervisor + Pending Badge */}
                    <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        Supervisor: {project.supervisor_name}
                      </span>
                      {pendingCount > 0 && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-bold bg-violet-100 dark:bg-violet-900/30 text-violet-700 dark:text-violet-300">
                          {pendingCount} pending
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
