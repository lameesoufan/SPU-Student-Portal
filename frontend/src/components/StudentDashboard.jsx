import React, { useState, useEffect, useRef, useCallback } from 'react';
import ChangeEmail from './ChangeEmail';
import './DashboardLayout.css';
import ProposeIdea from './ProposeIdea';
import BrowseIdeas from './BrowseIdeas';
import MyInvitations from './MyInvitations';
import MyProject from './MyProject';
import MyGrades from './MyGrades';
import ChangePassword from './ChangePassword';
import {
  fetchUnreadCount,
  fetchNotifications,
  markNotifRead,
  markAllNotifsRead,
  fetchMyBoard,
  fetchMyProposal,
  fetchMyIdeaApplication,
  fetchMyInvitations,
} from '../api';
import usePolling from '../hooks/usePolling';
/* ── SVG Icon Components (avoid module-level JSX duplication) ── */
const Icon = {
  Overview: ({ size = 20 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" />
      <rect x="14" y="14" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" />
    </svg>
  ),
  Search: ({ size = 20 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  ),
  Layers: ({ size = 20 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M2 12l10 5 10-5" />
    </svg>
  ),
  Mail: ({ size = 20 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" /><polyline points="22,6 12,13 2,6" />
    </svg>
  ),
  Book: ({ size = 20 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" /><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
    </svg>
  ),
  Calendar: ({ size = 20 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" /><line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  ),
  CheckCircle: ({ size = 20 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  ),
  TaskCheck: ({ size = 20 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 11 12 14 22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
    </svg>
  ),
  Bell: ({ size = 20 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  ),
  Menu: ({ size = 20 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
    </svg>
  ),
  Collapse: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  ),
  ArrowRight: ({ size = 18 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
    </svg>
  ),
  Settings: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
  Help: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" /><line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  ),
  Logout: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
    </svg>
  ),
  ChevronDown: ({ size = 14 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="6 9 12 15 18 9" />
    </svg>
  ),
  ChevronRight: ({ size = 12 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="9 18 15 12 9 6" />
  </svg>
),
  UserPlus: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="8.5" cy="7" r="4" /><line x1="20" y1="8" x2="20" y2="14" /><line x1="23" y1="11" x2="17" y2="11" />
    </svg>
  ),
  Clock: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
    </svg>
  ),
  Info: ({ size = 16 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  ),
};
/* ── Sub-item icons ── */
const SubIcon = {
  Board: ({ size = 18 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" />
    </svg>
  ),
  Workflow: ({ size = 18 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  ),
  GitLab: ({ size = 18 }) => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2L2 7l2 5 8 10 8-10 2-5-10-5z" /><path d="M4 12l8 10 8-10" />
    </svg>
  ),
};
/* ── Navigation Items ── */
const NAV_ITEMS = [
  { id: 'dashboard', label: 'نظرة عامة', IconComp: Icon.Overview },
  { id: 'browse', label: 'تصفح الأفكار', IconComp: Icon.Search },
  { id: 'propose', label: 'اقتراح فكرة', IconComp: Icon.Layers },
  { id: 'invitations', label: 'الدعوات', IconComp: Icon.Mail },
  {
    id: 'myproject',
    label: 'مشروعي',
    IconComp: Icon.Book,
    children: [
      { id: 'board', label: 'اللوحة', IconComp: SubIcon.Board },
      { id: 'workflow', label: 'سير العمل', IconComp: SubIcon.Workflow },
      { id: 'gitlab', label: 'GitLab', IconComp: SubIcon.GitLab },
    ],
  },
  { id: 'my-grades', label: 'علاماتي', IconComp: Icon.CheckCircle },
];
/* ── Breadcrumb Map ── */
const BREADCRUMB_MAP = {
  dashboard: [{ label: 'نظرة عامة', id: 'dashboard' }],
  browse: [
    { label: 'نظرة عامة', id: 'dashboard' },
    { label: 'تصفح الأفكار', id: 'browse' },
  ],
  propose: [
    { label: 'نظرة عامة', id: 'dashboard' },
    { label: 'اقتراح فكرة', id: 'propose' },
  ],
  invitations: [
    { label: 'نظرة عامة', id: 'dashboard' },
    { label: 'الدعوات', id: 'invitations' },
  ],
  myproject: [
    { label: 'نظرة عامة', id: 'dashboard' },
    { label: 'مشروعي', id: 'myproject' },
  ],
};

const MYPROJECT_SUB_TABS = {
  board: 'اللوحة',
  workflow: 'سير العمل',
  gitlab: 'GitLab',
};
/* ── Module Cards ── */
const MODULE_CARDS = [
  {
    IconComp: Icon.Search,
    label: 'تصفح الأفكار',
    desc: 'اكتشف أفكار المشاريع المبتكرة المقدمة من الهيئة التدريسية وتقدم للانضمام',
    page: 'browse',
    gradient: 'linear-gradient(135deg, #6366f1, #818cf8)',
  },
  {
    IconComp: Icon.Layers,
    label: 'اقتراح فكرة',
    desc: 'اقترح فكرة مشروع تخرجك وادعُ أعضاء الفريق',
    page: 'propose',
    gradient: 'linear-gradient(135deg, #f59e0b, #fbbf24)',
  },
  {
    IconComp: Icon.Mail,
    label: 'دعوات الفريق',
    desc: 'مراجعة والرد على دعوات فرق المشاريع من زملائك',
    page: 'invitations',
    gradient: 'linear-gradient(135deg, #06b6d4, #22d3ee)',
  },
  {
    IconComp: Icon.Book,
    label: 'مشروعي',
    desc: 'الوصول إلى لوحة كانبان، تتبع المهام، ومراقبة تقدم المشروع',
    page: 'myproject',
    gradient: 'linear-gradient(135deg, #8b5cf6, #a78bfa)',
  },
];

/* ── Animated Counter Hook ── */
function useAnimatedCounter(target, duration = 1200) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (target === 0) { setCount(0); return; }
    let start = 0;
    const step = Math.max(1, Math.ceil(target / (duration / 16)));
    const timer = setInterval(() => {
      start += step;
      if (start >= target) { setCount(target); clearInterval(timer); }
      else setCount(start);
    }, 16);
    return () => clearInterval(timer);
  }, [target, duration]);
  return count;
}

/* ── Progress Ring Component ── */
function ProgressRing({ radius = 40, stroke = 5, progress = 0 }) {
  const normalizedRadius = radius - stroke;
  const circumference = normalizedRadius * 2 * Math.PI;
  const strokeDashoffset = circumference - (progress / 100) * circumference;
  const [animated, setAnimated] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setAnimated(true), 600);
    return () => clearTimeout(t);
  }, []);

  return (
    <svg width={radius * 2} height={radius * 2} className="std-progress-ring">
      <circle
        strokeWidth={stroke}
        r={normalizedRadius}
        cx={radius}
        cy={radius}
        fill="transparent"
        stroke="rgba(255,255,255,0.08)"
      />
      <circle
        strokeWidth={stroke}
        r={normalizedRadius}
        cx={radius}
        cy={radius}
        fill="transparent"
        stroke="url(#std-ring-gradient)"
        strokeLinecap="round"
        strokeDasharray={`${circumference} ${circumference}`}
        strokeDashoffset={animated ? strokeDashoffset : circumference}
        style={{ transition: 'stroke-dashoffset 1.2s cubic-bezier(0.16, 1, 0.3, 1)' }}
        transform={`rotate(-90 ${radius} ${radius})`}
      />
      <defs>
        <linearGradient id="std-ring-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#818cf8" />
          <stop offset="100%" stopColor="#22d3ee" />
        </linearGradient>
      </defs>
      <text x="50%" y="50%" textAnchor="middle" dy=".1em" className="std-progress-text">
        {progress}%
      </text>
    </svg>
  );
}

/* ── Notification Icon Helper ── */
function NotifIcon({ type }) {
  const map = {
    invitation: Icon.UserPlus,
    update: Icon.CheckCircle,
    reminder: Icon.Clock,
    info: Icon.Info,
  };
  const Comp = map[type] || Icon.Info;
  return <Comp size={16} />;
}

function notifBgColor(type) {
  const map = {
    invitation: 'rgba(99,102,241,0.15)',
    update: 'rgba(16,185,129,0.15)',
    reminder: 'rgba(245,158,11,0.15)',
  };
  return map[type] || 'rgba(100,116,139,0.15)';
}

function notifTextColor(type) {
  const map = {
    invitation: '#6366f1',
    update: '#10b981',
    reminder: '#f59e0b',
  };
  return map[type] || '#64748b';
}

/* ── Main Component ── */
export default function StudentDashboard({ user, onLogout }) {
  const [page, setPage] = useState('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [expandedGroups, setExpandedGroups] = useState({ myproject: true });
  const [mounted, setMounted] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [mobileOverlay, setMobileOverlay] = useState(false);

  // API-driven state
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [dashboardStats, setDashboardStats] = useState({
    hasProject: false,
    hasProposal: false,
    hasApplication: false,
    projectProgress: 0,
    taskCount: 0,
    invitationCount: 0,
  });
  const [loading, setLoading] = useState(true);
  /* ── Track MyProject sub-tab for breadcrumb ── */
const [myProjectTab, setMyProjectTab] = useState('board');

/* ── Poll MyProject active tab from global ── */
useEffect(() => {
  const sync = () => {
    if (window.__myProjectActiveTab && window.__myProjectActiveTab !== myProjectTab) {
      setMyProjectTab(window.__myProjectActiveTab);
    }
  };
  const interval = setInterval(sync, 300);
  return () => clearInterval(interval);
}, [myProjectTab]);
  const notifRef = useRef(null);
  const profileRef = useRef(null);

  const animatedInvitations = useAnimatedCounter(dashboardStats.invitationCount);
  const animatedTasks = useAnimatedCounter(dashboardStats.taskCount);

  /* ── Fetch dashboard data ── */
  const loadDashboardData = useCallback(async () => {
    setLoading(true);
    try {
      const results = await Promise.allSettled([
        fetchUnreadCount(),
        fetchMyInvitations(),
        fetchMyBoard(),
        fetchMyProposal(),
        fetchMyIdeaApplication(),
      ]);

      // Unread count
      if (results[0].status === 'fulfilled') {
        setUnreadCount(results[0].value.data?.unread_count ?? results[0].value.data?.count ?? 0);
      }

      // Invitations count
      let invCount = 0;
      if (results[1].status === 'fulfilled') {
        const invData = results[1].value.data;
        invCount = Array.isArray(invData)
          ? invData.filter((i) => i.status === 'pending').length
          : invData?.pending_count ?? 0;
      }

      // Board / project
      let hasProject = false;
      let progress = 0;
      let taskCount = 0;
      if (results[2].status === 'fulfilled') {
        const board = results[2].value.data;
        if (board && board.id) {
          hasProject = true;
          const tasks = board.tasks || [];
          taskCount = tasks.filter((t) => t.status === 'done').length;
          const total = tasks.length || 1;
          progress = Math.round((taskCount / total) * 100);
        }
      }

      // Proposal
      const hasProposal = results[3].status === 'fulfilled' && !!results[3].value.data?.id;

      // Application
      const hasApplication = results[4].status === 'fulfilled' && !!results[4].value.data?.id;

      setDashboardStats({
        hasProject,
        hasProposal,
        hasApplication,
        projectProgress: progress,
        taskCount,
        invitationCount: invCount,
      });
    } catch {
      // Silently handle — dashboard still shows with defaults
    } finally {
      setLoading(false);
    }
  }, []);

  /* ── Fetch notifications ── */
  const loadNotifications = useCallback(async () => {
    try {
      const res = await fetchNotifications();
      setNotifications(res.data?.results || res.data || []);
    } catch {
      // Ignore
    }
  }, []);

  /* ── Initial load ── */
  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 50);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    loadDashboardData();
    loadNotifications();
  }, [loadDashboardData, loadNotifications]);

  /* ── Poll unread count ── */
/* ── Poll unread count ── */
usePolling(async () => {
  try {
    const res = await fetchUnreadCount();
    setUnreadCount(res.data?.unread_count ?? res.data?.count ?? 0);
  } catch {
    // Ignore
  }
}, 30000);

  /* ── Responsive sidebar ── */
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024) {
        setSidebarOpen(false);
        setMobileOverlay(false);
      } else {
        setSidebarOpen(true);
      }
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  /* ── Click outside to close dropdowns ── */
  useEffect(() => {
    const handleClick = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) setNotifOpen(false);
      if (profileRef.current && !profileRef.current.contains(e.target)) setProfileOpen(false);
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  /* ── Handlers ── */
  const handleLogout = () => {
    if (onLogout) onLogout();
  };

const handleNavClick = (id) => {
  /* If it's a group with children, toggle expansion instead of navigating */
  const navItem = NAV_ITEMS.find((n) => n.id === id);
  if (navItem && navItem.children) {
    setExpandedGroups((prev) => ({ ...prev, [id]: !prev[id] }));
    return;
  }
  setPage(id);
  if (window.innerWidth < 1024) {
    setSidebarOpen(false);
    setMobileOverlay(false);
  }
};

/* Handle sub-item click — navigate to parent page with sub-tab */
const handleSubNavClick = (parentId, childId) => {
  setPage(parentId);
  /* Tell MyProject to switch to the correct tab via a global ref or callback */
  if (window.myProjectSetActiveTab) {
    window.myProjectSetActiveTab(childId);
  }
  if (window.innerWidth < 1024) {
    setSidebarOpen(false);
    setMobileOverlay(false);
  }
};

  const toggleSidebar = () => {
    if (window.innerWidth < 1024) {
      setMobileOverlay((prev) => !prev);
      setSidebarOpen((prev) => !prev);
    } else {
      setSidebarOpen((prev) => !prev);
    }
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

  const goBack = () => {
    setPage('dashboard');
  };

  /* ── Determine student status text ── */
  const getStatusInfo = () => {
    if (dashboardStats.hasProject) {
      return { label: 'مشروع نشط', color: '#10b981', className: 'std-text-green' };
    }
    if (dashboardStats.hasProposal || dashboardStats.hasApplication) {
      return { label: 'قيد المراجعة', color: '#f59e0b', className: 'std-text-amber' };
    }
    return { label: 'لا يوجد مشروع بعد', color: '#64748b', className: 'std-text-gray' };
  };

  const statusInfo = getStatusInfo();
  /* ── Build breadcrumb trail ── */
const getBreadcrumbs = () => {
  const trail = BREADCRUMB_MAP[page] || BREADCRUMB_MAP.dashboard;
  // If on myproject, append the active sub-tab as a third crumb
  if (page === 'myproject' && MYPROJECT_SUB_TABS[myProjectTab]) {
    return [...trail, { label: MYPROJECT_SUB_TABS[myProjectTab], id: `myproject-${myProjectTab}` }];
  }
  return trail;
};

const breadcrumbs = getBreadcrumbs();
  /* ── Render sub-pages ── */
  const renderContent = () => {
    if (page === 'change-password') return <div className="std-page-wrapper"><ChangePassword user={user} onBack={goBack} /></div>;
    if (page === 'change-email') return <div className="std-page-wrapper"><ChangeEmail user={user} onBack={goBack} /></div>;
    if (page === 'propose') {
      return (
        <div className="std-page-wrapper">
          <ProposeIdea onBack={() => setPage('dashboard')} />
        </div>
      );
    }
    if (page === 'browse') {
      return (
        <div className="std-page-wrapper">
          <BrowseIdeas onBack={() => setPage('dashboard')} />
        </div>
      );
    }
    if (page === 'invitations') {
      return (
        <div className="std-page-wrapper">
          <MyInvitations onBack={() => setPage('dashboard')} />
        </div>
      );
    }
    if (page === 'myproject') {
      return (
        <div className="std-page-wrapper">
          <MyProject user={user} />
        </div>
      );
    }
    if (page === 'my-grades') {
      return (
        <div className="std-page-wrapper">
          <MyGrades />
        </div>
      );
    }

    // ── Overview Dashboard ──
    return (
      <div className="std-content">
        {/* Hero */}
        <div className={`std-hero ${mounted ? 'std-animate-in' : ''}`}>
          <div className="std-hero-bg-orbs">
            <div className="std-orb std-orb-1" />
            <div className="std-orb std-orb-2" />
            <div className="std-orb std-orb-3" />
          </div>
          <div className="std-hero-content">
            <div className="std-hero-text">
              <h1 className="std-hero-title">
                مرحباً بعودتك، <span className="std-gradient-text">{user.username}</span>
              </h1>
              <p className="std-hero-sub">
                Manage your graduation project journey — from idea to delivery.
              </p>
            </div>
            <div className="std-hero-right">
              {dashboardStats.hasProject ? (
                <>
                  <ProgressRing radius={46} stroke={5} progress={dashboardStats.projectProgress} />
                  <span className="std-ring-label">التقدم</span>
                </>
              ) : (
                <div className="std-hero-empty-ring">
                  <Icon.Book size={28} />
                  <span>لا يوجد مشروع نشط</span>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Stats */}
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
              <Icon.CheckCircle size={20} />
            </div>
            <div className="std-stat-info">
              <span className="std-stat-title">الحالة</span>
              <span className={`std-stat-value ${statusInfo.className}`}>{statusInfo.label}</span>
            </div>
          </div>
          <div className="std-stat-card">
            <div className="std-stat-icon std-stat-purple">
              <Icon.TaskCheck size={20} />
            </div>
            <div className="std-stat-info">
              <span className="std-stat-title">المهام المنجزة</span>
              <span className="std-stat-value std-text-purple">
                {loading ? '—' : animatedTasks}
              </span>
            </div>
          </div>
          <div className="std-stat-card">
            <div className="std-stat-icon std-stat-amber">
              <Icon.Mail size={20} />
            </div>
            <div className="std-stat-info">
              <span className="std-stat-title">الدعوات</span>
              <span className="std-stat-value std-text-amber">
                {loading ? '—' : animatedInvitations}
              </span>
            </div>
          </div>
        </div>

        {/* Modules */}
        <div className={`std-modules ${mounted ? 'std-animate-in std-delay-2' : ''}`}>
          <h2 className="std-section-title">وحدات المشروع</h2>
          <div className="std-modules-grid">
            {MODULE_CARDS.map((m, i) => (
              <div
                key={m.label}
                className={`std-module-card ${mounted ? `std-card-in std-card-delay-${i}` : ''}`}
                onClick={() => setPage(m.page)}
                tabIndex={0}
                role="button"
                onKeyDown={(e) => e.key === 'Enter' && setPage(m.page)}
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

        {/* Recent Notifications Preview */}
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

  /* ── Sidebar ── */
  const collapsed = !sidebarOpen;
  const currentPageLabel = NAV_ITEMS.find((n) => n.id === page)?.label || 'نظرة عامة';
  const initial = user.username ? user.username.charAt(0).toUpperCase() : 'S';

  return (
    <div className="std-layout">
      {/* Sidebar */}
      <aside
        className={`std-sidebar ${collapsed ? 'std-sidebar-collapsed' : 'std-sidebar-expanded'} ${mounted ? 'std-sidebar-mounted' : ''}`}
      >
        {/* Logo */}
        <div className="std-sidebar-logo">
          <div className="std-logo-icon">
            <Icon.Book size={22} />
          </div>
          {!collapsed && (
            <div className="std-logo-text">
              <span className="std-logo-title">بوابة SPU</span>
              <span className="std-logo-sub">لوحة الطالب</span>
            </div>
          )}
        </div>

        <div className="std-sidebar-divider" />

        {/* Navigation */}
<nav className="std-sidebar-nav">
  {!collapsed && <div className="std-nav-label">القائمة</div>}
  {NAV_ITEMS.map((item, index) => {
    const hasChildren = item.children && item.children.length > 0;
    const isExpanded = expandedGroups[item.id];
    const isGroupActive = page === item.id || (hasChildren && item.children.some((c) => page === item.id));
    return (
      <div key={item.id} className="std-nav-group">
        <button
          className={`std-nav-item ${isGroupActive ? 'std-nav-active' : ''} ${hasChildren && isExpanded ? 'std-nav-group-expanded' : ''} ${mounted ? `std-nav-item-in std-nav-item-delay-${index}` : ''}`}
          onClick={() => handleNavClick(item.id)}
          title={collapsed ? item.label : undefined}
        >
          {isGroupActive && !hasChildren && <div className="std-nav-active-bar" />}
          <span className="std-nav-icon">
            <item.IconComp size={20} />
          </span>
          {!collapsed && <span className="std-nav-text">{item.label}</span>}
          {item.badge && unreadCount > 0 && (
            <span className="std-nav-badge">{unreadCount}</span>
          )}
          {hasChildren && !collapsed && (
            <span className={`std-nav-chevron ${isExpanded ? 'std-nav-chevron-open' : ''}`}>
              <Icon.ChevronDown size={14} />
            </span>
          )}
        </button>
        {/* Collapsible sub-items */}
        {hasChildren && !collapsed && (
          <div className={`std-nav-children ${isExpanded ? 'std-nav-children-open' : ''}`}>
            {item.children.map((child) => (
              <button
                key={child.id}
                className={`std-nav-child-item ${page === item.id && window.__myProjectActiveTab === child.id ? 'std-nav-child-active' : ''}`}
                onClick={() => handleSubNavClick(item.id, child.id)}
              >
                <span className="std-nav-child-dot" />
                <span className="std-nav-child-icon">
                  <child.IconComp size={16} />
                </span>
                <span className="std-nav-child-text">{child.label}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  })}
</nav>

        <div className="std-sidebar-divider" />

        {/* Collapse Button */}
        <div className="std-sidebar-bottom">
          <button className="std-collapse-btn" onClick={toggleSidebar}>
            <span style={{ transform: collapsed ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.3s', display: 'inline-flex' }}>
              <Icon.Collapse size={16} />
            </span>
            {!collapsed && <span>طي</span>}
          </button>
        </div>
      </aside>

      {/* Mobile Overlay */}
      {mobileOverlay && (
        <div className="std-sidebar-overlay" onClick={() => { setSidebarOpen(false); setMobileOverlay(false); }} />
      )}

      {/* Main Area */}
      <div className={`std-main-wrapper ${collapsed ? 'std-main-shifted' : ''}`}>
              {/* Top Bar */}
        <header className={`std-topbar ${mounted ? 'std-topbar-in' : ''}`}>
          <div className="std-topbar-left" dir="ltr">
            <button className="std-hamburger" onClick={toggleSidebar}>
              <Icon.Menu size={20} />
            </button>
            <div className="std-topbar-title" dir="ltr">
              <h2>{currentPageLabel}</h2>
              <nav className="std-breadcrumb" aria-label="Breadcrumb">
                {breadcrumbs.map((crumb, i) => {
                  const isLast = i === breadcrumbs.length - 1;
                  return (
                    <span key={crumb.id} className="std-breadcrumb-item-wrapper">
                      {i > 0 && (
                        <span className="std-breadcrumb-sep">
                          <Icon.ChevronRight size={12} />
                        </span>
                      )}
                      {isLast ? (
                        <span className="std-breadcrumb-crumb std-breadcrumb-active">{crumb.label}</span>
                      ) : (
                        <button
                          className="std-breadcrumb-crumb std-breadcrumb-link"
                          onClick={() => setPage(crumb.id)}
                        >
                          {crumb.label}
                        </button>
                      )}
                    </span>
                  );
                })}
              </nav>
            </div>
          </div>

          <div className="std-topbar-right">
            {/* Search Bar */}
            <div className="std-search-bar">
              <Icon.Search size={15} />
              <input type="text" placeholder="بحث..." className="std-search-input" />
              <kbd className="std-search-kbd">Ctrl+K</kbd>
            </div>


            {/* Notification Bell */}
            <div className="std-notif-wrapper" ref={notifRef}>
              <button
                className={`std-notif-btn ${notifOpen ? 'std-notif-btn-open' : ''}`}
                onClick={() => { setNotifOpen(!notifOpen); setProfileOpen(false); }}
              >
                <Icon.Bell size={20} />
                {unreadCount > 0 && (
                  <span className="std-notif-badge">
                    {unreadCount}
                    <span className="std-notif-pulse" />
                  </span>
                )}
              </button>

              {notifOpen && (
                <div className="std-notif-dropdown">
                  <div className="std-notif-header">
                    <h3>الإشعارات</h3>
                    {unreadCount > 0 && (
                      <button className="std-notif-mark-read" onClick={handleMarkAllRead}>
                        Mark all read
                      </button>
                    )}
                  </div>
                  <div className="std-notif-list">
                    {notifications.length === 0 ? (
                      <div className="std-notif-empty">لا توجد إشعارات</div>
                    ) : (
                      notifications.slice(0, 5).map((n) => (
                        <div
                          key={n.id}
                          className={`std-notif-item ${!n.is_read ? 'std-notif-unread' : ''}`}
                          onClick={() => !n.is_read && handleMarkRead(n.id)}
                        >
                          <div
                            className="std-notif-item-icon"
                            style={{ background: notifBgColor(n.notif_type), color: notifTextColor(n.notif_type) }}
                          >
                            <NotifIcon type={n.notif_type} />
                          </div>
                          <div className="std-notif-item-content">
                            <p>{n.title || n.message}</p>
                            <span className="std-notif-time">
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
                          {!n.is_read && <div className="std-notif-dot" />}
                        </div>
                      ))
                    )}
                  </div>
                  <div className="std-notif-footer">
                    <button onClick={() => { setPage('dashboard'); setNotifOpen(false); }}>
                      View all notifications
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Profile Dropdown */}
            <div className="std-profile-wrapper" ref={profileRef}>
              <button
                className={`std-profile-btn ${profileOpen ? 'std-profile-btn-open' : ''}`}
                onClick={() => { setProfileOpen(!profileOpen); setNotifOpen(false); }}
              >
                <div className="std-avatar">{initial}</div>
                <div className="std-profile-info">
                  <span className="std-profile-name">{user.username || 'طالب'}</span>
                  <span className="std-profile-role">طالب</span>
                </div>
                <span style={{ transform: profileOpen ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.2s', display: 'inline-flex' }}>
                  <Icon.ChevronDown size={14} />
                </span>
              </button>

              {profileOpen && (
                <div className="std-profile-dropdown">
                  <div className="std-profile-dropdown-header">
                    <div className="std-avatar std-avatar-lg">{initial}</div>
                    <div>
                      <span className="std-profile-dropdown-name">{user.username || 'طالب'}</span>
                      <span className="std-profile-dropdown-email">{user.email || 'student@spu.edu'}</span>
                    </div>
                  </div>
                  <div className="std-profile-dropdown-divider" />
                  <button
                    className="std-profile-dropdown-item"
                    onClick={() => { setPage('change-password'); setProfileOpen(false); }}
                  >
                    <Icon.Settings size={16} />
                    تغيير كلمة المرور
                  </button>
                  <button
                    className="std-profile-dropdown-item"
                    onClick={() => { setPage('change-email'); setProfileOpen(false); }}
                  >
                    <Icon.Mail size={16} />
                    تغيير البريد الإلكتروني
                  </button>
                  <button
                    className="std-profile-dropdown-item"
                    onClick={() => setProfileOpen(false)}
                  >
                    <Icon.Help size={16} />
                    المساعدة
                  </button>
                  <div className="std-profile-dropdown-divider" />
                  <button className="std-profile-dropdown-item std-profile-item-danger" onClick={handleLogout}>
                    <Icon.Logout size={16} />
                    تسجيل الخروج
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="std-main-content">{renderContent()}</main>
      </div>
    </div>
  );
}
