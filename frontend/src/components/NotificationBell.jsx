import React, { useState, useEffect, useRef } from 'react';
import { fetchNotifications, fetchUnreadCount, markNotifRead, markAllNotifsRead } from '../api';
import { formatSafeDate, formatShortDate } from "../lib/utils";
import usePolling from '../hooks/usePolling'; 
/* Premium SVG Icons for Notifications */
const Icons = {
  Bell: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>,
  Lightbulb: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1.3.5 2.6 1.5 3.5.8.8 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>,
  Check: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>,
  XCircle: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>,
  FileText: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>,
  Party: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>,
  Mail: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>,
  Inbox: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>
};

const TYPE_ICON = {
  idea_submitted:           { icon: Icons.Lightbulb, color: 'bg-violet-50 dark:bg-violet-900/20 text-violet-600 dark:text-violet-400 border-violet-100 dark:border-violet-800/30' },
  idea_approved:            { icon: Icons.Check, color: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30' },
  idea_rejected:            { icon: Icons.XCircle, color: 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border-red-100 dark:border-red-800/30' },
  proposal_submitted:       { icon: Icons.FileText, color: 'bg-violet-50 dark:bg-violet-900/20 text-violet-600 dark:text-violet-400 border-violet-100 dark:border-violet-800/30' },
  proposal_approved_sup:    { icon: Icons.Check, color: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30' },
  proposal_approved_hod:    { icon: Icons.Check, color: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30' },
  proposal_rejected:        { icon: Icons.XCircle, color: 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border-red-100 dark:border-red-800/30' },
  proposal_assigned:        { icon: Icons.Party, color: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30' },
  application_submitted:    { icon: Icons.Mail, color: 'bg-violet-50 dark:bg-violet-900/20 text-violet-600 dark:text-violet-400 border-violet-100 dark:border-violet-800/30' },
  application_approved_doc: { icon: Icons.Check, color: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30' },
  application_approved_hod: { icon: Icons.Check, color: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30' },
  application_rejected:     { icon: Icons.XCircle, color: 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border-red-100 dark:border-red-800/30' },
  application_registered:   { icon: Icons.Party, color: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30' },
  invitation_received:      { icon: Icons.Mail, color: 'bg-violet-50 dark:bg-violet-900/20 text-violet-600 dark:text-violet-400 border-violet-100 dark:border-violet-800/30' },
  invitation_accepted:      { icon: Icons.Check, color: 'bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border-emerald-100 dark:border-emerald-800/30' },
  invitation_rejected:      { icon: Icons.XCircle, color: 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border-red-100 dark:border-red-800/30' },
};



export default function NotificationBell() {
  const [count, setCount]         = useState(0);
  const [notifs, setNotifs]       = useState([]);
  const [open, setOpen]           = useState(false);
 
  const wrapRef                   = useRef(null);
  const pollingRef                = useRef(false);


/* ── Poll unread count ── */
usePolling(async () => {
  try {
    var res = await fetchUnreadCount();
    setCount(res.data?.unread_count ?? res.data?.count ?? 0);
  } catch (e) {
    // Ignore
  }
}, 30000);

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

 const handleOpen = async () => {
  const willOpen = !open;
  setOpen(willOpen);
  if (willOpen) {           // ← كل مرة يفتح القائمة بيجلب من السيرفر
    try {
      const res = await fetchNotifications();
      setNotifs(res.data);
    } catch { /* ignore */ }
  }
};

  const handleRead = async (id) => {
    await markNotifRead(id).catch(() => {});
    setNotifs((prev) => prev.map((n) => n.id === id ? { ...n, is_read: true } : n));
    setCount((c) => Math.max(0, c - 1));
  };

  const handleMarkAll = async () => {
    await markAllNotifsRead().catch(() => {});
    setNotifs((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setCount(0);
  };

  return (
    <div className="relative" ref={wrapRef}>
      <button
        className="group relative bg-transparent border-none cursor-pointer p-2 rounded-full transition-all duration-200 flex items-center justify-center hover:bg-violet-50 dark:hover:bg-violet-900/30"
        aria-expanded={open}
        onClick={handleOpen}
        aria-label={`Notifications${count > 0 ? `, ${count} unread` : ''}`}
      >
        <span className="flex text-gray-500 dark:text-gray-400 group-hover:text-violet-600 dark:group-hover:text-violet-400" aria-hidden="true">{Icons.Bell}</span>
        {count > 0 && (
          <span className="absolute top-0 right-0 bg-red-500 text-white text-[10px] font-extrabold min-w-[16px] h-4 rounded-lg flex items-center justify-center px-1 border-2 border-white dark:border-gray-900">
            {count > 99 ? '99+' : count}
          </span>
        )}
      </button>

      {open && (
        <div
          className="card absolute top-[calc(100%+12px)] right-0 w-[380px] max-h-[500px] rounded-xl shadow-xl z-[500] flex flex-col overflow-hidden border border-gray-200 dark:border-gray-700 origin-top-right"
          role="dialog"
          aria-label="Notifications"
          dir="ltr"
          style={{ animation: 'slideIn 0.2s ease-out forwards' }}
        >
          <style>{`@keyframes slideIn { from { opacity: 0; transform: scale(0.95) translateY(-10px); } to { opacity: 1; transform: scale(1) translateY(0); } }`}</style>

          <div className="card-header flex items-center justify-between py-4 px-5 border-b border-gray-200 dark:border-gray-700 shrink-0 bg-gray-100 dark:bg-gray-700">
            <span className="text-[15px] font-extrabold text-gray-900 dark:text-white uppercase tracking-wide">Notifications</span>
            {count > 0 && (
              <button className="btn btn-ghost btn-sm bg-transparent border-none text-[13px] text-violet-600 dark:text-violet-400 cursor-pointer font-bold transition-all duration-200 p-0 hover:text-violet-800 dark:hover:text-violet-300 hover:underline" onClick={handleMarkAll}>Mark all read</button>
            )}
          </div>

          <div className="card-body" style={{ padding: 0, flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            {notifs.length === 0 && (
              <div className="empty-state flex flex-col items-center justify-center py-12 px-5 text-gray-500 dark:text-gray-400 text-center">
                <div className="w-14 h-14 bg-gray-100 dark:bg-gray-700 rounded-full flex items-center justify-center mb-4 text-gray-400 dark:text-gray-500">
                  {Icons.Inbox}
                </div>
                <p className="m-0 text-sm font-semibold">You have no notifications yet.</p>
              </div>
            )}

            {notifs.length > 0 && (
              <ul className="list-none overflow-y-auto flex-1 m-0 p-0">
                {notifs.map((n) => {
                  const conf = TYPE_ICON[n.notif_type] || { icon: Icons.Bell, color: 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400' };
                  return (
                    <li
                      key={n.id}
                      className={`flex items-start gap-4 py-4 px-5 cursor-pointer transition-colors duration-200 relative border-b border-gray-100 dark:border-gray-700 last:border-b-0 hover:bg-gray-50 dark:hover:bg-gray-700/50 ${n.is_read ? '' : 'bg-gray-50 dark:bg-gray-800 hover:bg-violet-50/50 dark:hover:bg-gray-700'}`}
                      onClick={() => !n.is_read && handleRead(n.id)}
                    >
                      <div className={`w-10 h-10 rounded-[10px] flex items-center justify-center shrink-0 border border-transparent ${conf.color}`}>
                        {conf.icon}
                      </div>
                      <div className="flex flex-col gap-1 flex-1 min-w-0">
                        <span className="text-sm font-extrabold text-gray-900 dark:text-white leading-snug">{n.title}</span>
                        <span className="text-[13px] text-gray-600 dark:text-gray-400 leading-relaxed font-medium">{n.message}</span>
                        <span className="text-[11px] text-gray-400 dark:text-gray-500 font-bold mt-1">{formatSafeDate(n.created_at)}</span>
                      </div>
                      {!n.is_read && (
                        <span className="w-2 h-2 rounded-full bg-violet-500 shrink-0 mt-4 shadow-[0_0_0_2px_rgba(139,92,246,0.2)]" aria-hidden="true" />
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}