import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  schedulePreview: vi.fn(), scheduleApply: vi.fn(), scheduleReject: vi.fn(), fetchSchedulingRuns: vi.fn(),
}));
vi.mock('../../api.jsx', () => ({ ...api }));

import SchedulePage from './SchedulePage.jsx';

const assignment = {
  committee_id: 77,
  committee_type: 'seminar_1',
  committee_type_ar: 'سيمينار 1',
  date: '2026-09-10',
  start_time: '09:00',
  end_time: '09:30',
  room_name: 'قاعة 201',
  doctors: [{ name: 'د. أحمد', role: 'chair' }, { name: 'د. سارة', role: 'member' }],
  projects_count: 2,
  duration_minutes: 30,
};
const successPreview = {
  success: true,
  run_id: 501,
  solver_status: 'OPTIMAL',
  wall_time: 1.25,
  summary_stats: { scheduled_committees: 1, days_used: 1, total_days_available: 4, rooms_used: 1, total_rooms_available: 3 },
  warnings: [{ message_ar: 'تنبيه تجريبي' }],
  plan: { assignments: [assignment] },
};
const failedPreview = {
  success: false,
  run_id: 502,
  solver_status: 'INFEASIBLE',
  wall_time: 0.5,
  infeasibility_report: [{ level: 'error', code: 'NO_SLOT', message_ar: 'لا يوجد وقت مناسب', suggestions_ar: ['زد الأيام'] }],
};
const runs = [
  { id: 10, committee_type_ar: 'سيمينار 1', semester: 'S2-2026', status: 'applied', solver_status: 'OPTIMAL', solver_wall_time_sec: 1.2, requested_by_name: 'Dean', requested_at: '2026-08-07T10:00:00Z', summary_stats: { days_used: 1, total_days_available: 4, rooms_used: 1, total_rooms_available: 3 }, plan_json: { assignments: [assignment] } },
  { id: 11, committee_type_ar: 'لجنة فنية', semester: 'S2-2026', status: 'failed', solver_status: 'INFEASIBLE', solver_wall_time_sec: 0.4, requested_by_name: '', requested_at: '2026-08-07T11:00:00Z', infeasibility_report: [{ level: 'warn', code: 'CONFLICT', message_ar: 'تعارض توفر' }] },
];

beforeEach(() => {
  vi.clearAllMocks();
  api.fetchSchedulingRuns.mockResolvedValue({ data: [] });
  api.schedulePreview.mockResolvedValue({ data: successPreview });
  api.scheduleApply.mockResolvedValue({ data: {} });
  api.scheduleReject.mockResolvedValue({ data: {} });
  vi.stubGlobal('confirm', vi.fn(() => true));
});

function renderPage(props = {}) { render(<SchedulePage {...props} />); }
function fieldByLabel(text) { return screen.getByText(text).parentElement.querySelector('input,select'); }
function semesterInput() { return screen.getByPlaceholderText('الفصل الثاني 2026'); }
function previewButton() { return screen.getByRole('button', { name: /معاينة الجدولة|جاري المعاينة/ }); }
function fillRequired() {
  fireEvent.change(semesterInput(), { target: { value: 'S2-2026' } });
  fireEvent.change(fieldByLabel('② من تاريخ *'), { target: { value: '2026-09-10' } });
  fireEvent.change(fieldByLabel('② إلى تاريخ *'), { target: { value: '2026-09-13' } });
}
async function runSuccessfulPreview() {
  renderPage(); fillRequired(); fireEvent.click(previewButton());
  await screen.findByText('✅ معاينة جاهزة');
}

