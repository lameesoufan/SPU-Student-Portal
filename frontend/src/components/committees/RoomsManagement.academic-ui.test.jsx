import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  fetchRooms: vi.fn(), createRoom: vi.fn(), updateRoom: vi.fn(), deleteRoom: vi.fn(),
}));
vi.mock('../../api.jsx', () => ({ ...api }));

import RoomsManagement from './RoomsManagement.jsx';

const rooms = [
  { id: 1, name: 'قاعة 201', capacity: 30, is_active: true, notes: 'طابق أول' },
  { id: 2, name: 'قاعة 305', capacity: 45, is_active: false, notes: '' },
];

beforeEach(() => {
  vi.clearAllMocks();
  api.fetchRooms.mockResolvedValue({ data: { results: rooms } });
  api.createRoom.mockResolvedValue({ data: { id: 3 } });
  api.updateRoom.mockResolvedValue({ data: {} });
  api.deleteRoom.mockResolvedValue({ data: {} });
  vi.spyOn(window, 'confirm').mockReturnValue(true);
});

async function ready(props = {}) {
  render(<RoomsManagement {...props} />);
  await screen.findByText('قاعة 201');
}

function openCreate() {
  fireEvent.click(screen.getByRole('button', { name: /قاعة جديدة/ }));
}

function createInputs() {
  return {
    name: screen.getByPlaceholderText('اسم القاعة، مثال: قاعة 201'),
    capacity: screen.getByPlaceholderText('السعة'),
    active: screen.getByRole('checkbox'),
    notes: screen.getByPlaceholderText('ملاحظات اختيارية'),
  };
}

describe('RoomsManagement loading and shell', () => {
  it('shows initial loading state', () => {
    api.fetchRooms.mockReturnValue(new Promise(() => {}));
    render(<RoomsManagement />);
    expect(screen.getByText('جاري تحميل القاعات...')).toBeTruthy();
  });
  it('loads rooms once on mount', async () => { await ready(); expect(api.fetchRooms).toHaveBeenCalledOnce(); });
  it('accepts paginated results response', async () => { await ready(); expect(screen.getByText('قاعة 305')).toBeTruthy(); });
  it('accepts direct array response', async () => { api.fetchRooms.mockResolvedValue({ data: rooms }); await ready(); expect(screen.getByText('قاعة 305')).toBeTruthy(); });
  it('shows page title', async () => { await ready(); expect(screen.getByText('إدارة القاعات')).toBeTruthy(); });
  it('shows room-count badge', async () => { await ready(); expect(screen.getByText('2 قاعة')).toBeTruthy(); });
  it('shows backend load detail', async () => { api.fetchRooms.mockRejectedValue({ response: { data: { detail: 'ROOM LOAD FAIL' } } }); render(<RoomsManagement />); expect(await screen.findByText('ROOM LOAD FAIL')).toBeTruthy(); });
  it('uses fallback load error', async () => { api.fetchRooms.mockRejectedValue(new Error('x')); render(<RoomsManagement />); expect(await screen.findByText('تعذر تحميل القاعات.')).toBeTruthy(); });
  it('shows empty state when no rooms exist', async () => { api.fetchRooms.mockResolvedValue({ data: [] }); render(<RoomsManagement />); expect(await screen.findByText('لا توجد قاعات')).toBeTruthy(); });
  it('refreshes room data', async () => { await ready(); fireEvent.click(screen.getByRole('button', { name: /تحديث/ })); await waitFor(() => expect(api.fetchRooms).toHaveBeenCalledTimes(2)); });
  it('navigates back to dashboard when onNavigate exists', async () => { const onNavigate = vi.fn(); await ready({ onNavigate }); fireEvent.click(screen.getByRole('button', { name: 'رجوع' })); expect(onNavigate).toHaveBeenCalledWith('dashboard'); });
  it('uses onBack when navigation callback is absent', async () => { const onBack = vi.fn(); await ready({ onBack }); fireEvent.click(screen.getByRole('button', { name: 'رجوع' })); expect(onBack).toHaveBeenCalledOnce(); });
});

