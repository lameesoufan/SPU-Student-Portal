import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ fetchMyCommitteeGrades:vi.fn(), enterBulkGrades:vi.fn(), submitGradeDraft:vi.fn(), downloadProjectReport:vi.fn() }));
vi.mock('../../api.jsx', () => ({ ...api }));
import GradeEntry from './GradeEntry.jsx';

const students = [
  {student_id:1,student_name:'Ali Student',student_number:'S001',is_leader:true,grade:null,my_draft:null},
  {student_id:2,student_name:'Sara Student',student_number:'S002',is_leader:false,grade:null,my_draft:null},
];
const makeCommittee = (overrides={}) => ({
  committee_id:20, committee_type:'seminar_1', committee_type_ar:'سيمينار 1', semester:'S1', collective_mode:false,
  projects:[{id:501,source:'proposal',title:'Project Alpha',all_graded:false,students,report_uploaded:false,report:null}], ...overrides,
});
const finalCommittee = makeCommittee({committee_id:30,committee_type:'final_discussion',committee_type_ar:'المناقشة النهائية',collective_mode:true,projects:[{id:700,source:'application',title:'Final Project',all_graded:false,students:[{...students[0],my_draft:{score_main:25,score_report:20,notes:'old'},grade:{score_main:26,score_report:21}}],report_uploaded:true,report:{original_name:'report.pdf'}}]});

beforeEach(()=>{
  vi.resetAllMocks(); api.fetchMyCommitteeGrades.mockResolvedValue({data:{committees:[makeCommittee()]}}); api.enterBulkGrades.mockResolvedValue({data:{}}); api.submitGradeDraft.mockResolvedValue({data:{}}); api.downloadProjectReport.mockResolvedValue({data:new Uint8Array([1])});
  Object.defineProperty(URL,'createObjectURL',{configurable:true,value:vi.fn(()=> 'blob:grade')}); Object.defineProperty(URL,'revokeObjectURL',{configurable:true,value:vi.fn()}); vi.spyOn(HTMLAnchorElement.prototype,'click').mockImplementation(()=>{});
});
function scoreInputs(){ return [...document.querySelectorAll('input[type="number"]')]; }
function notesInputs(){ return [...document.querySelectorAll('input[placeholder="ملاحظة اختيارية..."]')]; }
async function fillIndividual(a='8',b='9'){ await screen.findByText('Project Alpha'); const inputs=scoreInputs(); fireEvent.change(inputs[0],{target:{value:a}}); fireEvent.change(inputs[1],{target:{value:b}}); }