describe('SchedulePage form contract', () => {
  it('renders page title', () => { renderPage(); expect(screen.getByText('جدولة اللجان')).toBeTruthy(); });
  it('renders page description', () => { renderPage(); expect(screen.getByText(/أنشئ معاينة قبل تطبيق الجدول/)).toBeTruthy(); });
  it('calls optional back callback', () => { const onBack = vi.fn(); renderPage({ onBack }); fireEvent.click(screen.getByRole('button', { name: 'رجوع' })); expect(onBack).toHaveBeenCalledOnce(); });
  it('does not render back button without callback', () => { renderPage(); expect(screen.queryByRole('button', { name: 'رجوع' })).toBeNull(); });
  it.each([
    ['سيمينار 1','seminar_1'], ['سيمينار 2','seminar_2'], ['لجنة فنية','technical'], ['مناقشة نهائية','final_discussion'],
  ])('offers committee type %s', (label, value) => { renderPage(); const option = screen.getByRole('option', { name: label }); expect(option.value).toBe(value); });
  it('defaults committee type to seminar 1', () => { renderPage(); expect(fieldByLabel('① نوع اللجنة *').value).toBe('seminar_1'); });
  it('defaults discussion duration to fifteen', () => { renderPage(); expect(fieldByLabel('② مدة المناقشة (دقيقة) *').value).toBe('15'); });
  it('defaults daily start to 09:00', () => { renderPage(); expect(fieldByLabel('② ساعة البداية *').value).toBe('09:00'); });
  it('defaults daily end to 17:00', () => { renderPage(); expect(fieldByLabel('② ساعة النهاية *').value).toBe('17:00'); });
  it('defaults buffer to ten', () => { renderPage(); expect(fieldByLabel('الفاصل بين اللجان (دقيقة)').value).toBe('10'); });
  it('defaults Saturday as selected', () => { renderPage(); expect(screen.getByRole('button', { name: /السبت/ }).textContent).toContain('✓'); });
  it('defaults Sunday as selected', () => { renderPage(); expect(screen.getByRole('button', { name: /الأحد/ }).textContent).toContain('✓'); });
  it('keeps Monday unselected initially', () => { renderPage(); expect(screen.getByRole('button', { name: /الإثنين/ }).textContent).not.toContain('✓'); });
  it('toggles a workday on', () => { renderPage(); fireEvent.click(screen.getByRole('button', { name: /الإثنين/ })); expect(screen.getByRole('button', { name: /الإثنين/ }).textContent).toContain('✓'); });
  it('toggles a workday off', () => { renderPage(); fireEvent.click(screen.getByRole('button', { name: /السبت/ })); expect(screen.getByRole('button', { name: /السبت/ }).textContent).not.toContain('✓'); });
  it('starts preview disabled with missing required fields', () => { renderPage(); expect(previewButton().disabled).toBe(true); });
  it('stays disabled with semester only', () => { renderPage(); fireEvent.change(semesterInput(), { target: { value: 'S2-2026' } }); expect(previewButton().disabled).toBe(true); });
  it('enables preview after semester and date range', async () => { renderPage(); fillRequired(); expect(previewButton().disabled).toBe(false); await waitFor(() => expect(api.fetchSchedulingRuns).toHaveBeenCalled()); });
  it('does not load run history before semester exists', () => { renderPage(); expect(api.fetchSchedulingRuns).not.toHaveBeenCalled(); });
});

