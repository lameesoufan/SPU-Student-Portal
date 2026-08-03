import React from 'react';
import {
  AlertCircle,
  CheckCircle2,
  Inbox,
  Loader2,
} from 'lucide-react';

export function PageShell({ children, className = '', maxWidth = 'max-w-7xl' }) {
  return (
    <div className={`w-full bg-[var(--bg-primary)] px-3 py-5 text-[var(--text)] sm:px-5 lg:px-6 ${className}`} dir="rtl">
      <div className={`mx-auto w-full ${maxWidth}`}>{children}</div>
    </div>
  );
}

export function PageHeader({ icon: Icon, title, description, badge, actions }) {
  return (
    <header className="mb-5 flex flex-col gap-4 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-[var(--shadow-sm)] sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        {Icon && (
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--primary-light)] text-[var(--primary)]">
            <Icon size={21} />
          </div>
        )}
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="m-0 text-xl font-black text-[var(--text)] sm:text-2xl">{title}</h1>
            {badge != null && (
              <span className="rounded-full bg-[var(--primary-light)] px-2.5 py-1 text-xs font-bold text-[var(--primary)]">
                {badge}
              </span>
            )}
          </div>
          {description && (
            <p className="m-0 mt-1 text-sm leading-6 text-[var(--text-muted)]">{description}</p>
          )}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function PageCard({ children, className = '', padded = true }) {
  return (
    <section className={`rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-[var(--shadow-sm)] ${padded ? 'p-4 sm:p-5' : ''} ${className}`}>
      {children}
    </section>
  );
}

export function PageAlert({ type = 'error', children, className = '' }) {
  const success = type === 'success';
  const Icon = success ? CheckCircle2 : AlertCircle;
  return (
    <div
      className={`flex items-start gap-2 rounded-xl border px-4 py-3 text-sm leading-6 ${
        success
          ? 'border-[var(--success-border)] bg-[var(--success-bg)] text-[var(--success-text)]'
          : 'border-[var(--danger-border)] bg-[var(--danger-bg)] text-[var(--danger-text)]'
      } ${className}`}
    >
      <Icon size={17} className="mt-0.5 shrink-0" />
      <div>{children}</div>
    </div>
  );
}

export function LoadingState({ label = 'جاري التحميل...' }) {
  return (
    <div className="flex min-h-[280px] flex-col items-center justify-center gap-3 text-center text-[var(--text-muted)]" dir="rtl">
      <Loader2 size={28} className="animate-spin text-[var(--primary)]" />
      <span className="text-sm font-medium">{label}</span>
    </div>
  );
}

export function EmptyState({ icon: Icon = Inbox, title = 'لا توجد بيانات', description }) {
  return (
    <div className="flex min-h-[240px] flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-[var(--border-dark)] bg-[var(--card)] px-6 py-10 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--primary-light)] text-[var(--primary)]">
        <Icon size={25} />
      </div>
      <div className="text-base font-black text-[var(--text)]">{title}</div>
      {description && <p className="m-0 max-w-md text-sm leading-6 text-[var(--text-muted)]">{description}</p>}
    </div>
  );
}

export function StatCard({ label, value, icon: Icon, tone = 'primary' }) {
  const toneClass = {
    primary: 'bg-[var(--primary-light)] text-[var(--primary)]',
    success: 'bg-[var(--success-bg)] text-[var(--success-text)]',
    warning: 'bg-[var(--warning-bg)] text-[var(--warning-text)]',
    danger: 'bg-[var(--danger-bg)] text-[var(--danger-text)]',
  }[tone] || 'bg-[var(--primary-light)] text-[var(--primary)]';

  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-[var(--shadow-sm)]">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-2xl font-black text-[var(--text)]">{value}</div>
          <div className="mt-1 text-xs font-medium text-[var(--text-muted)]">{label}</div>
        </div>
        {Icon && <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${toneClass}`}><Icon size={19} /></div>}
      </div>
    </div>
  );
}

export const inputClass = 'w-full rounded-xl border border-[var(--border)] bg-[var(--bg-input)] px-3.5 py-2.5 text-sm text-[var(--text)] outline-none transition placeholder:text-[var(--text-faint)] focus:border-[var(--primary)] focus:ring-4 focus:ring-[var(--primary-light)]';
export const primaryButtonClass = 'btn btn-primary';
export const secondaryButtonClass = 'btn btn-ghost border border-[var(--border)] bg-[var(--card)] text-[var(--text-secondary)] hover:bg-[var(--bg-hover)]';
