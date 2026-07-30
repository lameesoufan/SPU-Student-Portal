
import React, { useState, useEffect, useRef, useCallback } from 'react';
import ChangePassword from './ChangePassword';
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
  ShieldAlert,
  DoorClosed,
  Settings as SettingsIcon,
  Sparkles,
} from 'lucide-react';
import DashboardLayout from './DashboardLayout';
import usePageHistory from '../hooks/usePageHistory';
import './DashboardLayout.css';
import HodProjects from './HodProjects';
import ImportUsers from './ImportUsers';
import ImportProjects from './ImportProjects';
import AssignHod from './AssignHod';
import CommitteesDashboard from './committees/CommitteesDashboard';
import TemplateForm from './committees/TemplateForm';
import DistributionTable from './committees/DistributionTable';
import CommitteeDetail from './committees/CommitteeDetail';
import ProjectsAssignment from './committees/ProjectsAssignment';
import RoomsManagement from './committees/RoomsManagement';
import DoctorAvailabilityPage from './committees/DoctorAvailabilityPage';
import SolverSettingsPage from './committees/SolverSettingsPage';
import SchedulePage from './committees/SchedulePage';
import SemesterSetupWizard from './committees/SemesterSetupWizard';
import StudentStatusManagement from './StudentStatusManagement';
import GradesSummary from './GradesSummary';
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
  StudentStatus: ShieldAlert,
  Door: DoorClosed,
  SolverSettings: SettingsIcon,
  Schedule: Calendar,
  Wizard: Sparkles,
};

/* ── Navigation Items ── */
const NAV_ITEMS = [
  { id: 'dashboard', label: 'نظرة عامة', IconComp: Icon.Overview },
  { section: 'إدارة اللجان' },
  { id: 'committees', label: 'التشكيلات والتوزيع', IconComp: Icon.Kanban },
  { id: 'schedule', label: 'جدولة اللجان', IconComp: Icon.Schedule },
  { id: 'rooms', label: 'القاعات', IconComp: Icon.Door },
  { id: 'availability', label: 'توفر الدكاترة', IconComp: Icon.Users },
  { section: 'الطلاب والمشاريع' },
  { id: 'projects', label: 'كل المشاريع', IconComp: Icon.Kanban },
  { id: 'student-status', label: 'حالة الطلاب', IconComp: Icon.StudentStatus },
  { id: 'grades-summary', label: 'علامات المشاريع', IconComp: Icon.CheckCircle },
  { section: 'الإدارة' },
  { id: 'import', label: 'استيراد مستخدمين', IconComp: Icon.Upload },
  { id: 'import-projects', label: 'استيراد مشاريع', IconComp: Icon.ProjectImport },
  { id: 'assign-hod', label: 'تعيين رؤساء أقسام', IconComp: Icon.UserPlus },
  { id: 'faculty', label: 'الدكاترة', IconComp: Icon.Users },
];

