import React, { useState, useEffect } from 'react';
import { fetchHodBoards, fetchHodStats } from '../api';
import KanbanBoard, { COLUMNS } from './KanbanBoard';
import { getProjectTypeLabel } from '../lib/constants';
import {
  FolderKanban, BarChart3, FileText, Lightbulb, TrendingUp,
  ArrowLeft, Eye, Loader2, FolderOpen, Users,
  Github,
} from 'lucide-react';

const STAT_ICONS = {
  projects: BarChart3,
  proposals: FileText,
  ideas: Lightbulb,
  progress: TrendingUp,
};

export default function HodProjects({ onBack, user }) {
  const [boards, setBoards]     = useState([]);
  const [stats, setStats]       = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    Promise.all([fetchHodBoards(), fetchHodStats()])
      .then(([boardsRes, statsRes]) => {
        setBoards(boardsRes.data);
        setStats(statsRes.data);
      })
      .catch(() => setError('Failed to load projects.'))
      .finally(() => setLoading(false));
  }, []);

  const selectedBoard = boards.find((b) => b.id === selected);

  /* ── Board View (Read-Only Kanban) ── */
  if (selected && selectedBoard) {
    return (
      <div className="w-full">
        <div className="flex items-center gap-3 mb-5 pb-4 border-b border-gray-200 dark:border-gray-700">
          <button
            className="inline-flex items-center gap-1.5 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg px-3.5 py-2 text-[13px] font-medium text-gray-500 dark:text-gray-400 cursor-pointer transition-colors hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-white"
            onClick={() => setSelected(null)}
          >
            <ArrowLeft size={16} />
            All Projects
          </button>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-600 border border-amber-500/20">
            <Eye size={12} />
            Read-Only View
          </span>
          {selectedBoard.github_repo && (
            <a 
              href={selectedBoard.github_repo} 
              target="_blank" 
              rel="noreferrer" 
              className="inline-flex items-center gap-1.5 ml-auto text-[13px] font-medium text-violet-600 dark:text-violet-400 hover:underline"
            >
              <Github size={14} />
              GitHub Repo
            </a>
          )}
        </div>
        <KanbanBoard
          board={selectedBoard}
          setBoard={() => {}}
          canEdit={false}
        />
      </div>
    );
  }

  /* ── Projects List View ── */
  return (
    <div className="py-2">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-violet-600/10 text-violet-600">
          <FolderKanban size={20} />
        </div>
        <h2 className="text-2xl font-extrabold tracking-tight text-gray-900 dark:text-white m-0">
          {user.role === 'dean' ? 'All Department Projects' : 'Department Projects'}
        </h2>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4 mb-7">
          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5 flex items-center gap-4 shadow-sm transition-all hover:border-violet-500/30 hover:shadow-md">
            <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-sky-500/10 text-sky-500 flex-shrink-0">
              <BarChart3 size={24} />
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[26px] font-bold text-gray-900 dark:text-white leading-none">{stats.total_projects}</span>
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Active Projects</span>
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5 flex items-center gap-4 shadow-sm transition-all hover:border-violet-500/30 hover:shadow-md">
            <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-violet-500/10 text-violet-500 flex-shrink-0">
              <FileText size={24} />
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[26px] font-bold text-gray-900 dark:text-white leading-none">{stats.proposals_count}</span>
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Student Proposals</span>
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5 flex items-center gap-4 shadow-sm transition-all hover:border-violet-500/30 hover:shadow-md">
            <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-amber-500/10 text-amber-500 flex-shrink-0">
              <Lightbulb size={24} />
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[26px] font-bold text-gray-900 dark:text-white leading-none">{stats.applications_count}</span>
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Doctor Ideas</span>
            </div>
          </div>

          <div className="bg-violet-500/5 border border-violet-500/20 rounded-xl p-5 flex items-center gap-4 shadow-sm transition-all hover:border-violet-500 hover:shadow-md">
            <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-500 flex-shrink-0">
              <TrendingUp size={24} />
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[26px] font-bold text-gray-900 dark:text-white leading-none">{stats.avg_progress}%</span>
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">Avg Progress</span>
            </div>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="border border-red-300 dark:border-red-700/50 rounded-lg py-3.5 px-4 bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 font-medium text-sm mb-5">
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex justify-center py-16">
          <Loader2 size={32} className="animate-spin text-violet-600" />
        </div>
      )}

      {/* Empty State */}
      {!loading && boards.length === 0 && !error && (
        <div className="flex flex-col items-center gap-3 py-16 text-center mb-8">
          <div className="flex items-center justify-center w-16 h-16 rounded-2xl bg-gray-100 dark:bg-gray-700/50 text-gray-500 dark:text-gray-400">
            <FolderOpen size={32} />
          </div>
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">No Active Projects</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-sm leading-relaxed">
            Projects will appear here once they are registered.
          </p>
        </div>
      )}

      {/* Projects Grid */}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4 mt-5">
        {boards.map((board) => {
          const done  = board.tasks.filter((t) => t.status === 'done').length;
          const total = board.tasks.length;
          const pct   = total > 0 ? Math.round((done / total) * 100) : 0;

          return (
            <div
              key={board.id}
              className="bg-white dark:bg-gray-800 rounded-2xl p-5 border-[1.5px] border-gray-200 dark:border-gray-700 cursor-pointer transition-all flex flex-col gap-3.5 hover:shadow-lg hover:border-violet-500 hover:-translate-y-0.5"
              onClick={() => setSelected(board.id)}
            >
              {/* Title + Task Count */}
              <div className="flex items-start justify-between gap-2">
                <h3 className="text-[15px] font-bold text-gray-900 dark:text-white m-0 leading-snug">{board.title}</h3>
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 whitespace-nowrap flex-shrink-0">
                  {total} tasks
                </span>
              </div>

              {board.project_type && (
                <div className="flex items-start">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-purple-500/10 text-purple-600 dark:text-purple-400 tracking-wide">
                    {getProjectTypeLabel(board.project_type)}
                  </span>
                </div>
              )}

              {/* Members */}
              <div className="flex items-center gap-1.5 flex-wrap">
                {board.members.map((m) => (
                  <span
                    key={m.id}
                    className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 text-white text-[11px] font-bold flex items-center justify-center border-2 border-white dark:border-gray-800 shadow-sm flex-shrink-0"
                    title={m.name}
                  >
                    {(m.name || m.username)[0].toUpperCase()}
                  </span>
                ))}
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {board.members.map((m) => m.name || m.username).join(', ')}
                </span>
              </div>

              {/* Column Stats */}
              <div className="grid grid-cols-4 gap-1.5">
                {COLUMNS.map((col) => {
                  const count = board.tasks.filter((t) => t.status === col.key).length;
                  return (
                    <div key={col.key} className="bg-gray-50 dark:bg-gray-700 rounded-lg py-2 px-1 text-center border border-gray-200/50 dark:border-gray-600/50 flex flex-col items-center gap-1">
                      <span className="w-[7px] h-[7px] rounded-full" style={{ background: col.color }} />
                      <span className="text-[9px] text-gray-400 dark:text-gray-500 font-semibold uppercase tracking-wide">{col.label}</span>
                      <span className="text-xl font-bold text-gray-900 dark:text-white leading-none">{count}</span>
                    </div>
                  );
                })}
              </div>

              {/* Progress Bar */}
              <div className="flex items-center gap-2.5">
                <div className="flex-1 h-[5px] bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full transition-[width] duration-400 ease-out"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="text-xs font-bold text-violet-600 dark:text-violet-400 min-w-[32px] text-right">{pct}%</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}