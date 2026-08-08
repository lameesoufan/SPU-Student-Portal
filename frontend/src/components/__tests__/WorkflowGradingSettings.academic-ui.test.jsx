import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ fetchGradingModes:vi.fn(), setGradingMode:vi.fn(), fetchWorkflowTemplates:vi.fn(), fetchAvailableProjects:vi.fn(), applyWorkflowBulk:vi.fn() }));
vi.mock('../../api.jsx', () => ({ ...api }));
import CollectiveGradingSettings from '../CollectiveGradingSettings.jsx';
import ApplyWorkflow from '../ApplyWorkflow.jsx';

const committees = [
  { committee_id:11, committee_type_ar:'سيمينار 1', department_ar:'برمجيات', project_type_ar:'تطبيقي', semester:'S1', collective:false },
  { committee_id:12, committee_type_ar:'مناقشة نهائية', department_ar:'ذكاء', project_type_ar:'بحثي', semester:'S2', collective:true },
];
const templates = [
  { id:1, name:'Active Flow', status:'active', description:'A flow', stages:[{name:'Start',is_required:true,trigger_type:'project_start'},{name:'Review',is_required:false,trigger_type:'manual'}] },
  { id:2, name:'Draft Flow', status:'draft', stages:[] },
];
const projects = [
  { id:101, title:'Project Alpha', has_own_workflow:false, has_workflow:false, team_members:[{name:'Ali'},{name:'Sara'}] },
  { id:102, title:'Project Beta', has_own_workflow:true, has_workflow:true, workflow_count:1, team_members:[] },
  { id:103, title:'Project Gamma', has_own_workflow:false, has_workflow:true, workflow_count:2, team_members:[{name:'Omar'}] },
];

beforeEach(()=>{ vi.clearAllMocks(); api.fetchGradingModes.mockResolvedValue({data:{committees}}); api.setGradingMode.mockImplementation(async (id,collective)=>({data:{collective,message:`MODE-${id}-${collective}`}})); api.fetchWorkflowTemplates.mockResolvedValue({data:templates}); api.fetchAvailableProjects.mockResolvedValue({data:projects}); api.applyWorkflowBulk.mockResolvedValue({data:{applied_count:2,skipped_count:1,error_count:0}}); });

describe('CollectiveGradingSettings contract',()=>{
  it('shows loading state',()=>{ api.fetchGradingModes.mockReturnValue(new Promise(()=>{})); render(<CollectiveGradingSettings/>); expect(screen.getByText('جاري تحميل إعدادات التقييم...')).toBeTruthy(); });
  it('loads grading modes once',async()=>{ render(<CollectiveGradingSettings/>); await screen.findByText(/سيمينار 1/); expect(api.fetchGradingModes).toHaveBeenCalledOnce(); });
  it('shows committee count badge',async()=>{ render(<CollectiveGradingSettings/>); expect(await screen.findByText('2 لجنة')).toBeTruthy(); });
  it('shows individual and collective states',async()=>{ render(<CollectiveGradingSettings/>); expect(await screen.findByText('تقييم فردي')).toBeTruthy(); expect(screen.getByText('تقييم جماعي')).toBeTruthy(); });
  it('switch aria state matches backend mode',async()=>{ render(<CollectiveGradingSettings/>); const sw=await screen.findAllByRole('switch'); expect(sw[0].getAttribute('aria-checked')).toBe('false'); expect(sw[1].getAttribute('aria-checked')).toBe('true'); });
  it('enables collective mode with inverse payload',async()=>{ render(<CollectiveGradingSettings/>); const sw=await screen.findAllByRole('switch'); fireEvent.click(sw[0]); await waitFor(()=>expect(api.setGradingMode).toHaveBeenCalledWith(11,true)); expect(await screen.findByText('MODE-11-true')).toBeTruthy(); });
  it('disables collective mode with inverse payload',async()=>{ render(<CollectiveGradingSettings/>); const sw=await screen.findAllByRole('switch'); fireEvent.click(sw[1]); await waitFor(()=>expect(api.setGradingMode).toHaveBeenCalledWith(12,false)); });
  it('updates switch state from server response',async()=>{ render(<CollectiveGradingSettings/>); const sw=await screen.findAllByRole('switch'); fireEvent.click(sw[0]); await waitFor(()=>expect(sw[0].getAttribute('aria-checked')).toBe('true')); });
  it('shows backend toggle error without mutating mode',async()=>{ api.setGradingMode.mockRejectedValue({response:{data:{detail:'DENIED'}}}); render(<CollectiveGradingSettings/>); const sw=await screen.findAllByRole('switch'); fireEvent.click(sw[0]); expect(await screen.findByText('DENIED')).toBeTruthy(); expect(sw[0].getAttribute('aria-checked')).toBe('false'); });
  it('shows loading error',async()=>{ api.fetchGradingModes.mockRejectedValue({response:{data:{detail:'LOAD FAIL'}}}); render(<CollectiveGradingSettings/>); expect(await screen.findByText('LOAD FAIL')).toBeTruthy(); });
  it('shows empty state when no committees exist',async()=>{ api.fetchGradingModes.mockResolvedValue({data:{committees:[]}}); render(<CollectiveGradingSettings/>); expect(await screen.findByText('لا توجد لجان متاحة')).toBeTruthy(); });
  it('falls back when semester is absent',async()=>{ api.fetchGradingModes.mockResolvedValue({data:{committees:[{...committees[0],semester:''}]}}); render(<CollectiveGradingSettings/>); expect(await screen.findByText('الفصل غير محدد')).toBeTruthy(); });
});

