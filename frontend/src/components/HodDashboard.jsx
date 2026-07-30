import ChangeEmail from './ChangeEmail';
import ChangePassword from './ChangePassword';
import {
  LayoutGrid,
  Search,
  Lightbulb,
  FileText,
  ClipboardCheck,
  Inbox,
  Table2,
  Kanban,
  BarChart3,
  BookOpen,
  Calendar,
  GraduationCap,
  Bell,
  ArrowRight,
  CheckCircle,
  UserPlus,
  Clock,
  Info,
  ClipboardList,
} from 'lucide-react';
import DashboardLayout from './DashboardLayout';
import React, { useState, useEffect, useRef, useCallback } from 'react';
import usePageHistory from '../hooks/usePageHistory';
import './DashboardLayout.css';
import HodProposalReview from './HodProposalReview';
import HodIdeaReview from './HodIdeaReview';
import HodApplicationReview from './HodApplicationReview';
import HodFormBuilder from './HodFormBuilder';
import HodProjects from './HodProjects';
import WorkflowBuilder from './WorkflowBuilder';
import ApplyWorkflow from './ApplyWorkflow';
import WorkflowReview from './WorkflowReview';import MyIdeas from './MyIdeas';         
import SubmitIdea from './SubmitIdea';
import CollectiveGradingSettings from './CollectiveGradingSettings';
import HodGradesSummary from './HodGradesSummary';
import GradeEntry from './committees/GradeEntry';
import { useTheme } from '../ThemeContext';
import {
  fetchUnreadCount,
  fetchNotifications,
  markNotifRead,
  markAllNotifsRead,
} from '../api';
import { NotifIcon, notifBgColor, notifTextColor } from './NotifHelpers.jsx';
const DEPT_LABELS = {
  software_engineering:    'برمجيات',
  artificial_intelligence: 'ذكاء اصطناعي',
  information_security:    'أمن سيبراني',
  communications:          'اتصالات',
  control_robotics:        'Control & Robotics',
};
import usePolling from '../hooks/usePolling';
/* ── SVG Icon Components ── */
const Icon = {
  Overview: LayoutGrid,
  Search: Search,
  Lightbulb: Lightbulb,
  FileText: FileText,
  ClipboardCheck: ClipboardCheck,
  Inbox: Inbox,
  Forms: Table2,
  Kanban: Kanban,
  BarChart: BarChart3,
  Book: BookOpen,
  Calendar: Calendar,
  GradCap: GraduationCap,
  CheckCircle: CheckCircle,
  Bell: Bell,
  ArrowRight: ArrowRight,
  UserPlus: UserPlus,
  Clock: Clock,
  Info: Info,
  ClipboardList: ClipboardList,
};

/* ── Navigation Items ── */
const NAV_ITEMS = [
  { id: 'dashboard', label: 'نظرة عامة', IconComp: Icon.Overview },
  { id: 'my-ideas', label: 'أفكاري', IconComp: Icon.Lightbulb },
  { id: 'ideas', label: 'أفكار الدكاترة', IconComp: Icon.Lightbulb },
  { id: 'proposals', label: 'مقترحات الطلاب', IconComp: Icon.ClipboardCheck },
  { id: 'applications', label: 'طلبات الأفكار', IconComp: Icon.Inbox },
  { id: 'formbuilder', label: 'منشئ النماذج', IconComp: Icon.Forms },
  { id: 'projects', label: 'المشاريع النشطة', IconComp: Icon.Kanban },
  { id: 'workflow', label: 'منشئ سير العمل', IconComp: Icon.BarChart },
  { id: 'applyworkflow', label: 'تطبيق سير العمل', IconComp: Icon.ClipboardList },
  { id: 'reviewworkflow', label: 'مراجعة سير العمل', IconComp: Icon.CheckCircle },
  { id: 'grading-settings', label: 'إعدادات التقييم', IconComp: Icon.CheckCircle },
  { id: 'hod-grades', label: 'علامات المشاريع', IconComp: Icon.BarChart },
  { id: 'grade-entry', label: 'إدخال العلامات', IconComp: Icon.CheckCircle },
];

