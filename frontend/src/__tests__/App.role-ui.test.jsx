import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ fetchCurrentUser: vi.fn(), logoutUser: vi.fn(), clearAccessToken: vi.fn() }));
vi.mock('../api.jsx', () => ({ ...api }));
vi.mock('../components/Login.jsx', () => ({ default: ({ onLogin, onRegister, onForgotPassword }) => <div>LOGIN<button onClick={() => onLogin({ username: 'logged', role: 'student' })}>DO LOGIN</button><button onClick={onRegister}>REGISTER</button><button onClick={onForgotPassword}>FORGOT</button></div> }));
vi.mock('../components/SelfRegister.jsx', () => ({ default: ({ onRegistered, onBack }) => <div>REGISTER SCREEN<button onClick={() => onRegistered({ username: 'new', role: 'student' })}>REGISTERED</button><button onClick={onBack}>BACK LOGIN</button></div> }));
vi.mock('../components/ForgotPassword.jsx', () => ({ default: ({ onBack }) => <div>FORGOT SCREEN<button onClick={onBack}>BACK LOGIN</button></div> }));
vi.mock('../components/ChangePassword.jsx', () => ({ default: ({ onSuccess }) => <div>FORCED PASSWORD<button onClick={onSuccess}>PASSWORD DONE</button></div> }));
vi.mock('../components/ChangeUsername.jsx', () => ({ default: ({ onSuccess }) => <div>FORCED USERNAME<button onClick={() => onSuccess('permanent-name')}>USERNAME DONE</button></div> }));
vi.mock('../components/StudentDashboard.jsx', () => ({ default: ({ user, onLogout }) => <div>STUDENT DASH {user.username}<button onClick={onLogout}>LOGOUT</button></div> }));
vi.mock('../components/DoctorDashboard.jsx', () => ({ default: ({ user, onLogout }) => <div>DOCTOR DASH {user.username}<button onClick={onLogout}>LOGOUT</button></div> }));
vi.mock('../components/HodDashboard.jsx', () => ({ default: ({ user, onLogout }) => <div>HOD DASH {user.username}<button onClick={onLogout}>LOGOUT</button></div> }));
vi.mock('../components/DeanDashboard.jsx', () => ({ default: ({ user, onLogout }) => <div>DEAN DASH {user.username}<button onClick={onLogout}>LOGOUT</button></div> }));
vi.mock('../components/Navbar.jsx', () => ({ default: ({ user, onLogout }) => <div>FALLBACK NAV {user.role}<button onClick={onLogout}>LOGOUT</button></div> }));
vi.mock('../components/Dashboard.jsx', () => ({ default: ({ user }) => <div>GENERIC DASH {user.role}</div> }));
vi.mock('../components/ImportUsers.jsx', () => ({ default: () => <div>IMPORT USERS</div> }));
vi.mock('../components/AssignHod.jsx', () => ({ default: () => <div>ASSIGN HOD</div> }));
vi.mock('../components/UploadReference.jsx', () => ({ default: () => <div>UPLOAD REFERENCE</div> }));
import App from '../App.jsx';

beforeEach(() => { vi.clearAllMocks(); api.logoutUser.mockResolvedValue({}); });
async function renderWithUser(user) { api.fetchCurrentUser.mockResolvedValue({ data: user }); render(<App />); return screen.findByText(new RegExp(`${user.role === 'student' ? 'STUDENT' : user.role === 'doctor' ? 'DOCTOR' : user.role === 'hod' ? 'HOD' : user.role === 'dean' ? 'DEAN' : 'GENERIC'} DASH`, 'i')); }

