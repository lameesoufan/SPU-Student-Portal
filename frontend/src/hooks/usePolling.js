import { useEffect, useRef } from 'react';

/**
 * usePolling — Runs a callback at a fixed interval with smart tab awareness.
 *
 * - Stops polling when the browser tab is hidden (saves API calls).
 * - Resumes polling when the tab becomes visible again.
 * - Uses setTimeout chain instead of setInterval to avoid overlapping calls.
 * - Cleans up automatically on unmount.
 *
 * @param {Function} callback   - Async (or sync) function to call on each tick.
 * @param {number}   intervalMs - Delay between ticks in milliseconds (default 30000 = 30s).
 */
export default function usePolling(callback, intervalMs = 30000) {
  const savedCallback = useRef(callback);

  // Keep the latest callback without restarting the effect
  useEffect(() => {
    savedCallback.current = callback;
  }, [callback]);

  useEffect(() => {
    let active = true;
    let timer = null;

    const tick = async () => {
      if (!active) return;
      try {
        await savedCallback.current();
      } catch {
        // Silently ignore — caller should handle its own errors
      }
      if (active) timer = setTimeout(tick, intervalMs);
    };

    // Start the first tick immediately
    tick();

    // Pause when tab is hidden, resume when visible
    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        clearTimeout(timer);
        tick(); // immediate refresh when returning to tab
      } else {
        clearTimeout(timer);
        timer = null;
      }
    };

    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      active = false;
      clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [intervalMs]);
}
