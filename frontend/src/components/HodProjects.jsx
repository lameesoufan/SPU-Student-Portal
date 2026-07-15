import React, { useState, useEffect, useMemo } from 'react';
import { fetchHodBoards, fetchHodStats } from '../api';
import KanbanBoard, { COLUMNS } from './KanbanBoard';
import { getProjectTypeLabel, getDepartmentLabel } from '../lib/constants';
import {
  FolderKanban, BarChart3, FileText, Lightbulb, TrendingUp,
  ArrowLeft, Eye, Loader2, FolderOpen, Users,
  GitBranch, Search, ChevronDown, ChevronLeft, Folder,
} from 'lucide-react';

const STAT_ICONS = {
  projects: BarChart3,
  proposals: FileText,
  ideas: Lightbulb,
  progress: TrendingUp,
};

const DEPT_COLORS = {
  'ai':       { bg: 'rgba(99, 102, 241, 0.10)', text: '#4f46e5', border: 'rgba(99, 102, 241, 0.25)' },
  'cs':       { bg: 'rgba(16, 185, 129, 0.10)', text: '#059669', border: 'rgba(16, 185, 129, 0.25)' },
  'is':       { bg: 'rgba(245, 158, 11, 0.10)', text: '#d97706', border: 'rgba(245, 158, 11, 0.25)' },
  'sw':       { bg: 'rgba(236, 72, 153, 0.10)', text: '#db2777', border: 'rgba(236, 72, 153, 0.25)' },
  'default':  { bg: 'rgba(139, 92, 246, 0.10)', text: '#7c3aed', border: 'rgba(139, 92, 246, 0.25)' },
};

function deptStyle(dept) {
  return DEPT_COLORS[dept] || DEPT_COLORS.default;
}

