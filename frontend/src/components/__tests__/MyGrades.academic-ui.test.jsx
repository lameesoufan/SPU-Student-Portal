import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ uploadProjectReport:vi.fn(), fetchMyGrades:vi.fn(), downloadProjectReport:vi.fn() }));
vi.mock('../../api.jsx', () => ({ ...api }));
import MyGrades from '../MyGrades.jsx';

const project = {
  project_source:'proposal', project_id:55, project_title:'Secure Portal', total_score:73,
  grades:{ seminar_1:{score_main:9,semester:'S1'}, seminar_2:null, technical:{score_main:18}, final_discussion:{score_main:27,score_report:19} },
  committees:{
    seminar_1:{ chair:{id:1,name:'Dr Chair'}, members:[{id:1,name:'Dr Chair'},{id:2,name:'Dr Member'}], date:'2026-08-10',start_time:'10:00',end_time:'11:00',room_name:'A1' },
    seminar_2:null,
    technical:{ members:[{id:3,name:'Dr Tech'}], location:'Lab' },
    final_discussion:{ chair:{email:'final@x',name:'Dr Final'}, members:[] },
  },
  report_uploaded:true, report:{original_name:'final-report.pdf'}
};

beforeEach(()=>{
  vi.clearAllMocks();
  api.fetchMyGrades.mockResolvedValue({data:{projects:[project]}});
  api.uploadProjectReport.mockResolvedValue({data:{}});
  api.downloadProjectReport.mockResolvedValue({data:new Uint8Array([1,2,3])});
  Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn(()=> 'blob:test')});
  Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()});
  vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{});
});

