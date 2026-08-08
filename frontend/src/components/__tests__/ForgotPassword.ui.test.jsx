// @vitest-environment jsdom
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  requestPasswordReset: vi.fn(),
  verifyPasswordResetCode: vi.fn(),
  confirmPasswordReset: vi.fn(),
}));
vi.mock('../../api.jsx', () => api);

import ForgotPassword from '../ForgotPassword.jsx';

const beginReset = async (data = { session_token: 'reset-session', email_hint: 'a***@spu.edu', message: 'sent' }) => {
  api.requestPasswordReset.mockResolvedValueOnce({ data });
  fireEvent.change(screen.getByPlaceholderText('أدخل اسم المستخدم الخاص بك'), { target: { value: '  doctor1  ' } });
  fireEvent.click(screen.getByRole('button', { name: 'إرسال رمز التحقق' }));
  if (data.session_token) await screen.findByText(/a\*\*\*@spu\.edu/);
};

const verify = async () => {
  api.verifyPasswordResetCode.mockResolvedValueOnce({ data: { ok: true } });
  fireEvent.change(screen.getByPlaceholderText('000000'), { target: { value: '123456' } });
  fireEvent.click(screen.getByRole('button', { name: 'التحقق من الرمز' }));
  await screen.findByText('كلمة المرور الجديدة');
};