export default function HodProjects({ onBack, user }) {
  const [boards, setBoards]     = useState([]);
  const [stats, setStats]       = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [selected, setSelected] = useState(null);
  // Department folder expansion + per-folder search
  const [expandedDepts, setExpandedDepts] = useState({});
  const [deptSearch, setDeptSearch]       = useState({});

  useEffect(() => {
    Promise.all([fetchHodBoards(), fetchHodStats()])
      .then(([boardsRes, statsRes]) => {
        setBoards(boardsRes.data);
        setStats(statsRes.data);
      })
      .catch(() => setError('فشل تحميل المشاريع.'))
      .finally(() => setLoading(false));
  }, []);

  const selectedBoard = boards.find((b) => b.id === selected);

  /* ── Group boards by department (Dean only) ── */
  const isDean = user?.role === 'dean';

  const groupedBoards = useMemo(() => {
    if (!isDean) return null;
    const groups = {};
    for (const b of boards) {
      const dept = b.department || 'unknown';
      if (!groups[dept]) groups[dept] = [];
      groups[dept].push(b);
    }
    // Sort departments alphabetically by Arabic label
    return Object.entries(groups).sort(([a], [b]) => {
      const la = getDepartmentLabel(a) || a;
      const lb = getDepartmentLabel(b) || b;
      return la.localeCompare(lb, 'ar');
    });
  }, [boards, isDean]);

  const totalDepts = groupedBoards ? groupedBoards.length : 0;

  const toggleDept = (dept) => {
    setExpandedDepts((prev) => ({ ...prev, [dept]: !prev[dept] }));
  };

  const setDeptSearchValue = (dept, value) => {
    setDeptSearch((prev) => ({ ...prev, [dept]: value }));
  };

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
            كل المشاريع
          </button>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-600 border border-amber-500/20">
            <Eye size={12} />
            عرض فقط
          </span>
          {selectedBoard.github_repo && selectedBoard.github_repo.startsWith('http') && (
            <a
              href={selectedBoard.github_repo}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 ml-auto text-[13px] font-medium text-violet-600 dark:text-violet-400 hover:underline"
            >
              <GitBranch size={14} />
              مستودع GitHub
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
          {isDean ? 'جميع مشاريع الأقسام' : 'مشاريع القسم'}
        </h2>
        {isDean && totalDepts > 0 && (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-violet-500/10 text-violet-600 border border-violet-500/20">
            <Folder size={12} />
            {totalDepts} أقسام
          </span>
        )}
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
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 tracking-wide">مشاريع نشطة</span>
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5 flex items-center gap-4 shadow-sm transition-all hover:border-violet-500/30 hover:shadow-md">
            <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-violet-500/10 text-violet-500 flex-shrink-0">
              <FileText size={24} />
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[26px] font-bold text-gray-900 dark:text-white leading-none">{stats.proposals_count}</span>
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 tracking-wide">مقترحات الطلاب</span>
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5 flex items-center gap-4 shadow-sm transition-all hover:border-violet-500/30 hover:shadow-md">
            <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-amber-500/10 text-amber-500 flex-shrink-0">
              <Lightbulb size={24} />
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[26px] font-bold text-gray-900 dark:text-white leading-none">{stats.applications_count}</span>
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 tracking-wide">أفكار الدكاترة</span>
            </div>
          </div>

          <div className="bg-violet-500/5 border border-violet-500/20 rounded-xl p-5 flex items-center gap-4 shadow-sm transition-all hover:border-violet-500 hover:shadow-md">
            <div className="flex items-center justify-center w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-500 flex-shrink-0">
              <TrendingUp size={24} />
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="text-[26px] font-bold text-gray-900 dark:text-white leading-none">{stats.avg_progress}%</span>
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400 tracking-wide">متوسط الإنجاز</span>
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
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">لا توجد مشاريع نشطة</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-sm leading-relaxed">
            ستظهر المشاريع هنا فور تسجيلها.
          </p>
        </div>
      )}

      {/* ── DEAN VIEW: Folders by Department ── */}
      {isDean && !loading && groupedBoards && groupedBoards.length > 0 && (
        <div className="flex flex-col gap-4 mt-5">
          {groupedBoards.map(([dept, deptBoards]) => {
            const isExpanded = expandedDepts[dept] ?? true; // default expanded
            const searchTerm = (deptSearch[dept] || '').toLowerCase().trim();
            const style = deptStyle(dept);
            const filteredBoards = searchTerm
              ? deptBoards.filter((b) => (b.title || '').toLowerCase().includes(searchTerm))
              : deptBoards;
            const totalTasks = deptBoards.reduce((sum, b) => sum + (b.tasks?.length || 0), 0);
            const doneTasks = deptBoards.reduce(
              (sum, b) => sum + (b.tasks?.filter((t) => t.status === 'done').length || 0), 0
            );
            const avgPct = deptBoards.length > 0
              ? Math.round(deptBoards.reduce((sum, b) => {
                  const done  = (b.tasks || []).filter((t) => t.status === 'done').length;
                  const total = (b.tasks || []).length;
                  return sum + (total > 0 ? (done / total) * 100 : 0);
                }, 0) / deptBoards.length)
              : 0;

            return (
              <div
                key={dept}
                className="bg-white dark:bg-gray-800 rounded-2xl border border-gray-200 dark:border-gray-700 overflow-hidden shadow-sm transition-all hover:shadow-md"
              >
                {/* Folder Header */}
                <button
                  className="flex items-center gap-3 w-full p-4 text-right bg-transparent border-none cursor-pointer transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/50"
                  onClick={() => toggleDept(dept)}
                  style={{ borderBottom: isExpanded ? `1px solid ${style.border}` : 'none' }}
                >
                  <span
                    className="flex items-center justify-center w-11 h-11 rounded-xl flex-shrink-0"
                    style={{ background: style.bg, color: style.text }}
                  >
                    <Folder size={22} />
                  </span>
                  <div className="flex-1 flex flex-col gap-0.5 text-right">
                    <span className="text-[15px] font-bold text-gray-900 dark:text-white">
                      {getDepartmentLabel(dept) || dept}
                    </span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      {deptBoards.length} مشروع · {totalTasks} مهمة · {avgPct}% إنجاز
                    </span>
                  </div>
                  {/* Progress mini-bar */}
                  <div className="hidden md:flex items-center gap-2 min-w-[140px]">
                    <div className="flex-1 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-[width] duration-300"
                        style={{ width: `${avgPct}%`, background: style.text }}
                      />
                    </div>
                    <span className="text-xs font-bold min-w-[34px] text-left" style={{ color: style.text }}>
                      {avgPct}%
                    </span>
                  </div>
                  <span
                    className="flex items-center justify-center w-7 h-7 rounded-lg text-gray-400 transition-transform duration-200"
                    style={{ transform: isExpanded ? 'rotate(0deg)' : 'rotate(-90deg)' }}
                  >
                    <ChevronDown size={18} />
                  </span>
                </button>

                {/* Folder Body (collapsible) */}
                {isExpanded && (
                  <div className="p-4 bg-gray-50/40 dark:bg-gray-900/20">
                    {/* In-folder Search Bar */}
                    <div className="relative mb-4">
                      <Search size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
                      <input
                        type="text"
                        value={deptSearch[dept] || ''}
                        onChange={(e) => setDeptSearchValue(dept, e.target.value)}
                        placeholder={`ابحث عن مشروع في ${getDepartmentLabel(dept) || dept}...`}
                        className="w-full py-2 pl-3 pr-9 text-[13px] bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-500/15 transition-all text-gray-900 dark:text-white placeholder:text-gray-400"
                      />
                      {searchTerm && (
                        <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[11px] text-gray-400">
                          {filteredBoards.length} نتيجة
                        </span>
                      )}
                    </div>

                    {/* Boards grid for this department */}
                    {filteredBoards.length > 0 ? (
                      <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-3">
                        {filteredBoards.map((board) => {
                          const done  = (board.tasks || []).filter((t) => t.status === 'done').length;
                          const total = (board.tasks || []).length;
                          const pct   = total > 0 ? Math.round((done / total) * 100) : 0;

                          return (
                            <div
                              key={board.id}
                              className="bg-white dark:bg-gray-800 rounded-xl p-4 border-[1.5px] border-gray-200 dark:border-gray-700 cursor-pointer transition-all flex flex-col gap-3 hover:shadow-lg hover:border-violet-500 hover:-translate-y-0.5"
                              onClick={() => setSelected(board.id)}
                            >
                              {/* Title + Task Count */}
                              <div className="flex items-start justify-between gap-2">
                                <h3 className="text-[14px] font-bold text-gray-900 dark:text-white m-0 leading-snug line-clamp-2">
                                  {board.title}
                                </h3>
                                <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 whitespace-nowrap flex-shrink-0">
                                  {total} مهمة
                                </span>
                              </div>

                              {board.project_type && (
                                <div className="flex items-start">
                                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold bg-purple-500/10 text-purple-600 dark:text-purple-400 tracking-wide">
                                    {getProjectTypeLabel(board.project_type)}
                                  </span>
                                </div>
                              )}

                              {/* Members */}
                              <div className="flex items-center gap-1.5 flex-wrap min-h-[28px]">
                                {(board.members || []).slice(0, 4).map((m) => (
                                  <span
                                    key={m.id}
                                    className="w-6 h-6 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 text-white text-[10px] font-bold flex items-center justify-center border-2 border-white dark:border-gray-800 shadow-sm flex-shrink-0"
                                    title={m.name || m.username}
                                  >
                                    {(m.name || m.username)[0].toUpperCase()}
                                  </span>
                                ))}
                                {(board.members || []).length > 4 && (
                                  <span className="text-[10px] text-gray-500 font-medium">
                                    +{(board.members || []).length - 4}
                                  </span>
                                )}
                              </div>

                              {/* Progress Bar */}
                              <div className="flex items-center gap-2.5">
                                <div className="flex-1 h-[4px] bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                  <div
                                    className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full transition-[width] duration-400 ease-out"
                                    style={{ width: `${pct}%` }}
                                  />
                                </div>
                                <span className="text-[11px] font-bold text-violet-600 dark:text-violet-400 min-w-[30px] text-right">{pct}%</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="flex flex-col items-center gap-2 py-8 text-center">
                        <Search size={20} className="text-gray-300" />
                        <p className="text-[13px] text-gray-500 dark:text-gray-400">
                          لا توجد نتائج مطابقة لبحثك
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── HOD VIEW: Flat projects grid (unchanged) ── */}
      {!isDean && !loading && boards.length > 0 && (
        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4 mt-5">
          {boards.map((board) => {
            const done  = (board.tasks || []).filter((t) => t.status === 'done').length;
            const total = (board.tasks || []).length;
            const pct   = total > 0 ? Math.round((done / total) * 100) : 0;

            return (
              <div
                key={board.id}
                className="bg-white dark:bg-gray-800 rounded-2xl p-5 border-[1.5px] border-gray-200 dark:border-gray-700 cursor-pointer transition-all flex flex-col gap-3.5 hover:shadow-lg hover:border-violet-500 hover:-translate-y-0.5"
                onClick={() => setSelected(board.id)}
              >
                <div className="flex items-start justify-between gap-2">
                  <h3 className="text-[15px] font-bold text-gray-900 dark:text-white m-0 leading-snug">{board.title}</h3>
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 whitespace-nowrap flex-shrink-0">
                    {total} مهمة
                  </span>
                </div>

                {board.project_type && (
                  <div className="flex items-start">
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-purple-500/10 text-purple-600 dark:text-purple-400 tracking-wide">
                      {getProjectTypeLabel(board.project_type)}
                    </span>
                  </div>
                )}

                <div className="flex items-center gap-1.5 flex-wrap">
                  {(board.members || []).map((m) => (
                    <span
                      key={m.id}
                      className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 text-white text-[11px] font-bold flex items-center justify-center border-2 border-white dark:border-gray-800 shadow-sm flex-shrink-0"
                      title={m.name}
                    >
                      {(m.name || m.username)[0].toUpperCase()}
                    </span>
                  ))}
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {(board.members || []).map((m) => m.name || m.username).join(', ')}
                  </span>
                </div>

                <div className="grid grid-cols-4 gap-1.5">
                  {COLUMNS.map((col) => {
                    const count = (board.tasks || []).filter((t) => t.status === col.key).length;
                    return (
                      <div key={col.key} className="bg-gray-50 dark:bg-gray-700 rounded-lg py-2 px-1 text-center border border-gray-200/50 dark:border-gray-600/50 flex flex-col items-center gap-1">
                        <span className="w-[7px] h-[7px] rounded-full" style={{ background: col.color }} />
                        <span className="text-[9px] text-gray-400 dark:text-gray-500 font-semibold tracking-wide">{col.label}</span>
                        <span className="text-xl font-bold text-gray-900 dark:text-white leading-none">{count}</span>
                      </div>
                    );
                  })}
                </div>

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
      )}
    </div>
  );
}
