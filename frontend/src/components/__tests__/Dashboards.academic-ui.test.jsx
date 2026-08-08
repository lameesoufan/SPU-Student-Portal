import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ fetchUnreadCount: vi.fn(), fetchNotifications: vi.fn(), markNotifRead: vi.fn(), markAllNotifsRead: vi.fn() }));
vi.mock('../../api.jsx', () => ({ ...api }));
vi.mock('../../hooks/usePolling.js', () => ({ default: () => {} }));
vi.mock('../../ThemeContext.jsx', () => ({ useTheme: () => ({ theme: 'light', toggleTheme: vi.fn() }) }));

vi.mock('../ChangeEmail.jsx', () => ({ default: () => <div>ChangeEmail</div> }));
vi.mock('../ChangePassword.jsx', () => ({ default: () => <div>ChangePassword</div> }));
vi.mock('../MyIdeas.jsx', () => ({ default: ({ onSubmitNew }) => <div>MyIdeas<button onClick={onSubmitNew}>OPEN-SUBMIT</button></div> }));
vi.mock('../SubmitIdea.jsx', () => ({ default: () => <div>SubmitIdea</div> }));
vi.mock('../SupervisorReview.jsx', () => ({ default: () => <div>SupervisorReview</div> }));
vi.mock('../DoctorApplicationReview.jsx', () => ({ default: () => <div>DoctorApplicationReview</div> }));
vi.mock('../SupervisorProjects.jsx', () => ({ default: () => <div>SupervisorProjects</div> }));
vi.mock('../WorkflowBuilder.jsx', () => ({ default: () => <div>WorkflowBuilder</div> }));
vi.mock('../ApplyWorkflow.jsx', () => ({ default: () => <div>ApplyWorkflow</div> }));
vi.mock('../WorkflowReview.jsx', () => ({ default: () => <div>WorkflowReview</div> }));
vi.mock('../committees/DoctorCommitteeSchedule.jsx', () => ({ default: () => <div>DoctorCommitteeSchedule</div> }));
vi.mock('../committees/GradeEntry.jsx', () => ({ default: () => <div>GradeEntry</div> }));
vi.mock('../committees/MyAvailabilityPage.jsx', () => ({ default: () => <div>MyAvailabilityPage</div> }));
vi.mock('../HodProposalReview.jsx', () => ({ default: () => <div>HodProposalReview</div> }));
vi.mock('../HodIdeaReview.jsx', () => ({ default: () => <div>HodIdeaReview</div> }));
vi.mock('../HodApplicationReview.jsx', () => ({ default: () => <div>HodApplicationReview</div> }));
vi.mock('../HodFormBuilder.jsx', () => ({ default: () => <div>HodFormBuilder</div> }));
vi.mock('../HodProjects.jsx', () => ({ default: () => <div>HodProjects</div> }));
vi.mock('../CollectiveGradingSettings.jsx', () => ({ default: () => <div>CollectiveGradingSettings</div> }));
vi.mock('../HodGradesSummary.jsx', () => ({ default: () => <div>HodGradesSummary</div> }));
vi.mock('../ImportUsers.jsx', () => ({ default: () => <div>ImportUsers</div> }));
vi.mock('../ImportProjects.jsx', () => ({ default: () => <div>ImportProjects</div> }));
vi.mock('../AssignHod.jsx', () => ({ default: () => <div>AssignHod</div> }));
vi.mock('../StudentStatusManagement.jsx', () => ({ default: () => <div>StudentStatusManagement</div> }));
vi.mock('../GradesSummary.jsx', () => ({ default: () => <div>GradesSummary</div> }));
vi.mock('../committees/CommitteesDashboard.jsx', () => ({ default: ({ onNavigate }) => <div>CommitteesDashboard<button onClick={() => onNavigate('committee-detail', { id: 77 })}>OPEN-CONTEXT</button></div> }));
vi.mock('../committees/TemplateForm.jsx', () => ({ default: () => <div>TemplateForm</div> }));
vi.mock('../committees/DistributionTable.jsx', () => ({ default: () => <div>DistributionTable</div> }));
vi.mock('../committees/CommitteeDetail.jsx', () => ({ default: ({ committeeId }) => <div>CommitteeDetail-{committeeId}</div> }));
vi.mock('../committees/ProjectsAssignment.jsx', () => ({ default: () => <div>ProjectsAssignment</div> }));
vi.mock('../committees/RoomsManagement.jsx', () => ({ default: () => <div>RoomsManagement</div> }));
vi.mock('../committees/DoctorAvailabilityPage.jsx', () => ({ default: () => <div>DoctorAvailabilityPage</div> }));
vi.mock('../committees/SolverSettingsPage.jsx', () => ({ default: () => <div>SolverSettingsPage</div> }));
vi.mock('../committees/SchedulePage.jsx', () => ({ default: () => <div>SchedulePage</div> }));
vi.mock('../committees/SemesterSetupWizard.jsx', () => ({ default: () => <div>SemesterSetupWizard</div> }));

