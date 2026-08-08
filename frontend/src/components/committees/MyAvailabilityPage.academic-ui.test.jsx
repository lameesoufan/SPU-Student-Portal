import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  addMyAvailabilityDay: vi.fn(), createMyException: vi.fn(), deleteMyAvailability: vi.fn(),
  deleteMyException: vi.fn(), fetchMyAvailability: vi.fn(), fetchMyExceptions: vi.fn(),
}));
vi.mock('../../api.jsx', () => ({ ...api }));

import MyAvailabilityPage from './MyAvailabilityPage.jsx';

const availability = [
  { id: 10, weekday: 0 },
  { id: 11, weekday: 5 },
];
const exceptions = [
  { id: 21, date: '2026-08-15', exception_type: 'blocked', reason: 'سفر' },
  { id: 22, date: '2026-08-22', exception_type: 'available', reason: '' },
];

beforeEach(() => {
  vi.clearAllMocks();
  api.fetchMyAvailability.mockResolvedValue({ data: availability });
  api.fetchMyExceptions.mockResolvedValue({ data: exceptions });
  api.addMyAvailabilityDay.mockImplementation(async (weekday) => ({ data: { id: 100 + weekday, weekday } }));
  api.createMyException.mockImplementation(async (payload) => ({ data: { id: 30, ...payload } }));
  api.deleteMyAvailability.mockResolvedValue({ data: {} });
  api.deleteMyException.mockResolvedValue({ data: {} });
});

async function ready(props = {}) {
  render(<MyAvailabilityPage user={{ first_name: 'Ahmad', last_name: 'Ali', username: 'doctor1' }} {...props} />);
  await screen.findByText('2026-08-15');
}
function dayButton(name) { return screen.getByRole('button', { name: new RegExp(name) }); }
function dateInput() { return document.querySelector('input[type="date"]'); }
function exceptionTypeSelect() { return screen.getByDisplayValue('محظور').closest('select'); }
function exceptionDeleteButton(date) { return screen.getByText(date).closest('tr').querySelector('button'); }

describe('MyAvailabilityPage loading and identity', () => {
  it('loads availability and exceptions in parallel on mount', async () => { await ready(); expect(api.fetchMyAvailability).toHaveBeenCalledOnce(); expect(api.fetchMyExceptions).toHaveBeenCalledOnce(); });
  it('shows page title', async () => { await ready(); expect(screen.getByText('توفري الأسبوعي')).toBeTruthy(); });
  it('uses full user name in description', async () => { await ready(); expect(screen.getByText(/مرحبًا Ahmad Ali/)).toBeTruthy(); });
  it('falls back to username when names are absent', async () => { render(<MyAvailabilityPage user={{ username: 'doctor1' }} />); expect(await screen.findByText(/مرحبًا doctor1/)).toBeTruthy(); });
  it('falls back to generic doctor when user is absent', async () => { render(<MyAvailabilityPage />); expect(await screen.findByText(/مرحبًا الدكتور/)).toBeTruthy(); });
  it('shows number of active weekdays', async () => { await ready(); expect(screen.getByText('2 أيام متاحة')).toBeTruthy(); });
  it('shows load error when either request fails', async () => { api.fetchMyAvailability.mockRejectedValue(new Error('x')); render(<MyAvailabilityPage />); expect(await screen.findByText('تعذر تحميل بيانات التوفر.')).toBeTruthy(); });
  it('clears availability after load failure', async () => { api.fetchMyExceptions.mockRejectedValue(new Error('x')); render(<MyAvailabilityPage />); await screen.findByText('تعذر تحميل بيانات التوفر.'); expect(screen.getByText('0 أيام متاحة')).toBeTruthy(); });
  it('shows empty exceptions state after load failure', async () => { api.fetchMyExceptions.mockRejectedValue(new Error('x')); render(<MyAvailabilityPage />); expect(await screen.findByText('لا توجد استثناءات مسجلة.')).toBeTruthy(); });
  it('refreshes both data sources', async () => { await ready(); fireEvent.click(screen.getByRole('button', { name: /تحديث/ })); await waitFor(() => expect(api.fetchMyAvailability).toHaveBeenCalledTimes(2)); expect(api.fetchMyExceptions).toHaveBeenCalledTimes(2); });
  it('calls back navigation', async () => { const onBack = vi.fn(); await ready({ onBack }); fireEvent.click(screen.getByRole('button', { name: 'رجوع' })); expect(onBack).toHaveBeenCalledOnce(); });
});

