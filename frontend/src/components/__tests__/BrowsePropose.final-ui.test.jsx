import React from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  browseIdeas: vi.fn(), applyOnIdea: vi.fn(), fetchMyIdeaApplication: vi.fn(), fetchMyProposal: vi.fn(), fetchStudentForm: vi.fn(), fetchMyBoard: vi.fn(),
  submitStudentProposal: vi.fn(), fetchDoctorsList: vi.fn(), replaceProposalMember: vi.fn(), removeRejectedProposalMember: vi.fn(), replaceRejectedSupervisor: vi.fn(), continueWithApprovedSupervisor: vi.fn(), reviseStudentProposal: vi.fn(),
}));
vi.mock('../../api.jsx', () => ({ ...api }));
vi.mock('../StudentSearch.jsx', () => ({ default: ({ id, value, onChange, placeholder }) => <div data-testid={id || 'student-search'}><button type="button" onClick={() => onChange('s200')}>PICK-STUDENT</button><span>{value || ''}</span><span>{placeholder || ''}</span></div> }));
vi.mock('../DynamicCheckboxGroup.jsx', () => ({ default: ({ field, value, onChange }) => <button type="button" data-testid={`checkbox-${field.id}`} onClick={() => onChange(['A'])}>CHECKBOX-{(value || []).join(',')}</button> }));

import BrowseIdeas from '../BrowseIdeas.jsx';
import ProposeIdea from '../ProposeIdea.jsx';

const ideas = [
  { id:1, title:'AI Tutor', description:'AI project', doctor_name:'Dr Noor', department:'artificial_intelligence', max_team_size:3, required_skills:'Python, React', is_taken:false, project_type:'graduation_1' },
  { id:2, title:'Secure Portal', description:'Security project', doctor_name:'Dr Samer', department:'information_security', max_team_size:2, required_skills:'Django', is_taken:false, project_type:'seasonal' },
];
const doctors = [
  { id:1, name:'Dr One', department:'software_engineering' },
  { id:2, name:'Dr Two', department:'artificial_intelligence' },
];

async function flushAsyncState() {
  await act(async () => {
    await Promise.resolve();
  });
}

async function openIdeaApplication() {
  render(<BrowseIdeas/>);
  fireEvent.click((await screen.findAllByRole('button',{name:'Apply for Project'}))[0]);
  await waitFor(()=>expect(api.fetchStudentForm).toHaveBeenCalled());
  await flushAsyncState();
}

beforeEach(() => {
  vi.resetAllMocks();
  api.browseIdeas.mockResolvedValue({ data: ideas });
  api.fetchMyIdeaApplication.mockResolvedValue({ data: null });
  api.fetchMyProposal.mockResolvedValue({ data: null });
  api.fetchMyBoard.mockResolvedValue({ data: { has_project:false } });
  api.fetchStudentForm.mockResolvedValue({ data: { id:7, title:'Department Form', fields:[] } });
  api.applyOnIdea.mockResolvedValue({ data: { idea:1, idea_title:'AI Tutor', status:'awaiting_members' } });
  api.fetchDoctorsList.mockResolvedValue({ data: doctors });
  api.submitStudentProposal.mockResolvedValue({ data: { proposal:{ id:9, title:'Smart Campus', status:'awaiting_members', department:'software_engineering', team_size:2, supervisors:[], members:[] } } });
  api.replaceProposalMember.mockResolvedValue({ data:{} });
  api.removeRejectedProposalMember.mockResolvedValue({ data:{} });
  api.replaceRejectedSupervisor.mockResolvedValue({ data:{} });
  api.continueWithApprovedSupervisor.mockResolvedValue({ data:{} });
  api.reviseStudentProposal.mockResolvedValue({ data:{} });
});

