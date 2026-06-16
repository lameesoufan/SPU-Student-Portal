import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}
// ── Safe Date Formatting ────────────────────────────────────────
// Never returns "Invalid Date" — returns '—' for null/invalid values

export function formatSafeDate(dateString, options) {
  if (!dateString) return '—';
  const d = new Date(dateString);
  if (isNaN(d.getTime())) return '—';

  const defaults = {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  };

  const formatter = new Intl.DateTimeFormat('en-US', { ...defaults, ...options });
  return formatter.format(d);
}

export function formatShortDate(dateString) {
  return formatSafeDate(dateString, { hour: undefined, minute: undefined, hour12: undefined });
}