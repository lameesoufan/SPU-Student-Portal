import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  LayoutGrid,
  Search,
  Upload,
  FileSpreadsheet,
  UserPlus,
  Users,
  BookOpen,
  Kanban,
  BarChart3,
  Calendar,
  GraduationCap,
  Bell,
  ArrowRight,
  CheckCircle,
  Clock,
  Info,
  Building2,
} from 'lucide-react';
import DashboardLayout from './DashboardLayout';
import usePageHistory from '../hooks/usePageHistory';
import './DashboardLayout.css';
import HodProjects from './HodProjects';
import ImportUsers from './ImportUsers';
import ImportProjects from './ImportProjects';
import AssignHod from './AssignHod';
import { useTheme } from '../ThemeContext';
import {
  fetchUnreadCount,
  fetchNotifications,
  markNotifRead,
  markAllNotifsRead,
} from '../api';
import { NotifIcon, notifBgColor, notifTextColor } from './NotifHelpers.jsx';
import usePolling from '../hooks/usePolling';
/* ── SVG Icon Components ── */
const Icon = {
  Overview: LayoutGrid,
  Search: Search,
  Upload: Upload,
  ProjectImport: FileSpreadsheet,
  UserPlus: UserPlus,
  Users: Users,
  BookOpen: BookOpen,
  Kanban: Kanban,
  BarChart: BarChart3,
  Calendar: Calendar,
  GradCap: GraduationCap,
  Bell: Bell,
  ArrowRight: ArrowRight,
  CheckCircle: CheckCircle,
  Clock: Clock,
  Info: Info,
  Building: Building2,
};

/* ── Navigation Items ── */
const NAV_ITEMS = [
  { id: 'dashboard', label: 'Overview', IconComp: Icon.Overview },
  { id: 'import', label: 'Import Users', IconComp: Icon.Upload },
  { id: 'import-projects', label: 'Import Projects', IconComp: Icon.ProjectImport },
  { id: 'assign-hod', label: 'Assign HoD', IconComp: Icon.UserPlus },
  { id: 'projects', label: 'All Projects', IconComp: Icon.Kanban },
  { id: 'faculty', label: 'Faculty Overview', IconComp: Icon.Users },
  { id: 'programs', label: 'Academic Programs', IconComp: Icon.BookOpen },
  { id: 'analytics', label: 'Analytics', IconComp: Icon.BarChart },
];

/* ── Module Cards ── */
const MODULE_CARDS = [
  {
    IconComp: Icon.Upload,
    label: 'Import Users',
    desc: 'Bulk import students and faculty members into the system',
    page: 'import',
    gradient: 'linear-gradient(135deg, #6366f1, #818cf8)',
  },
  {
    IconComp: Icon.ProjectImport,
    label: 'Import Projects',
    desc: 'Preview and import assigned student projects from XLSX files',
    page: 'import-projects',
    gradient: 'linear-gradient(135deg, #0ea5e9, #38bdf8)',
  },
  {
    IconComp: Icon.UserPlus,
    label: 'Assign HoD',
    desc: 'Assign heads of departments and manage department leadership',
    page: 'assign-hod',
    gradient: 'linear-gradient(135deg, #8b5cf6, #a78bfa)',
  },
  {
    IconComp: Icon.Kanban,
    label: 'All Projects',
    desc: 'Monitor all department projects across the university',
    page: 'projects',
    gradient: 'linear-gradient(135deg, #06b6d4, #22d3ee)',
  },
  {
    IconComp: Icon.Users,
    label: 'Faculty Overview',
    desc: 'View and manage all faculty members across departments',
    page: null,
    gradient: 'linear-gradient(135deg, #10b981, #34d399)',
  },
  {
    IconComp: Icon.BookOpen,
    label: 'Academic Programs',
    desc: 'Manage university academic programs and curricula',
    page: null,
    gradient: 'linear-gradient(135deg, #f59e0b, #fbbf24)',
  },
  {
    IconComp: Icon.BarChart,
    label: 'Analytics',
    desc: 'University-wide statistics and performance metrics',
    page: null,
    gradient: 'linear-gradient(135deg, #ec4899, #f472b6)',
  },
];



