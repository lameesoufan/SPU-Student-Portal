import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ searchStudents:vi.fn() }));
vi.mock('../../api.jsx', () => ({ ...api }));
import StudentSearch from '../StudentSearch.jsx';

const available={username:'s100',name:'Ali Student',display:'Ali Student (s100)',available:true,has_registered_project:false};
const blocked={username:'s200',name:'Blocked Student',display:'Blocked Student (s200)',available:false,unavailable_reason:'Already assigned'};
const registered={username:'s300',name:'Registered Student',display:'Registered Student (s300)',available:true,has_registered_project:true};

beforeEach(()=>{ vi.clearAllMocks(); vi.useFakeTimers(); api.searchStudents.mockResolvedValue({data:[available,blocked,registered]}); });
afterEach(()=>vi.useRealTimers());
async function search(q='Ali'){ fireEvent.change(screen.getByRole('combobox'),{target:{value:q}}); await act(async()=>{ await vi.advanceTimersByTimeAsync(300); await Promise.resolve(); }); expect(api.searchStudents).toHaveBeenCalled(); }

describe('StudentSearch teammate picker contract',()=>{
  it('uses default placeholder',()=>{ render(<StudentSearch value="" onChange={()=>{}}/>); expect(screen.getByPlaceholderText('Search by name or ID…')).toBeTruthy(); });
  it('uses custom placeholder',()=>{ render(<StudentSearch value="" onChange={()=>{}} placeholder="Find teammate"/>); expect(screen.getByPlaceholderText('Find teammate')).toBeTruthy(); });
  it('passes id to input',()=>{ render(<StudentSearch value="" onChange={()=>{}} id="member-1"/>); expect(screen.getByRole('combobox').id).toBe('member-1'); });
  it('starts collapsed',()=>{ render(<StudentSearch value="" onChange={()=>{}}/>); expect(screen.getByRole('combobox').getAttribute('aria-expanded')).toBe('false'); });
  it('starts with provided value as query',()=>{ render(<StudentSearch value="Existing" onChange={()=>{}}/>); expect(screen.getByRole('combobox').value).toBe('Existing'); });
  it('clears visible query when controlled value becomes empty',()=>{ const {rerender}=render(<StudentSearch value="s100" onChange={()=>{}}/>); expect(screen.getByRole('combobox').value).toBe('s100'); rerender(<StudentSearch value="" onChange={()=>{}}/>); expect(screen.getByRole('combobox').value).toBe(''); });
  it('clears selected username immediately while typing',()=>{ const fn=vi.fn(); render(<StudentSearch value="s100" onChange={fn}/>); fireEvent.change(screen.getByRole('combobox'),{target:{value:'A'}}); expect(fn).toHaveBeenCalledWith(''); });
  it('does not search before debounce expires',async()=>{ render(<StudentSearch value="" onChange={()=>{}}/>); fireEvent.change(screen.getByRole('combobox'),{target:{value:'Ali'}}); await act(async()=>{ await vi.advanceTimersByTimeAsync(299); }); expect(api.searchStudents).not.toHaveBeenCalled(); });
  it('searches after 300 ms',async()=>{ render(<StudentSearch value="" onChange={()=>{}}/>); await search('Ali'); expect(api.searchStudents).toHaveBeenCalledWith('Ali'); });
  it('does not search blank input',async()=>{ render(<StudentSearch value="" onChange={()=>{}}/>); fireEvent.change(screen.getByRole('combobox'),{target:{value:'   '}}); await act(async()=>{ await vi.advanceTimersByTimeAsync(500); }); expect(api.searchStudents).not.toHaveBeenCalled(); });
  it('opens result list after successful search',async()=>{ render(<StudentSearch value="" onChange={()=>{}} id="s"/>); await search(); expect(screen.getByRole('listbox')).toBeTruthy(); expect(screen.getByRole('combobox').getAttribute('aria-expanded')).toBe('true'); expect(screen.getByRole('combobox').getAttribute('aria-controls')).toBe('s-results'); });
  it.each(['Ali Student','Blocked Student','Registered Student'])('renders result %s',async(name)=>{ render(<StudentSearch value="" onChange={()=>{}}/>); await search(); expect(screen.getByText(name)).toBeTruthy(); });
  it('marks available result enabled',async()=>{ render(<StudentSearch value="" onChange={()=>{}}/>); await search(); expect(screen.getByText('Ali Student').closest('[role="option"]').getAttribute('aria-disabled')).toBe('false'); });
  it('marks explicitly unavailable result disabled',async()=>{ render(<StudentSearch value="" onChange={()=>{}}/>); await search(); expect(screen.getByText('Blocked Student').closest('[role="option"]').getAttribute('aria-disabled')).toBe('true'); });
  it('marks registered-project result disabled',async()=>{ render(<StudentSearch value="" onChange={()=>{}}/>); await search(); expect(screen.getByText('Registered Student').closest('[role="option"]').getAttribute('aria-disabled')).toBe('true'); });
  it('selects available student username',async()=>{ const fn=vi.fn(); render(<StudentSearch value="" onChange={fn}/>); await search(); fireEvent.mouseDown(screen.getByText('Ali Student').closest('[role="option"]')); expect(fn).toHaveBeenLastCalledWith('s100'); expect(screen.getByRole('combobox').value).toBe('Ali Student (s100)'); });
  it('closes list after valid selection',async()=>{ render(<StudentSearch value="" onChange={()=>{}}/>); await search(); fireEvent.mouseDown(screen.getByText('Ali Student').closest('[role="option"]')); expect(screen.queryByRole('listbox')).toBeNull(); });
  it('rejects explicitly unavailable student',async()=>{ const fn=vi.fn(); render(<StudentSearch value="" onChange={fn}/>); await search(); fireEvent.mouseDown(screen.getByText('Blocked Student').closest('[role="option"]')); expect(fn).toHaveBeenLastCalledWith(''); expect(screen.getByRole('alert').textContent).toContain('Already assigned'); });
  it('rejects student with registered project',async()=>{ const fn=vi.fn(); render(<StudentSearch value="" onChange={fn}/>); await search(); fireEvent.mouseDown(screen.getByText('Registered Student').closest('[role="option"]')); expect(fn).toHaveBeenLastCalledWith(''); expect(screen.getByRole('alert').textContent).toMatch(/لديه مشروع مسجل بالفعل/); });
  it('uses fallback name in unavailable error',async()=>{ api.searchStudents.mockResolvedValue({data:[{username:'s4',display:'S4',available:false}]}); render(<StudentSearch value="" onChange={()=>{}}/>); await search(); fireEvent.mouseDown(screen.getByText('s4').closest('[role="option"]')); expect(screen.getByRole('alert').textContent).toContain('الطالب s4 لديه مشروع مسجل بالفعل'); });
  it('clears local unavailable error on new input',async()=>{ render(<StudentSearch value="" onChange={()=>{}}/>); await search(); fireEvent.mouseDown(screen.getByText('Blocked Student').closest('[role="option"]')); expect(screen.getByRole('alert')).toBeTruthy(); fireEvent.change(screen.getByRole('combobox'),{target:{value:'New'}}); expect(screen.queryByRole('alert')).toBeNull(); });
  it('shows no-results state',async()=>{ api.searchStudents.mockResolvedValue({data:[]}); render(<StudentSearch value="" onChange={()=>{}}/>); await search('Nobody'); expect(screen.getByText('No students found')).toBeTruthy(); });
  it('shows visible search error on rejection',async()=>{ api.searchStudents.mockRejectedValue(new Error('x')); render(<StudentSearch value="" onChange={()=>{}}/>); await search('Nobody'); expect(screen.getByRole('alert').textContent).toContain('تعذر البحث عن الطلاب'); });
  it('closes dropdown on outside mousedown',async()=>{ render(<div><button>Outside</button><StudentSearch value="" onChange={()=>{}}/></div>); await search(); expect(screen.getByRole('listbox')).toBeTruthy(); fireEvent.mouseDown(screen.getByText('Outside')); expect(screen.queryByRole('listbox')).toBeNull(); });
  it('keeps dropdown open for inside mousedown until selection',async()=>{ render(<StudentSearch value="" onChange={()=>{}}/>); await search(); expect(screen.getByRole('listbox')).toBeTruthy(); fireEvent.mouseDown(screen.getByRole('combobox')); expect(screen.getByRole('listbox')).toBeTruthy(); });
  it('clears dropdown immediately when input is emptied',async()=>{ render(<StudentSearch value="" onChange={()=>{}}/>); await search(); fireEvent.change(screen.getByRole('combobox'),{target:{value:''}}); expect(screen.queryByRole('listbox')).toBeNull(); });
  it('renders unavailable badge for two blocked variants',async()=>{ render(<StudentSearch value="" onChange={()=>{}}/>); await search(); expect(screen.getAllByText('لديه مشروع')).toHaveLength(2); });
  it('renders username badge for available student',async()=>{ render(<StudentSearch value="" onChange={()=>{}}/>); await search(); expect(screen.getByText('s100')).toBeTruthy(); });
  it('marks selected option when controlled value matches username',async()=>{ render(<StudentSearch value="s100" onChange={()=>{}}/>); await search(); expect(screen.getByText('Ali Student').closest('[role="option"]').getAttribute('aria-selected')).toBe('true'); });
});
