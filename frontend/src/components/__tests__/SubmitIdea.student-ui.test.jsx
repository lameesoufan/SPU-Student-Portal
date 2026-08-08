import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ submitProjectIdea:vi.fn() }));
vi.mock('../../api.jsx', () => ({ ...api }));
import SubmitIdea from '../SubmitIdea.jsx';

beforeEach(()=>{ vi.clearAllMocks(); api.submitProjectIdea.mockResolvedValue({data:{id:1}}); });

function fields(){ return {
 title:screen.getByLabelText(/Title/), description:screen.getByLabelText(/Description/), department:screen.getByLabelText(/Department/), team:screen.getByLabelText(/Max Team Size/), type:screen.getByLabelText(/Project Type/), skills:screen.getByLabelText(/Required Skills/)
}; }
function fillValid(){ const f=fields(); fireEvent.change(f.title,{target:{value:' AI Portal '}}); fireEvent.change(f.description,{target:{value:'Secure project'}}); fireEvent.change(f.department,{target:{value:'software_engineering'}}); fireEvent.change(f.team,{target:{value:'3'}}); fireEvent.change(f.type,{target:{value:'graduation_1'}}); fireEvent.change(f.skills,{target:{value:'React, Python'}}); return f; }
async function submitAndFinish(){ fireEvent.click(screen.getByRole('button',{name:/Submit Idea/})); await waitFor(()=>expect(api.submitProjectIdea).toHaveBeenCalled()); await screen.findByText('تم إرسال الفكرة بنجاح'); }

