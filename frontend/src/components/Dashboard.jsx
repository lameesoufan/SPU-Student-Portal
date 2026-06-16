import React from 'react';

const Icons = {
  ImportUsers: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
  ),
  ManageDepts: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/>
    </svg>
  ),
  Reports: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
    </svg>
  ),
  Settings: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
    </svg>
  ),
  Users: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
    </svg>
  ),
  Faculty: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
    </svg>
  ),
  Courses: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
    </svg>
  ),
  Grades: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="8" r="7"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/>
    </svg>
  ),
  Schedule: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
    </svg>
  ),
  ArrowRight: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
    </svg>
  ),
};

const ROLE_MODULES = {
  dean: [
    { icon: Icons.ImportUsers, label: 'Import Users', desc: 'Bulk import students & faculty accounts', page: 'import', color: '#2563EB', bg: '#EFF6FF' },
    { icon: Icons.ManageDepts, label: 'Assign HoD', desc: 'Manage department heads', page: 'assign-hod', color: '#7C3AED', bg: '#F5F3FF' },
    { icon: Icons.Users, label: 'Faculty Overview', desc: 'View all faculty members', page: null, color: '#059669', bg: '#ECFDF5' },
    { icon: Icons.Courses, label: 'Academic Programs', desc: 'Manage university programs', page: null, color: '#D97706', bg: '#FFFBEB' },
    { icon: Icons.Reports, label: 'Analytics', desc: 'University-wide statistics', page: null, color: '#DC2626', bg: '#FEF2F2' },
    { icon: Icons.Settings, label: 'System Settings', desc: 'Configure portal settings', page: null, color: '#64748B', bg: '#F1F5F9' },
  ],
  admin: [
    { icon: Icons.ImportUsers, label: 'Import Users', desc: 'Bulk import user accounts', page: 'import', color: '#2563EB', bg: '#EFF6FF' },
    { icon: Icons.Users, label: 'Manage Users', desc: 'User account management', page: null, color: '#7C3AED', bg: '#F5F3FF' },
    { icon: Icons.Reports, label: 'View Reports', desc: 'System reports and analytics', page: null, color: '#D97706', bg: '#FFFBEB' },
    { icon: Icons.Settings, label: 'System Settings', desc: 'Configure portal settings', page: null, color: '#64748B', bg: '#F1F5F9' },
  ],
};

export default function Dashboard({ user, onNavigate }) {
  const modules = ROLE_MODULES[user.role] || ROLE_MODULES.admin;

  return (
    <div className="premium-dashboard">
      <header className="pd-header">
        <div className="flex flex-col gap-1">
          <h1 className="pd-title">System Overview</h1>
          <p className="pd-subtitle">Welcome, {user.username}. Here's what's happening today.</p>
        </div>
        <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 py-3 px-5 rounded-xl flex flex-col items-end shadow-[0_4px_12px_rgba(217,119,6,0.05)]">
          <span className="text-[11px] uppercase tracking-widest text-amber-600 dark:text-amber-400 font-bold mb-1">Academic Year</span>
          <span className="text-[15px] font-extrabold text-amber-700 dark:text-amber-300">2025/2026</span>
        </div>
      </header>

      <div className="grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-5">
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-6 flex flex-col gap-2 shadow-md transition-colors duration-300">
          <span className="text-[13px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Total Users</span>
          <strong className="text-4xl font-extrabold text-gray-900 dark:text-white leading-none">--</strong>
        </div>
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-6 flex flex-col gap-2 shadow-md transition-colors duration-300">
          <span className="text-[13px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Active Projects</span>
          <strong className="text-4xl font-extrabold text-violet-600 dark:text-violet-400 leading-none">--</strong>
        </div>
        <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-6 flex flex-col gap-2 shadow-md transition-colors duration-300">
          <span className="text-[13px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Pending Approvals</span>
          <strong className="text-4xl font-extrabold text-amber-500 dark:text-amber-400 leading-none">--</strong>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-extrabold text-gray-900 dark:text-white mb-5">System Modules</h2>
        <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4" role="list">
          {modules.map((m) => (
            <button
              key={m.label}
              className={`group flex items-center gap-4 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5 cursor-pointer transition-all duration-200 text-left focus-visible:outline focus-visible:outline-3 focus-visible:outline-violet-300 focus-visible:outline-offset-2 hover:bg-gray-50 dark:hover:bg-gray-700/50 hover:border-violet-500 hover:-translate-y-0.5 hover:shadow-[0_8px_24px_rgba(124,58,237,0.15)] ${!m.page ? 'opacity-60 pointer-events-none cursor-not-allowed' : ''}`}
              role="listitem"
              onClick={() => m.page && onNavigate(m.page)}
              aria-label={m.label}
            >
              <div className="flex items-center justify-center w-12 h-12 rounded-xl shrink-0" style={{ background: m.bg, color: m.color }}>
                {m.icon}
              </div>
              <div className="flex-1 flex flex-col gap-1">
                <span className="text-[15px] font-bold text-gray-900 dark:text-white">{m.label}</span>
                <span className="text-[13px] text-gray-500 dark:text-gray-400">{m.desc}</span>
              </div>
              {m.page && <div className="text-violet-600 dark:text-violet-400 opacity-0 -translate-x-2 transition-all duration-200 group-hover:opacity-100 group-hover:translate-x-0">{Icons.ArrowRight}</div>}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}