describe('MyGrades page contract',()=>{
  it('shows loading state',()=>{ api.fetchMyGrades.mockReturnValue(new Promise(()=>{})); render(<MyGrades/>); expect(screen.getByText('جاري تحميل العلامات...')).toBeTruthy(); });
  it('loads current student grades',async()=>{ render(<MyGrades/>); await screen.findByText('Secure Portal'); expect(api.fetchMyGrades).toHaveBeenCalledOnce(); });
  it('shows backend error detail',async()=>{ api.fetchMyGrades.mockRejectedValue({response:{data:{detail:'GRADES BLOCKED'}}}); render(<MyGrades/>); expect(await screen.findByText('GRADES BLOCKED')).toBeTruthy(); });
  it('uses generic load error',async()=>{ api.fetchMyGrades.mockRejectedValue(new Error('x')); render(<MyGrades/>); expect(await screen.findByText('تعذّر تحميل العلامات.')).toBeTruthy(); });
  it('shows empty state without active projects',async()=>{ api.fetchMyGrades.mockResolvedValue({data:{projects:[]}}); render(<MyGrades/>); expect(await screen.findByText('لا توجد مشاريع نشطة')).toBeTruthy(); });
  it('shows project count badge',async()=>{ render(<MyGrades/>); expect(await screen.findByText('1 مشروع')).toBeTruthy(); });
  it.each(['سيمينار 1','سيمينار 2','لجنة فنية','مناقشة نهائية'])('shows grade stage %s',async(label)=>{ render(<MyGrades/>); expect((await screen.findAllByText(label)).length).toBeGreaterThan(0); });
  it('shows stored grade values',async()=>{ render(<MyGrades/>); await screen.findByText('Secure Portal'); expect(screen.getAllByText('9').length).toBeGreaterThan(0); expect(screen.getAllByText('18').length).toBeGreaterThan(0); expect(screen.getAllByText('27').length).toBeGreaterThan(0); });
  it('shows report score separately',async()=>{ render(<MyGrades/>); await screen.findByText('Secure Portal'); expect(screen.getAllByText('19').length).toBeGreaterThan(0); });
  it('shows pending state for missing grade',async()=>{ render(<MyGrades/>); await screen.findByText('Secure Portal'); expect(screen.getAllByText('لم تُدخَل بعد').length).toBeGreaterThan(0); expect(screen.getAllByText('بانتظار الإدخال').length).toBeGreaterThan(0); });
  it('shows total out of 100',async()=>{ render(<MyGrades/>); expect(await screen.findByText('73 / 100')).toBeTruthy(); });
  it('deduplicates chair repeated in member list',async()=>{ render(<MyGrades/>); await screen.findByText('Secure Portal'); expect(screen.getAllByText('Dr Chair')).toHaveLength(1); expect(screen.getByText('Dr Member')).toBeTruthy(); });
  it('shows committee date and time',async()=>{ render(<MyGrades/>); await screen.findByText('Secure Portal'); expect(screen.getByText('2026-08-10')).toBeTruthy(); expect(screen.getByText('10:00 - 11:00')).toBeTruthy(); });
  it('prefers room name as place',async()=>{ render(<MyGrades/>); expect(await screen.findByText('A1')).toBeTruthy(); });
  it('falls back to location as place',async()=>{ render(<MyGrades/>); expect(await screen.findByText('Lab')).toBeTruthy(); });
  it('shows unspecified committee placeholders',async()=>{ render(<MyGrades/>); await screen.findByText('Secure Portal'); expect(screen.getAllByText('لم تُحدَّد اللجنة بعد').length).toBeGreaterThan(0); expect(screen.getAllByText('غير محدد').length).toBeGreaterThan(0); });
  it('shows uploaded report metadata',async()=>{ render(<MyGrades/>); expect(await screen.findByText('final-report.pdf')).toBeTruthy(); expect(screen.getByText('✔ مرفوع')).toBeTruthy(); });
  it('shows update wording for existing report',async()=>{ render(<MyGrades/>); expect(await screen.findByText(/تحديث التقرير/)).toBeTruthy(); });
  it('shows upload wording for missing report',async()=>{ api.fetchMyGrades.mockResolvedValue({data:{projects:[{...project,report_uploaded:false,report:null}]}}); render(<MyGrades/>); expect(await screen.findByText(/رفع تقرير المشروع/)).toBeTruthy(); });
  it('uploads selected report with project binding',async()=>{ render(<MyGrades/>); await screen.findByText('Secure Portal'); const input=document.querySelector('input[type="file"]'); const file=new File(['x'],'new.pdf',{type:'application/pdf'}); fireEvent.change(input,{target:{files:[file]}}); await waitFor(()=>expect(api.uploadProjectReport).toHaveBeenCalledOnce()); const fd=api.uploadProjectReport.mock.calls[0][0]; expect(fd.get('project_source')).toBe('proposal'); expect(fd.get('project_id')).toBe('55'); expect(fd.get('semester')).toBe('S1'); expect(fd.get('file').name).toBe('new.pdf'); });
  it('shows upload success and reloads data',async()=>{ render(<MyGrades/>); await screen.findByText('Secure Portal'); fireEvent.change(document.querySelector('input[type="file"]'),{target:{files:[new File(['x'],'new.pdf')]}}); expect(await screen.findByText('تم رفع التقرير بنجاح.')).toBeTruthy(); await waitFor(()=>expect(api.fetchMyGrades).toHaveBeenCalledTimes(2)); });
  it('shows backend upload error',async()=>{ api.uploadProjectReport.mockRejectedValue({response:{data:{detail:'BAD FILE'}}}); render(<MyGrades/>); await screen.findByText('Secure Portal'); fireEvent.change(document.querySelector('input[type="file"]'),{target:{files:[new File(['x'],'bad.exe')]}}); expect(await screen.findByText('BAD FILE')).toBeTruthy(); });
  it('downloads existing report through protected API',async()=>{ render(<MyGrades/>); fireEvent.click(await screen.findByRole('button',{name:/تحميل التقرير/})); await waitFor(()=>expect(api.downloadProjectReport).toHaveBeenCalledWith('proposal',55)); expect(URL.createObjectURL).toHaveBeenCalled(); expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test'); });
  it('shows report download error',async()=>{ api.downloadProjectReport.mockRejectedValue(new Error('x')); render(<MyGrades/>); fireEvent.click(await screen.findByRole('button',{name:/تحميل التقرير/})); expect(await screen.findByText('فشل تحميل التقرير.')).toBeTruthy(); });
  it('refreshes grade data when window regains focus',async()=>{ render(<MyGrades/>); await screen.findByText('Secure Portal'); fireEvent.focus(window); await waitFor(()=>expect(api.fetchMyGrades).toHaveBeenCalledTimes(2)); });
});
