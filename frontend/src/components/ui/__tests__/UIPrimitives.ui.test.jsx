// @vitest-environment jsdom
import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Button, buttonVariants } from '../button.jsx';
import { Input } from '../input.jsx';
import {
  EmptyState,
  LoadingState,
  PageAlert,
  PageCard,
  PageHeader,
  PageShell,
  StatCard,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from '../PagePrimitives.jsx';
import { NotifIcon, notifBgColor, notifTextColor } from '../../NotifHelpers.jsx';

const TestIcon = ({ size }) => <svg data-testid="test-icon" data-size={size} />;

describe('Button', () => {
  it('renders a native button and forwards click events', () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save</Button>);
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('applies the default variant and size classes', () => {
    render(<Button>Save</Button>);
    const button = screen.getByRole('button');
    expect(button.className).toContain('bg-violet-600');
    expect(button.className).toContain('h-10');
  });

  it.each([
    ['outline', 'border-violet-600'],
    ['ghost', 'hover:bg-slate-100'],
    ['destructive', 'bg-red-600'],
  ])('applies the %s variant', (variant, expected) => {
    render(<Button variant={variant}>Action</Button>);
    expect(screen.getByRole('button').className).toContain(expected);
  });

  it.each([
    ['sm', 'h-8'],
    ['lg', 'h-12'],
  ])('applies the %s size', (size, expected) => {
    render(<Button size={size}>Action</Button>);
    expect(screen.getByRole('button').className).toContain(expected);
  });

  it('merges a custom class name without losing defaults', () => {
    render(<Button className="custom-class">Action</Button>);
    const button = screen.getByRole('button');
    expect(button.className).toContain('custom-class');
    expect(button.className).toContain('rounded-lg');
  });

  it('forwards refs to the native button', () => {
    const ref = React.createRef();
    render(<Button ref={ref}>Action</Button>);
    expect(ref.current).toBe(screen.getByRole('button'));
  });

  it('exports all supported variant maps', () => {
    expect(Object.keys(buttonVariants.variant).sort()).toEqual(['default', 'destructive', 'ghost', 'outline']);
    expect(Object.keys(buttonVariants.size).sort()).toEqual(['default', 'lg', 'sm']);
  });
});

describe('Input', () => {
  it('forwards type, value, and change events', () => {
    const onChange = vi.fn();
    render(<Input aria-label="field" type="email" value="a@b.com" onChange={onChange} />);
    const input = screen.getByLabelText('field');
    expect(input.type).toBe('email');
    expect(input.value).toBe('a@b.com');
    fireEvent.change(input, { target: { value: 'c@d.com' } });
    expect(onChange).toHaveBeenCalledTimes(1);
  });

  it('merges custom classes and forwards refs', () => {
    const ref = React.createRef();
    render(<Input ref={ref} aria-label="field" className="special-input" />);
    const input = screen.getByLabelText('field');
    expect(input.className).toContain('special-input');
    expect(input.className).toContain('h-10');
    expect(ref.current).toBe(input);
  });
});

describe('Page primitives', () => {
  it('renders PageShell in RTL with custom width and class', () => {
    const { container } = render(<PageShell maxWidth="max-w-3xl" className="page-extra">Body</PageShell>);
    const root = container.firstElementChild;
    expect(root.getAttribute('dir')).toBe('rtl');
    expect(root.className).toContain('page-extra');
    expect(root.firstElementChild.className).toContain('max-w-3xl');
  });

  it('renders PageHeader title, description, badge, icon, and actions', () => {
    render(<PageHeader icon={TestIcon} title="Projects" description="Current work" badge="7" actions={<button>New</button>} />);
    expect(screen.getByRole('heading', { name: 'Projects' })).toBeTruthy();
    expect(screen.getByText('Current work')).toBeTruthy();
    expect(screen.getByText('7')).toBeTruthy();
    expect(screen.getByTestId('test-icon').getAttribute('data-size')).toBe('21');
    expect(screen.getByRole('button', { name: 'New' })).toBeTruthy();
  });

  it('omits optional PageHeader regions when not supplied', () => {
    render(<PageHeader title="Projects" />);
    expect(screen.getByRole('heading', { name: 'Projects' })).toBeTruthy();
    expect(screen.queryByTestId('test-icon')).toBeNull();
  });

  it('pads PageCard by default and can disable padding', () => {
    const { rerender, container } = render(<PageCard>Card</PageCard>);
    expect(container.firstElementChild.className).toContain('p-4');
    rerender(<PageCard padded={false}>Card</PageCard>);
    expect(container.firstElementChild.className).not.toContain('p-4');
  });

  it('renders error PageAlert styling by default', () => {
    const { container } = render(<PageAlert>Failed</PageAlert>);
    expect(screen.getByText('Failed')).toBeTruthy();
    expect(container.firstElementChild.className).toContain('danger-bg');
  });

  it('renders success PageAlert styling', () => {
    const { container } = render(<PageAlert type="success">Done</PageAlert>);
    expect(screen.getByText('Done')).toBeTruthy();
    expect(container.firstElementChild.className).toContain('success-bg');
  });

  it('uses the default loading label and supports a custom one', () => {
    const { rerender } = render(<LoadingState />);
    expect(screen.getByText('جاري التحميل...')).toBeTruthy();
    rerender(<LoadingState label="Loading grades" />);
    expect(screen.getByText('Loading grades')).toBeTruthy();
  });

  it('uses default EmptyState content', () => {
    render(<EmptyState />);
    expect(screen.getByText('لا توجد بيانات')).toBeTruthy();
  });

  it('renders custom EmptyState icon, title, and description', () => {
    render(<EmptyState icon={TestIcon} title="No projects" description="Nothing assigned" />);
    expect(screen.getByText('No projects')).toBeTruthy();
    expect(screen.getByText('Nothing assigned')).toBeTruthy();
    expect(screen.getByTestId('test-icon').getAttribute('data-size')).toBe('25');
  });

  it.each([
    ['primary', 'primary-light'],
    ['success', 'success-bg'],
    ['warning', 'warning-bg'],
    ['danger', 'danger-bg'],
    ['unknown', 'primary-light'],
  ])('renders StatCard tone %s', (tone, expected) => {
    render(<StatCard label="Open" value="12" icon={TestIcon} tone={tone} />);
    expect(screen.getByText('12')).toBeTruthy();
    expect(screen.getByText('Open')).toBeTruthy();
    expect(screen.getByTestId('test-icon').parentElement.className).toContain(expected);
  });

  it('exports shared form/button class contracts', () => {
    expect(inputClass).toContain('focus:border-[var(--primary)]');
    expect(primaryButtonClass).toBe('btn btn-primary');
    expect(secondaryButtonClass).toContain('btn btn-ghost');
  });
});

describe('notification presentation helpers', () => {
  it.each([
    ['invitation', 'rgba(99,102,241,0.15)', '#6366f1'],
    ['update', 'rgba(16,185,129,0.15)', '#10b981'],
    ['reminder', 'rgba(245,158,11,0.15)', '#f59e0b'],
    ['other', 'rgba(100,116,139,0.15)', '#64748b'],
  ])('maps %s notification colors', (type, background, text) => {
    expect(notifBgColor(type)).toBe(background);
    expect(notifTextColor(type)).toBe(text);
  });

  it.each(['invitation', 'update', 'reminder', 'info', 'unknown'])('renders an icon for %s notifications', (type) => {
    const { container, unmount } = render(<NotifIcon type={type} />);
    expect(container.querySelector('svg')).toBeTruthy();
    unmount();
  });
});
