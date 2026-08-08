import { describe, expect, it } from 'vitest';
import { cn, formatSafeDate, formatShortDate } from '../utils.js';

describe('cn', () => {
  it('joins ordinary class names', () => {
    expect(cn('card', 'active')).toBe('card active');
  });

  it('drops falsey conditional class names', () => {
    expect(cn('card', false && 'hidden', null, undefined, 'active')).toBe('card active');
  });

  it('resolves conflicting Tailwind padding classes to the last one', () => {
    expect(cn('px-2', 'px-4')).toBe('px-4');
  });

  it('resolves conflicting Tailwind background classes to the last one', () => {
    expect(cn('bg-red-500', 'bg-blue-500')).toBe('bg-blue-500');
  });

  it('supports object syntax through clsx', () => {
    expect(cn({ active: true, hidden: false }, 'ready')).toBe('active ready');
  });
});

describe('formatSafeDate', () => {
  it.each([null, undefined, '', 'not-a-date'])('returns em dash for invalid value %s', (value) => {
    expect(formatSafeDate(value)).toBe('—');
  });

  it('formats a valid date without returning Invalid Date', () => {
    const result = formatSafeDate('2026-08-07T10:15:00Z', { timeZone: 'UTC' });
    expect(result).not.toBe('Invalid Date');
    expect(result).not.toBe('—');
  });

  it('honors explicit Intl options', () => {
    const result = formatSafeDate('2026-08-07T10:15:00Z', {
      timeZone: 'UTC',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: undefined,
      minute: undefined,
      hour12: undefined,
    });
    expect(result).toBe('08/07/2026');
  });
});

describe('formatShortDate', () => {
  it('returns em dash for an empty value', () => {
    expect(formatShortDate(null)).toBe('—');
  });

  it('omits time for a valid date', () => {
    const result = formatShortDate('2026-08-07T10:15:00Z');
    expect(result).not.toMatch(/10:15|AM|PM/);
    expect(result).toContain('2026');
  });
});
