import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Dashboard from '../Dashboard.jsx';
import DynamicCheckboxGroup from '../DynamicCheckboxGroup.jsx';
import { NotifIcon, notifBgColor, notifTextColor } from '../NotifHelpers.jsx';
import {
  COMMITTEE_TYPES, PROJECT_TYPES, DEPARTMENTS, COMMITTEE_STATUSES,
  getCommitteeTypeLabel, getProjectTypeLabel, getDepartmentLabel, getCommitteeStatusLabel,
  COMMITTEE_TYPE_COLORS, DEPARTMENT_COLORS, STATUS_COLORS, WORKLOAD_COLORS, WARNING_COLORS,
} from '../committees/constants.js';

describe('Dashboard direct contract', () => {
  it('renders admin overview title', () => { render(<Dashboard user={{ role:'admin', username:'root' }} onNavigate={() => {}} />); expect(screen.getByText('System Overview')).toBeTruthy(); });
  it('renders username in welcome copy', () => { render(<Dashboard user={{ role:'admin', username:'root' }} onNavigate={() => {}} />); expect(screen.getByText(/Welcome, root/)).toBeTruthy(); });
  it('renders academic year', () => { render(<Dashboard user={{ role:'admin', username:'root' }} onNavigate={() => {}} />); expect(screen.getByText('2025/2026')).toBeTruthy(); });
  it.each(['Total Users','Active Projects','Pending Approvals'])('renders stat %s', (label) => { render(<Dashboard user={{ role:'admin', username:'root' }} onNavigate={() => {}} />); expect(screen.getByText(label)).toBeTruthy(); });
  it('admin can navigate to import', () => { const onNavigate=vi.fn(); render(<Dashboard user={{ role:'admin', username:'root' }} onNavigate={onNavigate} />); fireEvent.click(screen.getByRole('listitem',{name:'Import Users'})); expect(onNavigate).toHaveBeenCalledWith('import'); });
  it('dean can navigate to assign hod', () => { const onNavigate=vi.fn(); render(<Dashboard user={{ role:'dean', username:'dean' }} onNavigate={onNavigate} />); fireEvent.click(screen.getByRole('listitem',{name:'Assign HoD'})); expect(onNavigate).toHaveBeenCalledWith('assign-hod'); });
  it('falls back to admin modules for unknown role', () => { render(<Dashboard user={{ role:'auditor', username:'a' }} onNavigate={() => {}} />); expect(screen.getByRole('listitem',{name:'Import Users'})).toBeTruthy(); });
  it('non-routable module is visually disabled', () => { render(<Dashboard user={{ role:'admin', username:'root' }} onNavigate={() => {}} />); expect(screen.getByRole('listitem',{name:'Manage Users'}).className).toContain('pointer-events-none'); });
});

describe('DynamicCheckboxGroup direct contract', () => {
  const field={ label:'Skills', options:['React','Django','Docker'] };
  it('shows selected count', () => { render(<DynamicCheckboxGroup field={field} value={['React']} onChange={() => {}} />); expect(screen.getByText('1 of 3 selected')).toBeTruthy(); });
  it('uses field label as group name', () => { render(<DynamicCheckboxGroup field={field} value={[]} onChange={() => {}} />); expect(screen.getByRole('group',{name:'Skills'})).toBeTruthy(); });
  it.each(field.options)('renders option %s', (option) => { render(<DynamicCheckboxGroup field={field} value={[]} onChange={() => {}} />); expect(screen.getByText(option)).toBeTruthy(); });
  it('normalizes comma-separated value', () => { render(<DynamicCheckboxGroup field={field} value="React,Docker" onChange={() => {}} />); expect(screen.getByText('2 of 3 selected')).toBeTruthy(); });
  it('adds an unchecked option', () => { const onChange=vi.fn(); render(<DynamicCheckboxGroup field={field} value={['React']} onChange={onChange} />); fireEvent.click(screen.getByText('Django').closest('label')); expect(onChange).toHaveBeenCalledWith(['React','Django']); });
  it('removes a checked option', () => { const onChange=vi.fn(); render(<DynamicCheckboxGroup field={field} value={['React','Django']} onChange={onChange} />); fireEvent.click(screen.getByText('React').closest('label')); expect(onChange).toHaveBeenCalledWith(['Django']); });
  it('select all sends all options', () => { const onChange=vi.fn(); render(<DynamicCheckboxGroup field={field} value={[]} onChange={onChange} />); fireEvent.click(screen.getByRole('button',{name:'Select all'})); expect(onChange).toHaveBeenCalledWith(field.options); });
  it('clear sends empty array', () => { const onChange=vi.fn(); render(<DynamicCheckboxGroup field={field} value={['React']} onChange={onChange} />); fireEvent.click(screen.getByRole('button',{name:'Clear'})); expect(onChange).toHaveBeenCalledWith([]); });
  it('select all is disabled when complete', () => { render(<DynamicCheckboxGroup field={field} value={field.options} onChange={() => {}} />); expect(screen.getByRole('button',{name:'Select all'}).disabled).toBe(true); });
  it('clear is disabled when empty', () => { render(<DynamicCheckboxGroup field={field} value={[]} onChange={() => {}} />); expect(screen.getByRole('button',{name:'Clear'}).disabled).toBe(true); });
  it('single option omits bulk controls', () => { render(<DynamicCheckboxGroup field={{label:'One',options:['Only']}} value={[]} onChange={() => {}} />); expect(screen.queryByRole('button',{name:'Select all'})).toBeNull(); });
});