describe('MyAvailabilityPage weekdays', () => {
  it.each(['الإثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت','الأحد'])('renders weekday %s', async (name) => { await ready(); expect(dayButton(name)).toBeTruthy(); });
  it('marks existing Monday as active', async () => { await ready(); expect(dayButton('الإثنين').textContent).toContain('✓'); });
  it('marks existing Saturday as active', async () => { await ready(); expect(dayButton('السبت').textContent).toContain('✓'); });
  it('marks inactive Tuesday with plus', async () => { await ready(); expect(dayButton('الثلاثاء').textContent).toContain('+'); });
  it('deletes an existing availability day', async () => { await ready(); fireEvent.click(dayButton('الإثنين')); await waitFor(() => expect(api.deleteMyAvailability).toHaveBeenCalledWith(10)); });
  it('removes deleted day from local state', async () => { await ready(); fireEvent.click(dayButton('الإثنين')); await waitFor(() => expect(dayButton('الإثنين').textContent).toContain('+')); });
  it('adds an inactive availability day', async () => { await ready(); fireEvent.click(dayButton('الثلاثاء')); await waitFor(() => expect(api.addMyAvailabilityDay).toHaveBeenCalledWith(1)); });
  it('adds returned day to local state', async () => { await ready(); fireEvent.click(dayButton('الثلاثاء')); await waitFor(() => expect(dayButton('الثلاثاء').textContent).toContain('✓')); });
  it('shows backend toggle error', async () => { api.addMyAvailabilityDay.mockRejectedValue({ response: { data: { detail: 'DAY DENIED' } } }); await ready(); fireEvent.click(dayButton('الثلاثاء')); expect(await screen.findByText('DAY DENIED')).toBeTruthy(); });
  it('uses fallback toggle error', async () => { api.deleteMyAvailability.mockRejectedValue(new Error('x')); await ready(); fireEvent.click(dayButton('الإثنين')); expect(await screen.findByText('فشل تحديث التوفر.')).toBeTruthy(); });
  it('does not remove active day after failed delete', async () => { api.deleteMyAvailability.mockRejectedValue(new Error('x')); await ready(); fireEvent.click(dayButton('الإثنين')); await screen.findByText('فشل تحديث التوفر.'); expect(dayButton('الإثنين').textContent).toContain('✓'); });
});

