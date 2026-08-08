// @vitest-environment jsdom
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({ changePassword: vi.fn() }));
vi.mock('../../api.jsx', () => api);

import ChangePassword from '../ChangePassword.jsx';

const passwordInputs = () => Array.from(document.querySelectorAll('input'));

describe('ChangePassword', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
  });
  afterEach(() => vi.useRealTimers());

  it('hides current-password and cancel controls during forced password change', () => {
    render(<ChangePassword user={{ must_change_password: true }} onBack={vi.fn()} />);
    expect(screen.queryByText('كلمة المرور الحالية')).toBeNull();
    expect(screen.queryByRole('button', { name: 'إلغاء' })).toBeNull();
    expect(passwordInputs()).toHaveLength(2);
  });

  it('shows current-password and cancel controls for voluntary password change', () => {
    render(<ChangePassword user={{ must_change_password: false }} onBack={vi.fn()} />);
    expect(screen.getByText('كلمة المرور الحالية')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'إلغاء' })).toBeTruthy();
    expect(passwordInputs()).toHaveLength(3);
  });

  it('invokes onBack when cancel is available', () => {
    const onBack = vi.fn();
    render(<ChangePassword user={{ must_change_password: false }} onBack={onBack} />);
    fireEvent.click(screen.getByRole('button', { name: 'إلغاء' }));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it('rejects mismatched confirmation before calling the API', () => {
    render(<ChangePassword user={{ must_change_password: true }} />);
    const [next, confirm] = passwordInputs();
    fireEvent.change(next, { target: { value: 'StrongPass1' } });
    fireEvent.change(confirm, { target: { value: 'Different1' } });
    fireEvent.click(screen.getByRole('button', { name: 'حفظ كلمة المرور الجديدة' }));
    expect(screen.getByText('كلمتا المرور غير متطابقتين.')).toBeTruthy();
    expect(api.changePassword).not.toHaveBeenCalled();
  });

  it('submits current, new, and confirmation passwords in voluntary mode', async () => {
    api.changePassword.mockResolvedValueOnce({ data: { ok: true } });
    render(<ChangePassword user={{ must_change_password: false }} />);
    const [current, next, confirm] = passwordInputs();
    fireEvent.change(current, { target: { value: 'OldPass1' } });
    fireEvent.change(next, { target: { value: 'NewStrong1' } });
    fireEvent.change(confirm, { target: { value: 'NewStrong1' } });
    fireEvent.click(screen.getByRole('button', { name: 'حفظ كلمة المرور الجديدة' }));
    await waitFor(() => expect(api.changePassword).toHaveBeenCalledWith('NewStrong1', 'NewStrong1', 'OldPass1'));
  });

  it('submits an empty current password in forced mode', async () => {
    api.changePassword.mockResolvedValueOnce({ data: { ok: true } });
    render(<ChangePassword user={{ must_change_password: true }} />);
    const [next, confirm] = passwordInputs();
    fireEvent.change(next, { target: { value: 'NewStrong1' } });
    fireEvent.change(confirm, { target: { value: 'NewStrong1' } });
    fireEvent.click(screen.getByRole('button', { name: 'حفظ كلمة المرور الجديدة' }));
    await waitFor(() => expect(api.changePassword).toHaveBeenCalledWith('NewStrong1', 'NewStrong1', ''));
  });

  it('shows success and clears all fields after a successful change', async () => {
    api.changePassword.mockResolvedValueOnce({ data: { ok: true } });
    render(<ChangePassword user={{ must_change_password: false }} />);
    const [current, next, confirm] = passwordInputs();
    fireEvent.change(current, { target: { value: 'OldPass1' } });
    fireEvent.change(next, { target: { value: 'NewStrong1' } });
    fireEvent.change(confirm, { target: { value: 'NewStrong1' } });
    fireEvent.click(screen.getByRole('button', { name: 'حفظ كلمة المرور الجديدة' }));
    expect(await screen.findByText('تم تغيير كلمة المرور بنجاح.')).toBeTruthy();
    expect(passwordInputs().every((input) => input.value === '')).toBe(true);
  });

  it('calls onSuccess after the success delay', async () => {
    vi.useFakeTimers();
    api.changePassword.mockResolvedValueOnce({ data: { ok: true } });
    const onSuccess = vi.fn();
    render(<ChangePassword user={{ must_change_password: true }} onSuccess={onSuccess} />);
    const [next, confirm] = passwordInputs();
    fireEvent.change(next, { target: { value: 'NewStrong1' } });
    fireEvent.change(confirm, { target: { value: 'NewStrong1' } });
    fireEvent.click(screen.getByRole('button', { name: 'حفظ كلمة المرور الجديدة' }));
    await act(async () => { await Promise.resolve(); });
    expect(onSuccess).not.toHaveBeenCalled();
    await act(async () => { await vi.advanceTimersByTimeAsync(700); });
    expect(onSuccess).toHaveBeenCalledTimes(1);
  });

  it('shows a backend password error', async () => {
    api.changePassword.mockRejectedValueOnce({ response: { data: { error: 'Current password is incorrect.' } } });
    render(<ChangePassword user={{ must_change_password: true }} />);
    const [next, confirm] = passwordInputs();
    fireEvent.change(next, { target: { value: 'NewStrong1' } });
    fireEvent.change(confirm, { target: { value: 'NewStrong1' } });
    fireEvent.click(screen.getByRole('button', { name: 'حفظ كلمة المرور الجديدة' }));
    expect(await screen.findByText('Current password is incorrect.')).toBeTruthy();
  });

  it('uses a generic password error when the backend has no detail', async () => {
    api.changePassword.mockRejectedValueOnce(new Error('offline'));
    render(<ChangePassword user={{ must_change_password: true }} />);
    const [next, confirm] = passwordInputs();
    fireEvent.change(next, { target: { value: 'NewStrong1' } });
    fireEvent.change(confirm, { target: { value: 'NewStrong1' } });
    fireEvent.click(screen.getByRole('button', { name: 'حفظ كلمة المرور الجديدة' }));
    expect(await screen.findByText('تعذر تغيير كلمة المرور.')).toBeTruthy();
  });

  it('toggles visibility for every password field', () => {
    render(<ChangePassword user={{ must_change_password: false }} />);
    expect(passwordInputs().every((input) => input.type === 'password')).toBe(true);
    const toggle = document.querySelector('button[type="button"]');
    fireEvent.click(toggle);
    expect(passwordInputs().every((input) => input.type === 'text')).toBe(true);
  });

  it('disables the submit button while the request is pending', async () => {
    let resolve;
    api.changePassword.mockReturnValueOnce(new Promise((r) => { resolve = r; }));
    render(<ChangePassword user={{ must_change_password: true }} />);
    const [next, confirm] = passwordInputs();
    fireEvent.change(next, { target: { value: 'NewStrong1' } });
    fireEvent.change(confirm, { target: { value: 'NewStrong1' } });
    fireEvent.click(screen.getByRole('button', { name: 'حفظ كلمة المرور الجديدة' }));
    expect(screen.getByRole('button', { name: 'جاري الحفظ...' }).disabled).toBe(true);
    resolve({ data: { ok: true } });
    await waitFor(() => expect(screen.getByText('تم تغيير كلمة المرور بنجاح.')).toBeTruthy());
  });
});