describe('BrowseIdeas direct page contract', () => {
  it('shows loading state while ideas are pending', () => { api.browseIdeas.mockReturnValue(new Promise(()=>{})); render(<BrowseIdeas/>); expect(screen.getByText('جاري تحميل المشاريع…')).toBeTruthy(); });
  it('loads ideas and current ownership sources together', async () => { render(<BrowseIdeas/>); await screen.findByText('AI Tutor'); expect(api.browseIdeas).toHaveBeenCalledOnce(); expect(api.fetchMyIdeaApplication).toHaveBeenCalledOnce(); expect(api.fetchMyProposal).toHaveBeenCalledOnce(); expect(api.fetchMyBoard).toHaveBeenCalledOnce(); });
  it('renders page title', async () => { render(<BrowseIdeas/>); expect(await screen.findByRole('heading',{name:'تصفح أفكار المشاريع'})).toBeTruthy(); });
  it.each(['AI Tutor','Secure Portal'])('renders idea %s', async (title) => { render(<BrowseIdeas/>); expect(await screen.findByText(title)).toBeTruthy(); });
  it('renders supervisor name', async () => { render(<BrowseIdeas/>); expect(await screen.findByText('Dr Noor')).toBeTruthy(); });
  it('renders max team size', async () => { render(<BrowseIdeas/>); expect(await screen.findByText('Max 3')).toBeTruthy(); });
  it.each(['Python','React'])('renders required skill %s', async (skill) => { render(<BrowseIdeas/>); expect(await screen.findByText(skill)).toBeTruthy(); });
  it('renders project type label', async () => { render(<BrowseIdeas/>); expect(await screen.findByText('Graduation 1')).toBeTruthy(); });
  it('searches by title', async () => { render(<BrowseIdeas/>); await screen.findByText('AI Tutor'); fireEvent.change(screen.getByPlaceholderText('ابحث بالعنوان، الطبيب، أو المهارات…'),{target:{value:'Secure'}}); expect(screen.getByText('Secure Portal')).toBeTruthy(); expect(screen.queryByText('AI Tutor')).toBeNull(); });
  it('searches by doctor name', async () => { render(<BrowseIdeas/>); await screen.findByText('AI Tutor'); fireEvent.change(screen.getByPlaceholderText('ابحث بالعنوان، الطبيب، أو المهارات…'),{target:{value:'Noor'}}); expect(screen.getByText('AI Tutor')).toBeTruthy(); expect(screen.queryByText('Secure Portal')).toBeNull(); });
  it('searches by skill', async () => { render(<BrowseIdeas/>); await screen.findByText('AI Tutor'); fireEvent.change(screen.getByPlaceholderText('ابحث بالعنوان، الطبيب، أو المهارات…'),{target:{value:'Django'}}); expect(screen.getByText('Secure Portal')).toBeTruthy(); });
  it('filters by department', async () => { render(<BrowseIdeas/>); await screen.findByText('AI Tutor'); fireEvent.change(screen.getByRole('combobox'),{target:{value:'information_security'}}); expect(screen.getByText('Secure Portal')).toBeTruthy(); expect(screen.queryByText('AI Tutor')).toBeNull(); });
  it('shows empty state after unmatched filter', async () => { render(<BrowseIdeas/>); await screen.findByText('AI Tutor'); fireEvent.change(screen.getByPlaceholderText('ابحث بالعنوان، الطبيب، أو المهارات…'),{target:{value:'nothing'}}); expect(screen.getByText('لا توجد مشاريع')).toBeTruthy(); });
  it('shows load error when idea request fails', async () => { api.browseIdeas.mockRejectedValue(new Error('x')); render(<BrowseIdeas/>); expect(await screen.findByText('Failed to load ideas.')).toBeTruthy(); });
  it('blocks applying when student already owns a board', async () => { api.fetchMyBoard.mockResolvedValue({data:{has_project:true,board:{title:'Registered'}}}); render(<BrowseIdeas/>); expect(await screen.findByText('لديك مشروع مسجل بالفعل. لا يمكنك التقدم لفكرة أخرى.')).toBeTruthy(); expect(screen.getAllByRole('button',{name:/لديك مشروع بالفعل/}).length).toBeGreaterThan(0); });
  it('blocks a taken idea', async () => { api.browseIdeas.mockResolvedValue({data:[{...ideas[0],is_taken:true,registered_team:null}]}); render(<BrowseIdeas/>); expect(await screen.findByRole('button',{name:/غير متاح/})).toBeTruthy(); });
  it('opens application modal', async () => { await openIdeaApplication(); expect(screen.getByRole('dialog')).toBeTruthy(); expect(screen.getByText(/التقديم على: AI Tutor/)).toBeTruthy(); });
  it('loads department dynamic form for selected idea', async () => { await openIdeaApplication(); expect(api.fetchStudentForm).toHaveBeenCalledWith('artificial_intelligence','browse'); });
  it('starts application with team size one and justification', async () => { await openIdeaApplication(); expect(screen.getByLabelText(/حجم فريقك/).value).toBe('1'); expect(screen.getByText('Justification for team size')).toBeTruthy(); });
  it('team size two hides individual justification and creates teammate picker', async () => { await openIdeaApplication(); fireEvent.change(screen.getByLabelText(/حجم فريقك/),{target:{value:'2'}}); expect(screen.queryByText('Why are you working alone?')).toBeNull(); expect(screen.getByTestId('member-0')).toBeTruthy(); });
  it('renders dynamic form fields in modal', async () => { api.fetchStudentForm.mockResolvedValue({data:{id:7,title:'Extra Requirements',fields:[{id:5,label:'Portfolio',field_type:'text',required:true}]}}); render(<BrowseIdeas/>); fireEvent.click((await screen.findAllByRole('button',{name:'Apply for Project'}))[0]); expect(await screen.findByText('Extra Requirements')).toBeTruthy(); expect(screen.getByText('Portfolio')).toBeTruthy(); });
  it('submits application as FormData with selected project type', async () => { await openIdeaApplication(); fireEvent.change(screen.getByLabelText(/نوع المشروع/),{target:{value:'graduation_1'}}); fireEvent.change(screen.getByLabelText(/Justification for team size/),{target:{value:'  solo reason  '}}); fireEvent.click(screen.getByRole('button',{name:'تأكيد الطلب'})); await waitFor(()=>expect(api.applyOnIdea).toHaveBeenCalledOnce()); const [ideaId,fd]=api.applyOnIdea.mock.calls[0]; expect(ideaId).toBe(1); expect(fd.get('project_type')).toBe('graduation_1'); expect(fd.get('team_size_reason')).toBe('solo reason'); });
  it('shows backend application message', async () => { api.applyOnIdea.mockRejectedValue({response:{data:{message:'APPLICATION DENIED'}}}); await openIdeaApplication(); fireEvent.click(screen.getByRole('button',{name:'تأكيد الطلب'})); expect(await screen.findByText('APPLICATION DENIED')).toBeTruthy(); });
  it('closes application modal with cancel', async () => { await openIdeaApplication(); fireEvent.click(screen.getByRole('button',{name:'Cancel'})); expect(screen.queryByRole('dialog')).toBeNull(); });
});

