// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import usePageHistory from '../usePageHistory.js';

describe('usePageHistory', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/');
    vi.restoreAllMocks();
  });

  it('defaults to the dashboard page', () => {
    const { result } = renderHook(() => usePageHistory());
    expect(result.current[0]).toBe('dashboard');
  });

  it('accepts a custom initial page', () => {
    const { result } = renderHook(() => usePageHistory('projects'));
    expect(result.current[0]).toBe('projects');
  });

  it('replaces browser history state on mount', () => {
    const spy = vi.spyOn(window.history, 'replaceState');
    renderHook(() => usePageHistory('grades'));
    expect(spy).toHaveBeenCalledWith({ page: 'grades' }, '');
  });

  it('pushes a new state when changing page', () => {
    const spy = vi.spyOn(window.history, 'pushState');
    const { result } = renderHook(() => usePageHistory('dashboard'));
    act(() => result.current[1]('committees'));
    expect(result.current[0]).toBe('committees');
    expect(spy).toHaveBeenCalledWith({ page: 'committees' }, '');
  });

  it('restores the page from popstate state', () => {
    const { result } = renderHook(() => usePageHistory('dashboard'));
    act(() => window.dispatchEvent(new PopStateEvent('popstate', { state: { page: 'workflow' } })));
    expect(result.current[0]).toBe('workflow');
  });

  it('falls back to the initial page when popstate has no page', () => {
    const { result } = renderHook(() => usePageHistory('projects'));
    act(() => result.current[1]('grades'));
    act(() => window.dispatchEvent(new PopStateEvent('popstate', { state: null })));
    expect(result.current[0]).toBe('projects');
  });

  it('goBack delegates to browser history', () => {
    const spy = vi.spyOn(window.history, 'back').mockImplementation(() => {});
    const { result } = renderHook(() => usePageHistory());
    act(() => result.current[2]());
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it('removes the popstate listener when unmounted', () => {
    const spy = vi.spyOn(window, 'removeEventListener');
    const { unmount } = renderHook(() => usePageHistory());
    unmount();
    expect(spy).toHaveBeenCalledWith('popstate', expect.any(Function));
  });
});
