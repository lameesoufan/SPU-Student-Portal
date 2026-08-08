import React from 'react';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const state = vi.hoisted(() => ({ theme: 'light', toggleTheme: vi.fn() }));
vi.mock('../../ThemeContext.jsx', () => ({ useTheme: () => state }));
vi.mock('../NotificationBell.jsx', () => ({ default: () => <div data-testid="notification-bell">BELL</div> }));
import Navbar from '../Navbar.jsx';

beforeEach(() => { state.theme = 'light'; state.toggleTheme.mockReset(); });

const user = (role) => ({ username: `${role}-user`, role });

describe('Navbar role-aware presentation', () => {
  it.each([
    ['student', 'Student'], ['doctor', 'Doctor'], ['hod', 'Head of Department'], ['dean', 'Dean'], ['admin', 'Administrator'],
  ])('shows %s role label', (role, label) => { render(<Navbar user={user(role)} onLogout={() => {}} currentPage="dashboard" />); expect(screen.getAllByText(label).length).toBeGreaterThan(0); });
  it.each(['student', 'doctor', 'hod', 'dean'])('shows notification bell for %s', (role) => { render(<Navbar user={user(role)} onLogout={() => {}} />); expect(screen.getByTestId('notification-bell')).toBeTruthy(); });
  it('hides notification bell for admin', () => { render(<Navbar user={user('admin')} onLogout={() => {}} />); expect(screen.queryByTestId('notification-bell')).toBeNull(); });
  it('hides notification bell for an unknown role', () => { render(<Navbar user={user('auditor')} onLogout={() => {}} />); expect(screen.queryByTestId('notification-bell')).toBeNull(); });
  it('shows dashboard breadcrumb as role only', () => { render(<Navbar user={user('doctor')} onLogout={() => {}} currentPage="dashboard" />); expect(within(screen.getByLabelText('Breadcrumbs')).getByText('Doctor')).toBeTruthy(); });
  it('formats a dashed page name in breadcrumb', () => { render(<Navbar user={user('admin')} onLogout={() => {}} currentPage="upload-reference" />); expect(screen.getByText('Administrator / Upload Reference')).toBeTruthy(); });
  it('falls back to literal unknown role in breadcrumb', () => { render(<Navbar user={user('auditor')} onLogout={() => {}} currentPage="dashboard" />); expect(within(screen.getByLabelText('Breadcrumbs')).getByText('auditor')).toBeTruthy(); });
  it('renders username', () => { render(<Navbar user={{ username: 'rana', role: 'student' }} onLogout={() => {}} />); expect(screen.getByText('rana')).toBeTruthy(); });
  it('calls logout handler', () => { const logout = vi.fn(); render(<Navbar user={user('student')} onLogout={logout} />); fireEvent.click(screen.getByRole('button', { name: 'Sign out' })); expect(logout).toHaveBeenCalledTimes(1); });
  it('offers dark-mode switch while light', () => { render(<Navbar user={user('student')} onLogout={() => {}} />); expect(screen.getByRole('button', { name: 'Switch to dark theme' })).toBeTruthy(); });
  it('offers light-mode switch while dark', () => { state.theme = 'dark'; render(<Navbar user={user('student')} onLogout={() => {}} />); expect(screen.getByRole('button', { name: 'Switch to light theme' })).toBeTruthy(); });
  it('invokes theme toggle', () => { render(<Navbar user={user('student')} onLogout={() => {}} />); fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' })); expect(state.toggleTheme).toHaveBeenCalledTimes(1); });
});