/* ── Module Cards ── */
const MODULE_CARDS = [
    {                                              // ← أضف هاد البلوك كامل
    IconComp: Icon.Lightbulb,
    label: 'أفكاري',
    desc: 'تقديم وإدارة أفكار مشاريعك الخاصة (موافقة تلقائية)',
    page: 'my-ideas',
    gradient: 'linear-gradient(135deg, #ef4444, #f87171)',
  },
  {
    IconComp: Icon.Lightbulb,
    label: 'أفكار الدكاترة',
    desc: 'مراجعة والموافقة على أفكار المشاريع المقدمة من الدكاترة في قسمك',
    page: 'ideas',
    gradient: 'linear-gradient(135deg, #f59e0b, #fbbf24)',
  },
  {
    IconComp: Icon.ClipboardCheck,
    label: 'مقترحات الطلاب',
    desc: 'مراجعة والموافقة على مقترحات المشاريع المقدمة من الطلاب',
    page: 'proposals',
    gradient: 'linear-gradient(135deg, #6366f1, #818cf8)',
  },
  {
    IconComp: Icon.Inbox,
    label: 'طلبات الأفكار',
    desc: 'تسجيل وإدارة طلبات الطلاب على أفكار الدكاترة',
    page: 'applications',
    gradient: 'linear-gradient(135deg, #06b6d4, #22d3ee)',
  },
  {
    IconComp: Icon.Forms,
    label: 'منشئ النماذج',
    desc: 'تخصيص نماذج تقديم الطلاب لقسمك',
    page: 'formbuilder',
    gradient: 'linear-gradient(135deg, #8b5cf6, #a78bfa)',
  },
  {
    IconComp: Icon.Kanban,
    label: 'المشاريع النشطة',
    desc: 'مراقبة تقدم وحالة مشاريع القسم',
    page: 'projects',
    gradient: 'linear-gradient(135deg, #10b981, #34d399)',
  },
  {
    IconComp: Icon.BarChart,
    label: 'منشئ سير العمل',
    desc: 'إنشاء قوالب سير عمل ديناميكية للمشاريع بمراحل',
    page: 'workflow',
    gradient: 'linear-gradient(135deg, #ec4899, #f472b6)',
  },
  {
    IconComp: Icon.ClipboardList,
    label: 'تطبيق سير العمل',
    desc: 'تطبيق قوالب سير العمل على مشاريع الطلاب',
    page: 'applyworkflow',
    gradient: 'linear-gradient(135deg, #14b8a6, #2dd4bf)',
  },
  {
    IconComp: Icon.CheckCircle,
    label: 'مراجعة سير العمل',
    desc: 'مراجعة والموافقة على طلبات سير العمل من الطلاب',
    page: 'reviewworkflow',
    gradient: 'linear-gradient(135deg, #f97316, #fb923c)',
  },
  {
    IconComp: Icon.BarChart,
    label: 'علامات المشاريع',
    desc: 'عرض وتصفية علامات مشاريع القسم حسب النوع والفصل الدراسي',
    page: 'hod-grades',
    gradient: 'linear-gradient(135deg, #8b5cf6, #a78bfa)',
  },
  {
    IconComp: Icon.CheckCircle,
    label: 'إدخال العلامات',
    desc: 'أدخل علامات المشاريع للجان التي أنت عضو فيها',
    page: 'grade-entry',
    gradient: 'linear-gradient(135deg, #10b981, #34d399)',
  },
];

/* ── Notification Icon Helper ── */


