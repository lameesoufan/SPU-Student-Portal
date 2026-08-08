// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider } from '../../ThemeContext.jsx';

const api = vi.hoisted(() => ({
  login: vi.fn(),
  setAccessToken: vi.fn(),
  studentLoginRequest: vi.fn(),
  studentLoginVerify: vi.fn(),
}));

vi.mock('../../api.jsx', () => api);
vi.mock('../OTPVerification.jsx', () => ({
  default: ({ emailHint, sessionToken, onVerify, onBack, onResend }) => (
    <div data-testid="otp-screen">
      <span data-testid="otp-email">{emailHint}</span>
      <span data-testid="otp-session">{sessionToken}</span>
      <button onClick={() => onVerify(sessionToken, '123456')}>mock verify</button>
      <button onClick={onBack}>mock back</button>
      <button onClick={onResend}>mock resend</button>
    </div>
  ),
}));

import Login from '../Login.jsx';

const renderLogin = (props = {}) => {
  const defaults = {
    onLogin: vi.fn(),
    onRegister: vi.fn(),
    onForgotPassword: vi.fn(),
    ...props,
  };
  const view = render(<ThemeProvider><Login {...defaults} /></ThemeProvider>);
  return { ...view, props: defaults };
};

const fill = (username, password) => {
  fireEvent.change(screen.getByLabelText('Username'), { target: { value: username } });
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: password } });
};

const submit = () => fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));