vi.mock('../DashboardLayout.jsx', () => ({ default: ({ navItems, activePage, onNavigate, unreadCount, notifications, onMarkRead, onMarkAllRead, onLogout, roleLabel, children }) => (
  <div><div data-testid="layout-role">{roleLabel}</div><div data-testid="active-page">{activePage}</div><div data-testid="unread">{unreadCount}</div>
    <button onClick={onLogout}>LAYOUT-LOGOUT</button><button onClick={onMarkAllRead}>LAYOUT-MARK-ALL</button>
    {(notifications || []).map((n) => <button key={n.id} onClick={() => onMarkRead(n.id)}>NOTIF-{n.id}-{String(n.is_read)}</button>)}
    {(navItems || []).filter((x) => x.id).map((x) => <button key={x.id} data-testid={`nav-${x.id}`} onClick={() => onNavigate(x.id)}>NAV-{x.id}-{x.label}</button>)}<main>{children}</main></div>
) }));

import DoctorDashboard from '../DoctorDashboard.jsx';
import HodDashboard from '../HodDashboard.jsx';
import DeanDashboard from '../DeanDashboard.jsx';

beforeEach(() => { vi.clearAllMocks(); api.fetchUnreadCount.mockResolvedValue({ data: { unread_count: 2 } }); api.fetchNotifications.mockResolvedValue({ data: { results: [{ id: 9, title: 'N', is_read: false }] } }); api.markNotifRead.mockResolvedValue({ data: {} }); api.markAllNotifsRead.mockResolvedValue({ data: {} }); });

const doctorRoutes = [['my-ideas','MyIdeas'],['supervisor-review','SupervisorReview'],['app-review','DoctorApplicationReview'],['supervised-projects','SupervisorProjects'],['workflow','WorkflowBuilder'],['applyworkflow','ApplyWorkflow'],['reviewworkflow','WorkflowReview'],['committee-schedule','DoctorCommitteeSchedule'],['my-availability','MyAvailabilityPage'],['grade-entry','GradeEntry']];
const hodRoutes = [['my-ideas','MyIdeas'],['supervisor-review','SupervisorReview'],['ideas','HodIdeaReview'],['proposals','HodProposalReview'],['applications','HodApplicationReview'],['formbuilder','HodFormBuilder'],['projects','HodProjects'],['workflow','WorkflowBuilder'],['applyworkflow','ApplyWorkflow'],['reviewworkflow','WorkflowReview'],['grading-settings','CollectiveGradingSettings'],['hod-grades','HodGradesSummary'],['grade-entry','GradeEntry']];
const deanRoutes = [['committees','CommitteesDashboard'],['student-status','StudentStatusManagement'],['projects','HodProjects'],['grades-summary','GradesSummary'],['import','ImportUsers'],['import-projects','ImportProjects'],['assign-hod','AssignHod'],['schedule','SchedulePage'],['rooms','RoomsManagement'],['availability','DoctorAvailabilityPage']];
function clickNav(id) { fireEvent.click(screen.getByTestId(`nav-${id}`)); }

describe('Doctor dashboard page contracts', () => {
  it('renders Faculty role shell', async () => { render(<DoctorDashboard user={{ username:'doc', department:'software_engineering' }} />); expect(await screen.findByText('Faculty')).toBeTruthy(); });
  it.each(doctorRoutes)('routes %s to %s', async (id, page) => { render(<DoctorDashboard user={{ username:'doc' }} />); clickNav(id); expect(await screen.findByText(page)).toBeTruthy(); });
  it('opens submit idea from MyIdeas', async () => { render(<DoctorDashboard user={{ username:'doc' }} />); clickNav('my-ideas'); fireEvent.click(await screen.findByText('OPEN-SUBMIT')); expect(screen.getByText('SubmitIdea')).toBeTruthy(); });
  it('exposes individual/collective grading wording', async () => { render(<DoctorDashboard user={{ username:'doc' }} />); expect(await screen.findByText(/في الفردي: رئيس اللجنة فقط/)).toBeTruthy(); expect(screen.getByText(/في الجماعي: جميع أعضاء اللجنة/)).toBeTruthy(); });
  it('passes logout to shell', async () => { const onLogout=vi.fn(); render(<DoctorDashboard user={{ username:'doc' }} onLogout={onLogout}/>); fireEvent.click(await screen.findByText('LAYOUT-LOGOUT')); expect(onLogout).toHaveBeenCalledOnce(); });
  it('loads unread count and notifications independently', async () => { render(<DoctorDashboard user={{ username:'doc' }} />); expect((await screen.findByTestId('unread')).textContent).toBe('2'); expect(screen.getByText(/NOTIF-9-false/)).toBeTruthy(); });
  it('marks one notification only after API success', async () => { render(<DoctorDashboard user={{ username:'doc' }} />); fireEvent.click(await screen.findByText(/NOTIF-9-false/)); await waitFor(()=>expect(api.markNotifRead).toHaveBeenCalledWith(9)); await waitFor(()=>expect(screen.getByText(/NOTIF-9-true/)).toBeTruthy()); });
  it('does not mutate notification when mark-read fails', async () => { api.markNotifRead.mockRejectedValue(new Error('x')); render(<DoctorDashboard user={{ username:'doc' }} />); fireEvent.click(await screen.findByText(/NOTIF-9-false/)); await waitFor(()=>expect(api.markNotifRead).toHaveBeenCalled()); expect(screen.getByText(/NOTIF-9-false/)).toBeTruthy(); });
  it('marks all only after API success', async () => { render(<DoctorDashboard user={{ username:'doc' }} />); fireEvent.click(await screen.findByText('LAYOUT-MARK-ALL')); await waitFor(()=>expect(screen.getByTestId('unread').textContent).toBe('0')); });
});

