// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const api = vi.hoisted(() => ({
  changeUsername: vi.fn(),
  fetchUsernameSuggestions: vi.fn(),
}));
vi.mock('../../api.jsx', () => api);

import ChangeUsername from '../ChangeUsername.jsx';

const renderPage = (props = {}) => {
  const defaults = { user: { username: 'temporary_user' }, onSuccess: vi.fn(), ...props };
  return { ...render(<ChangeUsername {...defaults} />), props: defaults };
};

describe('ChangeUsername', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.fetchUsernameSuggestions.mockResolvedValue({ data: { suggestions: [] } });
  });

  it('shows the current username', async () => {
    renderPage();
    expect(screen.getByText('temporary_user')).toBeTruthy();
    await waitFor(() => expect(api.fetchUsernameSuggestions).toHaveBeenCalledTimes(1));
  });

  it('loads suggestions and selects the first one by default', async () => {
    api.fetchUsernameSuggestions.mockResolvedValueOnce({ data: { suggestions: ['dr_ahmad', 'ahmad_ite'] } });
    renderPage();
    const input = screen.getByLabelText('New Username');
    await waitFor(() => expect(input.value).toBe('dr_ahmad'));
    expect(screen.getByRole('button', { name: 'ahmad_ite' })).toBeTruthy();
  });

  it('lets the user select another suggestion', async () => {
    api.fetchUsernameSuggestions.mockResolvedValueOnce({ data: { suggestions: ['dr_ahmad', 'ahmad_ite'] } });
    renderPage();
    await screen.findByRole('button', { name: 'ahmad_ite' });
    fireEvent.click(screen.getByRole('button', { name: 'ahmad_ite' }));
    expect(screen.getByLabelText('New Username').value).toBe('ahmad_ite');
  });

  it('continues normally when suggestions cannot be loaded', async () => {
    api.fetchUsernameSuggestions.mockRejectedValueOnce(new Error('offline'));
    renderPage();
    await waitFor(() => expect(api.fetchUsernameSuggestions).toHaveBeenCalledTimes(1));
    expect(screen.getByLabelText('New Username')).toBeTruthy();
    expect(screen.queryByText('اقتراحات')).toBeNull();
  });

  it.each([
    ['', false],
    ['ab', false],
    ['a-b', false],
    ['اسم', false],
    ['abc def', false],
    ['a'.repeat(31), false],
    ['abc', true],
    ['DR_2026', true],
    ['user_name_123', true],
    ['  abc  ', true],
  ])('validates username pattern %s', async (value, valid) => {
    renderPage();
    await waitFor(() => expect(api.fetchUsernameSuggestions).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText('New Username'), { target: { value } });
    expect(screen.getByRole('button', { name: 'تعيين اسم المستخدم' }).disabled).toBe(!valid);
  });


  it('rejects an invalid username even if the form is submitted directly', async () => {
    renderPage();
    await waitFor(() => expect(api.fetchUsernameSuggestions).toHaveBeenCalledTimes(1));
    const input = screen.getByLabelText('New Username');
    fireEvent.change(input, { target: { value: 'bad-name' } });
    fireEvent.submit(input.closest('form'));
    expect(screen.getByText('Username must be 3-30 characters using only English letters, numbers, and underscores.')).toBeTruthy();
    expect(api.changeUsername).not.toHaveBeenCalled();
  });

  it('submits the trimmed valid username', async () => {
    api.changeUsername.mockResolvedValueOnce({ data: { ok: true } });
    const { props } = renderPage();
    await waitFor(() => expect(api.fetchUsernameSuggestions).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText('New Username'), { target: { value: '  doctor_2026  ' } });
    fireEvent.submit(screen.getByLabelText('New Username').closest('form'));
    await waitFor(() => expect(api.changeUsername).toHaveBeenCalledWith('doctor_2026'));
    expect(props.onSuccess).toHaveBeenCalledWith('doctor_2026');
  });

  it('shows a backend username error', async () => {
    api.changeUsername.mockRejectedValueOnce({ response: { data: { error: 'Username already used.' } } });
    renderPage();
    await waitFor(() => expect(api.fetchUsernameSuggestions).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText('New Username'), { target: { value: 'doctor_2026' } });
    fireEvent.click(screen.getByRole('button', { name: 'تعيين اسم المستخدم' }));
    expect(await screen.findByText('Username already used.')).toBeTruthy();
  });

  it('shows a generic error when username change fails without detail', async () => {
    api.changeUsername.mockRejectedValueOnce(new Error('offline'));
    renderPage();
    await waitFor(() => expect(api.fetchUsernameSuggestions).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText('New Username'), { target: { value: 'doctor_2026' } });
    fireEvent.click(screen.getByRole('button', { name: 'تعيين اسم المستخدم' }));
    expect(await screen.findByText('Failed to change username.')).toBeTruthy();
  });

  it('clears a previous server error when the username changes', async () => {
    api.changeUsername.mockRejectedValueOnce({ response: { data: { error: 'Taken.' } } });
    renderPage();
    await waitFor(() => expect(api.fetchUsernameSuggestions).toHaveBeenCalledTimes(1));
    const input = screen.getByLabelText('New Username');
    fireEvent.change(input, { target: { value: 'doctor_2026' } });
    fireEvent.click(screen.getByRole('button', { name: 'تعيين اسم المستخدم' }));
    await screen.findByText('Taken.');
    fireEvent.change(input, { target: { value: 'doctor_2027' } });
    expect(screen.queryByText('Taken.')).toBeNull();
  });

  it('disables submission while the username change is pending', async () => {
    let resolve;
    api.changeUsername.mockReturnValueOnce(new Promise((r) => { resolve = r; }));
    renderPage();
    await waitFor(() => expect(api.fetchUsernameSuggestions).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText('New Username'), { target: { value: 'doctor_2026' } });
    fireEvent.click(screen.getByRole('button', { name: 'تعيين اسم المستخدم' }));
    expect(screen.getByRole('button', { name: /جاري الحفظ/ }).disabled).toBe(true);
    resolve({ data: { ok: true } });
    await waitFor(() => expect(api.changeUsername).toHaveBeenCalledTimes(1));
  });
});