/* ── Main Component ── */
export default function DeanDashboard({ user, onLogout }) {
  const { theme, toggleTheme } = useTheme();
  const [page, setPage, goBack] = usePageHistory('dashboard');
  
  const [mounted, setMounted] = useState(false);
  
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);



  /* ── Fetch notifications ── */
  const loadNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const results = await Promise.allSettled([
        fetchUnreadCount(),
        fetchNotifications(),
      ]);
      if (results[0].status === 'fulfilled') {
        setUnreadCount(results[0].value.data?.unread_count ?? 0);
      }
      if (results[1].status === 'fulfilled') {
        setNotifications(results[1].value.data?.results || results[1].value.data || []);
      }
    } catch {
      // Ignore
    } finally {
      setLoading(false);
    }
   
  }, []);

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 50);
    return () => clearTimeout(t);
   
  }, []);

  useEffect(() => {
    loadNotifications();
  }, [loadNotifications]);

/* ── Poll unread count ── */
usePolling(async () => {
  try {
    var res = await fetchUnreadCount();
    setUnreadCount(res.data?.unread_count ?? res.data?.count ?? 0);
  } catch (e) {
    // Ignore
  }
}, 30000);


  const handleLogout = () => {
    if (onLogout) onLogout();
  };

  const handleNavClick = (id) => {
    if (id === 'faculty' || id === 'programs' || id === 'analytics') return;
    setPage(id);
  };

  const handleMarkAllRead = async () => {
    try {
      await markAllNotifsRead();
      setUnreadCount(0);
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch {
      // Ignore
    }
  };

  const handleMarkRead = async (notifId) => {
    try {
      await markNotifRead(notifId);
      setNotifications((prev) =>
        prev.map((n) => (n.id === notifId ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch {
      // Ignore
    }
  };

  /* ── Render sub-pages ── */
  const renderContent = () => {
    if (page === 'import') {
      return (
        <div className="std-page-wrapper">
          <ImportUsers onBack={goBack} />
        </div>
      );
    }
    if (page === 'import-projects') {
      return (
        <div className="std-page-wrapper">
          <ImportProjects onBack={goBack} />
        </div>
      );
    }
    if (page === 'assign-hod') {
      return (
        <div className="std-page-wrapper">
          <AssignHod onBack={goBack} />
        </div>
      );
    }
    if (page === 'projects') {
      return (
        <div className="std-page-wrapper">
          <HodProjects onBack={goBack} user={user} />
        </div>
      );
    }

    return (
      <div className="std-content">
        <div className={`std-hero ${mounted ? 'std-animate-in' : ''}`}>
          <div className="std-hero-bg-orbs">
            <div className="std-orb std-orb-1" />
            <div className="std-orb std-orb-2" />
            <div className="std-orb std-orb-3" />
          </div>
          <div className="std-hero-content">
            <div className="std-hero-text">
              <h1 className="std-hero-title">
                Welcome back, <span className="std-gradient-text">Dr. {user.username}</span>
              </h1>
              <p className="std-hero-sub">
                Overseeing all university operations, managing departments, and ensuring academic excellence.
              </p>
            </div>
            <div className="std-hero-right">
              <div className="std-hero-empty-ring">
                <Icon.Building size={28} />
                <span>Dean Portal</span>
              </div>
            </div>
          </div>
        </div>

        <div className={`std-stats ${mounted ? 'std-animate-in std-delay-1' : ''}`}>
          <div className="std-stat-card">
            <div className="std-stat-icon std-stat-blue">
              <Icon.Calendar size={20} />
            </div>
            <div className="std-stat-info">
              <span className="std-stat-title">Semester</span>
              <span className="std-stat-value">Spring</span>
            </div>
          </div>
          <div className="std-stat-card">
            <div className="std-stat-icon std-stat-green">
              <Icon.GradCap size={20} />
            </div>
            <div className="std-stat-info">
              <span className="std-stat-title">Role</span>
              <span className="std-stat-value std-text-green">Dean</span>
            </div>
          </div>
          <div className="std-stat-card">
            <div className="std-stat-icon std-stat-purple">
              <Icon.Building size={20} />
            </div>
            <div className="std-stat-info">
              <span className="std-stat-title">Departments</span>
              <span className="std-stat-value std-text-purple">5</span>
            </div>
          </div>
          <div className="std-stat-card">
            <div className="std-stat-icon std-stat-amber">
              <Icon.Bell size={20} />
            </div>
            <div className="std-stat-info">
              <span className="std-stat-title">Notifications</span>
              <span className="std-stat-value std-text-amber">
                {loading ? '—' : unreadCount}
              </span>
            </div>
          </div>
        </div>

        <div className={`std-modules ${mounted ? 'std-animate-in std-delay-2' : ''}`}>
          <h2 className="std-section-title">University Operations</h2>
          <div className="std-modules-grid">
            {MODULE_CARDS.map((m, i) => (
              <div
                key={m.label}
                className={`std-module-card ${mounted ? `std-card-in std-card-delay-${i}` : ''}`}
                onClick={() => m.page && setPage(m.page)}
                tabIndex={m.page ? 0 : -1}
                role="button"
                style={m.page ? {} : { opacity: 0.6, cursor: 'not-allowed' }}
                onKeyDown={m.page ? (e) => e.key === 'Enter' && setPage(m.page) : undefined}
              >
                <div className="std-module-icon" style={{ background: m.gradient }}>
                  <m.IconComp size={28} />
                </div>
                <div className="std-module-info">
                  <span className="std-module-label">{m.label}</span>
                  <span className="std-module-desc">{m.desc}</span>
                </div>
                {m.page && (
                  <div className="std-module-arrow">
                    <Icon.ArrowRight size={18} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        <div className={`std-activity ${mounted ? 'std-animate-in std-delay-3' : ''}`}>
          <h2 className="std-section-title">Recent Notifications</h2>
          <div className="std-activity-list">
            {notifications.length === 0 ? (
              <div className="std-empty-state">
                <Icon.Bell size={32} />
                <p>No notifications yet</p>
              </div>
            ) : (
              notifications.slice(0, 4).map((n, i) => (
                <div
                  key={n.id}
                  className={`std-activity-item ${mounted ? `std-activity-in std-activity-delay-${i}` : ''} ${!n.is_read ? 'std-activity-unread' : ''}`}
                  onClick={() => !n.is_read && handleMarkRead(n.id)}
                  role="button"
                  tabIndex={0}
                >
                  <div
                    className="std-activity-dot"
                    style={{ background: notifTextColor(n.notif_type) }}
                  />
                  <div className="std-activity-content">
                    <span className="std-activity-action">{n.title || n.message}</span>
                    {n.message && n.title && (
                      <span className="std-activity-detail">{n.message}</span>
                    )}
                  </div>
                  <span className="std-activity-time">
                    {n.created_at
                      ? new Date(n.created_at).toLocaleDateString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })
                      : ''}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    );
  };

 
  const currentPageLabel = NAV_ITEMS.find((n) => n.id === page)?.label || 'Overview';
    return (
    <DashboardLayout
      navItems={NAV_ITEMS}
      activePage={page}
      onNavigate={handleNavClick}
      unreadCount={unreadCount}
      logoSubtitle="Student Dashboard"
      pageTitle={currentPageLabel}
      theme={theme}
      onToggleTheme={toggleTheme}
      notifications={notifications}
      onMarkAllRead={handleMarkAllRead}
      onMarkRead={handleMarkRead}
      user={user}
      onLogout={handleLogout}
      roleLabel="Dean"
    >
      {renderContent()}
    </DashboardLayout>
  );


}
