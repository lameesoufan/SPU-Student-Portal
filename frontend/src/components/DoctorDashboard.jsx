import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  LayoutGrid,
  Search,
  Lightbulb,
  FileText,
  Inbox,
  Kanban,
  ClipboardList,
  BookOpen,
  Calendar,
  CheckCircle,
  Bell,
  ArrowRight,
  BarChart3,
  GraduationCap,
  UserPlus,
  Clock,
  Info,
} from 'lucide-react';
import ChangePassword from './ChangePassword';
import DashboardLayout from './DashboardLayout';
import usePageHistory from '../hooks/usePageHistory';
import './DashboardLayout.css';
import MyIdeas from './MyIdeas';
import SubmitIdea from './SubmitIdea';
import SupervisorReview from './SupervisorReview';
import DoctorApplicationReview from './DoctorApplicationReview';
import SupervisorProjects from './SupervisorProjects';
import WorkflowBuilder from './WorkflowBuilder';
import ApplyWorkflow from './ApplyWorkflow';
import WorkflowReview from './WorkflowReview';
import { useTheme } from '../ThemeContext';
import {
  fetchUnreadCount,
  fetchNotifications,
  markNotifRead,
  markAllNotifsRead,
} from '../api';
import { NotifIcon, notifBgColor, notifTextColor } from './NotifHelpers.jsx';
import usePolling from '../hooks/usePolling';
const Icon = {
  Overview: LayoutGrid,
  Search: Search,
  Lightbulb: Lightbulb,
  FileText: FileText,
  Inbox: Inbox,
  Kanban: Kanban,
  ClipboardList: ClipboardList,
  Book: BookOpen,
  Calendar: Calendar,
  CheckCircle: CheckCircle,
  Bell: Bell,
  ArrowRight: ArrowRight,
  BarChart: BarChart3,
  GradCap: GraduationCap,
  UserPlus: UserPlus,
  Clock: Clock,
  Info: Info,
  
};


const NAV_ITEMS = [
  { id: 'dashboard', label: 'Overview', IconComp: Icon.Overview },
  { id: 'my-ideas', label: 'My Ideas', IconComp: Icon.Lightbulb },
  { id: 'supervisor-review', label: 'Proposals', IconComp: Icon.FileText },
  { id: 'app-review', label: 'Applications', IconComp: Icon.Inbox },
  { id: 'supervised-projects', label: 'Projects', IconComp: Icon.Kanban },
  { id: 'workflow', label: 'Workflows', IconComp: Icon.BarChart },
  { id: 'applyworkflow', label: 'Apply Workflow', IconComp: Icon.ClipboardList },
  { id: 'reviewworkflow', label: 'Review Submissions', IconComp: Icon.CheckCircle },
];

const MODULE_CARDS = [
  { IconComp: Icon.Lightbulb, label: 'My Ideas', desc: 'Submit and manage your project ideas for student teams', page: 'my-ideas', gradient: 'linear-gradient(135deg, #f59e0b, #fbbf24)' },
  { IconComp: Icon.FileText, label: 'Student Proposals', desc: 'Review and approve student project proposals assigned to you', page: 'supervisor-review', gradient: 'linear-gradient(135deg, #6366f1, #818cf8)' },
  { IconComp: Icon.Inbox, label: 'Idea Applications', desc: 'Review student applications on your project ideas', page: 'app-review', gradient: 'linear-gradient(135deg, #06b6d4, #22d3ee)' },
  { IconComp: Icon.Kanban, label: 'Supervised Projects', desc: 'Track and monitor progress of your registered student projects', page: 'supervised-projects', gradient: 'linear-gradient(135deg, #8b5cf6, #a78bfa)' },
  { IconComp: Icon.BarChart, label: 'Workflow Builder', desc: 'Create dynamic project workflow templates with stages and fields', page: 'workflow', gradient: 'linear-gradient(135deg, #ec4899, #f472b6)' },
  { IconComp: Icon.ClipboardList, label: 'Apply Workflow', desc: 'Apply workflow templates to student projects', page: 'applyworkflow', gradient: 'linear-gradient(135deg, #10b981, #34d399)' },
];


export default function DoctorDashboard({ user, onLogout }) {
  const { theme, toggleTheme } = useTheme();
  const [page, setPage, goBack] = usePageHistory('dashboard');
  const [mounted, setMounted] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);


  const loadNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const results = await Promise.allSettled([fetchUnreadCount(), fetchNotifications()]);
      if (results[0].status === 'fulfilled') setUnreadCount(results[0].value.data?.unread_count ?? results[0].value.data?.count ?? 0);
      if (results[1].status === 'fulfilled') setNotifications(results[1].value.data?.results || results[1].value.data || []);
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { const t = setTimeout(() => setMounted(true), 50); return () => clearTimeout(t); }, []);
  useEffect(() => { loadNotifications(); }, [loadNotifications]);

