import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  fetchNotifications: vi.fn(), fetchUnreadCount: vi.fn(), markNotifRead: vi.fn(), markAllNotifsRead: vi.fn(), poll: null,
}));
vi.mock('../../api.jsx', () => ({
  fetchNotifications: mocks.fetchNotifications,
  fetchUnreadCount: mocks.fetchUnreadCount,
  markNotifRead: mocks.markNotifRead,
  markAllNotifsRead: mocks.markAllNotifsRead,
}));
vi.mock('../../hooks/usePolling.js', () => ({ default: (callback) => { mocks.poll = callback; } }));
import NotificationBell from '../NotificationBell.jsx';

const unread = { id: 1, title: 'New proposal', message: 'Please review', notif_type: 'proposal_submitted', is_read: false, created_at: '2026-08-07T10:00:00Z' };
const read = { id: 2, title: 'Accepted', message: 'Done', notif_type: 'idea_approved', is_read: true, created_at: '2026-08-07T09:00:00Z' };

beforeEach(() => {
  vi.clearAllMocks();
  mocks.poll = null;
  mocks.fetchUnreadCount.mockResolvedValue({ data: { unread_count: 0 } });
  mocks.fetchNotifications.mockResolvedValue({ data: [] });
  mocks.markNotifRead.mockResolvedValue({ data: {} });
  mocks.markAllNotifsRead.mockResolvedValue({ data: {} });
});

async function pollCount(value, shape = 'unread_count') {
  mocks.fetchUnreadCount.mockResolvedValue({ data: { [shape]: value } });
  await act(async () => { await mocks.poll(); });
}