describe('RoomsManagement room rendering', () => {
  it.each([['قاعة 201'], ['قاعة 305']])('renders room %s', async (name) => { await ready(); expect(screen.getByText(name)).toBeTruthy(); });
  it.each([['30'], ['45']])('renders capacity %s', async (capacity) => { await ready(); expect(screen.getByText(capacity)).toBeTruthy(); });
  it('renders active status', async () => { await ready(); expect(screen.getByText('فعّالة')).toBeTruthy(); });
  it('renders inactive status', async () => { await ready(); expect(screen.getByText('معطّلة')).toBeTruthy(); });
  it('renders room notes', async () => { await ready(); expect(screen.getByText('طابق أول')).toBeTruthy(); });
  it('uses dash for absent notes', async () => { await ready(); expect(screen.getByText('—')).toBeTruthy(); });
  it('renders one edit action per room', async () => { await ready(); expect(screen.getAllByTitle('تعديل')).toHaveLength(2); });
  it('renders one delete action per room', async () => { await ready(); expect(screen.getAllByTitle('حذف')).toHaveLength(2); });
});

describe('RoomsManagement create flow', () => {
  it('opens create form', async () => { await ready(); openCreate(); expect(screen.getByText('إضافة قاعة جديدة')).toBeTruthy(); });
  it('starts capacity at thirty', async () => { await ready(); openCreate(); expect(createInputs().capacity.value).toBe('30'); });
  it('starts active by default', async () => { await ready(); openCreate(); expect(createInputs().active.checked).toBe(true); });
  it('requires a nonblank room name', async () => { await ready(); openCreate(); fireEvent.click(screen.getByRole('button', { name: 'حفظ القاعة' })); expect(screen.getByText('اسم القاعة مطلوب.')).toBeTruthy(); expect(api.createRoom).not.toHaveBeenCalled(); });
  it('sends create payload from the form', async () => {
    await ready(); openCreate(); const f = createInputs();
    fireEvent.change(f.name, { target: { value: 'قاعة 410' } });
    fireEvent.change(f.capacity, { target: { value: '55' } });
    fireEvent.click(f.active);
    fireEvent.change(f.notes, { target: { value: 'مختبر' } });
    fireEvent.click(screen.getByRole('button', { name: 'حفظ القاعة' }));
    await waitFor(() => expect(api.createRoom).toHaveBeenCalledWith({ name: 'قاعة 410', capacity: 55, is_active: false, notes: 'مختبر' }));
  });
  it('shows create success toast', async () => { await ready(); openCreate(); fireEvent.change(createInputs().name, { target: { value: 'قاعة 410' } }); fireEvent.click(screen.getByRole('button', { name: 'حفظ القاعة' })); expect(await screen.findByText('تم إنشاء القاعة بنجاح.')).toBeTruthy(); });
  it('reloads rooms after create', async () => { await ready(); openCreate(); fireEvent.change(createInputs().name, { target: { value: 'قاعة 410' } }); fireEvent.click(screen.getByRole('button', { name: 'حفظ القاعة' })); await waitFor(() => expect(api.fetchRooms).toHaveBeenCalledTimes(2)); });
  it('closes create form after success', async () => { await ready(); openCreate(); fireEvent.change(createInputs().name, { target: { value: 'قاعة 410' } }); fireEvent.click(screen.getByRole('button', { name: 'حفظ القاعة' })); await waitFor(() => expect(screen.queryByText('إضافة قاعة جديدة')).toBeNull()); });
  it('shows backend create detail', async () => { api.createRoom.mockRejectedValue({ response: { data: { detail: 'CREATE DENIED' } } }); await ready(); openCreate(); fireEvent.change(createInputs().name, { target: { value: 'X' } }); fireEvent.click(screen.getByRole('button', { name: 'حفظ القاعة' })); expect(await screen.findByText('CREATE DENIED')).toBeTruthy(); });
  it('shows field-level create error', async () => { api.createRoom.mockRejectedValue({ response: { data: { name: ['NAME EXISTS'] } } }); await ready(); openCreate(); fireEvent.change(createInputs().name, { target: { value: 'X' } }); fireEvent.click(screen.getByRole('button', { name: 'حفظ القاعة' })); expect(await screen.findByText('NAME EXISTS')).toBeTruthy(); });
  it('cancels create form', async () => { await ready(); openCreate(); fireEvent.click(screen.getByRole('button', { name: 'إلغاء' })); expect(screen.queryByText('إضافة قاعة جديدة')).toBeNull(); });
});