describe('ForgotPassword', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });
  afterEach(() => vi.useRealTimers());

  it('starts at the account-identification step', () => {
    render(<ForgotPassword onBack={vi.fn()} />);
    expect(screen.getByPlaceholderText('أدخل اسم المستخدم الخاص بك')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'إرسال رمز التحقق' }).disabled).toBe(true);
  });

  it('trims the identifier before requesting a reset', async () => {
    render(<ForgotPassword onBack={vi.fn()} />);
    await beginReset();
    expect(api.requestPasswordReset).toHaveBeenCalledWith('doctor1');
  });

  it('shows backend request errors', async () => {
    api.requestPasswordReset.mockRejectedValueOnce({ response: { data: { error: 'Unknown account.' } } });
    render(<ForgotPassword onBack={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText('أدخل اسم المستخدم الخاص بك'), { target: { value: 'missing' } });
    fireEvent.click(screen.getByRole('button', { name: 'إرسال رمز التحقق' }));
    expect(await screen.findByText('Unknown account.')).toBeTruthy();
  });

  it('moves to verification only when a session token is returned', async () => {
    api.requestPasswordReset.mockResolvedValueOnce({ data: { message: 'Check your email.' } });
    render(<ForgotPassword onBack={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText('أدخل اسم المستخدم الخاص بك'), { target: { value: 'doctor1' } });
    fireEvent.click(screen.getByRole('button', { name: 'إرسال رمز التحقق' }));
    expect(await screen.findByText('Check your email.')).toBeTruthy();
    expect(screen.getByPlaceholderText('أدخل اسم المستخدم الخاص بك')).toBeTruthy();
    expect(screen.queryByPlaceholderText('000000')).toBeNull();
  });

  it('shows the email hint and a 60-second resend cooldown', async () => {
    render(<ForgotPassword onBack={vi.fn()} />);
    await beginReset();
    expect(screen.getByText(/a\*\*\*@spu\.edu/)).toBeTruthy();
    expect(screen.getByRole('button', { name: 'إعادة الإرسال بعد 60 ثانية' }).disabled).toBe(true);
  });

  it('filters nondigits out of the verification code', async () => {
    render(<ForgotPassword onBack={vi.fn()} />);
    await beginReset();
    const code = screen.getByPlaceholderText('000000');
    fireEvent.change(code, { target: { value: '1a2-3x4' } });
    expect(code.value).toBe('1234');
  });

  it('does not enable verification until six digits exist', async () => {
    render(<ForgotPassword onBack={vi.fn()} />);
    await beginReset();
    fireEvent.change(screen.getByPlaceholderText('000000'), { target: { value: '12345' } });
    expect(screen.getByRole('button', { name: 'التحقق من الرمز' }).disabled).toBe(true);
  });

  it('verifies the code with its bound reset session', async () => {
    render(<ForgotPassword onBack={vi.fn()} />);
    await beginReset();
    await verify();
    expect(api.verifyPasswordResetCode).toHaveBeenCalledWith('reset-session', '123456');
  });

  it('shows backend code-verification errors', async () => {
    api.verifyPasswordResetCode.mockRejectedValueOnce({ response: { data: { error: 'Expired code.' } } });
    render(<ForgotPassword onBack={vi.fn()} />);
    await beginReset();
    fireEvent.change(screen.getByPlaceholderText('000000'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: 'التحقق من الرمز' }));
    expect(await screen.findByText('Expired code.')).toBeTruthy();
  });

  it('enables resend after the cooldown and requests a fresh session', async () => {
    vi.useFakeTimers();
    api.requestPasswordReset
      .mockResolvedValueOnce({ data: { session_token: 'session-1', email_hint: 'old' } })
      .mockResolvedValueOnce({ data: { session_token: 'session-2', email_hint: 'new' } });
    render(<ForgotPassword onBack={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText('أدخل اسم المستخدم الخاص بك'), { target: { value: 'doctor1' } });
    fireEvent.click(screen.getByRole('button', { name: 'إرسال رمز التحقق' }));
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
    const resend = screen.getByRole('button', { name: 'إعادة إرسال الرمز' });
    expect(resend.disabled).toBe(false);
    fireEvent.click(resend);
    await act(async () => { await Promise.resolve(); });
    expect(api.requestPasswordReset).toHaveBeenCalledTimes(2);
    expect(screen.getByText(/new/)).toBeTruthy();
  });

  it('rejects mismatched new passwords without calling the reset endpoint', async () => {
    render(<ForgotPassword onBack={vi.fn()} />);
    await beginReset();
    await verify();
    const passwordInputs = Array.from(document.querySelectorAll('input[autocomplete="new-password"]'));
    fireEvent.change(passwordInputs[0], { target: { value: 'StrongPass1' } });
    fireEvent.change(passwordInputs[1], { target: { value: 'Different1' } });
    fireEvent.click(screen.getByRole('button', { name: 'تغيير كلمة المرور' }));
    expect(screen.getByText('كلمتا المرور غير متطابقتين.')).toBeTruthy();
    expect(api.confirmPasswordReset).not.toHaveBeenCalled();
  });

  it('toggles both new-password inputs between password and text', async () => {
    render(<ForgotPassword onBack={vi.fn()} />);
    await beginReset();
    await verify();
    const inputs = Array.from(document.querySelectorAll('input[autocomplete="new-password"]'));
    expect(inputs.every((input) => input.type === 'password')).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'إظهار كلمة المرور' }));
    expect(inputs.every((input) => input.type === 'text')).toBe(true);
  });

  it('submits the reset contract and shows completion', async () => {
    api.confirmPasswordReset.mockResolvedValueOnce({ data: { message: 'Password changed.' } });
    render(<ForgotPassword onBack={vi.fn()} />);
    await beginReset();
    await verify();
    const inputs = Array.from(document.querySelectorAll('input[autocomplete="new-password"]'));
    fireEvent.change(inputs[0], { target: { value: 'StrongPass1' } });
    fireEvent.change(inputs[1], { target: { value: 'StrongPass1' } });
    fireEvent.click(screen.getByRole('button', { name: 'تغيير كلمة المرور' }));
    await waitFor(() => expect(api.confirmPasswordReset).toHaveBeenCalledWith('reset-session', '123456', 'StrongPass1', 'StrongPass1'));
    expect(await screen.findByText('تم تغيير كلمة المرور')).toBeTruthy();
    expect(screen.getByText('Password changed.')).toBeTruthy();
  });

  it('shows backend reset errors and stays on password step', async () => {
    api.confirmPasswordReset.mockRejectedValueOnce({ response: { data: { error: 'Password too common.' } } });
    render(<ForgotPassword onBack={vi.fn()} />);
    await beginReset();
    await verify();
    const inputs = Array.from(document.querySelectorAll('input[autocomplete="new-password"]'));
    fireEvent.change(inputs[0], { target: { value: 'StrongPass1' } });
    fireEvent.change(inputs[1], { target: { value: 'StrongPass1' } });
    fireEvent.click(screen.getByRole('button', { name: 'تغيير كلمة المرور' }));
    expect(await screen.findByText('Password too common.')).toBeTruthy();
    expect(screen.getByText('كلمة المرور الجديدة')).toBeTruthy();
  });

  it('invokes onBack from the flow', () => {
    const onBack = vi.fn();
    render(<ForgotPassword onBack={onBack} />);
    fireEvent.click(screen.getByRole('button', { name: 'العودة إلى تسجيل الدخول' }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });
});