describe('notification helper contract', () => {
  it.each(['invitation','update','reminder','info','unknown'])('renders icon for %s', (type) => { const { container }=render(<NotifIcon type={type}/>); expect(container.querySelector('svg')).toBeTruthy(); });
  it('uses invitation background token', () => expect(notifBgColor('invitation')).toBe('rgba(99,102,241,0.15)'));
  it('uses update background token', () => expect(notifBgColor('update')).toBe('rgba(16,185,129,0.15)'));
  it('uses reminder background token', () => expect(notifBgColor('reminder')).toBe('rgba(245,158,11,0.15)'));
  it('uses neutral fallback background', () => expect(notifBgColor('other')).toBe('rgba(100,116,139,0.15)'));
  it('uses invitation text token', () => expect(notifTextColor('invitation')).toBe('#6366f1'));
  it('uses update text token', () => expect(notifTextColor('update')).toBe('#10b981'));
  it('uses reminder text token', () => expect(notifTextColor('reminder')).toBe('#f59e0b'));
  it('uses neutral fallback text token', () => expect(notifTextColor('other')).toBe('#64748b'));
});

describe('committee constants direct contract', () => {
  it('defines four committee types', () => expect(COMMITTEE_TYPES).toHaveLength(4));
  it('defines three project types', () => expect(PROJECT_TYPES).toHaveLength(3));
  it('defines five departments', () => expect(DEPARTMENTS).toHaveLength(5));
  it('defines four committee statuses', () => expect(COMMITTEE_STATUSES).toHaveLength(4));
  it.each([['seminar_1','سيمينار 1'],['seminar_2','سيمينار 2'],['technical','لجنة فنية'],['final_discussion','مناقشة نهائية']])('maps committee %s', (value,label) => expect(getCommitteeTypeLabel(value)).toBe(label));
  it.each([['seasonal','فصلي'],['graduation_1','تخرج 1'],['graduation_2','تخرج 2']])('maps project type %s', (value,label) => expect(getProjectTypeLabel(value)).toBe(label));
  it.each([['software_engineering','برمجيات'],['artificial_intelligence','ذكاء اصطناعي'],['information_security','أمن سيبراني'],['communications','اتصالات'],['control_robotics','تحكم وروبوتات']])('maps department %s', (value,label) => expect(getDepartmentLabel(value)).toBe(label));
  it.each([['draft','مسودة'],['scheduled','مجدولة'],['completed','منجزة'],['cancelled','ملغاة']])('maps status %s', (value,label) => expect(getCommitteeStatusLabel(value)).toBe(label));
  it('falls back for unknown committee type', () => expect(getCommitteeTypeLabel('x')).toBe('x'));
  it('falls back for unknown project type', () => expect(getProjectTypeLabel('x')).toBe('x'));
  it('falls back for unknown department', () => expect(getDepartmentLabel('x')).toBe('x'));
  it('falls back for unknown status', () => expect(getCommitteeStatusLabel('x')).toBe('x'));
  it.each(COMMITTEE_TYPES.map(x=>x.value))('has color token for committee %s', (value) => expect(COMMITTEE_TYPE_COLORS[value]).toMatchObject({bg:expect.any(String),text:expect.any(String),border:expect.any(String)}));
  it.each(DEPARTMENTS.map(x=>x.value))('has color token for department %s', (value) => expect(DEPARTMENT_COLORS[value]).toMatchObject({bg:expect.any(String),text:expect.any(String),border:expect.any(String)}));
  it.each(COMMITTEE_STATUSES.map(x=>x.value))('has color token for status %s', (value) => expect(STATUS_COLORS[value]).toMatchObject({bg:expect.any(String),text:expect.any(String),border:expect.any(String)}));
  it.each(['low','med','high'])('has workload token %s', (value) => expect(WORKLOAD_COLORS[value]).toMatchObject({bg:expect.any(String),text:expect.any(String),label:expect.any(String)}));
  it.each(['warn','info','error'])('has warning token %s', (value) => expect(WARNING_COLORS[value]).toMatchObject({bg:expect.any(String),text:expect.any(String),border:expect.any(String)}));
});