describe('SchedulePage preview request', () => {
  it('sends complete default scheduling payload', async () => {
    renderPage(); fillRequired(); fireEvent.click(previewButton());
    await waitFor(() => expect(api.schedulePreview).toHaveBeenCalledWith({
      committee_type: 'seminar_1', semester: 'S2-2026', date_range_start: '2026-09-10', date_range_end: '2026-09-13',
      daily_start: '09:00', daily_end: '17:00', buffer_minutes: 10, discussion_duration: 15, workdays: [5, 6], timeout_seconds: 30,
    }));
  });
  it('uses changed committee type', async () => { renderPage(); fillRequired(); fireEvent.change(fieldByLabel('① نوع اللجنة *'), { target: { value: 'technical' } }); fireEvent.click(previewButton()); await waitFor(() => expect(api.schedulePreview.mock.calls[0][0].committee_type).toBe('technical')); });
  it('uses changed discussion duration', async () => { renderPage(); fillRequired(); fireEvent.change(fieldByLabel('② مدة المناقشة (دقيقة) *'), { target: { value: '25' } }); fireEvent.click(previewButton()); await waitFor(() => expect(api.schedulePreview.mock.calls[0][0].discussion_duration).toBe(25)); });
  it('uses changed daily hours', async () => { renderPage(); fillRequired(); fireEvent.change(fieldByLabel('② ساعة البداية *'), { target: { value: '10:00' } }); fireEvent.change(fieldByLabel('② ساعة النهاية *'), { target: { value: '15:00' } }); fireEvent.click(previewButton()); await waitFor(() => expect(api.schedulePreview.mock.calls[0][0]).toEqual(expect.objectContaining({ daily_start: '10:00', daily_end: '15:00' }))); });
  it('uses changed buffer', async () => { renderPage(); fillRequired(); fireEvent.change(fieldByLabel('الفاصل بين اللجان (دقيقة)'), { target: { value: '20' } }); fireEvent.click(previewButton()); await waitFor(() => expect(api.schedulePreview.mock.calls[0][0].buffer_minutes).toBe(20)); });
  it('uses sorted changed workdays', async () => { renderPage(); fillRequired(); fireEvent.click(screen.getByRole('button', { name: /السبت/ })); fireEvent.click(screen.getByRole('button', { name: /الإثنين/ })); fireEvent.click(previewButton()); await waitFor(() => expect(api.schedulePreview.mock.calls[0][0].workdays).toEqual([0, 6])); });
  it('shows backend preview error detail', async () => { api.schedulePreview.mockRejectedValue({ response: { data: { detail: 'PREVIEW DENIED' } } }); renderPage(); fillRequired(); fireEvent.click(previewButton()); expect(await screen.findByText('PREVIEW DENIED')).toBeTruthy(); });
  it('uses fallback preview connection error', async () => { api.schedulePreview.mockRejectedValue(new Error('x')); renderPage(); fillRequired(); fireEvent.click(previewButton()); expect(await screen.findByText('فشل الاتصال بالخادم')).toBeTruthy(); });
  it('reloads history after a preview request', async () => { renderPage(); fillRequired(); await waitFor(() => expect(api.fetchSchedulingRuns).toHaveBeenCalled()); const before = api.fetchSchedulingRuns.mock.calls.length; fireEvent.click(previewButton()); await waitFor(() => expect(api.fetchSchedulingRuns.mock.calls.length).toBeGreaterThan(before)); });
});