describe('GradeEntry loading/filtering contracts',()=>{
  it('shows loader while request is pending',()=>{ api.fetchMyCommitteeGrades.mockReturnValue(new Promise(()=>{})); render(<GradeEntry/>); expect(screen.getByText('جاري تحميل لجانك ومشاريعك...')).toBeTruthy(); });
  it('loads committee grade workspace',async()=>{ render(<GradeEntry/>); expect(await screen.findByText('إدخال العلامات')).toBeTruthy(); expect(api.fetchMyCommitteeGrades).toHaveBeenCalledOnce(); });
  it('shows API detail on load failure',async()=>{ api.fetchMyCommitteeGrades.mockRejectedValue({response:{data:{detail:'NOT MEMBER'}}}); render(<GradeEntry/>); expect(await screen.findByText('NOT MEMBER')).toBeTruthy(); });
  it('retries failed load',async()=>{ api.fetchMyCommitteeGrades.mockRejectedValueOnce({response:{data:{detail:'TEMP'}}}).mockResolvedValueOnce({data:{committees:[makeCommittee()]}}); render(<GradeEntry/>); fireEvent.click(await screen.findByRole('button',{name:'إعادة المحاولة'})); expect(await screen.findByText('Project Alpha')).toBeTruthy(); expect(api.fetchMyCommitteeGrades).toHaveBeenCalledTimes(2); });
  it('shows empty assignment state',async()=>{ api.fetchMyCommitteeGrades.mockResolvedValue({data:{committees:[]}}); render(<GradeEntry/>); expect(await screen.findByText('لا توجد لجان متاحة لإدخال العلامات')).toBeTruthy(); });
  it('shows aggregate committee count',async()=>{ render(<GradeEntry/>); expect(await screen.findByText('اللجان')).toBeTruthy(); expect(screen.getAllByText('1').length).toBeGreaterThan(0); });
  it('shows project and student counts',async()=>{ render(<GradeEntry/>); await screen.findByText('Project Alpha'); expect(screen.getByText('2 طلاب')).toBeTruthy(); });
  it('searches by project title',async()=>{ render(<GradeEntry/>); await screen.findByText('Project Alpha'); fireEvent.change(screen.getByPlaceholderText('ابحث باسم المشروع أو الطالب...'),{target:{value:'missing'}}); expect(screen.getByText('لا توجد نتائج مطابقة')).toBeTruthy(); });
  it('searches by student name',async()=>{ render(<GradeEntry/>); await screen.findByText('Project Alpha'); fireEvent.change(screen.getByPlaceholderText('ابحث باسم المشروع أو الطالب...'),{target:{value:'Sara'}}); expect(screen.getByText('Project Alpha')).toBeTruthy(); });
  it('pending filter keeps unfinished project',async()=>{ render(<GradeEntry/>); await screen.findByText('Project Alpha'); fireEvent.click(screen.getByRole('button',{name:'غير مكتملة'})); expect(screen.getByText('Project Alpha')).toBeTruthy(); });
  it('completed filter hides unfinished project',async()=>{ render(<GradeEntry/>); await screen.findByText('Project Alpha'); fireEvent.click(screen.getByRole('button',{name:'مكتملة'})); expect(screen.getByText('لا توجد نتائج مطابقة')).toBeTruthy(); });
  it('committee type filter can hide other type',async()=>{ render(<GradeEntry/>); await screen.findByText('Project Alpha'); fireEvent.change(screen.getByRole('combobox'),{target:{value:'technical'}}); expect(screen.getByText('لا توجد نتائج مطابقة')).toBeTruthy(); });
});