describe('SubmitIdea student proposal contract',()=>{
  it('renders heading',()=>{ render(<SubmitIdea/>); expect(screen.getByRole('heading',{name:'إرسال فكرة مشروع جديدة'})).toBeTruthy(); });
  it('renders explanatory banner',()=>{ render(<SubmitIdea/>); expect(screen.getByText(/سيتم حفظ فكرتك كـ/)).toBeTruthy(); });
  it('calls back from header',()=>{ const fn=vi.fn(); render(<SubmitIdea onBack={fn}/>); fireEvent.click(screen.getByRole('button',{name:'Back'})); expect(fn).toHaveBeenCalledOnce(); });
  it.each([['Title','text'],['Description','textarea'],['Department','select'],['Max Team Size','select'],['Project Type','select'],['Required Skills','text']])('renders %s field', (label,kind)=>{ render(<SubmitIdea/>); const el=screen.getByLabelText(new RegExp(label)); expect(el).toBeTruthy(); if(kind==='textarea') expect(el.tagName).toBe('TEXTAREA'); if(kind==='select') expect(el.tagName).toBe('SELECT'); });
  it.each([['software_engineering','برمجيات'],['artificial_intelligence','ذكاء اصطناعي'],['information_security','أمن سيبراني'],['communications','اتصالات'],['control_robotics','Control & Robotics']])('offers department %s',(_,label)=>{ render(<SubmitIdea/>); expect(screen.getByRole('option',{name:label})).toBeTruthy(); });
  it.each([['2','2 Students'],['3','3 Students']])('offers team size %s',(_,label)=>{ render(<SubmitIdea/>); expect(screen.getByRole('option',{name:label})).toBeTruthy(); });
  it.each(['Seasonal','Graduation 1','Graduation 2'])('offers project type %s',(label)=>{ render(<SubmitIdea/>); expect(screen.getByRole('option',{name:label})).toBeTruthy(); });
  it('defaults team size to two',()=>{ render(<SubmitIdea/>); expect(fields().team.value).toBe('2'); });
  it('starts other values empty',()=>{ render(<SubmitIdea/>); const f=fields(); expect(f.title.value).toBe(''); expect(f.description.value).toBe(''); expect(f.department.value).toBe(''); expect(f.type.value).toBe(''); expect(f.skills.value).toBe(''); });
  it.each([['title','Project X'],['description','Description X'],['department','communications'],['team','3'],['type','graduation_2'],['skills','Node.js']])('updates %s field',(key,value)=>{ render(<SubmitIdea/>); const f=fields(); fireEvent.change(f[key],{target:{value}}); expect(f[key].value).toBe(value); });
  it('submits complete payload with numeric team size',async()=>{ render(<SubmitIdea/>); fillValid(); fireEvent.click(screen.getByRole('button',{name:/Submit Idea/})); await waitFor(()=>expect(api.submitProjectIdea).toHaveBeenCalledOnce()); expect(api.submitProjectIdea).toHaveBeenCalledWith({title:' AI Portal ',description:'Secure project',department:'software_engineering',required_skills:'React, Python',max_team_size:3,project_type:'graduation_1'}); });
  it('disables submit while request is pending',async()=>{ api.submitProjectIdea.mockReturnValue(new Promise(()=>{})); render(<SubmitIdea/>); fillValid(); const btn=screen.getByRole('button',{name:/Submit Idea/}); fireEvent.click(btn); await waitFor(()=>expect(btn.disabled).toBe(true)); expect(screen.getByText('Submitting…')).toBeTruthy(); });
  it('prevents a second submit while loading',async()=>{ api.submitProjectIdea.mockReturnValue(new Promise(()=>{})); render(<SubmitIdea/>); fillValid(); const form=screen.getByRole('button',{name:/Submit Idea/}).closest('form'); fireEvent.submit(form); fireEvent.submit(form); await waitFor(()=>expect(api.submitProjectIdea).toHaveBeenCalledTimes(1)); });
  it('shows success after request and anti-duplicate delay',async()=>{ render(<SubmitIdea/>); fillValid(); await submitAndFinish(); expect(screen.getByText('تم إرسال الفكرة بنجاح')).toBeTruthy(); });
  it('shows pending-review badge after success',async()=>{ render(<SubmitIdea/>); fillValid(); await submitAndFinish(); expect(screen.getByText('Pending Review')).toBeTruthy(); });
  it('shows success guidance after submit',async()=>{ render(<SubmitIdea/>); fillValid(); await submitAndFinish(); expect(screen.getByText(/تم استلام فكرة مشروعك/)).toBeTruthy(); });
  it('returns to form with submit-another action',async()=>{ render(<SubmitIdea/>); fillValid(); await submitAndFinish(); fireEvent.click(screen.getByRole('button',{name:'Submit Another Idea'})); expect(screen.getByLabelText(/Title/).value).toBe(''); });
  it('clears all form values after successful submit',async()=>{ render(<SubmitIdea/>); fillValid(); await submitAndFinish(); fireEvent.click(screen.getByRole('button',{name:'Submit Another Idea'})); const f=fields(); expect(f.title.value).toBe(''); expect(f.description.value).toBe(''); expect(f.department.value).toBe(''); expect(f.skills.value).toBe(''); expect(f.team.value).toBe('2'); expect(f.type.value).toBe(''); });
  it('calls back from success card',async()=>{ const fn=vi.fn(); render(<SubmitIdea onBack={fn}/>); fillValid(); await submitAndFinish(); fireEvent.click(screen.getByRole('button',{name:'View My Ideas'})); expect(fn).toHaveBeenCalledOnce(); });
  it('flattens backend field errors',async()=>{ api.submitProjectIdea.mockRejectedValue({response:{data:{title:['Required'],department:['Invalid']}}}); render(<SubmitIdea/>); fireEvent.click(screen.getByRole('button',{name:/Submit Idea/})); expect((await screen.findByRole('alert')).textContent).toContain('Required Invalid'); });
  it('flattens string backend values',async()=>{ api.submitProjectIdea.mockRejectedValue({response:{data:{error:'Blocked'}}}); render(<SubmitIdea/>); fireEvent.click(screen.getByRole('button',{name:/Submit Idea/})); expect((await screen.findByRole('alert')).textContent).toContain('Blocked'); });
  it('uses generic failure without response object',async()=>{ api.submitProjectIdea.mockRejectedValue(new Error('network')); render(<SubmitIdea/>); fireEvent.click(screen.getByRole('button',{name:/Submit Idea/})); expect((await screen.findByRole('alert')).textContent).toContain('Something went wrong. Please try again.'); });
  it('reenables submit after failure',async()=>{ api.submitProjectIdea.mockRejectedValue(new Error('network')); render(<SubmitIdea/>); const btn=screen.getByRole('button',{name:/Submit Idea/}); fireEvent.click(btn); await screen.findByRole('alert'); expect(btn.disabled).toBe(false); });
  it('clears previous error on resubmit',async()=>{ api.submitProjectIdea.mockRejectedValueOnce(new Error('x')).mockResolvedValue({data:{}}); render(<SubmitIdea/>); const btn=screen.getByRole('button',{name:/Submit Idea/}); fireEvent.click(btn); await screen.findByRole('alert'); fireEvent.click(btn); await waitFor(()=>expect(screen.queryByRole('alert')).toBeNull()); });
  it('form bypasses native browser validation intentionally',()=>{ render(<SubmitIdea/>); expect(screen.getByRole('button',{name:/Submit Idea/}).closest('form').noValidate).toBe(true); });
  it.each(['e.g. AI-based Attendance System','صف أهداف المشروع ونطاقه...','مثال: Python، تعلم الآلة، React'])('shows placeholder %s',(text)=>{ render(<SubmitIdea/>); expect(screen.getByPlaceholderText(text)).toBeTruthy(); });
});