describe('Login', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    document.documentElement.setAttribute('data-theme', 'light');
  });

  it('renders the username and password controls', () => {
    renderLogin();
    expect(screen.getByLabelText('Username')).toBeTruthy();
    expect(screen.getByLabelText('Password')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeTruthy();
  });

  it('validates both required fields before calling the API', () => {
    renderLogin();
    submit();
    expect(screen.getByText('Please enter your university ID')).toBeTruthy();
    expect(screen.getByText('Please enter your password')).toBeTruthy();
    expect(api.login).not.toHaveBeenCalled();
    expect(api.studentLoginRequest).not.toHaveBeenCalled();
  });

  it('validates a missing password independently', () => {
    renderLogin();
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'doctor1' } });
    submit();
    expect(screen.getByText('Please enter your password')).toBeTruthy();
    expect(screen.queryByText('Please enter your university ID')).toBeNull();
  });

  it('validates a missing username independently', () => {
    renderLogin();
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret123' } });
    submit();
    expect(screen.getByText('Please enter your university ID')).toBeTruthy();
    expect(screen.queryByText('Please enter your password')).toBeNull();
  });

  it('toggles password visibility', () => {
    renderLogin();
    const password = screen.getByLabelText('Password');
    expect(password.getAttribute('type')).toBe('password');
    fireEvent.click(screen.getByRole('button', { name: 'Show password' }));
    expect(password.getAttribute('type')).toBe('text');
    fireEvent.click(screen.getByRole('button', { name: 'Hide password' }));
    expect(password.getAttribute('type')).toBe('password');
  });

  it('invokes the forgot-password navigation callback', () => {
    const { props } = renderLogin();
    fireEvent.click(screen.getByRole('button', { name: 'هل نسيت كلمة المرور؟' }));
    expect(props.onForgotPassword).toHaveBeenCalledTimes(1);
  });

  it('invokes the registration navigation callback', () => {
    const { props } = renderLogin();
    fireEvent.click(screen.getByRole('button', { name: /Create your account/i }));
    expect(props.onRegister).toHaveBeenCalledTimes(1);
  });

  it('uses regular login for a nonnumeric username', async () => {
    api.login.mockResolvedValueOnce({ data: { access: 'token', username: 'dr_ahmad', role: 'doctor', must_change_password: false, must_change_username: false, department: 'ITE' } });
    const { props } = renderLogin();
    fill('dr_ahmad', 'password123');
    submit();
    await waitFor(() => expect(api.login).toHaveBeenCalledWith('dr_ahmad', 'password123'));
    expect(api.studentLoginRequest).not.toHaveBeenCalled();
    expect(api.setAccessToken).toHaveBeenCalledWith('token');
    expect(props.onLogin).toHaveBeenCalledWith(expect.objectContaining({ username: 'dr_ahmad', role: 'doctor', department: 'ITE' }));
  });

  it('trims whitespace before deciding that a numeric username is a student', async () => {
    api.studentLoginRequest.mockResolvedValueOnce({ data: { access: 'student-token', role: 'student' } });
    renderLogin();
    fill('  2026001  ', 'password123');
    submit();
    await waitFor(() => expect(api.studentLoginRequest).toHaveBeenCalledWith('2026001', 'password123'));
    expect(api.login).not.toHaveBeenCalled();
  });

  it('uses the typed username and defaults must_change_username when regular login omits them', async () => {
    api.login.mockResolvedValueOnce({ data: { role: 'hod', access: 'x' } });
    const { props } = renderLogin();
    fill('hod_user', 'password123');
    submit();
    await waitFor(() => expect(props.onLogin).toHaveBeenCalledTimes(1));
    expect(props.onLogin).toHaveBeenCalledWith({
      username: 'hod_user',
      role: 'hod',
      must_change_password: undefined,
      must_change_username: true,
      department: undefined,
    });
  });

  it('shows a backend regular-login error', async () => {
    api.login.mockRejectedValueOnce({ response: { data: { error: 'Account disabled.' } } });
    renderLogin();
    fill('doctor1', 'password123');
    submit();
    expect(await screen.findByText('Account disabled.')).toBeTruthy();
  });

  it('falls back to a safe generic regular-login error', async () => {
    api.login.mockRejectedValueOnce(new Error('offline'));
    renderLogin();
    fill('doctor1', 'password123');
    submit();
    expect(await screen.findByText('Invalid credentials. Please try again.')).toBeTruthy();
  });

  it('moves a first-login student into the OTP screen', async () => {
    api.studentLoginRequest.mockResolvedValueOnce({ data: { session_token: 'session-1', email_hint: 's***@spu.edu', expires_in_seconds: 300 } });
    renderLogin();
    fill('2026001', 'password123');
    submit();
    expect(await screen.findByTestId('otp-screen')).toBeTruthy();
    expect(screen.getByTestId('otp-session').textContent).toBe('session-1');
    expect(screen.getByTestId('otp-email').textContent).toBe('s***@spu.edu');
  });

  it('accepts a direct JWT student login without OTP', async () => {
    api.studentLoginRequest.mockResolvedValueOnce({ data: { access: 'student-token', username: '2026001', role: 'student', must_change_password: false, must_change_username: false, department: 'ITE' } });
    const { props } = renderLogin();
    fill('2026001', 'password123');
    submit();
    await waitFor(() => expect(props.onLogin).toHaveBeenCalledTimes(1));
    expect(api.setAccessToken).toHaveBeenCalledWith('student-token');
    expect(screen.queryByTestId('otp-screen')).toBeNull();
  });

  it('rejects an unexpected student login contract', async () => {
    api.studentLoginRequest.mockResolvedValueOnce({ data: { role: 'student' } });
    renderLogin();
    fill('2026001', 'password123');
    submit();
    expect(await screen.findByText('Invalid credentials. Please try again.')).toBeTruthy();
  });

  it('verifies an OTP and completes student login', async () => {
    api.studentLoginRequest.mockResolvedValueOnce({ data: { session_token: 'session-1', email_hint: 's***@spu.edu', expires_in_seconds: 300 } });
    api.studentLoginVerify.mockResolvedValueOnce({ data: { access: 'verified-token', role: 'student', username: '2026001', must_change_password: false, must_change_username: false, department: 'ITE' } });
    const { props } = renderLogin();
    fill('2026001', 'password123');
    submit();
    await screen.findByTestId('otp-screen');
    fireEvent.click(screen.getByRole('button', { name: 'mock verify' }));
    await waitFor(() => expect(api.studentLoginVerify).toHaveBeenCalledWith('session-1', '123456'));
    expect(api.setAccessToken).toHaveBeenCalledWith('verified-token');
    expect(props.onLogin).toHaveBeenCalledWith(expect.objectContaining({ username: '2026001', role: 'student' }));
  });

  it('back from OTP clears the entered credentials', async () => {
    api.studentLoginRequest.mockResolvedValueOnce({ data: { session_token: 'session-1', email_hint: 'hint', expires_in_seconds: 300 } });
    renderLogin();
    fill('2026001', 'password123');
    submit();
    await screen.findByTestId('otp-screen');
    fireEvent.click(screen.getByRole('button', { name: 'mock back' }));
    expect(screen.getByLabelText('Username').value).toBe('');
    expect(screen.getByLabelText('Password').value).toBe('');
  });

  it('resends OTP with the same student id and password and replaces session data', async () => {
    api.studentLoginRequest
      .mockResolvedValueOnce({ data: { session_token: 'session-1', email_hint: 'old', expires_in_seconds: 300 } })
      .mockResolvedValueOnce({ data: { session_token: 'session-2', email_hint: 'new', expires_in_seconds: 600 } });
    renderLogin();
    fill('2026001', 'password123');
    submit();
    await screen.findByTestId('otp-screen');
    fireEvent.click(screen.getByRole('button', { name: 'mock resend' }));
    await waitFor(() => expect(screen.getByTestId('otp-session').textContent).toBe('session-2'));
    expect(api.studentLoginRequest).toHaveBeenLastCalledWith('2026001', 'password123');
    expect(screen.getByTestId('otp-email').textContent).toBe('new');
  });

  it('scopes dark theme to the login screen without overwriting the global theme', () => {
    renderLogin();
    const themedLogin = screen.getByText('Welcome back').closest('[data-theme="dark"]');
    expect(themedLogin).toBeTruthy();
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });
});