describe('App authentication and role routing', () => {
  it('shows bootstrap loader before session check resolves', () => { api.fetchCurrentUser.mockReturnValue(new Promise(() => {})); const { container } = render(<App />); expect(container.querySelector('.spinner')).toBeTruthy(); });
  it('shows login when session restore fails', async () => { api.fetchCurrentUser.mockRejectedValue(new Error('401')); render(<App />); expect(await screen.findByText('LOGIN')).toBeTruthy(); });
  it('shows login when session response has no user data', async () => { api.fetchCurrentUser.mockResolvedValue({ data: null }); render(<App />); expect(await screen.findByText('LOGIN')).toBeTruthy(); });
  it.each([
    ['student', 'STUDENT DASH'], ['doctor', 'DOCTOR DASH'], ['hod', 'HOD DASH'], ['dean', 'DEAN DASH'],
  ])('routes restored %s session to its dashboard', async (role, text) => { api.fetchCurrentUser.mockResolvedValue({ data: { username: role, role } }); render(<App />); expect(await screen.findByText(new RegExp(text))).toBeTruthy(); });
  it('routes admin to generic administrative shell', async () => { api.fetchCurrentUser.mockResolvedValue({ data: { username: 'admin', role: 'admin' } }); render(<App />); expect(await screen.findByText('GENERIC DASH admin')).toBeTruthy(); });
  it('routes unknown role to generic fallback shell', async () => { api.fetchCurrentUser.mockResolvedValue({ data: { username: 'x', role: 'auditor' } }); render(<App />); expect(await screen.findByText('GENERIC DASH auditor')).toBeTruthy(); });
  it('forces password change before student dashboard', async () => { api.fetchCurrentUser.mockResolvedValue({ data: { username: 's', role: 'student', must_change_password: true } }); render(<App />); expect(await screen.findByText('FORCED PASSWORD')).toBeTruthy(); expect(screen.queryByText(/STUDENT DASH/)).toBeNull(); });
  it('forces password change before doctor username change', async () => { api.fetchCurrentUser.mockResolvedValue({ data: { username: 'd', role: 'doctor', must_change_password: true, must_change_username: true } }); render(<App />); expect(await screen.findByText('FORCED PASSWORD')).toBeTruthy(); });
  it('continues to username change after forced password for doctor', async () => { api.fetchCurrentUser.mockResolvedValue({ data: { username: 'd', role: 'doctor', must_change_password: true, must_change_username: true } }); render(<App />); fireEvent.click(await screen.findByText('PASSWORD DONE')); expect(await screen.findByText('FORCED USERNAME')).toBeTruthy(); });
  it('forces username change for imported doctor', async () => { api.fetchCurrentUser.mockResolvedValue({ data: { username: 'temp', role: 'doctor', must_change_username: true } }); render(<App />); expect(await screen.findByText('FORCED USERNAME')).toBeTruthy(); });
  it('forces username change for imported HoD', async () => { api.fetchCurrentUser.mockResolvedValue({ data: { username: 'temp', role: 'hod', must_change_username: true } }); render(<App />); expect(await screen.findByText('FORCED USERNAME')).toBeTruthy(); });
  it('does not force username workflow for student', async () => { api.fetchCurrentUser.mockResolvedValue({ data: { username: 's', role: 'student', must_change_username: true } }); render(<App />); expect(await screen.findByText(/STUDENT DASH/)).toBeTruthy(); });
  it('does not force username workflow for dean', async () => { api.fetchCurrentUser.mockResolvedValue({ data: { username: 'dean', role: 'dean', must_change_username: true } }); render(<App />); expect(await screen.findByText(/DEAN DASH/)).toBeTruthy(); });
  it('uses permanent username after username flow succeeds', async () => { api.fetchCurrentUser.mockResolvedValue({ data: { username: 'temp', role: 'doctor', must_change_username: true } }); render(<App />); fireEvent.click(await screen.findByText('USERNAME DONE')); expect(await screen.findByText('DOCTOR DASH permanent-name')).toBeTruthy(); });
  it('login callback enters role dashboard', async () => { api.fetchCurrentUser.mockRejectedValue(new Error('401')); render(<App />); fireEvent.click(await screen.findByText('DO LOGIN')); expect(await screen.findByText('STUDENT DASH logged')).toBeTruthy(); });
  it('opens registration from login', async () => { api.fetchCurrentUser.mockRejectedValue(new Error('401')); render(<App />); fireEvent.click(await screen.findByText('REGISTER')); expect(await screen.findByText('REGISTER SCREEN')).toBeTruthy(); });
  it('registration callback enters student dashboard', async () => { api.fetchCurrentUser.mockRejectedValue(new Error('401')); render(<App />); fireEvent.click(await screen.findByText('REGISTER')); fireEvent.click(screen.getByText('REGISTERED')); expect(await screen.findByText('STUDENT DASH new')).toBeTruthy(); });
  it('can return from registration to login', async () => { api.fetchCurrentUser.mockRejectedValue(new Error('401')); render(<App />); fireEvent.click(await screen.findByText('REGISTER')); fireEvent.click(screen.getByText('BACK LOGIN')); expect(await screen.findByText('LOGIN')).toBeTruthy(); });
  it('opens forgot-password from login', async () => { api.fetchCurrentUser.mockRejectedValue(new Error('401')); render(<App />); fireEvent.click(await screen.findByText('FORGOT')); expect(await screen.findByText('FORGOT SCREEN')).toBeTruthy(); });
  it('can return from forgot-password to login', async () => { api.fetchCurrentUser.mockRejectedValue(new Error('401')); render(<App />); fireEvent.click(await screen.findByText('FORGOT')); fireEvent.click(screen.getByText('BACK LOGIN')); expect(await screen.findByText('LOGIN')).toBeTruthy(); });
  it('logout calls backend logout', async () => { api.fetchCurrentUser.mockResolvedValue({ data: { username: 's', role: 'student' } }); render(<App />); fireEvent.click(await screen.findByText('LOGOUT')); await act(async () => {}); expect(api.logoutUser).toHaveBeenCalledTimes(1); });
  it('logout clears in-memory access token', async () => { api.fetchCurrentUser.mockResolvedValue({ data: { username: 's', role: 'student' } }); render(<App />); fireEvent.click(await screen.findByText('LOGOUT')); await act(async () => {}); expect(api.clearAccessToken).toHaveBeenCalledTimes(1); });
  it('logout returns to login screen', async () => { api.fetchCurrentUser.mockResolvedValue({ data: { username: 's', role: 'student' } }); render(<App />); fireEvent.click(await screen.findByText('LOGOUT')); expect(await screen.findByText('LOGIN')).toBeTruthy(); });
  it('logout still clears local session if backend logout fails', async () => { api.logoutUser.mockRejectedValue(new Error('network')); api.fetchCurrentUser.mockResolvedValue({ data: { username: 's', role: 'student' } }); render(<App />); fireEvent.click(await screen.findByText('LOGOUT')); expect(await screen.findByText('LOGIN')).toBeTruthy(); expect(api.clearAccessToken).toHaveBeenCalled(); });
  it('restores session exactly once on mount', async () => { api.fetchCurrentUser.mockResolvedValue({ data: { username: 's', role: 'student' } }); render(<App />); await screen.findByText(/STUDENT DASH/); expect(api.fetchCurrentUser).toHaveBeenCalledTimes(1); });
});