describe('GradeEntry individual grading contract',()=>{
  it('shows individual bulk-entry guidance',async()=>{ render(<GradeEntry/>); expect(await screen.findByText('أدخل العلامات في الجدول ثم احفظ المشروع دفعة واحدة.')).toBeTruthy(); });
  it('save button is individual wording',async()=>{ render(<GradeEntry/>); expect(await screen.findByRole('button',{name:'حفظ العلامات'})).toBeTruthy(); });
  it('requires every main score',async()=>{ render(<GradeEntry/>); await screen.findByText('Project Alpha'); fireEvent.click(screen.getByRole('button',{name:'حفظ العلامات'})); expect(await screen.findByText(/علامات ناقصة أو خارج المجال/)).toBeTruthy(); expect(api.enterBulkGrades).not.toHaveBeenCalled(); });
  it('rejects seminar score above ten',async()=>{ render(<GradeEntry/>); await fillIndividual('11','9'); fireEvent.click(screen.getByRole('button',{name:'حفظ العلامات'})); expect(screen.getByText('0–10')).toBeTruthy(); expect(api.enterBulkGrades).not.toHaveBeenCalled(); });
  it('rejects negative score',async()=>{ render(<GradeEntry/>); await fillIndividual('-1','9'); fireEvent.click(screen.getByRole('button',{name:'حفظ العلامات'})); expect(screen.getAllByText('0–10').length).toBeGreaterThan(0); });
  it('submits bulk grades with project/committee binding',async()=>{ render(<GradeEntry/>); await fillIndividual(); fireEvent.click(screen.getByRole('button',{name:'حفظ العلامات'})); await waitFor(()=>expect(api.enterBulkGrades).toHaveBeenCalledOnce(),{timeout:3000}); expect(api.enterBulkGrades.mock.calls[0][0]).toMatchObject({project_source:'proposal',project_id:501,committee_type:'seminar_1',committee_id:20,semester:'S1',confirm_update:false}); });
  it('converts score strings to numbers',async()=>{ render(<GradeEntry/>); await fillIndividual('8.5','9'); fireEvent.click(screen.getByRole('button',{name:'حفظ العلامات'})); await waitFor(()=>expect(api.enterBulkGrades).toHaveBeenCalled()); const grades=api.enterBulkGrades.mock.calls[0][0].grades; expect(grades[0].score_main).toBe(8.5); expect(grades[1].score_main).toBe(9); });
  it('trims notes before submitting',async()=>{ const committee=makeCommittee(); committee.projects[0]={...committee.projects[0],students:[{...students[0],grade:{score_main:8,notes:'  useful note  '}},{...students[1],grade:{score_main:9,notes:''}}]}; api.fetchMyCommitteeGrades.mockResolvedValue({data:{committees:[committee]}}); render(<GradeEntry/>); await screen.findByText('Project Alpha'); fireEvent.click(screen.getByRole('button',{name:'حفظ العلامات'})); await waitFor(()=>expect(api.enterBulkGrades).toHaveBeenCalledOnce(),{timeout:3000}); expect(api.enterBulkGrades.mock.calls[0][0].grades[0].notes).toBe('useful note'); });
  it('shows save success then reloads workspace',async()=>{ render(<GradeEntry/>); await fillIndividual(); fireEvent.click(screen.getByRole('button',{name:'حفظ العلامات'})); expect(await screen.findByText('تم حفظ علامات المشروع بنجاح.')).toBeTruthy(); await waitFor(()=>expect(api.fetchMyCommitteeGrades).toHaveBeenCalledTimes(2)); });
  it('asks confirmation on overwrite conflict',async()=>{ api.enterBulkGrades.mockRejectedValueOnce({response:{status:409,data:{requires_confirmation:true,message:'REPLACE?'}}}); render(<GradeEntry/>); await fillIndividual(); fireEvent.click(screen.getByRole('button',{name:'حفظ العلامات'})); expect(await screen.findByText('REPLACE?')).toBeTruthy(); expect(screen.getByRole('button',{name:'استبدال العلامات وحفظها'})).toBeTruthy(); });
  it('confirmation retries with confirm_update true',async()=>{ api.enterBulkGrades.mockRejectedValueOnce({response:{status:409,data:{requires_confirmation:true,message:'REPLACE?'}}}).mockResolvedValueOnce({data:{}}); render(<GradeEntry/>); await fillIndividual(); fireEvent.click(screen.getByRole('button',{name:'حفظ العلامات'})); await waitFor(()=>expect(api.enterBulkGrades).toHaveBeenCalledTimes(1)); const replaceButton = await screen.findByRole('button',{name:'استبدال العلامات وحفظها'}, {timeout:3000}); fireEvent.click(replaceButton); await waitFor(()=>expect(api.enterBulkGrades).toHaveBeenCalledTimes(2),{timeout:3000}); expect(api.enterBulkGrades.mock.calls[1][0].confirm_update).toBe(true); });
  it('can cancel overwrite confirmation',async()=>{ api.enterBulkGrades.mockRejectedValue({response:{status:409,data:{requires_confirmation:true,message:'REPLACE?'}}}); render(<GradeEntry/>); await fillIndividual(); fireEvent.click(screen.getByRole('button',{name:'حفظ العلامات'})); fireEvent.click(await screen.findByRole('button',{name:'العودة دون تغيير'})); expect(screen.queryByText('تأكيد استبدال العلامات السابقة')).toBeNull(); });
  it('shows structured backend save error',async()=>{ api.enterBulkGrades.mockRejectedValue({response:{data:{grades:['bad'],non_field_errors:['denied']}}}); render(<GradeEntry/>); await fillIndividual(); fireEvent.click(screen.getByRole('button',{name:'حفظ العلامات'})); await waitFor(()=>expect(api.enterBulkGrades).toHaveBeenCalledTimes(1)); expect(await screen.findByText('grades: bad — denied', { exact:true }, {timeout:3000})).toBeTruthy(); });
});

