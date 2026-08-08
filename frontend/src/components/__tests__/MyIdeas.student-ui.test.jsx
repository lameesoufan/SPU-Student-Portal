import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ fetchMyIdeas: vi.fn() }));
vi.mock('../../api.jsx', () => ({ ...api }));
import MyIdeas from '../MyIdeas.jsx';

const ideas = [
  { id:1, title:'Pending AI', description:'Pending description', department:'artificial_intelligence', max_team_size:2, project_type:'graduation_1', required_skills:'Python', status:'pending_review', created_at:'2026-08-01T00:00:00Z' },
  { id:2, title:'Approved Security', description:'Approved description', department:'information_security', max_team_size:3, project_type:'graduation_2', required_skills:'React', status:'approved', created_at:'2026-08-02T00:00:00Z' },
  { id:3, title:'Rejected Robot', description:'Rejected description', department:'control_robotics', max_team_size:2, project_type:'seasonal', status:'rejected', rejection_reason:'Scope too large', created_at:'2026-08-03T00:00:00Z' },
  { id:4, title:'Unknown State', description:'Fallback meta', department:'software_engineering', max_team_size:3, project_type:null, status:'unexpected', created_at:'2026-08-04T00:00:00Z' },
];

beforeEach(() => { vi.clearAllMocks(); api.fetchMyIdeas.mockResolvedValue({ data: ideas }); });

describe('MyIdeas student project contract', () => {
  it('renders the page heading', async()=>{ render(<MyIdeas/>); expect(await screen.findByRole('heading',{name:'أفكار مشاريعي'})).toBeTruthy(); });
  it('fetches ideas on mount', async()=>{ render(<MyIdeas/>); await screen.findByText('Pending AI'); expect(api.fetchMyIdeas).toHaveBeenCalledOnce(); });
  it('shows loading copy while pending', ()=>{ api.fetchMyIdeas.mockReturnValue(new Promise(()=>{})); render(<MyIdeas/>); expect(screen.getByText('جاري تحميل الأفكار...')).toBeTruthy(); });
  it('shows generic load failure', async()=>{ api.fetchMyIdeas.mockRejectedValue(new Error('x')); render(<MyIdeas/>); expect((await screen.findByRole('alert')).textContent).toContain('Failed to load ideas. Please try again.'); });
  it('calls back navigation', async()=>{ const onBack=vi.fn(); render(<MyIdeas onBack={onBack}/>); fireEvent.click(await screen.findByRole('button',{name:/العودة إلى لوحة التحكم/})); expect(onBack).toHaveBeenCalledOnce(); });
  it('calls submit-new from header', async()=>{ const fn=vi.fn(); render(<MyIdeas onSubmitNew={fn}/>); fireEvent.click(await screen.findByRole('button',{name:'+ Submit New Idea'})); expect(fn).toHaveBeenCalledOnce(); });
  it('shows empty state', async()=>{ api.fetchMyIdeas.mockResolvedValue({data:[]}); render(<MyIdeas/>); expect(await screen.findByText('لا توجد أفكار بعد')).toBeTruthy(); });
  it('calls submit-new from empty state', async()=>{ api.fetchMyIdeas.mockResolvedValue({data:[]}); const fn=vi.fn(); render(<MyIdeas onSubmitNew={fn}/>); fireEvent.click(await screen.findByRole('button',{name:'قدم فكرتك الأولى'})); expect(fn).toHaveBeenCalledOnce(); });
  it('shows empty help text', async()=>{ api.fetchMyIdeas.mockResolvedValue({data:[]}); render(<MyIdeas/>); expect(await screen.findByText(/You haven't submitted any project ideas yet/)).toBeTruthy(); });
  it.each(['Pending AI','Approved Security','Rejected Robot','Unknown State'])('renders idea title %s', async(title)=>{ render(<MyIdeas/>); expect(await screen.findByText(title)).toBeTruthy(); });
  it.each(['Pending description','Approved description','Rejected description','Fallback meta'])('renders description %s', async(text)=>{ render(<MyIdeas/>); expect(await screen.findByText(text)).toBeTruthy(); });
  it.each([['artificial intelligence'],['information security'],['control robotics'],['software engineering']])('normalizes department %s', async(label)=>{ render(<MyIdeas/>); expect(await screen.findByText(label)).toBeTruthy(); });
  it('shows both team-size variants', async()=>{ render(<MyIdeas/>); await screen.findByText('Pending AI'); expect(screen.getAllByText('2 students').length).toBeGreaterThanOrEqual(2); expect(screen.getAllByText('3 students').length).toBeGreaterThanOrEqual(2); });
  it.each(['قيد المراجعة','مقبول','مرفوض'])('renders status label %s', async(label)=>{ render(<MyIdeas/>); expect((await screen.findAllByText(label)).length).toBeGreaterThan(0); });
  it('falls back unknown status to pending label', async()=>{ render(<MyIdeas/>); await screen.findByText('Unknown State'); expect(screen.getAllByText('قيد المراجعة').length).toBeGreaterThanOrEqual(2); });
  it('shows rejection reason only for rejected idea', async()=>{ render(<MyIdeas/>); expect(await screen.findByText('Scope too large')).toBeTruthy(); expect(screen.getAllByText('Rejection reason:')).toHaveLength(1); });
  it.each(['Python','React'])('shows required skill %s', async(skill)=>{ render(<MyIdeas/>); expect(await screen.findByText(skill)).toBeTruthy(); });
  it('omits missing required skills badge', async()=>{ render(<MyIdeas/>); await screen.findByText('Rejected Robot'); expect(screen.queryByText('undefined')).toBeNull(); });
  it.each(['Graduation 1','Graduation 2','Seasonal'])('shows project type %s', async(label)=>{ render(<MyIdeas/>); expect(await screen.findByText(label)).toBeTruthy(); });
  it('does not render a project-type badge when absent', async()=>{ render(<MyIdeas/>); await screen.findByText('Unknown State'); expect(document.body.textContent.includes('null')).toBe(false); });
  it('shows one card for each returned idea', async()=>{ render(<MyIdeas/>); await screen.findByText('Pending AI'); expect(['Pending AI','Approved Security','Rejected Robot','Unknown State'].every(t=>screen.getByText(t))).toBe(true); });
  it('does not show empty state when ideas exist', async()=>{ render(<MyIdeas/>); await screen.findByText('Pending AI'); expect(screen.queryByText('لا توجد أفكار بعد')).toBeNull(); });
  it('does not show error after successful load', async()=>{ render(<MyIdeas/>); await screen.findByText('Pending AI'); expect(screen.queryByRole('alert')).toBeNull(); });
});
