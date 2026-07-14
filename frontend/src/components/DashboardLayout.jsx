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
  X,
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
  const [searchQuery, setSearchQuery] = useState('');

  const notifRef = useRef(null);
  const profileRef = useRef(null);
  const searchRef = useRef(null);

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

  // Keyboard shortcut for search (Ctrl+K)
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        if (searchRef.current) searchRef.current.focus();
      }
      if (e.key === 'Escape') {
        setNotifOpen(false);
        setProfileOpen(false);
        if (searchRef.current) searchRef.current.blur();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
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
  const displayName = user.first_name && user.last_name 
    ? `${user.first_name} ${user.last_name}` 
    : user.username || roleLabel;

  // Filter nav items based on search
  const filteredNavItems = searchQuery
    ? navItems.filter(item => 
        !item.section && item.label?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : navItems;

  return (
    <div className="flex min-h-screen bg-[var(--bg-primary)] text-[var(--text)] font-['Cairo',-apple-system,BlinkMacSystemFont,'Segoe_UI',sans-serif]">
      {/* Sidebar */}
      <aside
        className={`fixed top-0 left-0 h-screen bg-[var(--card)] border-r border-[var(--border)] flex flex-col z-[100] overflow-hidden transition-[width] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] ${collapsed ? 'w-[var(--sidebar-collapsed)]' : 'w-[var(--sidebar-width)]'} ${mounted ? 'opacity-100' : 'opacity-0'}`}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 py-5 px-5 min-h-[64px] overflow-hidden">
          <div className="shrink-0 w-9 h-9 bg-gradient-to-br from-[var(--primary)] to-[var(--accent)] rounded-[10px] flex items-center justify-center text-white shadow-md shadow-[var(--primary-shadow)]">
            <LogoIcon size={22} />
          </div>
          {!collapsed && (
            <div className="flex flex-col whitespace-nowrap overflow-hidden">
              <span className="text-base font-bold text-[var(--text)] tracking-[-0.02em]">SPU Portal</span>
              <span className="text-[11px] text-[var(--text-muted)] uppercase tracking-[0.06em] font-medium">{logoSubtitle}</span>
            </div>
          )}
        </div>

        <div className="h-px bg-[var(--border)] mx-4" />

        {/* Search in Sidebar (when not collapsed) */}
        {!collapsed && (
          <div className="px-4 py-3">
            <div className="relative">
              <Search size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none" />
              <input
                ref={searchRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="بحث..."
                className="w-full py-2 pl-3 pr-9 text-[13px] bg-[var(--bg-tertiary)] border border-[var(--border)] rounded-lg outline-none focus:border-[var(--primary)] focus:ring-2 focus:ring-[var(--primary-light)] transition-all duration-200 text-[var(--text)] placeholder:text-[var(--text-muted)]"
              />
            </div>
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 py-2 px-3 overflow-y-auto overflow-x-hidden">
          {!collapsed && !searchQuery && (
            <div className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-[0.08em] px-3 pt-2 pb-2 mb-1">القائمة</div>
          )}
          {filteredNavItems.map((item, index) => {
            if (item.section) {
              if (collapsed || searchQuery) return <div key={`sep-${index}`} className="h-px bg-[var(--border)] mx-3 my-2" />;
              return (
                <div key={`sec-${index}`} className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-[0.06em] px-3 pt-3 pb-1 mt-2 border-t border-[var(--border)]">
                  {item.section}
                </div>
              );
            }
            const isActive = activePage === item.id;
            return (
            <button
              key={item.id}
              className={`group relative flex items-center gap-3 w-full py-2.5 px-3 border-none rounded-[10px] bg-transparent text-[13px] font-medium cursor-pointer transition-all duration-200 text-left whitespace-nowrap overflow-hidden ${isActive ? 'bg-[var(--primary-light)] text-[var(--primary)] font-semibold' : 'text-[var(--text-muted)] hover:bg-[var(--bg-hover)] hover:text-[var(--text)]'} ${mounted ? 'animate-[stdSlideIn_0.4s_ease_both]' : ''}`}
              style={mounted ? { animationDelay: `${0.05 + index * 0.04}s` } : undefined}
              onClick={() => handleNavClick(item.id)}
              title={collapsed ? item.label : undefined}
            >
              {isActive && (
                <div className="absolute bottom-0.5 left-4 right-4 h-[2px] bg-[var(--primary)] rounded-full" />
              )}
              <span className={`shrink-0 flex items-center justify-center w-5 h-5 transition-transform duration-200 ${isActive ? 'scale-110' : 'group-hover:scale-105'}`}>
                <item.IconComp size={20} />
              </span>
              {!collapsed && <span className="overflow-hidden text-ellipsis">{item.label}</span>}
              {item.badge && unreadCount > 0 && (
                <span className="ml-auto bg-[var(--danger)] text-white text-[11px] font-bold py-0 px-[6px] rounded-full min-w-[18px] h-[18px] flex items-center justify-center shadow-sm">{unreadCount > 99 ? '99+' : unreadCount}</span>
              )}
            </button>
            );
          })}
          {searchQuery && filteredNavItems.length === 0 && (
            <div className="text-center py-8 px-4 text-[var(--text-muted)] text-[13px]">
              لا توجد نتائج
            </div>
          )}
        </nav>

        <div className="h-px bg-[var(--border)] mx-4" />

        {/* Collapse Button */}
        <div className="p-3">
          <button
            className="flex items-center gap-2 w-full py-2 px-3 border-none rounded-[10px] bg-transparent text-[var(--text-muted)] text-xs cursor-pointer transition-all duration-200 hover:bg-[var(--bg-hover)] hover:text-[var(--text)] font-medium"
            onClick={toggleSidebar}
          >
            <span style={{ transform: collapsed ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.3s', display: 'inline-flex' }}>
              <PanelLeftClose size={16} />
            </span>
            {!collapsed && <span>طي القائمة</span>}
          </button>
        </div>
      </aside>

      {/* Mobile Overlay */}
      {mobileOverlay && (
        <div
          className="hidden max-lg:block fixed inset-0 bg-black/60 backdrop-blur-sm z-[99] animate-[stdFadeIn_0.2s_ease]"
          onClick={() => { setSidebarOpen(false); setMobileOverlay(false); }}
        />
      )}

      {/* Main Area */}
      <div
        className={`flex-1 flex flex-col min-h-screen transition-[margin-left] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] ${collapsed ? 'ml-[var(--sidebar-collapsed)]' : 'ml-[var(--sidebar-width)]'} max-lg:ml-0`}
      >
        {/* Top Bar */}
        <header className={`sticky top-0 z-50 h-[var(--topbar-height)] flex items-center justify-between px-6 bg-[var(--topbar-bg)] backdrop-blur-[16px] border-b border-[var(--border)] ${mounted ? 'animate-[stdFadeIn_0.5s_ease_both]' : ''}`}>
          <div className="flex items-center gap-4">
            <button
              className="hidden max-lg:flex border-none bg-transparent text-[var(--text-muted)] cursor-pointer p-2 rounded-lg transition-all duration-200 hover:bg-[var(--bg-hover)] hover:text-[var(--text)]"
              onClick={toggleSidebar}
            >
              <Menu size={20} />
            </button>
            <div className="flex flex-col">
              <h2 className="text-base font-bold text-[var(--text)] m-0 leading-tight">{pageTitle}</h2>
              <span className="text-[11px] text-[var(--text-muted)] mt-0.5">{roleLabel} / {pageTitle}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Theme Toggle */}
            <button
              className="theme-toggle-btn"
              onClick={onToggleTheme}
              aria-label={theme === 'light' ? 'الوضع الليلي' : 'الوضع النهاري'}
              title={theme === 'light' ? 'الوضع الليلي' : 'الوضع النهاري'}
            >
              {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
            </button>

            {/* Notification Bell */}
            <div className="relative" ref={notifRef}>
              <button
                className={`relative border-none bg-transparent text-[var(--text-muted)] cursor-pointer p-2.5 rounded-lg transition-all duration-200 flex items-center ${notifOpen ? 'bg-[var(--bg-hover)] text-[var(--text)]' : 'hover:bg-[var(--bg-hover)] hover:text-[var(--text)]'}`}
                onClick={() => { setNotifOpen(!notifOpen); setProfileOpen(false); }}
                aria-label="الإشعارات"
              >
                <Bell size={20} />
                {unreadCount > 0 && (
                  <span className="absolute -top-0.5 -right-0.5 bg-[var(--danger)] text-white text-[10px] font-bold min-w-[18px] h-[18px] rounded-full flex items-center justify-center px-1 shadow-sm ring-2 ring-[var(--card)]">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                )}
              </button>

              {notifOpen && (
                <div className="absolute top-[calc(100%+8px)] left-0 w-[360px] bg-[var(--card)] border border-[var(--border)] rounded-xl z-[200] animate-[stdDropdownIn_0.2s_ease] overflow-hidden shadow-lg max-[480px]:w-[calc(100vw-32px)] max-[480px]:left-0">
                  <div className="flex items-center justify-between py-3.5 px-4 border-b border-[var(--border)]">
                    <h3 className="text-sm font-bold m-0">الإشعارات</h3>
                    {unreadCount > 0 && (
                      <button className="border-none bg-none text-[var(--primary)] text-xs cursor-pointer p-0 hover:underline font-medium" onClick={onMarkAllRead}>
                        تعليم الكل كمقروء
                      </button>
                    )}
                  </div>
                  <div className="max-h-[320px] overflow-y-auto">
                    {notifications.length === 0 ? (
                      <div className="py-10 px-4 text-center text-[var(--text-muted)] text-[13px]">
                        <Bell size={28} className="mx-auto mb-2 opacity-30" />
                        لا توجد إشعارات
                      </div>
                    ) : (
                      notifications.slice(0, 5).map((n) => (
                        <div
                          key={n.id}
                          className={`flex items-start gap-3 py-3 px-4 cursor-pointer transition-[background] duration-150 border-b border-[var(--border)] last:border-b-0 ${!n.is_read ? 'bg-[var(--bg-hover)]' : 'hover:bg-[var(--bg-hover)]'}`}
                          onClick={() => !n.is_read && onMarkRead && onMarkRead(n.id)}
                        >
                          <div
                            className="shrink-0 w-9 h-9 rounded-lg flex items-center justify-center"
                            style={{ background: notifBgColor(n.notif_type), color: notifTextColor(n.notif_type) }}
                          >
                            <NotifIcon type={n.notif_type} />
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="m-0 text-[13px] leading-snug text-[var(--text)] overflow-hidden text-ellipsis line-clamp-2 font-medium">{n.title || n.message}</p>
                            <span className="text-[11px] text-[var(--text-muted)] mt-1 block">
                              {n.created_at
                                ? new Date(n.created_at).toLocaleDateString('ar', {
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
                  <div className="py-2.5 px-4 border-t border-[var(--border)] text-center bg-[var(--bg-tertiary)]">
                    <button
                      className="border-none bg-none text-[var(--primary)] text-[13px] cursor-pointer p-0 hover:underline font-medium"
                      onClick={() => { if (onNavigate) onNavigate('dashboard'); setNotifOpen(false); }}
                    >
                      عرض كل الإشعارات
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Profile Dropdown */}
            <div className="relative" ref={profileRef}>
              <button
                className={`flex items-center gap-2.5 border-none bg-transparent text-[var(--text)] cursor-pointer py-1.5 px-2.5 rounded-lg transition-all duration-200 ${profileOpen ? 'bg-[var(--bg-hover)]' : 'hover:bg-[var(--bg-hover)]'}`}
                onClick={() => { setProfileOpen(!profileOpen); setNotifOpen(false); }}
              >
                <div className="w-8 h-8 rounded-full bg-gradient-to-br from-[var(--primary)] to-[var(--accent)] flex items-center justify-center text-[13px] font-bold text-white shrink-0 shadow-sm">{initial}</div>
                <div className="flex flex-col text-right max-[640px]:hidden">
                  <span className="text-[13px] font-bold leading-tight">{displayName}</span>
                  <span className="text-[11px] text-[var(--text-muted)] mt-0.5">{roleLabel}</span>
                </div>
                <span style={{ transform: profileOpen ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.2s', display: 'inline-flex' }} className="text-[var(--text-muted)]">
                  <ChevronDown size={14} />
                </span>
              </button>

              {profileOpen && (
                <div className="absolute top-[calc(100%+8px)] left-0 w-[280px] bg-[var(--card)] border border-[var(--border)] rounded-xl z-[200] animate-[stdDropdownIn_0.2s_ease] overflow-hidden shadow-lg">
                  <div className="flex items-center gap-3 p-4 bg-[var(--bg-tertiary)]">
                    <div className="w-12 h-12 rounded-full bg-gradient-to-br from-[var(--primary)] to-[var(--accent)] flex items-center justify-center text-lg font-bold text-white shrink-0 shadow-md">{initial}</div>
                    <div className="overflow-hidden">
                      <span className="block text-sm font-bold truncate">{displayName}</span>
                      <span className="block text-xs text-[var(--text-muted)] truncate">{user.email || `${roleLabel.toLowerCase()}@spu.edu`}</span>
                    </div>
                  </div>
                  <div className="h-px bg-[var(--border)]" />
                  <button
                    className="flex items-center gap-3 w-full py-3 px-4 border-none bg-transparent text-[var(--text)] text-[13px] cursor-pointer transition-[background] duration-150 text-right hover:bg-[var(--bg-hover)] font-medium"
                    onClick={() => { if (onNavigate) onNavigate('change-password'); setProfileOpen(false); }}
                  >
                    <Settings size={16} className="text-[var(--text-muted)]" />
                    تغيير كلمة المرور
                  </button>
                  <button
                    className="flex items-center gap-3 w-full py-3 px-4 border-none bg-transparent text-[var(--text)] text-[13px] cursor-pointer transition-[background] duration-150 text-right hover:bg-[var(--bg-hover)] font-medium"
                    onClick={() => setProfileOpen(false)}
                  >
                    <HelpCircle size={16} className="text-[var(--text-muted)]" />
                    المساعدة
                  </button>
                  <div className="h-px bg-[var(--border)]" />
                  <button
                    className="flex items-center gap-3 w-full py-3 px-4 border-none bg-transparent text-[var(--danger)] text-[13px] cursor-pointer transition-[background] duration-150 text-right hover:bg-[var(--danger-bg)] font-medium"
                    onClick={onLogout}
                  >
                    <LogOut size={16} />
                    تسجيل الخروج
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