describe('SchedulePage successful preview UI', () => {
  it('shows ready heading', async () => { await runSuccessfulPreview(); expect(screen.getByText('✅ معاينة جاهزة')).toBeTruthy(); });
  it('shows solver status', async () => { await runSuccessfulPreview(); expect(screen.getAllByText(/OPTIMAL/).length).toBeGreaterThan(0); });
  it('shows run id', async () => { await runSuccessfulPreview(); expect(screen.getByText(/run #501/)).toBeTruthy(); });
  it('shows scheduled committees stat', async () => { await runSuccessfulPreview(); expect(screen.getByText('اللجان المجدولة')).toBeTruthy(); });
  it('shows days-used stat', async () => { await runSuccessfulPreview(); expect(screen.getByText('1/4')).toBeTruthy(); });
  it('shows rooms-used stat', async () => { await runSuccessfulPreview(); expect(screen.getByText('1/3')).toBeTruthy(); });
  it('shows warning message', async () => { await runSuccessfulPreview(); expect(screen.getByText('تنبيه تجريبي')).toBeTruthy(); });
  it('shows Gantt heading', async () => { await runSuccessfulPreview(); expect(screen.getByText('خريطة الجدولة (Gantt)')).toBeTruthy(); });
  it('shows assignments count', async () => { await runSuccessfulPreview(); expect(screen.getByText('تفاصيل الجدولة (1)')).toBeTruthy(); });
  it('shows assigned room', async () => { await runSuccessfulPreview(); expect(screen.getAllByText(/قاعة 201/).length).toBeGreaterThan(0); });
  it('shows chair crown in assignment table', async () => { await runSuccessfulPreview(); expect(screen.getByText(/د\. أحمد 👑/)).toBeTruthy(); });
  it('shows project count', async () => { await runSuccessfulPreview(); expect(screen.getByText('2 مشروع')).toBeTruthy(); });
  it('shows duration', async () => { await runSuccessfulPreview(); expect(screen.getByText('30 دقيقة')).toBeTruthy(); });
});

describe('SchedulePage apply and reject flows', () => {
  it('does not apply when confirmation is cancelled', async () => { globalThis.confirm.mockReturnValue(false); await runSuccessfulPreview(); fireEvent.click(screen.getByRole('button', { name: /تطبيق الجدولة/ })); expect(api.scheduleApply).not.toHaveBeenCalled(); });
  it('applies the preview run id', async () => { await runSuccessfulPreview(); fireEvent.click(screen.getByRole('button', { name: /تطبيق الجدولة/ })); await waitFor(() => expect(api.scheduleApply).toHaveBeenCalledWith(501)); });
  it('shows apply success toast', async () => { await runSuccessfulPreview(); fireEvent.click(screen.getByRole('button', { name: /تطبيق الجدولة/ })); expect(await screen.findByText('تم تطبيق الجدولة بنجاح')).toBeTruthy(); });
  it('clears preview after apply', async () => { await runSuccessfulPreview(); fireEvent.click(screen.getByRole('button', { name: /تطبيق الجدولة/ })); await waitFor(() => expect(screen.queryByText('✅ معاينة جاهزة')).toBeNull()); });
  it('shows backend apply detail', async () => { api.scheduleApply.mockRejectedValue({ response: { data: { detail: 'APPLY DENIED' } } }); await runSuccessfulPreview(); fireEvent.click(screen.getByRole('button', { name: /تطبيق الجدولة/ })); expect(await screen.findByText('APPLY DENIED')).toBeTruthy(); });
  it('uses fallback apply error', async () => { api.scheduleApply.mockRejectedValue(new Error('x')); await runSuccessfulPreview(); fireEvent.click(screen.getByRole('button', { name: /تطبيق الجدولة/ })); expect(await screen.findByText('فشل التطبيق')).toBeTruthy(); });
  it('rejects the preview run id', async () => { await runSuccessfulPreview(); fireEvent.click(screen.getByRole('button', { name: 'رفض' })); await waitFor(() => expect(api.scheduleReject).toHaveBeenCalledWith(501)); });
  it('shows reject success toast', async () => { await runSuccessfulPreview(); fireEvent.click(screen.getByRole('button', { name: 'رفض' })); expect(await screen.findByText('تم رفض المعاينة')).toBeTruthy(); });
  it('clears preview after reject', async () => { await runSuccessfulPreview(); fireEvent.click(screen.getByRole('button', { name: 'رفض' })); await waitFor(() => expect(screen.queryByText('✅ معاينة جاهزة')).toBeNull()); });
  it('shows reject fallback error', async () => { api.scheduleReject.mockRejectedValue(new Error('x')); await runSuccessfulPreview(); fireEvent.click(screen.getByRole('button', { name: 'رفض' })); expect(await screen.findByText('فشل الرفض')).toBeTruthy(); });
});

describe('SchedulePage failed preview and history', () => {
  it('shows failed preview heading', async () => { api.schedulePreview.mockResolvedValue({ data: failedPreview }); renderPage(); fillRequired(); fireEvent.click(previewButton()); expect(await screen.findByText('فشل إنشاء المعاينة')).toBeTruthy(); });
  it('shows infeasibility code', async () => { api.schedulePreview.mockResolvedValue({ data: failedPreview }); renderPage(); fillRequired(); fireEvent.click(previewButton()); expect(await screen.findByText('NO_SLOT')).toBeTruthy(); });
  it('shows infeasibility message', async () => { api.schedulePreview.mockResolvedValue({ data: failedPreview }); renderPage(); fillRequired(); fireEvent.click(previewButton()); expect(await screen.findByText('لا يوجد وقت مناسب')).toBeTruthy(); });
  it('shows infeasibility suggestion', async () => { api.schedulePreview.mockResolvedValue({ data: failedPreview }); renderPage(); fillRequired(); fireEvent.click(previewButton()); expect(await screen.findByText('زد الأيام')).toBeTruthy(); });
  it('loads history after semester entry', async () => { renderPage(); fireEvent.change(semesterInput(), { target: { value: 'S2-2026' } }); await waitFor(() => expect(api.fetchSchedulingRuns).toHaveBeenCalledWith({ committee_type: 'seminar_1', semester: 'S2-2026' })); });
  it('shows empty history by default', () => { renderPage(); expect(screen.getByText('لا توجد عمليات سابقة')).toBeTruthy(); });
  it('renders returned history rows', async () => { api.fetchSchedulingRuns.mockResolvedValue({ data: runs }); renderPage(); fireEvent.change(semesterInput(), { target: { value: 'S2-2026' } }); expect(await screen.findByText('#10')).toBeTruthy(); expect(screen.getByText('#11')).toBeTruthy(); });
  it('renders applied history status', async () => { api.fetchSchedulingRuns.mockResolvedValue({ data: runs }); renderPage(); fireEvent.change(semesterInput(), { target: { value: 'S2-2026' } }); expect(await screen.findByText('مُطبَّق')).toBeTruthy(); });
  it('renders failed history status', async () => { api.fetchSchedulingRuns.mockResolvedValue({ data: runs }); renderPage(); fireEvent.change(semesterInput(), { target: { value: 'S2-2026' } }); expect(await screen.findByText('فشل')).toBeTruthy(); });
  it('expands successful run details', async () => { api.fetchSchedulingRuns.mockResolvedValue({ data: runs }); renderPage(); fireEvent.change(semesterInput(), { target: { value: 'S2-2026' } }); await screen.findByText('#10'); fireEvent.click(screen.getAllByTitle('عرض التفاصيل')[0]); expect(await screen.findByText('تفاصيل الجدولة (1)')).toBeTruthy(); });
  it('expands failed run report', async () => { api.fetchSchedulingRuns.mockResolvedValue({ data: runs }); renderPage(); fireEvent.change(semesterInput(), { target: { value: 'S2-2026' } }); await screen.findByText('#11'); fireEvent.click(screen.getAllByTitle('عرض التفاصيل')[1]); expect(await screen.findByText('CONFLICT')).toBeTruthy(); });
  it('collapses expanded history row', async () => { api.fetchSchedulingRuns.mockResolvedValue({ data: runs }); renderPage(); fireEvent.change(semesterInput(), { target: { value: 'S2-2026' } }); await screen.findByText('#10'); const btn = screen.getAllByTitle('عرض التفاصيل')[0]; fireEvent.click(btn); await screen.findByText('تفاصيل الجدولة (1)'); fireEvent.click(btn); await waitFor(() => expect(screen.queryByText('تفاصيل الجدولة (1)')).toBeNull()); });
  it('refreshes history manually', async () => { renderPage(); fireEvent.change(semesterInput(), { target: { value: 'S2-2026' } }); await waitFor(() => expect(api.fetchSchedulingRuns).toHaveBeenCalled()); const before = api.fetchSchedulingRuns.mock.calls.length; fireEvent.click(screen.getByRole('button', { name: /تحديث/ })); await waitFor(() => expect(api.fetchSchedulingRuns.mock.calls.length).toBe(before + 1)); });
  it('clears history when history request fails', async () => { api.fetchSchedulingRuns.mockRejectedValue(new Error('x')); renderPage(); fireEvent.change(semesterInput(), { target: { value: 'S2-2026' } }); expect(await screen.findByText('لا توجد عمليات سابقة')).toBeTruthy(); });
});
