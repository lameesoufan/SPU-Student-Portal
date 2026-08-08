// @vitest-environment jsdom
import React from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import OTPVerification from '../OTPVerification.jsx';

const renderOtp = (props = {}) => {
  const defaults = {
    emailHint: 's***@spu.edu',
    sessionToken: 'session-1',
    expiresIn: 600,
    onVerify: vi.fn().mockResolvedValue(undefined),
    onBack: vi.fn(),
    onResend: vi.fn().mockResolvedValue(undefined),
    ...props,
  };
  const view = render(<OTPVerification {...defaults} />);
  return { ...view, props: defaults };
};

const otpInputs = () => Array.from(document.querySelectorAll('.otp-input'));
const setOtp = (digits = '123456') => {
  digits.split('').forEach((digit, index) => {
    fireEvent.change(otpInputs()[index], { target: { value: digit } });
  });
};

describe('OTPVerification', () => {
  beforeEach(() => vi.useRealTimers());
  afterEach(() => vi.useRealTimers());

  it('renders the masked email and initial countdown', () => {
    renderOtp({ expiresIn: 125 });
    expect(screen.getByText('s***@spu.edu')).toBeTruthy();
    expect(screen.getByText('Expires in 2:05')).toBeTruthy();
    expect(otpInputs()).toHaveLength(6);
  });

  it('uses ten minutes when expiresIn is missing', () => {
    renderOtp({ expiresIn: undefined });
    expect(screen.getByText('Expires in 10:00')).toBeTruthy();
  });

  it('rejects nondigit characters', () => {
    renderOtp();
    fireEvent.change(otpInputs()[0], { target: { value: 'A' } });
    expect(otpInputs()[0].value).toBe('');
  });

  it('accepts a single digit and focuses the next box', () => {
    renderOtp();
    fireEvent.change(otpInputs()[0], { target: { value: '4' } });
    expect(otpInputs()[0].value).toBe('4');
    expect(document.activeElement).toBe(otpInputs()[1]);
  });

  it('moves focus backward when backspace is pressed on an empty box', () => {
    renderOtp();
    otpInputs()[2].focus();
    fireEvent.keyDown(otpInputs()[2], { key: 'Backspace' });
    expect(document.activeElement).toBe(otpInputs()[1]);
  });

  it('pastes six digits, ignores separators, and verifies immediately', async () => {
    const onVerify = vi.fn().mockResolvedValue(undefined);
    renderOtp({ onVerify });
    fireEvent.paste(otpInputs()[0], { clipboardData: { getData: () => '12-34 56' } });
    await waitFor(() => expect(onVerify).toHaveBeenCalledWith('session-1', '123456'));
    expect(otpInputs().map((input) => input.value).join('')).toBe('123456');
  });

  it('keeps the verify button disabled until all six boxes are filled', () => {
    renderOtp();
    expect(screen.getByRole('button', { name: 'Verify Code' }).disabled).toBe(true);
    '12345'.split('').forEach((digit, index) => fireEvent.change(otpInputs()[index], { target: { value: digit } }));
    expect(screen.getByRole('button', { name: 'Verify Code' }).disabled).toBe(true);
  });

  it('auto-verifies when the sixth digit is entered', async () => {
    const onVerify = vi.fn().mockResolvedValue(undefined);
    renderOtp({ onVerify });
    setOtp();
    await waitFor(() => expect(onVerify).toHaveBeenCalledWith('session-1', '123456'));
  });

  it('shows success state after verification succeeds', async () => {
    renderOtp();
    setOtp();
    expect(await screen.findByText('Verification successful! Logging in...')).toBeTruthy();
    expect(otpInputs().every((input) => input.disabled)).toBe(true);
  });

  it('shows backend verification error and remaining attempts', async () => {
    const onVerify = vi.fn().mockRejectedValue({ response: { data: { error: 'Wrong code.', attempts_remaining: 2 } } });
    renderOtp({ onVerify });
    setOtp();
    expect(await screen.findByText('Wrong code.')).toBeTruthy();
    expect(screen.getByText('2 attempts remaining')).toBeTruthy();
    expect(otpInputs().every((input) => input.value === '')).toBe(true);
    expect(document.activeElement).toBe(otpInputs()[0]);
  });

  it('uses a generic error when verification fails without backend detail', async () => {
    renderOtp({ onVerify: vi.fn().mockRejectedValue(new Error('offline')) });
    setOtp();
    expect(await screen.findByText('Invalid OTP code. Please try again.')).toBeTruthy();
  });

  it('expires the code when the countdown reaches zero', async () => {
    vi.useFakeTimers();
    renderOtp({ expiresIn: 1 });
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(screen.getByText('Code expired')).toBeTruthy();
    expect(otpInputs().every((input) => input.disabled)).toBe(true);
  });

  it('does not allow a manual verification after expiry', async () => {
    vi.useFakeTimers();
    const onVerify = vi.fn().mockResolvedValue(undefined);
    renderOtp({ expiresIn: 1, onVerify });
    setOtp('12345');
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(onVerify).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Verify Code' }).disabled).toBe(true);
  });

  it('keeps resend disabled during the first minute of a fresh ten-minute code', () => {
    renderOtp({ expiresIn: 600 });
    expect(screen.getByRole('button', { name: /Resend Code/ }).disabled).toBe(true);
  });

  it('enables resend after the first minute', async () => {
    vi.useFakeTimers();
    renderOtp({ expiresIn: 600 });
    await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
    expect(screen.getByRole('button', { name: /Resend Code/ }).disabled).toBe(false);
  });

  it('resends, resets the countdown, and clears entered digits', async () => {
    vi.useFakeTimers();
    const onResend = vi.fn().mockResolvedValue(undefined);
    renderOtp({ expiresIn: 60, onResend });
    fireEvent.change(otpInputs()[0], { target: { value: '1' } });
    fireEvent.click(screen.getByRole('button', { name: /Resend Code/ }));
    await act(async () => { await Promise.resolve(); });
    expect(onResend).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Expires in 10:00')).toBeTruthy();
    expect(otpInputs().every((input) => input.value === '')).toBe(true);
  });

  it('shows a resend error without destroying the screen', async () => {
    const onResend = vi.fn().mockRejectedValue({ response: { data: { error: 'Too many requests.' } } });
    renderOtp({ expiresIn: 500, onResend });
    fireEvent.click(screen.getByRole('button', { name: /Resend Code/ }));
    expect(await screen.findByText('Too many requests.')).toBeTruthy();
    expect(screen.getByText('Enter Verification Code')).toBeTruthy();
  });

  it('invokes the back callback', () => {
    const { props } = renderOtp();
    fireEvent.click(screen.getByRole('button', { name: 'Go back' }));
    expect(props.onBack).toHaveBeenCalledTimes(1);
  });
});