async function openProposalDepartmentStep() {
  render(<ProposeIdea/>);
  await screen.findByRole('heading',{name:'مقترح مشروع'});
  fireEvent.change(screen.getByLabelText(/Project Title/),{target:{value:'Smart Campus'}});
  fireEvent.change(screen.getByLabelText(/Project Description/),{target:{value:'Long description'}});
  fireEvent.click(screen.getByRole('button',{name:'متابعة'}));
}

async function completeDepartmentStep() {
  await openProposalDepartmentStep();
  fireEvent.change(screen.getByLabelText(/Department/),{target:{value:'software_engineering'}});
  fireEvent.change(screen.getByLabelText(/Preferred Supervisor/),{target:{value:'1'}});
  fireEvent.change(screen.getByLabelText(/Project Type/),{target:{value:'graduation_1'}});
  await waitFor(()=>expect(api.fetchStudentForm).toHaveBeenCalledWith('software_engineering','propose'));
  await flushAsyncState();
}

describe('ProposeIdea direct page contract', () => {
  it('shows loading state while proposal sources are pending', () => { api.fetchMyProposal.mockReturnValue(new Promise(()=>{})); api.fetchDoctorsList.mockReturnValue(new Promise(()=>{})); render(<ProposeIdea/>); expect(screen.getByText('Loading proposal data…')).toBeTruthy(); });
  it('loads existing proposal and doctors together', async () => { render(<ProposeIdea/>); await screen.findByRole('heading',{name:'مقترح مشروع'}); expect(api.fetchMyProposal).toHaveBeenCalledOnce(); expect(api.fetchDoctorsList).toHaveBeenCalledOnce(); });
  it('renders first idea step', async () => { render(<ProposeIdea/>); expect(await screen.findByRole('heading',{name:'فكرة مشروع'})).toBeTruthy(); });
  it('starts continue disabled', async () => { render(<ProposeIdea/>); await screen.findByRole('heading',{name:'فكرة مشروع'}); expect(screen.getByRole('button',{name:'متابعة'}).disabled).toBe(true); });
  it('enables continue after title and description', async () => { render(<ProposeIdea/>); await screen.findByRole('heading',{name:'فكرة مشروع'}); fireEvent.change(screen.getByLabelText(/Project Title/),{target:{value:'Smart'}}); fireEvent.change(screen.getByLabelText(/Project Description/),{target:{value:'Desc'}}); expect(screen.getByRole('button',{name:'متابعة'}).disabled).toBe(false); });
  it('moves to department and supervisor step', async () => { await openProposalDepartmentStep(); expect(screen.getByRole('heading',{name:'القسم والمشرف'})).toBeTruthy(); });
  it.each(['برمجيات','ذكاء اصطناعي','أمن سيبراني','اتصالات','Control & Robotics'])('offers department %s', async (label) => { await openProposalDepartmentStep(); expect(screen.getByRole('option',{name:label})).toBeTruthy(); });
  it.each(['Dr One (software engineering)','Dr Two (artificial intelligence)'])('offers supervisor %s', async (label) => { await openProposalDepartmentStep(); const primary = screen.getByLabelText(/Preferred Supervisor/); expect(within(primary).getByRole('option',{name:label})).toBeTruthy(); });
  it('co-supervisor starts disabled', async () => { await openProposalDepartmentStep(); expect(screen.getByLabelText(/المشرف الثاني/).disabled).toBe(true); });
  it('selecting primary supervisor enables co-supervisor', async () => { await openProposalDepartmentStep(); fireEvent.change(screen.getByLabelText(/Preferred Supervisor/),{target:{value:'1'}}); expect(screen.getByLabelText(/المشرف الثاني/).disabled).toBe(false); });
  it('co-supervisor list excludes selected primary', async () => { await openProposalDepartmentStep(); fireEvent.change(screen.getByLabelText(/Preferred Supervisor/),{target:{value:'1'}}); expect(screen.queryByRole('option',{name:/Dr One/})).not.toBeNull(); const co=screen.getByLabelText(/المشرف الثاني/); expect(Array.from(co.options).some(o=>o.textContent.includes('Dr One'))).toBe(false); expect(Array.from(co.options).some(o=>o.textContent.includes('Dr Two'))).toBe(true); });
  it.each(['Seasonal','Graduation 1','Graduation 2'])('offers project type %s', async (label) => { await openProposalDepartmentStep(); expect(screen.getByRole('option',{name:label})).toBeTruthy(); });
  it('loads department dynamic form when department changes', async () => { await openProposalDepartmentStep(); fireEvent.change(screen.getByLabelText(/Department/),{target:{value:'software_engineering'}}); await waitFor(()=>expect(api.fetchStudentForm).toHaveBeenCalledWith('software_engineering','propose')); });
  it('moves to team step after required department choices', async () => { await completeDepartmentStep(); fireEvent.click(screen.getByRole('button',{name:'متابعة'})); expect(screen.getByRole('heading',{name:'إعداد الفريق'})).toBeTruthy(); });
  it('defaults team size to two', async () => { await completeDepartmentStep(); fireEvent.click(screen.getByRole('button',{name:'متابعة'})); expect(screen.getByText('2').closest('button').className).toContain('border-[var(--primary)]'); });
  it('default team size renders one teammate picker', async () => { await completeDepartmentStep(); fireEvent.click(screen.getByRole('button',{name:'متابعة'})); expect(screen.getByTestId('p-member-0')).toBeTruthy(); });
  it('team size one requires justification and removes teammate picker', async () => { await completeDepartmentStep(); fireEvent.click(screen.getByRole('button',{name:'متابعة'})); fireEvent.click(screen.getByText('1').closest('button')); expect(screen.getByText('Justification for team size')).toBeTruthy(); expect(screen.queryByTestId('p-member-0')).toBeNull(); });
  it('previous button returns to department step', async () => { await completeDepartmentStep(); fireEvent.click(screen.getByRole('button',{name:'متابعة'})); fireEvent.click(screen.getByRole('button',{name:'السابق'})); expect(screen.getByRole('heading',{name:'القسم والمشرف'})).toBeTruthy(); });
  it('renders dynamic field step when department form exists', async () => { api.fetchStudentForm.mockResolvedValue({data:{id:8,title:'Extra Dept',description:'Extra',fields:[{id:4,label:'Portfolio',field_type:'text',required:true}]}}); await completeDepartmentStep(); await waitFor(()=>expect(api.fetchStudentForm).toHaveBeenCalled()); fireEvent.click(screen.getByRole('button',{name:'متابعة'})); fireEvent.click(screen.getByRole('button',{name:'متابعة'})); expect(await screen.findByRole('heading',{name:'Extra Dept'})).toBeTruthy(); expect(screen.getByText('Portfolio')).toBeTruthy(); });
  it('submits normalized proposal payload without dynamic form', async () => { await completeDepartmentStep(); fireEvent.click(screen.getByRole('button',{name:'متابعة'})); fireEvent.click(screen.getByRole('button',{name:'إرسال المقترح'})); await waitFor(()=>expect(api.submitStudentProposal).toHaveBeenCalledOnce()); expect(api.submitStudentProposal.mock.calls[0][0]).toMatchObject({title:'Smart Campus',description:'Long description',department:'software_engineering',supervisor:1,supervisor_ids:[1],team_size:2,project_type:'graduation_1',form_id:null}); });
  it('submits selected co-supervisor as numeric id', async () => { await openProposalDepartmentStep(); fireEvent.change(screen.getByLabelText(/Department/),{target:{value:'software_engineering'}}); fireEvent.change(screen.getByLabelText(/Preferred Supervisor/),{target:{value:'1'}}); fireEvent.change(screen.getByLabelText(/المشرف الثاني/),{target:{value:'2'}}); fireEvent.change(screen.getByLabelText(/Project Type/),{target:{value:'graduation_1'}}); await waitFor(()=>expect(api.fetchStudentForm).toHaveBeenCalledWith('software_engineering','propose')); await flushAsyncState(); fireEvent.click(screen.getByRole('button',{name:'متابعة'})); fireEvent.click(screen.getByRole('button',{name:'إرسال المقترح'})); await waitFor(()=>expect(api.submitStudentProposal).toHaveBeenCalled()); expect(api.submitStudentProposal.mock.calls[0][0].supervisor_ids).toEqual([1,2]); });
  it('shows backend proposal error', async () => { api.submitStudentProposal.mockRejectedValue({response:{data:{message:'PROPOSAL DENIED'}}}); await completeDepartmentStep(); fireEvent.click(screen.getByRole('button',{name:'متابعة'})); fireEvent.click(screen.getByRole('button',{name:'إرسال المقترح'})); expect(await screen.findByText('PROPOSAL DENIED')).toBeTruthy(); });
  it('shows supervisor-load error but still renders proposal form', async () => { api.fetchDoctorsList.mockRejectedValue(new Error('x')); render(<ProposeIdea/>); expect(await screen.findByText('Could not load supervisors list. Please refresh the page.')).toBeTruthy(); });
  it('renders existing proposal status page instead of new form', async () => { api.fetchMyProposal.mockResolvedValue({data:{id:3,title:'Existing Idea',description:'D',status:'pending_hod',department:'software_engineering',team_size:2,team_size_reason:'',supervisors:[{id:1,name:'Dr One',status:'approved',is_primary:true}],members:[]}}); render(<ProposeIdea/>); expect(await screen.findByRole('heading',{name:'مقترحك'})).toBeTruthy(); expect(screen.getByText('Existing Idea')).toBeTruthy(); expect(screen.queryByRole('heading',{name:'مقترح مشروع'})).toBeNull(); });
  it('shows no-doctors warning when list is empty', async () => { api.fetchDoctorsList.mockResolvedValue({data:[]}); await openProposalDepartmentStep(); expect(screen.getByText(/No doctors found in the system/)).toBeTruthy(); expect(screen.getByLabelText(/Preferred Supervisor/).disabled).toBe(true); });
});