/* ── Module Cards ── */
const MODULE_CARDS = [
  {
    IconComp: Icon.Kanban,
    label: 'إدارة اللجان',
    desc: 'إنشاء التشكيلات، توزيع المشاريع، مراقبة اللجان وأعباء الدكاترة',
    page: 'committees',
    gradient: 'linear-gradient(135deg, #7c3aed, #a78bfa)',
  },
  {
    IconComp: Icon.StudentStatus,
    label: 'إدارة حالة الطلاب',
    desc: 'تحديد حالة المشاركين في المشاريع: نشط، راسب، منسحب مع سجل التدقيق',
    page: 'student-status',
    gradient: 'linear-gradient(135deg, #0f766e, #14b8a6)',
  },
  {
    IconComp: Icon.Upload,
    label: 'استيراد المستخدمين',
    desc: 'استيراد جماعي للطلاب وأعضاء الهيئة التدريسية إلى النظام',
    page: 'import',
    gradient: 'linear-gradient(135deg, #6366f1, #818cf8)',
  },
  {
    IconComp: Icon.ProjectImport,
    label: 'استيراد المشاريع',
    desc: 'معاينة واستيراد المشاريع الطلابية المسندة من ملفات XLSX',
    page: 'import-projects',
    gradient: 'linear-gradient(135deg, #0ea5e9, #38bdf8)',
  },
  {
    IconComp: Icon.UserPlus,
    label: 'تعيين رؤساء الأقسام',
    desc: 'تعيين رؤساء الأقسام وإدارة قيادة الأقسام',
    page: 'assign-hod',
    gradient: 'linear-gradient(135deg, #8b5cf6, #a78bfa)',
  },
  {
    IconComp: Icon.Kanban,
    label: 'جميع المشاريع',
    desc: 'مراقبة جميع مشاريع الأقسام في الجامعة',
    page: 'projects',
    gradient: 'linear-gradient(135deg, #06b6d4, #22d3ee)',
  },
  {
    IconComp: Icon.Users,
    label: 'نظرة عامة على الهيئة التدريسية',
    desc: 'عرض وإدارة جميع أعضاء الهيئة التدريسية عبر الأقسام',
    page: null,
    gradient: 'linear-gradient(135deg, #10b981, #34d399)',
  },
  {
    IconComp: Icon.BookOpen,
    label: 'البرامج الأكاديمية',
    desc: 'إدارة البرامج الأكاديمية والمناهج الجامعية',
    page: null,
    gradient: 'linear-gradient(135deg, #f59e0b, #fbbf24)',
  },
  {
    IconComp: Icon.BarChart,
    label: 'التحليلات',
    desc: 'إحصائيات ومؤشرات الأداء على مستوى الجامعة',
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

  // Track navigation context (e.g., which committee/template to load)
  const [navContext, setNavContext] = useState(null);

  const handleNavClick = (id) => {
    if (id === 'faculty' || id === 'programs' || id === 'analytics') return;
    setNavContext(null);
    setPage(id);
  };

  // Programmatic navigation with context (e.g., open committee detail by id)
  const navigateTo = (id, ctx = null) => {
    setNavContext(ctx);
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
    if (page === 'change-password') return <div className="std-page-wrapper"><ChangePassword user={user} onBack={goBack} /></div>;
    if (page === 'committees') {
      return (
        <div className="std-page-wrapper">
          <CommitteesDashboard user={user} onNavigate={navigateTo} />
        </div>
      );
    }
    if (page === 'student-status') {
      return (
        <div className="std-page-wrapper">
          <StudentStatusManagement onBack={goBack} />
        </div>
      );
    }
    if (page === 'committees-template-form') {
      return (
        <div className="std-page-wrapper">
          <TemplateForm
            editId={navContext?.editId || null}
            onBack={() => setPage('committees')}
            onSaved={() => setPage('committees')}
          />
        </div>
      );
    }
    if (page === 'committees-list') {
      return (
        <div className="std-page-wrapper">
          <DistributionTable
            filterTemplateId={navContext?.templateId || null}
            onBack={() => setPage('committees')}
            onNavigate={navigateTo}
          />
        </div>
      );
    }
    if (page === 'committee-detail') {
      const committeeId = navContext?.id || navContext?.committeeId;
      if (!committeeId) {
        // No id provided — bounce back to list
        setPage('committees-list');
        return null;
      }
      return (
        <div className="std-page-wrapper">
          <CommitteeDetail
            committeeId={committeeId}
            onBack={() => setPage('committees-list')}
            onNavigate={navigateTo}
          />
        </div>
      );
    }
    if (page === 'projects-assignment') {
      return (
        <div className="std-page-wrapper">
          <ProjectsAssignment onBack={() => setPage('committees')} />
        </div>
      );
    }
    if (page === 'rooms') {
      return (
        <div className="std-page-wrapper">
          <RoomsManagement onBack={goBack} />
        </div>
      );
    }
    if (page === 'availability') {
      return (
        <div className="std-page-wrapper">
          <DoctorAvailabilityPage onBack={goBack} />
        </div>
      );
    }
    if (page === 'solver-settings') {
      return (
        <div className="std-page-wrapper">
          <SolverSettingsPage onBack={goBack} />
        </div>
      );
    }
    if (page === 'semester-wizard') {
      return (
        <div className="std-page-wrapper">
          <SemesterSetupWizard onBack={goBack} />
        </div>
      );
    }
    if (page === 'schedule') {
      return (
        <div className="std-page-wrapper">
          <SchedulePage onBack={goBack} />
        </div>
      );
    }
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
    if (page === 'grades-summary') {
      return (
        <div className="std-page-wrapper">
          <GradesSummary onBack={goBack} />
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
                مرحباً بعودتك، <span className="std-gradient-text">د. {user.username}</span>
              </h1>
              <p className="std-hero-sub">
                الإشراف على جميع عمليات الجامعة، إدارة الأقسام، وضمان التميز الأكاديمي.
              </p>
            </div>
            <div className="std-hero-right">
              <div className="std-hero-empty-ring">
                <Icon.Building size={28} />
                <span>بوابة العميد</span>
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
              <span className="std-stat-title">الفصل</span>
              <span className="std-stat-value">ربيعي</span>
            </div>
          </div>
          <div className="std-stat-card">
            <div className="std-stat-icon std-stat-green">
              <Icon.GradCap size={20} />
            </div>
            <div className="std-stat-info">
              <span className="std-stat-title">الدور</span>
              <span className="std-stat-value std-text-green">عميد</span>
            </div>
          </div>
          <div className="std-stat-card">
            <div className="std-stat-icon std-stat-purple">
              <Icon.Building size={20} />
            </div>
            <div className="std-stat-info">
              <span className="std-stat-title">الأقسام</span>
              <span className="std-stat-value std-text-purple">5</span>
            </div>
          </div>
          <div className="std-stat-card">
            <div className="std-stat-icon std-stat-amber">
              <Icon.Bell size={20} />
            </div>
            <div className="std-stat-info">
              <span className="std-stat-title">الإشعارات</span>
              <span className="std-stat-value std-text-amber">
                {loading ? '—' : unreadCount}
              </span>
            </div>
          </div>
        </div>

        <div className={`std-modules ${mounted ? 'std-animate-in std-delay-2' : ''}`}>
          <h2 className="std-section-title">عمليات الجامعة</h2>
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
          <h2 className="std-section-title">آخر الإشعارات</h2>
          <div className="std-activity-list">
            {notifications.length === 0 ? (
              <div className="std-empty-state">
                <Icon.Bell size={32} />
                <p>لا توجد إشعارات بعد</p>
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

 
  const currentPageLabel = NAV_ITEMS.find((n) => n.id === page)?.label || 'نظرة عامة';
    return (
    <DashboardLayout
      navItems={NAV_ITEMS}
      activePage={page}
      onNavigate={handleNavClick}
      unreadCount={unreadCount}
      logoSubtitle="لوحة التحكم"
      pageTitle={currentPageLabel}
      theme={theme}
      onToggleTheme={toggleTheme}
      notifications={notifications}
      onMarkAllRead={handleMarkAllRead}
      onMarkRead={handleMarkRead}
      user={user}
      onLogout={handleLogout}
      roleLabel="عميد"
    >
      {renderContent()}
    </DashboardLayout>
  );


}
