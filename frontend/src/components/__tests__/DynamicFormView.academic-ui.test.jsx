import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ fetchStudentForm: vi.fn(), submitFormResponse: vi.fn() }));
vi.mock('../../api.jsx', () => ({ ...api }));
vi.mock('../DynamicCheckboxGroup.jsx', () => ({ default: ({ field, value, onChange }) => <div data-testid={`checkbox-${field.id}`}><button type="button" onClick={() => onChange(['A','B'])}>SET-CHECKBOX</button><span>{JSON.stringify(value)}</span></div> }));
import DynamicFormView from '../DynamicFormView.jsx';

const form = {
  id: 91, title: 'Department Extra Form', fields: [
    { id: 1, label: 'Text field', field_type: 'text', required: true },
    { id: 2, label: 'Long field', field_type: 'textarea', required: false },
    { id: 3, label: 'Number field', field_type: 'number', required: false },
    { id: 4, label: 'Date field', field_type: 'date', required: false },
    { id: 5, label: 'Select field', field_type: 'select', required: false, options: ['One','Two'] },
    { id: 6, label: 'Radio field', field_type: 'radio', required: false, options: ['Yes','No'] },
    { id: 7, label: 'Check field', field_type: 'checkbox', required: false, options: ['A','B'] },
    { id: 8, label: 'File field', field_type: 'file', required: false },
  ],
};

beforeEach(() => { vi.clearAllMocks(); api.fetchStudentForm.mockResolvedValue({ data: form }); });
function renderForm(props={}) { const onSubmit=vi.fn(); const view=render(<DynamicFormView context="propose" onSubmit={onSubmit} submitting={false} {...props}/>); return { ...view, onSubmit }; }
function departmentSelect() { return screen.getByText('Select department...').closest('select'); }
function findControl(label) { const labelNode=screen.getByText(label, { selector: 'label', exact: false }); return labelNode.parentElement.querySelector('input,textarea,select'); }
async function chooseDepartment() { fireEvent.change(departmentSelect(), { target:{ value:'software_engineering' } }); await waitFor(()=>expect(api.fetchStudentForm).toHaveBeenCalled()); }

describe('DynamicFormView basic contract', () => {
  it('renders department selector', () => { renderForm(); expect(departmentSelect()).toBeTruthy(); });
  it.each(['Software Engineering','Artificial Intelligence','Information Security','Communications','Control & Robotics'])('offers department %s', (label) => { renderForm(); expect(screen.getByText(label)).toBeTruthy(); });
  it('does not fetch until department exists', () => { renderForm(); expect(api.fetchStudentForm).not.toHaveBeenCalled(); });
  it('preselected department is disabled', async () => { renderForm({department:'software_engineering'}); expect(departmentSelect().disabled).toBe(true); await waitFor(()=>expect(api.fetchStudentForm).toHaveBeenCalledWith('software_engineering','propose')); });
  it('loads form after selecting department', async () => { renderForm(); await chooseDepartment(); expect(await screen.findByRole('heading', { name: 'Department Extra Form' })).toBeTruthy(); });
  it('passes browse context to form API', async () => { renderForm({context:'browse',department:'communications'}); await waitFor(()=>expect(api.fetchStudentForm).toHaveBeenCalledWith('communications','browse')); });
  it('shows loading indicator while form request is pending', async () => { api.fetchStudentForm.mockReturnValue(new Promise(()=>{})); renderForm(); fireEvent.change(departmentSelect(), {target:{value:'software_engineering'}}); expect(await screen.findByText('Loading department form...')).toBeTruthy(); });
  it('hides dynamic form if API fails', async () => { api.fetchStudentForm.mockRejectedValue(new Error('x')); renderForm(); await chooseDepartment(); await waitFor(()=>expect(screen.queryByText('Department Extra Form')).toBeNull()); });
  it('shows title field in propose context', () => { renderForm(); expect(screen.getByPlaceholderText('Enter your project title')).toBeTruthy(); });
  it('shows description field in propose context', () => { renderForm(); expect(screen.getByPlaceholderText('Describe your project idea...')).toBeTruthy(); });
  it('hides title field in browse context', () => { renderForm({context:'browse'}); expect(screen.queryByPlaceholderText('Enter your project title')).toBeNull(); });
  it('hides description field in browse context', () => { renderForm({context:'browse'}); expect(screen.queryByPlaceholderText('Describe your project idea...')).toBeNull(); });
  it('starts team size at two', () => { renderForm(); expect(findControl('Team Size').value).toBe('2'); });
  it('changes team size numerically', () => { renderForm(); fireEvent.change(findControl('Team Size'), {target:{value:'4'}}); expect(findControl('Team Size').value).toBe('4'); });
  it('disables submit without department', () => { renderForm(); expect(screen.getByRole('button',{name:'Submit'}).disabled).toBe(true); });
  it('disables submit while parent is submitting', async () => { renderForm({department:'software_engineering', submitting:true}); await screen.findByRole('heading', { name: 'Department Extra Form' }); expect(screen.getByRole('button',{name:'Submitting...'}).disabled).toBe(true); });
  it('shows external parent error', () => { renderForm({externalError:'SERVER ERROR'}); expect(screen.getByText('SERVER ERROR')).toBeTruthy(); });
});