describe('HoD dashboard page contracts', () => {
  it('renders HoD role shell', async () => { render(<HodDashboard user={{ username:'hod', department:'software_engineering' }} />); expect((await screen.findByTestId('layout-role')).textContent).toBe('رئيس القسم'); });
  it.each(hodRoutes)('routes %s to %s', async (id, page) => { render(<HodDashboard user={{ username:'hod', department:'software_engineering' }} />); clickNav(id); expect(await screen.findByText(page)).toBeTruthy(); });
  it('opens submit idea from HoD MyIdeas', async () => { render(<HodDashboard user={{ username:'hod', department:'software_engineering' }} />); clickNav('my-ideas'); fireEvent.click(await screen.findByText('OPEN-SUBMIT')); expect(screen.getByText('SubmitIdea')).toBeTruthy(); });
  it('shows department label', async () => { render(<HodDashboard user={{ username:'hod', department:'artificial_intelligence' }} />); expect(await screen.findByText('ذكاء اصطناعي')).toBeTruthy(); });
  it('falls back to generic department label', async () => { render(<HodDashboard user={{ username:'hod', department:'other' }} />); expect(await screen.findByText('قسمك')).toBeTruthy(); });
  it('passes logout to shell', async () => { const onLogout=vi.fn(); render(<HodDashboard user={{username:'hod'}} onLogout={onLogout}/>); fireEvent.click(await screen.findByText('LAYOUT-LOGOUT')); expect(onLogout).toHaveBeenCalledOnce(); });
  it('loads notification state', async () => { render(<HodDashboard user={{username:'hod'}}/>); expect((await screen.findByTestId('unread')).textContent).toBe('2'); expect(screen.getByText(/NOTIF-9-false/)).toBeTruthy(); });
});

describe('Dean dashboard page contracts', () => {
  it('renders dean role shell', async () => { render(<DeanDashboard user={{ username:'dean' }} />); expect((await screen.findByTestId('layout-role')).textContent).toBe('عميد'); });
  it.each(deanRoutes)('routes %s to %s', async (id, page) => { render(<DeanDashboard user={{ username:'dean' }} />); clickNav(id); expect(await screen.findByText(page)).toBeTruthy(); });
  it('ignores unimplemented faculty route', async () => { render(<DeanDashboard user={{username:'dean'}}/>); await screen.findByText(/NOTIF-9-false/); clickNav('faculty'); expect(screen.queryByText('HodProjects')).toBeNull(); expect(screen.getByTestId('active-page').textContent).toBe('dashboard'); });
  it('opens committee detail with navigation context', async () => { render(<DeanDashboard user={{username:'dean'}}/>); clickNav('committees'); fireEvent.click(await screen.findByText('OPEN-CONTEXT')); expect(await screen.findByText('CommitteeDetail-77')).toBeTruthy(); });
  it('passes logout to shell', async () => { const onLogout=vi.fn(); render(<DeanDashboard user={{username:'dean'}} onLogout={onLogout}/>); fireEvent.click(await screen.findByText('LAYOUT-LOGOUT')); expect(onLogout).toHaveBeenCalledOnce(); });
  it('keeps unread count unchanged if mark-all fails', async () => { api.markAllNotifsRead.mockRejectedValue(new Error('x')); render(<DeanDashboard user={{username:'dean'}}/>); await screen.findByText(/NOTIF-9-false/); fireEvent.click(screen.getByText('LAYOUT-MARK-ALL')); await waitFor(()=>expect(api.markAllNotifsRead).toHaveBeenCalled()); expect(screen.getByTestId('unread').textContent).toBe('2'); });
});