describe('RoomsManagement edit and delete flow', () => {
  it('loads selected room into edit controls', async () => { await ready(); fireEvent.click(screen.getAllByTitle('تعديل')[0]); expect(screen.getByDisplayValue('قاعة 201')).toBeTruthy(); expect(screen.getByDisplayValue('طابق أول')).toBeTruthy(); });
  it('updates selected room', async () => { await ready(); fireEvent.click(screen.getAllByTitle('تعديل')[0]); const name = screen.getByDisplayValue('قاعة 201'); fireEvent.change(name, { target: { value: 'قاعة 201A' } }); fireEvent.click(screen.getByRole('button', { name: /حفظ$/ })); await waitFor(() => expect(api.updateRoom).toHaveBeenCalledWith(1, expect.objectContaining({ name: 'قاعة 201A', capacity: 30, is_active: true, notes: 'طابق أول' }))); });
  it('shows update success toast', async () => { await ready(); fireEvent.click(screen.getAllByTitle('تعديل')[0]); fireEvent.click(screen.getByRole('button', { name: /حفظ$/ })); expect(await screen.findByText('تم تحديث القاعة بنجاح.')).toBeTruthy(); });
  it('reloads after update', async () => { await ready(); fireEvent.click(screen.getAllByTitle('تعديل')[0]); fireEvent.click(screen.getByRole('button', { name: /حفظ$/ })); await waitFor(() => expect(api.fetchRooms).toHaveBeenCalledTimes(2)); });
  it('does not delete when confirmation is cancelled', async () => { window.confirm.mockReturnValue(false); await ready(); fireEvent.click(screen.getAllByTitle('حذف')[0]); expect(api.deleteRoom).not.toHaveBeenCalled(); });
  it('uses room name in delete confirmation', async () => { await ready(); fireEvent.click(screen.getAllByTitle('حذف')[0]); expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining('قاعة 201')); await waitFor(() => expect(api.fetchRooms).toHaveBeenCalledTimes(2)); });
  it('deletes confirmed room', async () => { await ready(); fireEvent.click(screen.getAllByTitle('حذف')[0]); await waitFor(() => expect(api.deleteRoom).toHaveBeenCalledWith(1)); });
  it('shows delete success toast', async () => { await ready(); fireEvent.click(screen.getAllByTitle('حذف')[0]); expect(await screen.findByText('تم حذف القاعة.')).toBeTruthy(); });
  it('reloads after delete', async () => { await ready(); fireEvent.click(screen.getAllByTitle('حذف')[0]); await waitFor(() => expect(api.fetchRooms).toHaveBeenCalledTimes(2)); });
  it('shows backend delete detail', async () => { api.deleteRoom.mockRejectedValue({ response: { data: { detail: 'ROOM IN USE' } } }); await ready(); fireEvent.click(screen.getAllByTitle('حذف')[0]); expect(await screen.findByText('ROOM IN USE')).toBeTruthy(); });
  it('uses fallback delete error', async () => { api.deleteRoom.mockRejectedValue(new Error('x')); await ready(); fireEvent.click(screen.getAllByTitle('حذف')[0]); expect(await screen.findByText('تعذر حذف القاعة؛ قد تكون مستخدمة في جدول حالي.')).toBeTruthy(); });
});