describe('DynamicFormView dynamic fields', () => {
  it.each([
    ['Text field','INPUT'], ['Long field','TEXTAREA'], ['Number field','INPUT'], ['Date field','INPUT'], ['Select field','SELECT'], ['File field','INPUT'],
  ])('renders %s control', async (label, tag) => { renderForm({department:'software_engineering'}); await screen.findByRole('heading', { name: 'Department Extra Form' }); expect(findControl(label).tagName).toBe(tag); });
  it('number field is numeric and nonnegative', async () => { renderForm({department:'software_engineering'}); await screen.findByRole('heading', { name: 'Department Extra Form' }); const c=findControl('Number field'); expect(c.type).toBe('number'); expect(c.min).toBe('0'); });
  it('date field uses date input', async () => { renderForm({department:'software_engineering'}); await screen.findByRole('heading', { name: 'Department Extra Form' }); expect(findControl('Date field').type).toBe('date'); });
  it('select renders all configured options', async () => { renderForm({department:'software_engineering'}); await screen.findByRole('heading', { name: 'Department Extra Form' }); expect(screen.getByText('One')).toBeTruthy(); expect(screen.getByText('Two')).toBeTruthy(); });
  it('radio renders all configured options', async () => { renderForm({department:'software_engineering'}); await screen.findByRole('heading', { name: 'Department Extra Form' }); expect(screen.getByDisplayValue('Yes')).toBeTruthy(); expect(screen.getByDisplayValue('No')).toBeTruthy(); });
  it('checkbox delegates to DynamicCheckboxGroup', async () => { renderForm({department:'software_engineering'}); await screen.findByRole('heading', { name: 'Department Extra Form' }); expect(screen.getByTestId('checkbox-7')).toBeTruthy(); });
  it('file input restricts expected extensions', async () => { renderForm({department:'software_engineering'}); await screen.findByRole('heading', { name: 'Department Extra Form' }); expect(findControl('File field').accept).toContain('.pdf'); expect(findControl('File field').accept).toContain('.docx'); });
  it('initial checkbox value is empty array', async () => { renderForm({department:'software_engineering'}); await screen.findByRole('heading', { name: 'Department Extra Form' }); expect(screen.getByTestId('checkbox-7').textContent).toContain('[]'); });
});

describe('DynamicFormView submission', () => {
  it('blocks missing required dynamic field', async () => { const {onSubmit}=renderForm({department:'software_engineering'}); await screen.findByRole('heading', { name: 'Department Extra Form' }); fireEvent.submit(screen.getByRole('button',{name:'Submit'}).closest('form')); expect(screen.getByText('"Text field" is required.')).toBeTruthy(); expect(onSubmit).not.toHaveBeenCalled(); });
  it('submits default and dynamic values with form id', async () => { const {onSubmit}=renderForm({department:'software_engineering'}); await screen.findByRole('heading', { name: 'Department Extra Form' }); fireEvent.change(screen.getByPlaceholderText('Enter your project title'),{target:{value:'Project X'}}); fireEvent.change(screen.getByPlaceholderText('Describe your project idea...'),{target:{value:'Desc'}}); fireEvent.change(findControl('Text field'),{target:{value:'Required'}}); fireEvent.change(findControl('Long field'),{target:{value:'Long'}}); fireEvent.change(findControl('Number field'),{target:{value:'12.5'}}); fireEvent.change(findControl('Date field'),{target:{value:'2026-08-07'}}); fireEvent.change(findControl('Select field'),{target:{value:'Two'}}); fireEvent.click(screen.getByDisplayValue('Yes')); fireEvent.click(screen.getByText('SET-CHECKBOX')); fireEvent.change(findControl('File field'),{target:{files:[new File(['x'],'report.pdf',{type:'application/pdf'})]}}); fireEvent.submit(screen.getByRole('button',{name:'Submit'}).closest('form')); expect(onSubmit).toHaveBeenCalledOnce(); const [defaults,dynamic,id]=onSubmit.mock.calls[0]; expect(defaults).toEqual({title:'Project X',description:'Desc',department:'software_engineering',team_size:2}); expect(id).toBe(91); expect(dynamic).toEqual(expect.arrayContaining([{field:1,value:'Required'},{field:5,value:'Two'},{field:6,value:'Yes'},{field:7,value:['A','B']},{field:8,value:'report.pdf'}])); });
  it('uses null form id when department has no dynamic form', async () => { api.fetchStudentForm.mockRejectedValue(new Error('404')); const {onSubmit}=renderForm({department:'software_engineering'}); await waitFor(()=>expect(api.fetchStudentForm).toHaveBeenCalled()); fireEvent.change(screen.getByPlaceholderText('Enter your project title'),{target:{value:'P'}}); fireEvent.change(screen.getByPlaceholderText('Describe your project idea...'),{target:{value:'D'}}); fireEvent.submit(screen.getByRole('button',{name:'Submit'}).closest('form')); expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({department:'software_engineering'}),[],null); });
  it('clears previous validation error after valid resubmit', async () => { const {onSubmit}=renderForm({department:'software_engineering'}); await screen.findByRole('heading', { name: 'Department Extra Form' }); const f=screen.getByRole('button',{name:'Submit'}).closest('form'); fireEvent.submit(f); expect(screen.getByText('\"Text field\" is required.')).toBeTruthy(); fireEvent.change(findControl('Text field'),{target:{value:'ok'}}); fireEvent.submit(f); expect(onSubmit).toHaveBeenCalledOnce(); expect(screen.queryByText('\"Text field\" is required.')).toBeNull(); });
  it('keeps number dynamic value as entered string in dynamic payload', async () => { const {onSubmit}=renderForm({department:'software_engineering'}); await screen.findByRole('heading', { name: 'Department Extra Form' }); fireEvent.change(findControl('Text field'),{target:{value:'ok'}}); fireEvent.change(findControl('Number field'),{target:{value:'7.25'}}); fireEvent.submit(screen.getByRole('button',{name:'Submit'}).closest('form')); const dynamic=onSubmit.mock.calls[0][1]; expect(dynamic.find(x=>x.field===3).value).toBe('7.25'); });
});
