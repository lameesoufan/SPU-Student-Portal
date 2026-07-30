import React from 'react';
import NotificationBell from './NotificationBell';
import { useTheme } from '../ThemeContext';

const ROLE_LABELS = {
  dean: 'Dean',
  admin: 'Administrator',
  hod: 'Head of Department',
  doctor: 'Doctor',
  student: 'Student',
};

/* SVG Icons for theme toggle */
const SunIcon = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="5"/>
    <line x1="12" y1="1" x2="12" y2="3"/>
    <line x1="12" y1="21" x2="12" y2="23"/>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
    <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
    <line x1="1" y1="12" x2="3" y2="12"/>
    <line x1="21" y1="12" x2="23" y2="12"/>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
    <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
  </svg>
);

const MoonIcon = ({ size = 20 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>
);

export default function Navbar({ user, onLogout, currentPage }) {
  const { theme, toggleTheme } = useTheme();
  const showBell = ['student', 'doctor', 'hod', 'dean'].includes(user.role);

  const getBreadcrumb = () => {
    const roleName = ROLE_LABELS[user.role] || user.role;
    if (!currentPage || currentPage === 'dashboard') return roleName;
    const pageName = currentPage.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    return `${roleName} / ${pageName}`;
  };

  return (
    <nav className="flex items-center justify-between bg-white dark:bg-gray-900 text-gray-900 dark:text-white px-6 h-16 shadow-md sticky top-0 z-[100] border-b border-gray-200 dark:border-gray-700 transition-colors duration-300" role="navigation" aria-label="Main navigation">
      <div className="flex items-center gap-8">
        <div className="flex items-center gap-3">
          <span className="text-2xl" aria-hidden="true">🎓</span>
          <span className="text-base font-extrabold text-violet-600 dark:text-violet-400 tracking-tight">SPU Portal</span>
        </div>
        <div className="flex items-center gap-2 text-[13px] text-gray-500 dark:text-gray-400 font-medium" aria-label="Breadcrumbs">
          <span className="text-gray-500 dark:text-gray-400 font-medium transition-colors duration-200 hover:text-violet-600 dark:hover:text-violet-400 cursor-pointer">Home</span>
          <span className="opacity-40 text-[10px]">/</span>
          <span className="text-gray-900 dark:text-white font-semibold">{getBreadcrumb()}</span>
        </div>
      </div>

      <div className="flex items-center gap-5">
        <button
          className="flex items-center justify-center w-[38px] h-[38px] rounded-full border-[1.5px] border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 cursor-pointer transition-all duration-200 shrink-0 hover:bg-violet-50 dark:hover:bg-violet-900/30 hover:border-violet-500 hover:text-violet-600 dark:hover:text-violet-400 hover:rotate-[15deg] active:rotate-0 active:scale-95"
          onClick={toggleTheme}
          aria-label={theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'}
          title={theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'}
        >
          {theme === 'light' ? <MoonIcon size={18} /> : <SunIcon size={18} />}
        </button>
        {showBell && <NotificationBell />}
        <div className="flex items-center gap-3 p-1 pl-3 bg-gray-50 dark:bg-gray-800 rounded-[30px] border border-gray-200 dark:border-gray-700 transition-colors duration-300">
          <div className="flex flex-col gap-px min-w-0">
            <span className="block text-[13px] font-bold text-gray-900 dark:text-white">{user.username}</span>
            <span className="block text-[11px] text-gray-500 dark:text-gray-400 font-semibold uppercase">{ROLE_LABELS[user.role] || user.role}</span>
          </div>
          <button className="btn btn-outline-danger py-1.5 px-4 text-xs font-bold rounded-[20px]" onClick={onLogout} aria-label="Sign out">
            Sign Out
          </button>
        </div>
      </div>
    </nav>
  );
}