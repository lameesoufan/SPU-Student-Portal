import React, { useState, useEffect } from 'react';
import { fetchSupervisorBoards } from '../api';
import KanbanBoard, { COLUMNS } from './KanbanBoard';
import GitLabPanel from './GitLabPanel';
import {
  FolderKanban, ListTodo, CheckCircle2, TrendingUp,
  ArrowLeft, Users, ArrowRight, GitBranch, Loader2, FolderOpen,
} from 'lucide-react';

const COL_COLORS = {
  todo: '#6366f1',
  in_progress: '#f59e0b',
  review: '#8b5cf6',
  done: '#22c55e',
};

export default function SupervisorProjects({ onBack }) {
  const [boards, setBoards]       = useState([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');
  const [selected, setSelected]   = useState(null);
  const [viewMode, setViewMode]   = useState('board');

  useEffect(() => {
    fetchSupervisorBoards()
      .then((res) => setBoards(res.data))
      .catch(() => setError('Failed to load projects.'))
      .finally(() => setLoading(false));
  }, []);

  const selectedBoard = boards.find((b) => b.id === selected);

  const setSelectedBoard = (updater) => {
    setBoards((prev) => prev.map((b) => b.id === selected ? updater(b) : b));
  };

  const totalTasks     = boards.reduce((s, b) => s + b.tasks.length, 0);
  const completedTasks = boards.reduce((s, b) => s + b.tasks.filter(t => t.status === 'done').length, 0);
  const avgProgress    = boards.length > 0
    ? Math.round(boards.reduce((s, b) => {
        const done = b.tasks.filter(t => t.status === 'done').length;
        return s + (b.tasks.length > 0 ? (done / b.tasks.length) * 100 : 0);
      }, 0) / boards.length)
    : 0;

  /* ── Selected Board Detail View ── */
  if (selected && selectedBoard) {
    return (
      <div className="max-w-4xl mx-auto py-8 px-6 flex flex-col gap-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <button
            className="inline-flex items-center gap-1.5 bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-sm)] px-3.5 py-2 text-[13px] font-medium text-[var(--text-muted)] cursor-pointer transition-colors hover:bg-[var(--bg-tertiary)] hover:text-[var(--text)]"
            onClick={() => { setSelected(null); setViewMode('board'); }}
          >
            <ArrowLeft size={16} />
            All Projects
          </button>
          <div className="flex-1">
            <h1 className="text-xl font-bold tracking-tight text-[var(--text)] m-0">{selectedBoard.title}</h1>
            <p className="text-[13px] font-medium text-[var(--text-muted)] m-0">
              {selectedBoard.members.map(m => m.name || m.username).join(', ')}
            </p>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-0 bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-sm)] p-1.5 shadow-[var(--shadow)]">
          <button
            className={`flex-1 py-2 px-4 rounded-md text-sm font-semibold transition-all border-[1.5px] ${
              viewMode === 'board'
                ? 'bg-[var(--primary)] text-white border-[var(--primary)] shadow-md shadow-[var(--primary)]/25'
                : 'bg-transparent text-[var(--text-muted)] border-transparent hover:bg-[var(--primary)]/10 hover:text-[var(--primary)]'
            }`}
            onClick={() => setViewMode('board')}
          >
            <ListTodo size={14} className="inline mr-1.5 -mt-px" />
            Board
          </button>
          <button
            className={`flex-1 py-2 px-4 rounded-md text-sm font-semibold transition-all border-[1.5px] ${
              viewMode === 'gitlab'
                ? 'bg-[var(--primary)] text-white border-[var(--primary)] shadow-md shadow-[var(--primary)]/25'
                : 'bg-transparent text-[var(--text-muted)] border-transparent hover:bg-[var(--primary)]/10 hover:text-[var(--primary)]'
            }`}
            onClick={() => setViewMode('gitlab')}
          >
            <GitBranch size={14} className="inline mr-1.5 -mt-px" />
            GitLab
          </button>
        </div>

        <div className="mt-0">
          {viewMode === 'board' ? (
            <KanbanBoard board={selectedBoard} setBoard={setSelectedBoard} canEdit={true} />
          ) : (
            <GitLabPanel boardId={selectedBoard.id} canManage={true} />
          )}
        </div>
      </div>
    );
  }

  /* ── Project List View ── */
  return (
    <div className="max-w-4xl mx-auto py-8 px-6 flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-amber-500/10 flex items-center justify-center text-amber-500">
          <FolderKanban size={20} />
        </div>
        <div>
          <h1 className="text-xl font-extrabold text-[var(--text)] leading-tight">Supervised Projects</h1>
          <p className="text-sm text-[var(--text-muted)]">Track and manage all projects you are supervising.</p>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-4">
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] p-5 flex items-center gap-4 shadow-[var(--shadow)] transition-all hover:border-[var(--primary)]/30 hover:shadow-md">
          <div className="flex items-center justify-center w-11 h-11 rounded-xl bg-violet-500/10 text-violet-500 flex-shrink-0">
            <FolderKanban size={20} />
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-[22px] font-bold text-[var(--text)] leading-none">{loading ? '—' : boards.length}</span>
            <span className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Total Projects</span>
          </div>
        </div>
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] p-5 flex items-center gap-4 shadow-[var(--shadow)] transition-all hover:border-[var(--primary)]/30 hover:shadow-md">
          <div className="flex items-center justify-center w-11 h-11 rounded-xl bg-amber-500/10 text-amber-500 flex-shrink-0">
            <ListTodo size={20} />
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-[22px] font-bold text-[var(--text)] leading-none">{loading ? '—' : totalTasks}</span>
            <span className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Total Tasks</span>
          </div>
        </div>
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] p-5 flex items-center gap-4 shadow-[var(--shadow)] transition-all hover:border-[var(--primary)]/30 hover:shadow-md">
          <div className="flex items-center justify-center w-11 h-11 rounded-xl bg-emerald-500/10 text-emerald-500 flex-shrink-0">
            <CheckCircle2 size={20} />
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-[22px] font-bold text-[var(--text)] leading-none">{loading ? '—' : completedTasks}</span>
            <span className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Completed</span>
          </div>
        </div>
        <div className="bg-[var(--primary)]/5 border border-[var(--primary)]/20 rounded-[var(--radius)] p-5 flex items-center gap-4 shadow-[var(--shadow)] transition-all hover:border-[var(--primary)] hover:shadow-md">
          <div className="flex items-center justify-center w-11 h-11 rounded-xl bg-purple-500/10 text-purple-500 flex-shrink-0">
            <TrendingUp size={20} />
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-[22px] font-bold text-[var(--text)] leading-none">{loading ? '—' : `${avgProgress}%`}</span>
            <span className="text-[11px] font-medium text-[var(--text-muted)] uppercase tracking-wide">Avg. Progress</span>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-[var(--radius-sm)] bg-red-500/10 border border-red-500/20 text-red-600 dark:text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex justify-center py-16">
          <Loader2 size={32} className="animate-spin text-[var(--primary)]" />
        </div>
      )}

      {/* Empty State */}
      {!loading && boards.length === 0 && !error && (
        <div className="flex flex-col items-center gap-3 py-16 text-center">
          <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-[var(--bg-tertiary)] text-[var(--text-muted)]">
            <FolderOpen size={32} />
          </div>
          <h3 className="text-lg font-bold text-[var(--text)]">No active projects</h3>
          <p className="text-sm text-[var(--text-muted)] max-w-sm leading-relaxed">
            Projects will appear here once student proposals or applications are registered and approved.
          </p>
        </div>
      )}

      {/* Projects Grid */}
      {!loading && boards.length > 0 && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-4">
          {boards.map((board) => {
            const done  = board.tasks.filter((t) => t.status === 'done').length;
            const total = board.tasks.length;
            const pct   = total > 0 ? Math.round((done / total) * 100) : 0;

            return (
              <div
                key={board.id}
                className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] cursor-pointer transition-all hover:shadow-lg hover:border-[var(--primary)] hover:-translate-y-0.5 overflow-hidden"
                onClick={() => setSelected(board.id)}
              >
                <div className="p-5 pb-0">
                  {/* Title + Badge */}
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-[15px] font-bold text-[var(--text)] m-0 leading-snug">{board.title}</h3>
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[var(--bg-tertiary)] text-[var(--text-muted)] whitespace-nowrap flex-shrink-0">
                      {total} tasks
                    </span>
                  </div>

                  {/* Members */}
                  <div className="flex items-center gap-2 mt-3 flex-wrap">
                    <Users size={14} className="text-[var(--text-muted)] flex-shrink-0" />
                    <div className="flex">
                      {board.members.slice(0, 4).map((m, idx) => (
                        <div
                          key={m.id}
                          title={m.name || m.username}
                          className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 text-white text-[11px] font-bold flex items-center justify-center border-2 border-[var(--card)] shadow-sm -ml-1 first:ml-0"
                          style={{ zIndex: board.members.length - idx }}
                        >
                          {(m.name || m.username)[0].toUpperCase()}
                        </div>
                      ))}
                    </div>
                    <span className="text-[13px] text-[var(--text-muted)]">
                      {board.members.map((m) => m.name || m.username).join(', ')}
                    </span>
                  </div>

                  {/* Column Stats */}
                  <div className="flex gap-3 mt-4 flex-wrap">
                    {COLUMNS.map((col) => {
                      const count = board.tasks.filter((t) => t.status === col.key).length;
                      return (
                        <div key={col.key} className="flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full" style={{ background: COL_COLORS[col.key] || col.color }} />
                          <span className="text-xs text-[var(--text-muted)]">{col.label}</span>
                          <span className="text-xs font-semibold text-[var(--text)]">{count}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Progress Footer */}
                <div className="px-5 py-4 mt-4 border-t border-[var(--border-light)]">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[13px] font-semibold text-[var(--text-muted)]">Progress</span>
                    <span className={`text-[13px] font-bold ${pct === 100 ? 'text-emerald-500' : 'text-[var(--text)]'}`}>{pct}%</span>
                  </div>
                  <div className="w-full h-1.5 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-[width] duration-500 ease-out"
                      style={{
                        width: `${pct}%`,
                        background: pct === 100 ? '#22c55e' : 'linear-gradient(90deg, #6366f1, #818cf8)',
                      }}
                    />
                  </div>
                  <div className="flex justify-end mt-3">
                    <span className="inline-flex items-center gap-1 text-[13px] font-semibold text-[var(--primary)] cursor-pointer hover:underline">
                      View Board <ArrowRight size={14} />
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