describe('NotificationBell', () => {
  it('starts closed', () => { render(<NotificationBell />); expect(screen.queryByRole('dialog', { name: 'الإشعارات' })).toBeNull(); });
  it('starts without an unread suffix', () => { render(<NotificationBell />); expect(screen.getByRole('button', { name: 'الإشعارات' })).toBeTruthy(); });
  it('polls and displays unread_count', async () => { render(<NotificationBell />); await pollCount(4); expect(screen.getByRole('button', { name: 'الإشعارات، 4 غير مقروءة' })).toBeTruthy(); });
  it('supports legacy count response', async () => { render(<NotificationBell />); await pollCount(5, 'count'); expect(screen.getByText('5')).toBeTruthy(); });
  it('caps badge at 99+', async () => { render(<NotificationBell />); await pollCount(101); expect(screen.getByText('99+')).toBeTruthy(); });
  it('ignores polling failures', async () => { mocks.fetchUnreadCount.mockRejectedValue(new Error('offline')); render(<NotificationBell />); await act(async () => { await mocks.poll(); }); expect(screen.getByRole('button', { name: 'الإشعارات' })).toBeTruthy(); });
  it('opens and fetches notifications', async () => { mocks.fetchNotifications.mockResolvedValue({ data: [unread] }); render(<NotificationBell />); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); await screen.findByText('New proposal'); expect(mocks.fetchNotifications).toHaveBeenCalledTimes(1); });
  it('accepts paginated notification response', async () => { mocks.fetchNotifications.mockResolvedValue({ data: { results: [read] } }); render(<NotificationBell />); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); expect(await screen.findByText('Accepted')).toBeTruthy(); });
  it('shows empty state', async () => { render(<NotificationBell />); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); expect(await screen.findByText('لا توجد إشعارات بعد')).toBeTruthy(); });
  it('falls back to empty state if fetch fails', async () => { mocks.fetchNotifications.mockRejectedValue(new Error('boom')); render(<NotificationBell />); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); expect(await screen.findByText('لا توجد إشعارات بعد')).toBeTruthy(); });
  it('closes by pressing Escape', async () => { render(<NotificationBell />); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); await screen.findByRole('dialog', { name: 'الإشعارات' }); fireEvent.keyDown(document, { key: 'Escape' }); expect(screen.queryByRole('dialog', { name: 'الإشعارات' })).toBeNull(); });
  it('closes on outside mouse click', async () => { render(<NotificationBell />); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); await screen.findByRole('dialog', { name: 'الإشعارات' }); fireEvent.mouseDown(document.body); expect(screen.queryByRole('dialog', { name: 'الإشعارات' })).toBeNull(); });
  it('does not close when clicking inside dialog', async () => { render(<NotificationBell />); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); const dialog = await screen.findByRole('dialog', { name: 'الإشعارات' }); fireEvent.mouseDown(dialog); expect(screen.getByRole('dialog', { name: 'الإشعارات' })).toBeTruthy(); });
  it('toggles closed when bell is clicked twice', async () => { render(<NotificationBell />); const bell = screen.getByRole('button', { name: 'الإشعارات' }); fireEvent.click(bell); await screen.findByRole('dialog', { name: 'الإشعارات' }); fireEvent.click(bell); expect(screen.queryByRole('dialog', { name: 'الإشعارات' })).toBeNull(); });
  it('does not refetch when closing', async () => { render(<NotificationBell />); const bell = screen.getByRole('button', { name: 'الإشعارات' }); fireEvent.click(bell); await screen.findByRole('dialog', { name: 'الإشعارات' }); fireEvent.click(bell); expect(mocks.fetchNotifications).toHaveBeenCalledTimes(1); });
  it('marks one unread notification after backend success', async () => { mocks.fetchNotifications.mockResolvedValue({ data: [unread] }); render(<NotificationBell />); await pollCount(1); fireEvent.click(screen.getByRole('button', { name: /الإشعارات/ })); fireEvent.click(await screen.findByText('New proposal')); await waitFor(() => expect(mocks.markNotifRead).toHaveBeenCalledWith(1)); expect(screen.getByText('جميع الإشعارات مقروءة')).toBeTruthy(); });
  it('does not call mark API for already-read notification', async () => { mocks.fetchNotifications.mockResolvedValue({ data: [read] }); render(<NotificationBell />); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); fireEvent.click(await screen.findByText('Accepted')); expect(mocks.markNotifRead).not.toHaveBeenCalled(); });
  it('keeps unread state if mark-one backend request fails', async () => { mocks.fetchNotifications.mockResolvedValue({ data: [unread] }); mocks.markNotifRead.mockRejectedValue(new Error('fail')); render(<NotificationBell />); await pollCount(1); fireEvent.click(screen.getByRole('button', { name: /الإشعارات/ })); fireEvent.click(await screen.findByText('New proposal')); await waitFor(() => expect(mocks.markNotifRead).toHaveBeenCalled()); expect(screen.getByText('1 إشعار غير مقروء')).toBeTruthy(); });
  it('shows mark-all when count is positive', async () => { render(<NotificationBell />); await pollCount(2); fireEvent.click(screen.getByRole('button', { name: /الإشعارات/ })); expect(screen.getByText('تحديد الكل كمقروء')).toBeTruthy(); });
  it('hides mark-all when count is zero', async () => { render(<NotificationBell />); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); expect(screen.queryByText('تحديد الكل كمقروء')).toBeNull(); });
  it('marks all locally only after backend success', async () => { mocks.fetchNotifications.mockResolvedValue({ data: [unread] }); render(<NotificationBell />); await pollCount(1); fireEvent.click(screen.getByRole('button', { name: /الإشعارات/ })); await screen.findByText('New proposal'); fireEvent.click(screen.getByText('تحديد الكل كمقروء')); await waitFor(() => expect(mocks.markAllNotifsRead).toHaveBeenCalledTimes(1)); expect(screen.getByText('جميع الإشعارات مقروءة')).toBeTruthy(); });
  it('keeps unread state if mark-all backend request fails', async () => { mocks.fetchNotifications.mockResolvedValue({ data: [unread] }); mocks.markAllNotifsRead.mockRejectedValue(new Error('fail')); render(<NotificationBell />); await pollCount(1); fireEvent.click(screen.getByRole('button', { name: /الإشعارات/ })); await screen.findByText('New proposal'); fireEvent.click(screen.getByText('تحديد الكل كمقروء')); await waitFor(() => expect(mocks.markAllNotifsRead).toHaveBeenCalled()); expect(screen.getByText('1 إشعار غير مقروء')).toBeTruthy(); });
  it('renders unknown notification types safely', async () => { mocks.fetchNotifications.mockResolvedValue({ data: [{ ...unread, notif_type: 'new_future_type' }] }); render(<NotificationBell />); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); expect(await screen.findByText('New proposal')).toBeTruthy(); });
  it('uses message text alongside title', async () => { mocks.fetchNotifications.mockResolvedValue({ data: [unread] }); render(<NotificationBell />); fireEvent.click(screen.getByRole('button', { name: 'الإشعارات' })); expect(await screen.findByText('Please review')).toBeTruthy(); });
  it('sets aria-expanded true while open', async () => { render(<NotificationBell />); const bell = screen.getByRole('button', { name: 'الإشعارات' }); fireEvent.click(bell); await screen.findByRole('dialog', { name: 'الإشعارات' }); expect(bell.getAttribute('aria-expanded')).toBe('true'); });
});
