import React from 'react';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DashboardLayout from '../DashboardLayout.jsx';

const Icon = ({ size }) => <span aria-hidden="true" data-testid="nav-icon">icon-{size}</span>;
const navItems = [
  { id: 'dashboard', label: 'نظرة عامة', IconComp: Icon },
  { section: 'الإدارة' },
  { id: 'projects', label: 'المشاريع', IconComp: Icon },
  { id: 'alerts', label: 'التنبيهات', IconComp: Icon, badge: true },
];

function renderLayout(overrides = {}) {
  const props = {
    navItems,
    activePage: 'dashboard',
    onNavigate: vi.fn(),
    unreadCount: 3,
    logoSubtitle: 'Student Dashboard',
    pageTitle: 'نظرة عامة',
    theme: 'light',
    onToggleTheme: vi.fn(),
    notifications: [],
    onMarkAllRead: vi.fn(),
    onMarkRead: vi.fn(),
    user: { username: 's123', first_name: 'Ali', last_name: 'Ahmad', email: 'ali@example.com' },
    onLogout: vi.fn(),
    roleLabel: 'طالب',
    ...overrides,
  };
  return { ...render(<DashboardLayout {...props}><div>PAGE CONTENT</div></DashboardLayout>), props };
}

beforeEach(() => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: 1280 });
});

