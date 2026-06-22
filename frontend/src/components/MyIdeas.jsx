import React, { useEffect, useState } from 'react';
import { fetchMyIdeas } from '../api';
import { getProjectTypeLabel } from '../lib/constants';

const STATUS_META = {
  pending_review: { label: 'Pending Review', cls: 'badge-warning' },
  approved:       { label: 'Approved',        cls: 'badge-success' },
  rejected:       { label: 'Rejected',        cls: 'badge-danger' },
};

export default function MyIdeas({ onBack, onSubmitNew }) {
  const [ideas, setIdeas]     = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  useEffect(() => {
    fetchMyIdeas()
      .then((res) => setIdeas(res.data))
      .catch(() => setError('Failed to load ideas. Please try again.'))
      .finally(() => setLoading(false));
  }, []);

  const counts = {
    pending_review: ideas.filter((i) => i.status === 'pending_review').length,
    approved:       ideas.filter((i) => i.status === 'approved').length,
    rejected:       ideas.filter((i) => i.status === 'rejected').length,
  };

  return (
    <div className="max-w-[1000px] mx-auto py-8 px-6 flex flex-col gap-6">
      {/* Header */}
      <div className="page-header flex flex-col gap-4">
        <button className="back-btn" onClick={onBack}>← Back to Dashboard</button>
        <div className="flex items-center justify-between gap-4 flex-wrap max-[600px]:flex-col max-[600px]:items-start">
          <div>
            <h1 className="text-[26px] font-extrabold text-gray-900 dark:text-white m-0">My Project Ideas</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400 mt-1 m-0">Manage and track your submitted project ideas.</p>
          </div>
          <button className="btn btn-primary" onClick={onSubmitNew}>+ Submit New Idea</button>
        </div>
      </div>

      <div className="flex flex-col gap-5">
        {/* Summary strip */}
        <div className="grid grid-cols-3 gap-4 max-[600px]:grid-cols-1">
          <div className="bg-white dark:bg-gray-800 rounded-xl py-5 px-4 text-center shadow-md border border-gray-200 dark:border-gray-700 border-t-4 border-t-violet-500 transition-all duration-200">
            <span className="block text-[32px] font-extrabold text-gray-900 dark:text-white leading-tight">{counts.pending_review}</span>
            <span className="block text-xs text-gray-500 dark:text-gray-400 mt-1 uppercase tracking-widest font-bold">Pending Review</span>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-xl py-5 px-4 text-center shadow-md border border-gray-200 dark:border-gray-700 border-t-4 border-t-emerald-500 transition-all duration-200">
            <span className="block text-[32px] font-extrabold text-gray-900 dark:text-white leading-tight">{counts.approved}</span>
            <span className="block text-xs text-gray-500 dark:text-gray-400 mt-1 uppercase tracking-widest font-bold">Approved</span>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-xl py-5 px-4 text-center shadow-md border border-gray-200 dark:border-gray-700 border-t-4 border-t-red-500 transition-all duration-200">
            <span className="block text-[32px] font-extrabold text-gray-900 dark:text-white leading-tight">{counts.rejected}</span>
            <span className="block text-xs text-gray-500 dark:text-gray-400 mt-1 uppercase tracking-widest font-bold">Rejected</span>
          </div>
        </div>

        {/* Content */}
        {loading && (
          <div className="empty-state">
            <div className="spinner-dark" style={{ width: 24, height: 24 }}></div>
            <p className="text-gray-500 dark:text-gray-400" style={{ marginTop: 12 }}>Loading ideas…</p>
          </div>
        )}

        {error && <div className="alert alert-error" role="alert">{error}</div>}

        {!loading && !error && ideas.length === 0 && (
          <div className="card">
            <div className="empty-state">
              <div className="w-16 h-16 flex items-center justify-center rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 mx-auto mb-4">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 11l3 3L22 4"/>
                  <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
                </svg>
              </div>
              <h3>No ideas yet</h3>
              <p>You haven't submitted any project ideas yet. Start by proposing your first idea.</p>
              <button className="btn btn-primary" onClick={onSubmitNew}>Submit Your First Idea</button>
            </div>
          </div>
        )}

        {!loading && ideas.length > 0 && (
          <div className="flex flex-col gap-4">
            {ideas.map((idea) => {
              const meta = STATUS_META[idea.status] || STATUS_META.pending_review;
              return (
                <div key={idea.id} className="bg-white dark:bg-gray-800 rounded-xl shadow-md border border-gray-200 dark:border-gray-700 overflow-hidden transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_10px_24px_rgba(124,58,237,0.15)] hover:border-violet-300 dark:hover:border-violet-600">
                  <div className="p-6 flex flex-col gap-3.5">
                    <div className="flex flex-col gap-2.5">
                      <div className="flex items-start justify-between gap-3 max-[600px]:flex-col max-[600px]:gap-1.5">
                        <h3 className="text-lg font-extrabold text-gray-900 dark:text-white leading-snug m-0">{idea.title}</h3>
                        <span className={`badge ${meta.cls}`}>{meta.label}</span>
                      </div>
                      <p className="text-sm text-gray-500 dark:text-gray-400 leading-relaxed m-0 line-clamp-2">{idea.description}</p>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <span className="bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs py-1 px-3 rounded-md font-semibold">{idea.department.replace(/_/g, ' ')}</span>
                      <span className="bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs py-1 px-3 rounded-md font-semibold">{idea.max_team_size} students</span>
                      {idea.project_type && (
                        <span className="bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 text-xs py-1 px-3 rounded-md font-semibold">{getProjectTypeLabel(idea.project_type)}</span>
                      )}
                      {idea.required_skills && (
                        <span className="bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs py-1 px-3 rounded-md font-semibold">{idea.required_skills}</span>
                      )}
                      <span className="text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-xs py-1 px-3 rounded-md font-semibold">{new Date(idea.created_at).toLocaleDateString()}</span>
                    </div>

                    {idea.status === 'rejected' && idea.rejection_reason && (
                      <div className="alert alert-error" style={{ margin: 0 }}>
                        <strong>Rejection reason:</strong> {idea.rejection_reason}
                      </div>
                    )}
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