function projectCheckbox(title){ return screen.getByText(title).closest('label').querySelector('input[type="checkbox"]'); }

describe('ApplyWorkflow page contract',()=>{
  it('shows loading while both APIs resolve',()=>{ api.fetchWorkflowTemplates.mockReturnValue(new Promise(()=>{})); api.fetchAvailableProjects.mockReturnValue(new Promise(()=>{})); render(<ApplyWorkflow/>); expect(screen.getByText('Loading workflow configuration...')).toBeTruthy(); });
  it('loads templates and projects in parallel',async()=>{ render(<ApplyWorkflow/>); await screen.findByText('Assign Workflow'); expect(api.fetchWorkflowTemplates).toHaveBeenCalledOnce(); expect(api.fetchAvailableProjects).toHaveBeenCalledOnce(); });
  it('shows only active templates',async()=>{ render(<ApplyWorkflow/>); await screen.findByText('Assign Workflow'); expect(screen.getByText(/Active Flow \(2 stages\)/)).toBeTruthy(); expect(screen.queryByText(/Draft Flow/)).toBeNull(); });
  it.each(['Project Alpha','Project Beta','Project Gamma'])('renders project %s',async(title)=>{ render(<ApplyWorkflow/>); expect(await screen.findByText(title)).toBeTruthy(); });
  it('disables already-owned project',async()=>{ render(<ApplyWorkflow/>); await screen.findByText('Project Beta'); expect(projectCheckbox('Project Beta').disabled).toBe(true); });
  it('keeps available project selectable',async()=>{ render(<ApplyWorkflow/>); await screen.findByText('Project Alpha'); expect(projectCheckbox('Project Alpha').disabled).toBe(false); });
  it('shows own-workflow explanation',async()=>{ render(<ApplyWorkflow/>); expect(await screen.findByText('سبق أن أسندت سير عمل لهذا المشروع')).toBeTruthy(); });
  it('shows foreign workflow explanation',async()=>{ render(<ApplyWorkflow/>); expect(await screen.findByText(/يوجد 2 سير عمل من جهة أخرى/)).toBeTruthy(); });
  it('apply button starts disabled',async()=>{ render(<ApplyWorkflow/>); await screen.findByText('Assign Workflow'); expect(screen.getByRole('button',{name:/إسناد إلى 0 مشروع/}).disabled).toBe(true); });
  it('selects one project',async()=>{ render(<ApplyWorkflow/>); await screen.findByText('Project Alpha'); fireEvent.click(projectCheckbox('Project Alpha')); expect(screen.getByText('تم اختيار 1')).toBeTruthy(); });
  it('select all excludes projects already owned',async()=>{ render(<ApplyWorkflow/>); await screen.findByText('Project Alpha'); fireEvent.click(screen.getByRole('button',{name:/اختيار كل المشاريع/})); expect(projectCheckbox('Project Alpha').checked).toBe(true); expect(projectCheckbox('Project Gamma').checked).toBe(true); expect(projectCheckbox('Project Beta').checked).toBe(false); });
  it('select all toggles back to none',async()=>{ render(<ApplyWorkflow/>); await screen.findByText('Project Alpha'); fireEvent.click(screen.getByRole('button',{name:/اختيار كل المشاريع/})); fireEvent.click(screen.getByRole('button',{name:/إلغاء اختيار الكل/})); expect(projectCheckbox('Project Alpha').checked).toBe(false); });
  it('previews selected template',async()=>{ render(<ApplyWorkflow/>); await screen.findByText('Assign Workflow'); fireEvent.change(screen.getByRole('combobox'),{target:{value:'1'}}); expect(screen.getAllByText('Active Flow').length).toBeGreaterThan(0); expect(screen.getByText('A flow')).toBeTruthy(); expect(screen.getAllByText('Start').length).toBeGreaterThan(0); });
  it('previews one selected project team members',async()=>{ render(<ApplyWorkflow/>); await screen.findByText('Project Alpha'); fireEvent.click(projectCheckbox('Project Alpha')); expect(screen.getByText('Ali, Sara')).toBeTruthy(); });
  it('enables apply after template and project selection',async()=>{ render(<ApplyWorkflow/>); await screen.findByText('Project Alpha'); fireEvent.change(screen.getByRole('combobox'),{target:{value:'1'}}); fireEvent.click(projectCheckbox('Project Alpha')); expect(screen.getByRole('button',{name:/إسناد إلى 1 مشروع/}).disabled).toBe(false); });
  it('sends numeric template and selected project ids',async()=>{ render(<ApplyWorkflow/>); await screen.findByText('Project Alpha'); fireEvent.change(screen.getByRole('combobox'),{target:{value:'1'}}); fireEvent.click(projectCheckbox('Project Alpha')); fireEvent.click(screen.getByRole('button',{name:/إسناد إلى 1 مشروع/})); await waitFor(()=>expect(api.applyWorkflowBulk).toHaveBeenCalledWith({template_id:1,project_ids:[101],replace_existing:false})); });
  it('shows applied/skipped success summary',async()=>{ render(<ApplyWorkflow/>); await screen.findByText('Project Alpha'); fireEvent.change(screen.getByRole('combobox'),{target:{value:'1'}}); fireEvent.click(projectCheckbox('Project Alpha')); fireEvent.click(screen.getByRole('button',{name:/إسناد إلى 1 مشروع/})); expect(await screen.findByText(/تم إسناد سير العمل إلى 2 مشروع، وتم تجاوز 1/)).toBeTruthy(); });
  it('reloads both lists after successful apply',async()=>{ render(<ApplyWorkflow/>); await screen.findByText('Project Alpha'); fireEvent.change(screen.getByRole('combobox'),{target:{value:'1'}}); fireEvent.click(projectCheckbox('Project Alpha')); fireEvent.click(screen.getByRole('button',{name:/إسناد إلى 1 مشروع/})); await waitFor(()=>expect(api.fetchWorkflowTemplates).toHaveBeenCalledTimes(2)); expect(api.fetchAvailableProjects).toHaveBeenCalledTimes(2); });
  it('uses backend apply error',async()=>{ api.applyWorkflowBulk.mockRejectedValue({response:{data:{error:'CANNOT APPLY'}}}); render(<ApplyWorkflow/>); await screen.findByText('Project Alpha'); fireEvent.change(screen.getByRole('combobox'),{target:{value:'1'}}); fireEvent.click(projectCheckbox('Project Alpha')); fireEvent.click(screen.getByRole('button',{name:/إسناد إلى 1 مشروع/})); expect(await screen.findByText('CANNOT APPLY')).toBeTruthy(); });
  it('shows load error if source APIs fail',async()=>{ api.fetchWorkflowTemplates.mockRejectedValue(new Error('x')); render(<ApplyWorkflow/>); expect(await screen.findByText('Failed to load workflow data. Refresh the page or try again later.')).toBeTruthy(); });
  it('calls back button',async()=>{ const onBack=vi.fn(); render(<ApplyWorkflow onBack={onBack}/>); await screen.findByText('Assign Workflow'); fireEvent.click(screen.getByRole('button',{name:/Back/})); expect(onBack).toHaveBeenCalledOnce(); });
});