describe('MyAvailabilityPage exception form', () => {
  it('renders date input', async () => { await ready(); expect(dateInput().type).toBe('date'); });
  it('defaults exception type to blocked', async () => { await ready(); expect(exceptionTypeSelect().value).toBe('blocked'); });
  it('offers available exception type', async () => { await ready(); expect(screen.getByRole('option', { name: 'متاح' })).toBeTruthy(); });
  it('renders reason placeholder', async () => { await ready(); expect(screen.getByPlaceholderText('سفر، مرض، إجازة...')).toBeTruthy(); });
  it('requires a date before creating exception', async () => { await ready(); fireEvent.click(screen.getByRole('button', { name: /إضافة/ })); expect(screen.getByText('حدد تاريخ الاستثناء أولًا.')).toBeTruthy(); expect(api.createMyException).not.toHaveBeenCalled(); });
  it('sends complete exception payload', async () => {
    await ready();
    fireEvent.change(dateInput(), { target: { value: '2026-08-30' } });
    fireEvent.change(exceptionTypeSelect(), { target: { value: 'available' } });
    fireEvent.change(screen.getByPlaceholderText('سفر، مرض، إجازة...'), { target: { value: 'دوام استثنائي' } });
    fireEvent.click(screen.getByRole('button', { name: /إضافة/ }));
    await waitFor(() => expect(api.createMyException).toHaveBeenCalledWith({ date: '2026-08-30', exception_type: 'available', reason: 'دوام استثنائي' }));
  });
  it('shows create success toast', async () => { await ready(); fireEvent.change(dateInput(), { target: { value: '2026-08-30' } }); fireEvent.click(screen.getByRole('button', { name: /إضافة/ })); expect(await screen.findByText('تمت إضافة الاستثناء.')).toBeTruthy(); });
  it('adds created exception to table', async () => { await ready(); fireEvent.change(dateInput(), { target: { value: '2026-08-30' } }); fireEvent.click(screen.getByRole('button', { name: /إضافة/ })); expect(await screen.findByText('2026-08-30')).toBeTruthy(); });
  it('resets date after successful create', async () => { await ready(); fireEvent.change(dateInput(), { target: { value: '2026-08-30' } }); fireEvent.click(screen.getByRole('button', { name: /إضافة/ })); await screen.findByText('تمت إضافة الاستثناء.'); expect(dateInput().value).toBe(''); });
  it('resets type to blocked after successful create', async () => { await ready(); fireEvent.change(dateInput(), { target: { value: '2026-08-30' } }); fireEvent.change(exceptionTypeSelect(), { target: { value: 'available' } }); fireEvent.click(screen.getByRole('button', { name: /إضافة/ })); await screen.findByText('تمت إضافة الاستثناء.'); expect(exceptionTypeSelect().value).toBe('blocked'); });
  it('shows backend create error', async () => { api.createMyException.mockRejectedValue({ response: { data: { detail: 'EXCEPTION DENIED' } } }); await ready(); fireEvent.change(dateInput(), { target: { value: '2026-08-30' } }); fireEvent.click(screen.getByRole('button', { name: /إضافة/ })); expect(await screen.findByText('EXCEPTION DENIED')).toBeTruthy(); });
  it('uses fallback create error', async () => { api.createMyException.mockRejectedValue(new Error('x')); await ready(); fireEvent.change(dateInput(), { target: { value: '2026-08-30' } }); fireEvent.click(screen.getByRole('button', { name: /إضافة/ })); expect(await screen.findByText('فشلت إضافة الاستثناء.')).toBeTruthy(); });
});

describe('MyAvailabilityPage exception table', () => {
  it.each(['2026-08-15','2026-08-22'])('renders exception date %s', async (date) => { await ready(); expect(screen.getByText(date)).toBeTruthy(); });
  it('renders blocked exception status', async () => { await ready(); expect(screen.getAllByText('محظور').length).toBeGreaterThan(0); });
  it('renders available exception status', async () => { await ready(); expect(screen.getAllByText('متاح').length).toBeGreaterThan(0); });
  it('renders exception reason', async () => { await ready(); expect(screen.getByText('سفر')).toBeTruthy(); });
  it('uses dash for empty reason', async () => { await ready(); expect(screen.getByText('—')).toBeTruthy(); });
  it('deletes an exception by id', async () => { await ready(); fireEvent.click(exceptionDeleteButton('2026-08-15')); await waitFor(() => expect(api.deleteMyException).toHaveBeenCalledWith(21)); });
  it('removes deleted exception locally', async () => { await ready(); fireEvent.click(exceptionDeleteButton('2026-08-15')); await waitFor(() => expect(screen.queryByText('2026-08-15')).toBeNull()); });
  it('shows fallback delete exception error', async () => { api.deleteMyException.mockRejectedValue(new Error('x')); await ready(); fireEvent.click(exceptionDeleteButton('2026-08-15')); expect(await screen.findByText('فشل حذف الاستثناء.')).toBeTruthy(); });
  it('keeps exception after failed delete', async () => { api.deleteMyException.mockRejectedValue(new Error('x')); await ready(); fireEvent.click(exceptionDeleteButton('2026-08-15')); await screen.findByText('فشل حذف الاستثناء.'); expect(screen.getByText('2026-08-15')).toBeTruthy(); });
});
