import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  fetchNotifications,
  fetchUnreadCount,
  markNotifRead,
  markAllNotifsRead,
} from '../api';
import { formatSafeDate } from '../lib/utils';
import usePolling from '../hooks/usePolling';

const Icons = {
  Bell: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>,
  Lightbulb: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1.3.5 2.6 1.5 3.5.8.8 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>,
  Check: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>,
  XCircle: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>,
  FileText: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>,
  Party: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>,
  Mail: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>,
  Inbox: <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>,
};

const TYPE_ICON = {
  idea_submitted: { icon: Icons.Lightbulb, color: 'bg-violet-50 dark:bg-violet-900/20 text-violet-600 dark:text-violet-400 border-violet-100 dark:border-violet-800/30' },
  idea_approved: { icon: Icons.Check, color: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30' },
  idea_rejected: { icon: Icons.XCircle, color: 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border-red-100 dark:border-red-800/30' },
  proposal_submitted: { icon: Icons.FileText, color: 'bg-violet-50 dark:bg-violet-900/20 text-violet-600 dark:text-violet-400 border-violet-100 dark:border-violet-800/30' },
  proposal_approved_sup: { icon: Icons.Check, color: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30' },
  proposal_approved_hod: { icon: Icons.Check, color: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30' },
  proposal_rejected: { icon: Icons.XCircle, color: 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border-red-100 dark:border-red-800/30' },
  proposal_assigned: { icon: Icons.Party, color: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30' },
  application_submitted: { icon: Icons.Mail, color: 'bg-violet-50 dark:bg-violet-900/20 text-violet-600 dark:text-violet-400 border-violet-100 dark:border-violet-800/30' },
  application_approved_doc: { icon: Icons.Check, color: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30' },
  application_approved_hod: { icon: Icons.Check, color: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30' },
  application_rejected: { icon: Icons.XCircle, color: 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border-red-100 dark:border-red-800/30' },
  application_registered: { icon: Icons.Party, color: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30' },
  invitation_received: { icon: Icons.Mail, color: 'bg-violet-50 dark:bg-violet-900/20 text-violet-600 dark:text-violet-400 border-violet-100 dark:border-violet-800/30' },
  invitation_accepted: { icon: Icons.Check, color: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30' },
  invitation_rejected: { icon: Icons.XCircle, color: 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border-red-100 dark:border-red-800/30' },
};

export default function NotificationBell() {
  const [count, setCount] = useState(0);
  const [notifs, setNotifs] = useState([]);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const panelRef = useRef(null);

  usePolling(async () => {
    try {
      const res = await fetchUnreadCount();
      setCount(res.data?.unread_count ?? res.data?.count ?? 0);
    } catch {
      // Polling failures should not interrupt the interface.
    }
  }, 30000);

  useEffect(() => {
    const handleOutsideClick = (event) => {
      const clickedBell = wrapRef.current?.contains(event.target);
      const clickedPanel = panelRef.current?.contains(event.target);
      if (!clickedBell && !clickedPanel) setOpen(false);
    };

    const handleEscape = (event) => {
      if (event.key === 'Escape') setOpen(false);
    };

    document.addEventListener('mousedown', handleOutsideClick);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleEscape);
    };
  }, []);

  const handleOpen = async () => {
    const willOpen = !open;
    setOpen(willOpen);

    if (willOpen) {
      try {
        const res = await fetchNotifications();
        setNotifs(Array.isArray(res.data) ? res.data : res.data?.results || []);
      } catch {
        setNotifs([]);
      }
    }
  };

  const handleRead = async (id) => {
    try {
      await markNotifRead(id);
      setNotifs((previous) => previous.map((notification) => (
        notification.id === id ? { ...notification, is_read: true } : notification
      )));
      setCount((current) => Math.max(0, current - 1));
    } catch {
      // Keep the notification unread locally when the backend update fails.
    }
  };

  const handleMarkAll = async () => {
    try {
      await markAllNotifsRead();
      setNotifs((previous) => previous.map((notification) => ({ ...notification, is_read: true })));
      setCount(0);
    } catch {
      // Keep local unread state in sync with the backend on failure.
    }
  };

  return (
    <div className="relative shrink-0" ref={wrapRef}>
      <button
        type="button"
        className="group relative flex h-10 w-10 items-center justify-center rounded-full border border-transparent bg-transparent text-slate-500 transition hover:border-slate-200 hover:bg-slate-100 hover:text-violet-600 dark:text-slate-400 dark:hover:border-slate-700 dark:hover:bg-slate-800 dark:hover:text-violet-400"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={handleOpen}
        aria-label={`الإشعارات${count > 0 ? `، ${count} غير مقروءة` : ''}`}
      >
        <span aria-hidden="true">{Icons.Bell}</span>
        {count > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full border-2 border-white bg-red-500 px-1 text-[9px] font-extrabold leading-none text-white dark:border-slate-900">
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>

      {open && createPortal(
        <div
          ref={panelRef}
          className="fixed inset-x-3 top-[76px] z-[2147483647] mx-auto flex max-h-[calc(100dvh-92px)] w-auto max-w-[420px] origin-top flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_24px_70px_rgba(15,23,42,0.22)] dark:border-slate-700 dark:bg-slate-900 sm:inset-x-auto sm:left-4 sm:mx-0 sm:w-[420px]"
          role="dialog"
          aria-label="الإشعارات"
          dir="rtl"
          style={{ animation: 'notificationDrop 180ms ease-out forwards' }}
        >
          <style>{`
            @keyframes notificationDrop {
              from { opacity: 0; transform: translateY(-8px) scale(.98); }
              to { opacity: 1; transform: translateY(0) scale(1); }
            }
          `}</style>

          <div className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-5 py-4 dark:border-slate-700 dark:bg-slate-900">
            <div>
              <h3 className="m-0 text-[15px] font-extrabold text-slate-900 dark:text-white">الإشعارات</h3>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                {count > 0 ? `${count} إشعار غير مقروء` : 'جميع الإشعارات مقروءة'}
              </p>
            </div>

            {count > 0 && (
              <button
                type="button"
                className="shrink-0 rounded-lg px-2.5 py-1.5 text-xs font-bold text-violet-600 transition hover:bg-violet-50 dark:text-violet-400 dark:hover:bg-violet-900/20"
                onClick={handleMarkAll}
              >
                تحديد الكل كمقروء
              </button>
            )}
          </div>

          <div className="min-h-0 flex-1 overflow-hidden">
            {notifs.length === 0 ? (
              <div className="flex min-h-[240px] flex-col items-center justify-center px-6 py-12 text-center text-slate-500 dark:text-slate-400">
                <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-500">
                  {Icons.Inbox}
                </div>
                <p className="m-0 text-sm font-bold text-slate-700 dark:text-slate-200">لا توجد إشعارات بعد</p>
                <p className="mt-1 text-xs">ستظهر الإشعارات الجديدة هنا.</p>
              </div>
            ) : (
              <ul className="m-0 max-h-[min(60vh,520px)] list-none overflow-y-auto overscroll-contain p-0">
                {notifs.map((notification) => {
                  const config = TYPE_ICON[notification.notif_type] || {
                    icon: Icons.Bell,
                    color: 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 border-slate-200 dark:border-slate-700',
                  };

                  return (
                    <li
                      key={notification.id}
                      className={`relative flex cursor-pointer items-start gap-3 border-b border-slate-100 px-5 py-4 text-right transition last:border-b-0 dark:border-slate-800 ${
                        notification.is_read
                          ? 'bg-white hover:bg-slate-50 dark:bg-slate-900 dark:hover:bg-slate-800/70'
                          : 'bg-violet-50/45 hover:bg-violet-50 dark:bg-violet-950/20 dark:hover:bg-violet-950/30'
                      }`}
                      onClick={() => !notification.is_read && handleRead(notification.id)}
                    >
                      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${config.color}`}>
                        {config.icon}
                      </div>

                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-3">
                          <span className="break-words text-sm font-extrabold leading-6 text-slate-900 dark:text-white">
                            {notification.title}
                          </span>
                          {!notification.is_read && (
                            <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-violet-500 ring-4 ring-violet-500/10" aria-hidden="true" />
                          )}
                        </div>
                        <p className="mt-0.5 break-words text-[13px] font-medium leading-6 text-slate-600 dark:text-slate-400">
                          {notification.message}
                        </p>
                        <span className="mt-1.5 block text-[11px] font-semibold text-slate-400 dark:text-slate-500">
                          {formatSafeDate(notification.created_at)}
                        </span>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