/* ── Poll unread count ── */
usePolling(async () => {
  try {
    const res = await fetchUnreadCount();
    setUnreadCount(res.data?.unread_count ?? res.data?.count ?? 0);
  } catch {
    // Ignore
  }
}, 30000);


  const handleLogout = () => { if (onLogout) onLogout(); };
  const handleNavClick = (id) => {
    setPage(id);
  };

  const handleMarkAllRead = async () => {
    try { await markAllNotifsRead(); setUnreadCount(0); setNotifications((p) => p.map((n) => ({ ...n, is_read: true }))); } catch {}
  };
  const handleMarkRead = async (id) => {
    try { await markNotifRead(id); setNotifications((p) => p.map((n) => (n.id === id ? { ...n, is_read: true } : n))); setUnreadCount((p) => Math.max(0, p - 1)); } catch {}
  };

  const renderContent = () => {
    if (page === 'my-ideas') return <div className="std-page-wrapper"><MyIdeas onBack={goBack} onSubmitNew={() => setPage('submit-idea')} /></div>;
    if (page === 'submit-idea') return <div className="std-page-wrapper"><SubmitIdea onBack={goBack} /></div>;
    if (page === 'supervisor-review') return <div className="std-page-wrapper"><SupervisorReview onBack={goBack} /></div>;
    if (page === 'app-review') return <div className="std-page-wrapper"><DoctorApplicationReview onBack={goBack} /></div>;
    if (page === 'supervised-projects') return <div className="std-page-wrapper"><SupervisorProjects onBack={goBack} /></div>;
    if (page === 'workflow') return <div className="std-page-wrapper"><WorkflowBuilder onBack={goBack} /></div>;
    if (page === 'applyworkflow') return <div className="std-page-wrapper"><ApplyWorkflow onBack={goBack} /></div>;
    if (page === 'reviewworkflow') return <div className="std-page-wrapper"><WorkflowReview onBack={goBack} /></div>;
    if (page === 'change-password') return <div className="std-page-wrapper"><ChangePassword onBack={goBack} /></div>;
    return (
      <div className="std-content">
        <div className={`std-hero ${mounted ? 'std-animate-in' : ''}`}>
          <div className="std-hero-bg-orbs"><div className="std-orb std-orb-1"/><div className="std-orb std-orb-2"/><div className="std-orb std-orb-3"/></div>
          <div className="std-hero-content">
            <div className="std-hero-text">
              <h1 className="std-hero-title">Welcome back, <span className="std-gradient-text">Dr. {user.username}</span></h1>
              <p className="std-hero-sub">Manage your project ideas, review student proposals, and track supervised projects.</p>
            </div>
            <div className="std-hero-right">
              <div className="std-hero-empty-ring"><Icon.GradCap size={28}/><span>Faculty Portal</span></div>
            </div>
          </div>
        </div>

        <div className={`std-stats ${mounted ? 'std-animate-in std-delay-1' : ''}`}>
          <div className="std-stat-card"><div className="std-stat-icon std-stat-blue"><Icon.Calendar size={20}/></div><div className="std-stat-info"><span className="std-stat-title">Semester</span><span className="std-stat-value">Spring</span></div></div>
          <div className="std-stat-card"><div className="std-stat-icon std-stat-green"><Icon.GradCap size={20}/></div><div className="std-stat-info"><span className="std-stat-title">Role</span><span className="std-stat-value std-text-green">Faculty</span></div></div>
          <div className="std-stat-card"><div className="std-stat-icon std-stat-purple"><Icon.Book size={20}/></div><div className="std-stat-info"><span className="std-stat-title">Department</span><span className="std-stat-value std-text-purple">{user.department || '—'}</span></div></div>
          <div className="std-stat-card"><div className="std-stat-icon std-stat-amber"><Icon.Bell size={20}/></div><div className="std-stat-info"><span className="std-stat-title">Notifications</span><span className="std-stat-value std-text-amber">{loading ? '—' : unreadCount}</span></div></div>
        </div>

        <div className={`std-modules ${mounted ? 'std-animate-in std-delay-2' : ''}`}>
          <h2 className="std-section-title">Faculty Modules</h2>
          <div className="std-modules-grid">
            {MODULE_CARDS.map((m, i) => (
              <div key={m.label} className={`std-module-card ${mounted ? `std-card-in std-card-delay-${i}` : ''}`} onClick={() => setPage(m.page)} tabIndex={0} role="button" onKeyDown={(e) => e.key === 'Enter' && setPage(m.page)}>
                <div className="std-module-icon" style={{ background: m.gradient }}><m.IconComp size={28}/></div>
                <div className="std-module-info"><span className="std-module-label">{m.label}</span><span className="std-module-desc">{m.desc}</span></div>
                <div className="std-module-arrow"><Icon.ArrowRight size={18}/></div>
              </div>
            ))}
          </div>
        </div>

        <div className={`std-activity ${mounted ? 'std-animate-in std-delay-3' : ''}`}>
          <h2 className="std-section-title">Recent Notifications</h2>
          <div className="std-activity-list">
            {notifications.length === 0 ? (
              <div className="std-empty-state"><Icon.Bell size={32}/><p>No notifications yet</p></div>
            ) : (
              notifications.slice(0, 4).map((n, i) => (
                <div key={n.id} className={`std-activity-item ${mounted ? `std-activity-in std-activity-delay-${i}` : ''} ${!n.is_read ? 'std-activity-unread' : ''}`} onClick={() => !n.is_read && handleMarkRead(n.id)} role="button" tabIndex={0}>
                  <div className="std-activity-dot" style={{ background: notifTextColor(n.notif_type) }}/>
                  <div className="std-activity-content"><span className="std-activity-action">{n.title || n.message}</span>{n.message && n.title && <span className="std-activity-detail">{n.message}</span>}</div>
                  <span className="std-activity-time">{n.created_at ? new Date(n.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    );
  };

 
  const currentPageLabel = NAV_ITEMS.find((n) => n.id === page)?.label || 'Overview';
    const initial = user.username ? user.username.charAt(0).toUpperCase() : 'D';
  return (
    <DashboardLayout
      navItems={NAV_ITEMS}
      activePage={page}
      onNavigate={handleNavClick}
      unreadCount={unreadCount}
      logoSubtitle="Faculty Dashboard"
      pageTitle={currentPageLabel}
      theme={theme}
      onToggleTheme={toggleTheme}
      notifications={notifications}
      onMarkAllRead={handleMarkAllRead}
      onMarkRead={handleMarkRead}
      user={user}
      onLogout={handleLogout}
       roleLabel="Faculty"
    >
      {renderContent()}
    </DashboardLayout>
  );

}