/* ── Main Component ── */
export default function HodDashboard({ user, onLogout }) {
  const { theme, toggleTheme } = useTheme();
  const [page, setPage, goBack] = usePageHistory('dashboard');
  const [mounted, setMounted] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);


  const deptLabel = DEPT_LABELS[user.department] || 'قسمك';

  /* ── Fetch notifications ── */
  const loadNotifications = useCallback(async () => {
    setLoading(true);
    try {
      const results = await Promise.allSettled([
        fetchUnreadCount(),
        fetchNotifications(),
      ]);
      if (results[0].status === 'fulfilled') {
        setUnreadCount(results[0].value.data?.unread_count ?? results[0].value.data?.count ?? 0);
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
    if (page === 'change-email') return <div className="std-page-wrapper"><ChangeEmail user={user} onBack={goBack} /></div>;
      
    if (page === 'my-ideas') {                                        // ← أضف
      return (                                                        // ← أضف
        <div className="std-page-wrapper">                            
          <MyIdeas onBack={goBack} onSubmitNew={() => setPage('submit-idea')} />  
        </div>                                                        // ← أضف
      );                                                              // ← أضف
    }                                                                 // ← أضف
    if (page === 'submit-idea') {                                     // ← أضف
      return (                                                        // ← أضف
        <div className="std-page-wrapper">                            
          <SubmitIdea onBack={goBack} />                              
        </div>                                                        // ← أضف
      );                                                              // ← أضف
    }  
    if (page === 'ideas') {
      return (
        <div className="std-page-wrapper">
          <HodIdeaReview onBack={goBack} />
        </div>
      );
    }
    if (page === 'proposals') {
      return (
        <div className="std-page-wrapper">
          <HodProposalReview onBack={goBack} />
        </div>
      );
    }
    if (page === 'applications') {
      return (
        <div className="std-page-wrapper">
          <HodApplicationReview onBack={goBack} />
        </div>
      );
    }
    if (page === 'formbuilder') {
      return (
        <div className="std-page-wrapper">
          <HodFormBuilder onBack={goBack} />
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
    if (page === 'workflow') {
      return (
        <div className="std-page-wrapper">
          <WorkflowBuilder onBack={goBack} />
        </div>
      );
    }
    if (page === 'applyworkflow') {
      return (
        <div className="std-page-wrapper">
          <ApplyWorkflow onBack={goBack} />
        </div>
      );
    }
    if (page === 'reviewworkflow') {
      return (
        <div className="std-page-wrapper">
          <WorkflowReview onBack={goBack} />
        </div>
      );
    }
    if (page === 'grading-settings') {
      return (
        <div className="std-page-wrapper">
          <CollectiveGradingSettings user={user} />
        </div>
      );
    }
    if (page === 'hod-grades') {
      return (
        <div className="std-page-wrapper">
          <HodGradesSummary onBack={goBack} />
        </div>
      );
    }
    if (page === 'grade-entry') {
      return (
        <div className="std-page-wrapper">
          <GradeEntry onBack={goBack} />
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
                Managing operations for {deptLabel}. Review ideas, approve proposals, and oversee department projects.
              </p>
            </div>
            <div className="std-hero-right">
              <div className="std-hero-empty-ring">
                <Icon.GradCap size={28} />
                <span>بوابة رئيس القسم</span>
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
              <span className="std-stat-value std-text-green">Head of Dept</span>
            </div>
          </div>
          <div className="std-stat-card">
            <div className="std-stat-icon std-stat-purple">
              <Icon.Book size={20} />
            </div>
            <div className="std-stat-info">
              <span className="std-stat-title">القسم</span>
              <span className="std-stat-value std-text-purple" style={{ fontSize: '14px' }}>{deptLabel}</span>
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
          <h2 className="std-section-title">عمليات القسم</h2>
          <div className="std-modules-grid">
            {MODULE_CARDS.map((m, i) => (
              <div
                key={m.label}
                className={`std-module-card ${mounted ? `std-card-in std-card-delay-${i}` : ''}`}
                onClick={() => m.page && setPage(m.page)}
                tabIndex={0}
                role="button"
                onKeyDown={(e) => e.key === 'Enter' && m.page && setPage(m.page)}
              >
                <div className="std-module-icon" style={{ background: m.gradient }}>
                  <m.IconComp size={28} />
                </div>
                <div className="std-module-info">
                  <span className="std-module-label">{m.label}</span>
                  <span className="std-module-desc">{m.desc}</span>
                </div>
                <div className="std-module-arrow">
                  <Icon.ArrowRight size={18} />
                </div>
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
    const initial = user.username ? user.username.charAt(0).toUpperCase() : 'H';

  /* ── Notification Slot ── */
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
      roleLabel="Head of Dept"
    >
      {renderContent()}
    </DashboardLayout>
  );

}
