// @vitest-environment jsdom
import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ThemeProvider, THEME_KEY, useTheme } from '../ThemeContext.jsx';

function ThemeConsumer() {
  const { theme, toggleTheme } = useTheme();
  return <button onClick={toggleTheme}>theme:{theme}</button>;
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    vi.restoreAllMocks();
  });

  it('uses light mode when no saved theme exists', () => {
    render(<ThemeProvider><ThemeConsumer /></ThemeProvider>);
    expect(screen.getByRole('button').textContent).toBe('theme:light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  it('restores a saved dark theme', () => {
    localStorage.setItem(THEME_KEY, 'dark');
    render(<ThemeProvider><ThemeConsumer /></ThemeProvider>);
    expect(screen.getByRole('button').textContent).toBe('theme:dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('restores a saved light theme', () => {
    localStorage.setItem(THEME_KEY, 'light');
    render(<ThemeProvider><ThemeConsumer /></ThemeProvider>);
    expect(screen.getByRole('button').textContent).toBe('theme:light');
  });

  it('ignores an invalid saved theme', () => {
    localStorage.setItem(THEME_KEY, 'neon');
    render(<ThemeProvider><ThemeConsumer /></ThemeProvider>);
    expect(screen.getByRole('button').textContent).toBe('theme:light');
  });

  it('toggles light to dark and persists the choice', () => {
    render(<ThemeProvider><ThemeConsumer /></ThemeProvider>);
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByRole('button').textContent).toBe('theme:dark');
    expect(localStorage.getItem(THEME_KEY)).toBe('dark');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
  });

  it('toggles dark to light and persists the choice', () => {
    localStorage.setItem(THEME_KEY, 'dark');
    render(<ThemeProvider><ThemeConsumer /></ThemeProvider>);
    fireEvent.click(screen.getByRole('button'));
    expect(screen.getByRole('button').textContent).toBe('theme:light');
    expect(localStorage.getItem(THEME_KEY)).toBe('light');
  });

  it('falls back safely when localStorage read fails', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked'); });
    render(<ThemeProvider><ThemeConsumer /></ThemeProvider>);
    expect(screen.getByRole('button').textContent).toBe('theme:light');
  });

  it('still toggles when localStorage write fails', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
    render(<ThemeProvider><ThemeConsumer /></ThemeProvider>);
    expect(() => fireEvent.click(screen.getByRole('button'))).not.toThrow();
    expect(screen.getByRole('button').textContent).toBe('theme:dark');
  });

  it('renders provider children', () => {
    render(<ThemeProvider><span>child-content</span></ThemeProvider>);
    expect(screen.getByText('child-content')).toBeTruthy();
  });

  it('throws when useTheme is used outside ThemeProvider', () => {
    const Broken = () => {
      useTheme();
      return null;
    };
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Broken />)).toThrow('useTheme must be used within a ThemeProvider');
    errorSpy.mockRestore();
  });
});
