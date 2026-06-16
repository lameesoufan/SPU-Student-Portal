import React, { useState, useEffect } from 'react';
import { fetchMyBoard } from '../api';
import KanbanBoard from './KanbanBoard';
import ProjectWorkflowView from './ProjectWorkflowView';
import GitLabPanel from './GitLabPanel';

export default function MyProject() {
  const [board, setBoard]     = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [activeTab, setActiveTab] = useState('board');
  /* ── Global callback so parent dashboard can track active sub-tab ── */
useEffect(() => {
  window.myProjectSetActiveTab = (tab) => setActiveTab(tab);
  window.__myProjectActiveTab = activeTab;
  return () => { delete window.myProjectSetActiveTab; };
}, [activeTab]);

useEffect(() => {
  window.__myProjectActiveTab = activeTab;
}, [activeTab]);
    /* Register global callback so sidebar can switch tabs */
  useEffect(() => {
    window.myProjectSetActiveTab = (tab) => setActiveTab(tab);
    window.__myProjectActiveTab = activeTab;
    return () => { delete window.myProjectSetActiveTab; };
  }, [activeTab]);

  /* Keep global tab state in sync for sidebar highlight */
  useEffect(() => {
    window.__myProjectActiveTab = activeTab;
  }, [activeTab]);
  useEffect(() => {
    fetchMyBoard()
      .then((res) => { if (res.data.has_project) setBoard(res.data.board); })
      .catch(() => setError('Failed to load board.'))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="mp-loading-state">
      <div className="spinner spinner-dark"></div>
      <p>Loading your project board…</p>
    </div>
  );

  if (error) return (
    <div className="mp-error-state">
      <div className="alert alert-error">{error}</div>
    </div>
  );

  if (!board) return (
    <div className="my-project-page">
      <div className="page-header">
        <h1 className="page-title">My Project</h1>
      </div>
      <div className="mp-empty-state">
        <div className="empty-state">
          <div className="empty-state-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="var(--muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <line x1="3" y1="9" x2="21" y2="9"/>
              <line x1="9" y1="21" x2="9" y2="9"/>
            </svg>
          </div>
          <h3>No Active Project</h3>
          <p>Your project board will appear here once your project proposal is approved by the Head of Department.</p>
        </div>
      </div>
    </div>
  );

  return (
    <div className="my-project-page">
      <div className="page-header">
        <h1 className="page-title">My Project</h1>
      </div>

      <div className="flex gap-0 mb-6 border-b-2 border-gray-200 dark:border-gray-700 p-0">
        <button
          className={`inline-flex items-center gap-2 py-3 px-6 bg-transparent border-none border-b-[3px] text-sm font-medium cursor-pointer transition-all duration-200 -mb-[2px] relative [&_svg]:transition-opacity [&_svg]:duration-200 ${activeTab === 'board' ? 'text-violet-600 dark:text-violet-400 border-b-violet-500 font-semibold [&_svg]:opacity-100' : 'text-gray-500 dark:text-gray-400 border-b-transparent [&_svg]:opacity-60 hover:text-violet-600 dark:hover:text-violet-400 hover:bg-violet-50 dark:hover:bg-violet-900/20 hover:[&_svg]:opacity-100'}`}
          onClick={() => setActiveTab('board')}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
          Board
        </button>
        <button
          className={`inline-flex items-center gap-2 py-3 px-6 bg-transparent border-none border-b-[3px] text-sm font-medium cursor-pointer transition-all duration-200 -mb-[2px] relative [&_svg]:transition-opacity [&_svg]:duration-200 ${activeTab === 'workflow' ? 'text-violet-600 dark:text-violet-400 border-b-violet-500 font-semibold [&_svg]:opacity-100' : 'text-gray-500 dark:text-gray-400 border-b-transparent [&_svg]:opacity-60 hover:text-violet-600 dark:hover:text-violet-400 hover:bg-violet-50 dark:hover:bg-violet-900/20 hover:[&_svg]:opacity-100'}`}
          onClick={() => setActiveTab('workflow')}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
          Workflow
        </button>
        <button
          className={`inline-flex items-center gap-2 py-3 px-6 bg-transparent border-none border-b-[3px] text-sm font-medium cursor-pointer transition-all duration-200 -mb-[2px] relative [&_svg]:transition-opacity [&_svg]:duration-200 ${activeTab === 'gitlab' ? 'text-violet-600 dark:text-violet-400 border-b-violet-500 font-semibold [&_svg]:opacity-100' : 'text-gray-500 dark:text-gray-400 border-b-transparent [&_svg]:opacity-60 hover:text-violet-600 dark:hover:text-violet-400 hover:bg-violet-50 dark:hover:bg-violet-900/20 hover:[&_svg]:opacity-100'}`}
          onClick={() => setActiveTab('gitlab')}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/><path d="M9 18c-4.51 2-5-2-7-2"/></svg>
          GitLab
        </button>
      </div>

      <div className="my-project-content">
        {activeTab === 'board' ? (
          <KanbanBoard board={board} setBoard={setBoard} canEdit={true} />
        ) : activeTab === 'workflow' ? (
          <ProjectWorkflowView projectBoardId={board.id} />
        ) : (
          <GitLabPanel boardId={board.id} canManage={false} />
        )}
      </div>
    </div>
  );
}