describe('DashboardLayout role/navigation shell', () => {
  it('renders child page content', () => { renderLayout(); expect(screen.getByText('PAGE CONTENT')).toBeTruthy(); });
  it('renders the portal brand', () => { renderLayout(); expect(screen.getByText('SPU Portal')).toBeTruthy(); });
  it('renders the role dashboard subtitle', () => { renderLayout(); expect(screen.getByText('Student Dashboard')).toBeTruthy(); });
  it('renders the page title', () => { renderLayout(); expect(screen.getByText('نظرة عامة', { selector: 'h2' })).toBeTruthy(); });
  it('renders the role breadcrumb', () => { renderLayout(); expect(screen.getByText('طالب / نظرة عامة')).toBeTruthy(); });
  it.each(['نظرة عامة', 'المشاريع'])('renders allowed navigation item %s', (label) => { renderLayout(); expect(screen.getByRole('button', { name: label })).toBeTruthy(); });
  it('renders allowed navigation item التنبيهات', () => { renderLayout(); expect(screen.getByRole('button', { name: /^التنبيهات/ })).toBeTruthy(); });
  it('renders navigation section headings', () => { renderLayout(); expect(screen.getByText('الإدارة')).toBeTruthy(); });
  it('navigates to the selected permitted page', () => { const { props } = renderLayout(); fireEvent.click(screen.getByRole('button', { name: 'المشاريع' })); expect(props.onNavigate).toHaveBeenCalledWith('projects'); });
  it('marks the active navigation item visually', () => { renderLayout({ activePage: 'projects' }); expect(screen.getByRole('button', { name: 'المشاريع' }).className).toContain('font-semibold'); });
  it('shows unread badge on a badge-enabled navigation item', () => { renderLayout({ unreadCount: 7 }); const navButton = screen.getByRole('button', { name: /^التنبيهات/ }); expect(within(navButton).getByText('7')).toBeTruthy(); });
  it('caps navigation unread badge at 99+', () => { renderLayout({ unreadCount: 120 }); const navButton = screen.getByRole('button', { name: /^التنبيهات/ }); expect(within(navButton).getByText('99+')).toBeTruthy(); });
  it('does not show a navigation badge when unread count is zero', () => { renderLayout({ unreadCount: 0 }); expect(screen.queryByText('99+')).toBeNull(); });
  it('filters navigation using sidebar search', () => { renderLayout(); fireEvent.change(screen.getByPlaceholderText('بحث...'), { target: { value: 'مشاريع' } }); expect(screen.getByRole('button', { name: 'المشاريع' })).toBeTruthy(); expect(screen.queryByRole('button', { name: 'التنبيهات' })).toBeNull(); });
  it('search is case insensitive for latin labels', () => { renderLayout({ navItems: [{ id: 'gitlab', label: 'GitLab', IconComp: Icon }] }); fireEvent.change(screen.getByPlaceholderText('بحث...'), { target: { value: 'gitlab' } }); expect(screen.getByRole('button', { name: 'GitLab' })).toBeTruthy(); });
  it('shows no-results state for unmatched search', () => { renderLayout(); fireEvent.change(screen.getByPlaceholderText('بحث...'), { target: { value: 'ZZZ' } }); expect(screen.getByText('لا توجد نتائج')).toBeTruthy(); });
  it('Ctrl+K focuses sidebar search', () => { renderLayout(); const input = screen.getByPlaceholderText('بحث...'); fireEvent.keyDown(document, { key: 'k', ctrlKey: true }); expect(document.activeElement).toBe(input); });
  it('Meta+K focuses sidebar search', () => { renderLayout(); const input = screen.getByPlaceholderText('بحث...'); fireEvent.keyDown(document, { key: 'k', metaKey: true }); expect(document.activeElement).toBe(input); });
  it('Escape blurs sidebar search', () => { renderLayout(); const input = screen.getByPlaceholderText('بحث...'); input.focus(); fireEvent.keyDown(document, { key: 'Escape' }); expect(document.activeElement).not.toBe(input); });
  it('calls theme toggle', () => { const { props } = renderLayout(); fireEvent.click(screen.getByRole('button', { name: 'الوضع الليلي' })); expect(props.onToggleTheme).toHaveBeenCalledTimes(1); });
  it('uses day-mode label while currently dark', () => { renderLayout({ theme: 'dark' }); expect(screen.getByRole('button', { name: 'الوضع النهاري' })).toBeTruthy(); });
  it('shows full user name when available', () => { renderLayout(); expect(screen.getAllByText('Ali Ahmad').length).toBeGreaterThan(0); });
  it('falls back to username when names are missing', () => { renderLayout({ user: { username: 'doctor7' } }); expect(screen.getAllByText('doctor7').length).toBeGreaterThan(0); });
  it('opens the profile menu', () => { renderLayout(); fireEvent.click(screen.getByText('Ali Ahmad').closest('button')); expect(screen.getByText('تغيير كلمة المرور')).toBeTruthy(); });
  it('profile password action navigates to change-password', () => { const { props } = renderLayout(); fireEvent.click(screen.getByText('Ali Ahmad').closest('button')); fireEvent.click(screen.getByText('تغيير كلمة المرور')); expect(props.onNavigate).toHaveBeenCalledWith('change-password'); });
  it('profile email action navigates to change-email', () => { const { props } = renderLayout(); fireEvent.click(screen.getByText('Ali Ahmad').closest('button')); fireEvent.click(screen.getByText('تغيير البريد الإلكتروني')); expect(props.onNavigate).toHaveBeenCalledWith('change-email'); });
  it('profile logout invokes supplied handler', () => { const { props } = renderLayout(); fireEvent.click(screen.getByText('Ali Ahmad').closest('button')); fireEvent.click(screen.getByText('تسجيل الخروج')); expect(props.onLogout).toHaveBeenCalledTimes(1); });
  it('opens notification dropdown', () => { renderLayout(); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); expect(screen.getByText('لا توجد إشعارات')).toBeTruthy(); });
  it('shows at most five notifications', () => { const notifications = Array.from({ length: 7 }, (_, i) => ({ id: i + 1, title: `N${i + 1}`, is_read: true })); renderLayout({ notifications }); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); expect(screen.getByText('N5')).toBeTruthy(); expect(screen.queryByText('N6')).toBeNull(); });
  it('shows mark-all only when unread items exist', () => { renderLayout({ unreadCount: 2 }); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); expect(screen.getByText('تعليم الكل كمقروء')).toBeTruthy(); });
  it('hides mark-all when unread count is zero', () => { renderLayout({ unreadCount: 0 }); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); expect(screen.queryByText('تعليم الكل كمقروء')).toBeNull(); });
  it('calls mark-all callback', () => { const { props } = renderLayout({ unreadCount: 2 }); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); fireEvent.click(screen.getByText('تعليم الكل كمقروء')); expect(props.onMarkAllRead).toHaveBeenCalledTimes(1); });
  it('calls mark-read only for unread notification', () => { const { props } = renderLayout({ notifications: [{ id: 4, title: 'Unread', is_read: false }] }); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); fireEvent.click(screen.getByText('Unread')); expect(props.onMarkRead).toHaveBeenCalledWith(4); });
  it('does not mark already-read notification again', () => { const { props } = renderLayout({ notifications: [{ id: 4, title: 'Read', is_read: true }] }); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); fireEvent.click(screen.getByText('Read')); expect(props.onMarkRead).not.toHaveBeenCalled(); });
  it('Escape closes notification dropdown', () => { renderLayout(); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); fireEvent.keyDown(document, { key: 'Escape' }); expect(screen.queryByText('لا توجد إشعارات')).toBeNull(); });
  it('outside click closes notification dropdown', () => { renderLayout(); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); fireEvent.mouseDown(document.body); expect(screen.queryByText('لا توجد إشعارات')).toBeNull(); });
  it('desktop collapse hides sidebar search', () => { renderLayout(); fireEvent.click(screen.getByText('طي القائمة')); expect(screen.queryByPlaceholderText('بحث...')).toBeNull(); });
  it('mobile resize starts with collapsed sidebar', () => { Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: 700 }); renderLayout(); act(() => window.dispatchEvent(new Event('resize'))); expect(screen.queryByPlaceholderText('بحث...')).toBeNull(); });
});