describe('GradeEntry collective/final contract',()=>{
  beforeEach(()=>{ api.fetchMyCommitteeGrades.mockResolvedValue({data:{committees:[finalCommittee]}}); });
  it('shows collective grading guidance',async()=>{ render(<GradeEntry/>); expect(await screen.findByText(/يحسب النظام المتوسط بعد اكتمال تقييم أعضاء اللجنة/)).toBeTruthy(); });
  it('uses draft save wording',async()=>{ render(<GradeEntry/>); expect(await screen.findByRole('button',{name:'حفظ تقييمي'})).toBeTruthy(); });
  it('preloads own draft rather than final average',async()=>{ render(<GradeEntry/>); await screen.findByText('Final Project'); const inputs=scoreInputs(); expect(inputs[0].value).toBe('25'); expect(inputs[1].value).toBe('20'); expect(screen.getByText(/تقييمي: 25/)).toBeTruthy(); expect(screen.getByText(/المتوسط: 26 \+ 21/)).toBeTruthy(); });
  it('final discussion renders report score input',async()=>{ render(<GradeEntry/>); await screen.findByText('Final Project'); expect(scoreInputs()).toHaveLength(2); });
  it('allows blank report score and serializes null',async()=>{ render(<GradeEntry/>); await screen.findByText('Final Project'); fireEvent.change(scoreInputs()[1],{target:{value:''}}); fireEvent.click(screen.getByRole('button',{name:'حفظ تقييمي'})); await waitFor(()=>expect(api.submitGradeDraft).toHaveBeenCalled()); expect(api.submitGradeDraft.mock.calls[0][0].grades[0].score_report).toBeNull(); });
  it('rejects report score above 30',async()=>{ render(<GradeEntry/>); await screen.findByText('Final Project'); fireEvent.change(scoreInputs()[1],{target:{value:'31'}}); fireEvent.click(screen.getByRole('button',{name:'حفظ تقييمي'})); expect(screen.getByText('0–30')).toBeTruthy(); expect(api.submitGradeDraft).not.toHaveBeenCalled(); });
  it('submits collective grades as draft',async()=>{ render(<GradeEntry/>); await screen.findByText('Final Project'); fireEvent.click(screen.getByRole('button',{name:'حفظ تقييمي'})); await waitFor(()=>expect(api.submitGradeDraft).toHaveBeenCalledWith(expect.objectContaining({committee_id:30,project_source:'application',project_id:700,committee_type:'final_discussion',semester:'S1'}))); expect(api.enterBulkGrades).not.toHaveBeenCalled(); });
  it('shows collective pending-average success message',async()=>{ render(<GradeEntry/>); await screen.findByText('Final Project'); fireEvent.click(screen.getByRole('button',{name:'حفظ تقييمي'})); expect(await screen.findByText(/ستظهر النتيجة النهائية بعد اكتمال تقييم جميع الأعضاء/)).toBeTruthy(); });
  it('offers protected report download when uploaded',async()=>{ render(<GradeEntry/>); fireEvent.click(await screen.findByRole('button',{name:'تحميل التقرير'})); await waitFor(()=>expect(api.downloadProjectReport).toHaveBeenCalledWith('application',700)); expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:grade'); });
  it('shows report download API error',async()=>{ api.downloadProjectReport.mockRejectedValue({response:{data:{detail:'NO FILE'}}}); render(<GradeEntry/>); fireEvent.click(await screen.findByRole('button',{name:'تحميل التقرير'})); expect(await screen.findByText('NO FILE')).toBeTruthy(); });
  it('warns but permits grade entry when final report is not uploaded',async()=>{ api.fetchMyCommitteeGrades.mockResolvedValue({data:{committees:[{...finalCommittee,projects:[{...finalCommittee.projects[0],report_uploaded:false}]}]}}); render(<GradeEntry/>); expect(await screen.findByText(/التقرير غير مرفوع إلكترونيًا/)).toBeTruthy(); expect(screen.getByRole('button',{name:'حفظ تقييمي'}).disabled).toBe(false); });
});
