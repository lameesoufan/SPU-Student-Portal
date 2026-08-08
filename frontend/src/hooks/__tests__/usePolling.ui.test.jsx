// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import usePolling from '../usePolling.js';

const setVisibility = (value) => {
  Object.defineProperty(document, 'visibilityState', { configurable: true, value });
};

const flush = async () => {
  await act(async () => { await Promise.resolve(); });
};

describe('usePolling', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setVisibility('visible');
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('runs the callback immediately on mount', async () => {
    const callback = vi.fn().mockResolvedValue(undefined);
    renderHook(() => usePolling(callback, 1000));
    await flush();
    expect(callback).toHaveBeenCalledTimes(1);
  });

  it('runs again after the configured interval', async () => {
    const callback = vi.fn().mockResolvedValue(undefined);
    renderHook(() => usePolling(callback, 1000));
    await flush();
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(callback).toHaveBeenCalledTimes(2);
  });

  it('does not overlap a pending callback with another tick', async () => {
    let resolve;
    const callback = vi.fn(() => new Promise((r) => { resolve = r; }));
    renderHook(() => usePolling(callback, 1000));
    await flush();
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(callback).toHaveBeenCalledTimes(1);
    await act(async () => { resolve(); await Promise.resolve(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(callback).toHaveBeenCalledTimes(2);
  });

  it('continues polling after callback rejection', async () => {
    const callback = vi.fn()
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValue(undefined);
    renderHook(() => usePolling(callback, 1000));
    await flush();
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(callback).toHaveBeenCalledTimes(2);
  });

  it('pauses the scheduled timer when the tab becomes hidden', async () => {
    const callback = vi.fn().mockResolvedValue(undefined);
    renderHook(() => usePolling(callback, 1000));
    await flush();
    setVisibility('hidden');
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(callback).toHaveBeenCalledTimes(1);
  });

  it('refreshes immediately when the tab becomes visible again', async () => {
    const callback = vi.fn().mockResolvedValue(undefined);
    renderHook(() => usePolling(callback, 1000));
    await flush();
    setVisibility('hidden');
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    setVisibility('visible');
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    await flush();
    expect(callback).toHaveBeenCalledTimes(2);
  });

  it('uses the newest callback without resetting the polling effect', async () => {
    const first = vi.fn().mockResolvedValue(undefined);
    const second = vi.fn().mockResolvedValue(undefined);
    const { rerender } = renderHook(({ cb }) => usePolling(cb, 1000), { initialProps: { cb: first } });
    await flush();
    rerender({ cb: second });
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(first).toHaveBeenCalledTimes(1);
    expect(second).toHaveBeenCalledTimes(1);
  });

  it('restarts polling when the interval changes', async () => {
    const callback = vi.fn().mockResolvedValue(undefined);
    const { rerender } = renderHook(({ interval }) => usePolling(callback, interval), { initialProps: { interval: 1000 } });
    await flush();
    rerender({ interval: 2000 });
    await flush();
    expect(callback).toHaveBeenCalledTimes(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(1999); });
    expect(callback).toHaveBeenCalledTimes(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(callback).toHaveBeenCalledTimes(3);
  });

  it('cancels future polling on unmount', async () => {
    const callback = vi.fn().mockResolvedValue(undefined);
    const { unmount } = renderHook(() => usePolling(callback, 1000));
    await flush();
    unmount();
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(callback).toHaveBeenCalledTimes(1);
  });

  it('removes the visibility listener on unmount', async () => {
    const callback = vi.fn().mockResolvedValue(undefined);
    const spy = vi.spyOn(document, 'removeEventListener');
    const { unmount } = renderHook(() => usePolling(callback, 1000));
    await flush();
    unmount();
    expect(spy).toHaveBeenCalledWith('visibilitychange', expect.any(Function));
  });
});
