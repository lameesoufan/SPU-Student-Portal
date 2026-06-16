import React, { useState, useEffect, useRef } from 'react';
import {
  BookOpen,
  PanelLeftClose,
  Menu,
  Search,
  Sun,
  Moon,
  Bell,
  Settings,
  HelpCircle,
  LogOut,
  ChevronDown,
} from 'lucide-react';
import { NotifIcon, notifBgColor, notifTextColor } from './NotifHelpers';

export default function DashboardLayout({
  children,
  navItems = [],
  activePage,
  onNavigate,
  unreadCount = 0,
  logoSubtitle = 'Dashboard',
  logoIcon: LogoIcon = BookOpen,
  pageTitle = 'Overview',
  theme = 'light',
  onToggleTheme,
  notifications = [],
  onMarkAllRead,
  onMarkRead,
  user = {},
  onLogout,
  roleLabel = 'User',
}) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mounted, setMounted] = useState(false);
  const [mobileOverlay, setMobileOverlay] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);

  const notifRef = useRef(null);
  const profileRef = useRef(null);

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 50);
    return () => clearTimeout(t);
  }, []);

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

  useEffect(() => {
    const handleClick = (e) => {
      if (notifRef.current && !notifRef.current.contains(e.target)) setNotifOpen(false);
      if (profileRef.current && !profileRef.current.contains(e.target)) setProfileOpen(false);
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  const collapsed = !sidebarOpen;

  const handleNavClick = (id) => {
    if (onNavigate) onNavigate(id);
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

  const initial = user.username ? user.username.charAt(0).toUpperCase() : 'U';

  return (
    <div className="flex min-h-screen bg-[var(--bg-primary)] text-[var(--text)] font-['Inter',-apple-system,BlinkMacSystemFont,'Segoe_UI',sans-serif]">
      {/* Sidebar */}
      <aside
        className={`fixed top-0 left-0 h-screen bg-[var(--card)] border-r border-[var(--border)] flex flex-col z-[100] overflow-hidden transition-[width] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] ${collapsed ? 'w-[var(--sidebar-collapsed)]' : 'w-[var(--sidebar-width)]'} ${mounted ? 'opacity-100' : 'opacity-0'}`}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 py-5 px-5 min-h-[64px] overflow-hidden">
          <div className="shrink-0 w-9 h-9 bg-gradient-to-br from-[var(--primary)] to-[var(--accent)] rounded-[var(--radius-sm)] flex items-center justify-center text-white">
            <LogoIcon size={22} />
          </div>
          {!collapsed && (
            <div className="flex flex-col whitespace-nowrap overflow-hidden">
              <span className="text-base font-bold text-[var(--text)] tracking-[-0.02em]">SPU Portal</span>
              <span className="text-[11px] text-[var(--text-muted)] uppercase tracking-[0.06em]">{logoSubtitle}</span>
            </div>
          )}
        </div>

        <div className="h-px bg-[var(--border)] mx-4" />

        {/* Navigation */}
        <nav className="flex-1 py-3 px-3 overflow-y-auto overflow-x-hidden">
          {!collapsed && (
            <div className="text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-[0.08em] px-3 pt-2 pb-2 mb-1">Menu</div>
          )}
          {navItems.map((item, index) => (
            <button
              key={item.id}
              className={`relative flex items-center gap-3 w-full py-2.5 px-3 border-none rounded-[var(--radius-sm)] bg-transparent text-[13px] font-medium cursor-pointer transition-all duration-200 text-left whitespace-nowrap overflow-hidden ${activePage === item.id ? 'bg-[var(--bg-hover)] text-[var(--info)]' : 'text-[var(--text-muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)]'} ${mounted ? 'animate-[stdSlideIn_0.4s_ease_both]' : ''}`}
              style={mounted ? { animationDelay: `${0.05 + index * 0.05}s` } : undefined}
              onClick={() => handleNavClick(item.id)}
              title={collapsed ? item.label : undefined}
            >
              {activePage === item.id && (
                <div className="absolute -left-3 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-[var(--primary)] rounded-r" />
              )}
              <span className="shrink-0 flex items-center justify-center w-5 h-5">
                <item.IconComp size={20} />
              </span>
              {!collapsed && <span className="overflow-hidden text-ellipsis">{item.label}</span>}
              {item.badge && unreadCount > 0 && (
                <span className="ml-auto bg-[var(--danger)] text-white text-[11px] font-semibold py-0 px-[7px] rounded-[10px] min-w-[18px] text-center">{unreadCount}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="h-px bg-[var(--border)] mx-4" />

        {/* Collapse Button */}
        <div className="p-3">
          <button
            className="flex items-center gap-2 w-full py-2 px-3 border-none rounded-[var(--radius-sm)] bg-transparent text-[var(--text-muted)] text-xs cursor-pointer transition-all duration-200 hover:bg-[var(--bg-hover)] hover:text-[var(--text)]"
            onClick={toggleSidebar}
          >
            <span style={{ transform: collapsed ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.3s', display: 'inline-flex' }}>
              <PanelLeftClose size={16} />
            </span>
            {!collapsed && <span>Collapse</span>}
          </button>
        </div>
      </aside>

      {/* Mobile Overlay */}
      {mobileOverlay && (
        <div
          className="hidden max-lg:block fixed inset-0 bg-black/50 z-[99]"
          onClick={() => { setSidebarOpen(false); setMobileOverlay(false); }}
        />
      )}

      {/* Main Area */}
      <div
        className={`flex-1 flex flex-col min-h-screen transition-[margin-left] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] ${collapsed ? 'ml-[var(--sidebar-collapsed)]' : 'ml-[var(--sidebar-width)]'} max-lg:ml-0`}
      >
        {/* Top Bar */}
        <header className={`sticky top-0 z-50 h-[var(--topbar-height)] flex items-center justify-between px-6 bg-[var(--topbar-bg)] backdrop-blur-[12px] border-b border-[var(--border)] ${mounted ? 'animate-[stdFadeIn_0.5s_ease_both]' : ''}`}>
          <div className="flex items-center gap-4">
            <button
              className="hidden max-lg:flex border-none bg-transparent text-[var(--text-muted)] cursor-pointer p-1 rounded-md transition-all duration-200 hover:bg-[var(--bg-hover)] hover:text-[var(--text)]"
              onClick={toggleSidebar}
            >
              <Menu size={20} />
            </button>
            <div>
              <h2 className="text-base font-semibold text-[var(--text)] m-0">{pageTitle}</h2>
              <span className="text-xs text-[var(--text-muted)]">{roleLabel} / {pageTitle}</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Search Bar */}
            <div className="flex items-center gap-2 py-1.5 px-3 bg-[var(--bg-tertiary)] border border-[var(--border)] rounded-[var(--radius-sm)] min-w-[200px] text-[var(--text-muted)] max-[767px]:hidden">
              <Search size={15} />
              <input
                type="text"
                placeholder="Search..."
                className="border-none bg-transparent text-[var(--text)] text-[13px] outline-none w-[140px] placeholder:text-[var(--text-muted)] placeholder:opacity-60"
              />
              <kbd className="text-[10px] py-0.5 px-1.5 bg-white/[0.06] rounded text-[var(--text-muted)] font-inherit whitespace-nowrap">Ctrl+K</kbd>
            </div>

            {/* Theme Toggle */}
            <button
              className="theme-toggle-btn"
              onClick={onToggleTheme}
              aria-label={theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'}
              title={theme === 'light' ? 'Switch to dark theme' : 'Switch to light theme'}
            >
              {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
            </button>

            {/* Notification Bell */}
            <div className="relative" ref={notifRef}>
              <button
                className={`relative border-none bg-transparent text-[var(--text-muted)] cursor-pointer p-2 rounded-[var(--radius-sm)] transition-all duration-200 flex items-center ${notifOpen ? 'bg-[var(--bg-hover)] text-[var(--text)]' : 'hover:bg-[var(--bg-hover)] hover:text-[var(--text)]'}`}
                onClick={() => { setNotifOpen(!notifOpen); setProfileOpen(false); }}
              >
                <Bell size={20} />
        {unreadCount > 0 && (
            <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] font-bold min-w-[18px] h-[18px] rounded-full flex items-center justify-center px-1 shadow-sm shadow-red-500/30">
           {unreadCount > 99 ? '99+' : unreadCount}
           </span>
)}    
              </button>

              {notifOpen && (
                <div className="absolute top-[calc(100%+8px)] right-0 w-[360px] bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] z-[200] animate-[stdDropdownIn_0.2s_ease] overflow-hidden max-[480px]:w-[calc(100vw-32px)] max-[480px]:-right-[60px]">
                  <div className="flex items-center justify-between py-3.5 px-4 border-b border-[var(--border)]">
                    <h3 className="text-sm font-semibold m-0">Notifications</h3>
                    {unreadCount > 0 && (
                      <button className="border-none bg-none text-[var(--info)] text-xs cursor-pointer p-0 hover:underline" onClick={onMarkAllRead}>
                        Mark all read
                      </button>
                    )}
                  </div>
                  <div className="max-h-[320px] overflow-y-auto">
                    {notifications.length === 0 ? (
                      <div className="py-8 px-4 text-center text-[var(--text-muted)] text-[13px]">No notifications</div>
                    ) : (
                      notifications.slice(0, 5).map((n) => (
                        <div
                          key={n.id}
                          className={`flex items-start gap-3 py-3 px-4 cursor-pointer transition-[background] duration-150 border-b border-[var(--border)] last:border-b-0 ${!n.is_read ? 'bg-[var(--bg-hover)]' : 'hover:bg-[var(--bg-hover)]'}`}
                          onClick={() => !n.is_read && onMarkRead && onMarkRead(n.id)}
                        >
                          <div
                            className="shrink-0 w-8 h-8 rounded-lg flex items-center justify-center"
                            style={{ background: notifBgColor(n.notif_type), color: notifTextColor(n.notif_type) }}
                          >
                            <NotifIcon type={n.notif_type} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="m-0 text-[13px] leading-snug text-[var(--text)] overflow-hidden text-ellipsis line-clamp-2">{n.title || n.message}</p>
                            <span className="text-[11px] text-[var(--text-muted)] mt-0.5 block">
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
                          {!n.is_read && <div className="shrink-0 w-2 h-2 rounded-full bg-[var(--primary)] mt-1.5" />}
                        </div>
                      ))
                    )}
                  </div>
                  <div className="py-2.5 px-4 border-t border-[var(--border)] text-center">
                    <button
                      className="border-none bg-none text-[var(--info)] text-[13px] cursor-pointer p-0 hover:underline"
                      onClick={() => { if (onNavigate) onNavigate('dashboard'); setNotifOpen(false); }}
                    >
                      View all notifications
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Profile Dropdown */}
            <div className="relative" ref={profileRef}>
              <button
                className={`flex items-center gap-2 border-none bg-transparent text-[var(--text)] cursor-pointer py-1.5 px-2.5 rounded-[var(--radius-sm)] transition-all duration-200 ${profileOpen ? 'bg-[var(--bg-hover)]' : 'hover:bg-[var(--bg-hover)]'}`}
                onClick={() => { setProfileOpen(!profileOpen); setNotifOpen(false); }}
              >
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[var(--primary)] to-[var(--accent)] flex items-center justify-center text-[13px] font-semibold text-white shrink-0">{initial}</div>
                <div className="flex flex-col text-left max-[640px]:hidden">
                  <span className="text-[13px] font-semibold leading-tight">{user.username || roleLabel}</span>
                  <span className="text-[11px] text-[var(--text-muted)]">{roleLabel}</span>
                </div>
                <span style={{ transform: profileOpen ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.2s', display: 'inline-flex' }}>
                  <ChevronDown size={14} />
                </span>
              </button>

              {profileOpen && (
                <div className="absolute top-[calc(100%+8px)] right-0 w-[260px] bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius)] z-[200] animate-[stdDropdownIn_0.2s_ease] overflow-hidden">
                  <div className="flex items-center gap-3 p-4">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[var(--primary)] to-[var(--accent)] flex items-center justify-center text-base font-semibold text-white shrink-0">{initial}</div>
                    <div>
                      <span className="block text-sm font-semibold">{user.username || roleLabel}</span>
                      <span className="block text-xs text-[var(--text-muted)]">{user.email || `${roleLabel.toLowerCase()}@spu.edu`}</span>
                    </div>
                  </div>
                  <div className="h-px bg-[var(--border)]" />
                  <button
                    className="flex items-center gap-2.5 w-full py-2.5 px-4 border-none bg-transparent text-[var(--text)] text-[13px] cursor-pointer transition-[background] duration-150 text-left hover:bg-[var(--bg-hover)]"
                    onClick={() => { if (onNavigate) onNavigate('change-password'); setProfileOpen(false); }}
                  >
                    <Settings size={16} />
                    Change Password
                  </button>
                  <button
                    className="flex items-center gap-2.5 w-full py-2.5 px-4 border-none bg-transparent text-[var(--text)] text-[13px] cursor-pointer transition-[background] duration-150 text-left hover:bg-[var(--bg-hover)]"
                    onClick={() => setProfileOpen(false)}
                  >
                    <HelpCircle size={16} />
                    Help
                  </button>
                  <div className="h-px bg-[var(--border)]" />
                  <button
                    className="flex items-center gap-2.5 w-full py-2.5 px-4 border-none bg-transparent text-[var(--danger)] text-[13px] cursor-pointer transition-[background] duration-150 text-left hover:bg-[var(--danger-bg)]"
                    onClick={onLogout}
                  >
                    <LogOut size={16} />
                    Sign Out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}