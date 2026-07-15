import React, { useState, useRef, useEffect } from 'react';
import { createTask, updateTask, deleteTask,
         postComment, deleteComment,
         uploadAttachment, deleteAttachment,
         fetchBoardActivity } from '../api';
import {
  Plus, Pencil, Trash2, X, User, Calendar, Flag,
  Phone, Paperclip, MessageSquare, Activity, Send,
  Download, Loader2,
} from 'lucide-react';
import { formatSafeDate, formatShortDate } from "../lib/utils";
// ─── Constants ────────────────────────────────────────────────────────────────
export const COLUMNS = [
  { key: 'todo',        label: 'للقيام',     color: '#64748b' },
  { key: 'in_progress', label: 'قيد التنفيذ', color: '#f59e0b' },
  { key: 'in_review',   label: 'قيد المراجعة', color: '#2563EB' },
  { key: 'done',        label: 'منجزة',       color: '#22c55e' },
];

const PRIORITY_META = {
  low:    { color: '#22c55e', bg: 'bg-emerald-500/10', text: 'text-emerald-600', label: 'منخفضة' },
  medium: { color: '#f59e0b', bg: 'bg-amber-500/10',  text: 'text-amber-600',  label: 'متوسطة' },
  high:   { color: '#ef4444', bg: 'bg-red-500/10',    text: 'text-red-600',    label: 'عالية' },
};

const FILE_ICONS = {
  pdf: '📄', doc: '📝', docx: '📝', xls: '📊', xlsx: '📊',
  ppt: '📊', pptx: '📊', zip: '🗜️', rar: '🗜️',
  jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️',
  mp4: '🎬', mp3: '🎵', txt: '📃', py: '🐍', js: '📜',
};
const fileIcon = (ext) => FILE_ICONS[ext] || '📎';
const fmtSize  = (b) => b < 1024 ? `${b} B` : b < 1048576 ? `${(b/1024).toFixed(1)} KB` : `${(b/1048576).toFixed(1)} MB`;
const fmtDate = (iso) => formatSafeDate(iso, { day:'2-digit', month:'short', hour:'2-digit', minute:'2-digit', hour12: false });

// ─── Task Card ────────────────────────────────────────────────────────────────
function TaskCard({ task, canEdit, onEdit, onDelete, onDragStart, onDragEnd, isDragging }) {
  const pm = PRIORITY_META[task.priority] || PRIORITY_META.medium;
  const isOverdue = task.due_date && new Date(task.due_date) < new Date() && task.status !== 'done';
  const commentCount = task.comments?.length || 0;
  const attachCount  = task.attachments?.length || 0;

  return (
    <div
      className={`bg-white dark:bg-gray-800 rounded-[10px] border-[1.5px] border-gray-200 dark:border-gray-700 flex overflow-hidden cursor-pointer transition-all relative ${
        isDragging ? 'opacity-40' : ''
      } ${!canEdit ? 'cursor-default' : 'hover:shadow-md hover:border-gray-300 dark:hover:border-gray-600 hover:-translate-y-px'}`}
      draggable={canEdit}
      onDragStart={canEdit ? onDragStart : undefined}
      onDragEnd={canEdit ? onDragEnd : undefined}
      onClick={() => onEdit(task)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onEdit(task)}
      aria-label={`Task: ${task.title}`}
    >
      <div className="w-1 flex-shrink-0" style={{ background: pm.color }} />
      <div className="py-2.5 px-2.5 pl-2 flex-1 min-w-0">
        <div className="flex items-start gap-1.5 mb-1">
          <span className="text-[13px] font-semibold text-gray-900 dark:text-white flex-1 leading-snug break-words">{task.title}</span>
          {canEdit && (
            <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0 [&:hover]:opacity-100 [.kb-task:hover_&]:opacity-100" onClick={(e) => e.stopPropagation()}>
              <button className="p-1 rounded bg-transparent border-none cursor-pointer text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-500 dark:hover:text-gray-400 transition-colors" onClick={() => onEdit(task)} title="Edit"><Pencil size={13} /></button>
              <button className="p-1 rounded bg-transparent border-none cursor-pointer text-gray-400 dark:text-gray-500 hover:bg-red-500/10 hover:text-red-500 transition-colors" onClick={() => onDelete(task.id)} title="Delete"><Trash2 size={13} /></button>
            </div>
          )}
        </div>
        {task.description && <p className="text-xs text-gray-500 dark:text-gray-400 m-0 mb-2 leading-normal line-clamp-2">{task.description}</p>}
        <div className="flex flex-wrap gap-1">
          <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded-md ${pm.bg} ${pm.text}`}>
            <Flag size={10} /> {pm.label}
          </span>
          {task.assignee_name && (
            <span className="inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded-md bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400">
              <User size={10} /> {task.assignee_name}
            </span>
          )}
          {task.due_date && (
            <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded-md ${isOverdue ? 'bg-red-500/10 text-red-500' : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'}`}>
              <Calendar size={10} /> {task.due_date}
            </span>
          )}
          {task.created_by_role === 'doctor' && (
            <span className="inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded-md bg-violet-500/10 text-violet-600" title="Assigned by supervisor">
              <Phone size={10} /> Supervisor
            </span>
          )}
          {commentCount > 0 && (
            <span className="inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded-md bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400">
              <MessageSquare size={10} /> {commentCount}
            </span>
          )}
          {attachCount > 0 && (
            <span className="inline-flex items-center gap-1 text-[11px] font-medium px-1.5 py-0.5 rounded-md bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400">
              <Paperclip size={10} /> {attachCount}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Task Drawer ──────────────────────────────────────────────────────────────
function TaskDrawer({ task, board, onClose, onSave, onDelete, isSaving }) {
  const isNew = !task.id;
  const [tab, setTab] = useState('details');
  const [form, setForm] = useState({
    title:       task.title       || '',
    description: task.description || '',
    priority:    task.priority    || 'medium',
    status:      task.status      || 'todo',
    assignee:    task.assignee    || '',
    due_date:    task.due_date    || '',
  });

  const [comments, setComments]       = useState(task.comments || []);
  const [commentBody, setCommentBody] = useState('');
  const [postingComment, setPostingComment] = useState(false);

  const [attachments, setAttachments] = useState(task.attachments || []);
  const [uploading, setUploading]     = useState(false);
  const fileInputRef = useRef(null);

  const [activities, setActivities] = useState([]);
  const [loadingActivity, setLoadingActivity] = useState(false);

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const valid = form.title.trim().length > 0;

  useEffect(() => {
    if (tab === 'activity' && !isNew && activities.length === 0) {
      setLoadingActivity(true);
      fetchBoardActivity(board.id)
        .then((res) => setActivities(res.data.filter((a) => a.task === task.id)))
        .catch(() => {})
        .finally(() => setLoadingActivity(false));
    }
  }, [tab, isNew, board.id, task.id, activities.length]);

  const handlePostComment = async () => {
    if (!commentBody.trim() || postingComment) return;
    setPostingComment(true);
    try {
      const res = await postComment(board.id, task.id, commentBody.trim());
      setComments((c) => [...c, res.data]);
      setCommentBody('');
    } finally { setPostingComment(false); }
  };

  const handleDeleteComment = async (cid) => {
    if (!window.confirm('Delete this comment?')) return;
    await deleteComment(board.id, task.id, cid);
    setComments((c) => c.filter((x) => x.id !== cid));
  };

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { alert('File too large. Max 10 MB.'); return; }
    setUploading(true);
    try {
      const res = await uploadAttachment(board.id, task.id, file);
      setAttachments((a) => [...a, res.data]);
    } catch (err) { alert(err.response?.data?.error || 'Upload failed.'); }
    finally { setUploading(false); if (fileInputRef.current) fileInputRef.current.value = ''; }
  };

  const handleDeleteAttachment = async (aid) => {
    if (!window.confirm('Delete this file?')) return;
    await deleteAttachment(board.id, task.id, aid);
    setAttachments((a) => a.filter((x) => x.id !== aid));
  };

  const TAB_ITEMS = [
    { key: 'details',    label: 'Details',    icon: Pencil },
    { key: 'comments',   label: `Comments${comments.length > 0 ? ` (${comments.length})` : ''}`, icon: MessageSquare },
    { key: 'attachments',label: `Files${attachments.length > 0 ? ` (${attachments.length})` : ''}`, icon: Paperclip },
    { key: 'activity',   label: 'Activity',   icon: Activity },
  ];

  return (
    <div className="fixed inset-0 bg-slate-900/40 z-[1000] flex justify-end backdrop-blur-sm" onClick={onClose} role="dialog" aria-modal="true">
      <aside className="w-[420px] max-w-full h-full bg-white dark:bg-gray-900 flex flex-col shadow-[-8px_0_40px_rgba(0,0,0,0.15)]" onClick={(e) => e.stopPropagation()}>
        {/* Drawer Header */}
        <div className="flex items-center justify-between px-5 pt-5 pb-4 border-b border-gray-200/50 dark:border-gray-700/50">
          <h3 className="text-[17px] font-bold text-gray-900 dark:text-white m-0">{isNew ? 'New Task' : task.title}</h3>
          <button className="p-1 rounded bg-transparent border-none cursor-pointer text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-white transition-colors" onClick={onClose} aria-label="Close"><X size={18} /></button>
        </div>

        {/* Drawer Tabs */}
        {!isNew && (
          <div className="flex border-b border-gray-200/50 dark:border-gray-700/50 bg-gray-50 dark:bg-gray-800/30 px-5">
            {TAB_ITEMS.map(t => {
              const TabIcon = t.icon;
              return (
                <button key={t.key} className={`py-3 px-4 border-none bg-transparent text-[13px] font-medium cursor-pointer border-b-2 transition-all flex items-center gap-1.5 ${
                  tab === t.key ? 'text-violet-600 dark:text-violet-400 border-b-violet-600 dark:border-b-violet-400 font-semibold' : 'text-gray-500 dark:text-gray-400 border-b-transparent hover:text-gray-400 dark:hover:text-gray-500'
                }`} onClick={() => setTab(t.key)}>
                  <TabIcon size={14} /> {t.label}
                </button>
              );
            })}
          </div>
        )}

        {/* Drawer Body */}
        <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-4">
          {/* DETAILS TAB */}
          {tab === 'details' && (
            <>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Title <span className="text-red-500">*</span></label>
                <input className="w-full py-2.5 px-3 text-sm border-[1.5px] border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white transition-all placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none" value={form.title} onChange={(e) => set('title', e.target.value)} placeholder="What needs to be done?" autoFocus />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Description</label>
                <textarea className="w-full py-2.5 px-3 text-sm border-[1.5px] border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white transition-all placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none resize-none" value={form.description} onChange={(e) => set('description', e.target.value)} placeholder="Add more context…" rows={4} />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Priority</label>
                <div className="flex gap-2">
                  {Object.entries(PRIORITY_META).map(([k, v]) => (
                    <button key={k} type="button" className={`flex-1 py-1.5 px-1 border-[1.5px] rounded-lg text-[13px] font-medium cursor-pointer transition-all text-center ${
                      form.priority === k ? `border-[${v.color}] ${v.bg} ${v.text} font-bold` : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:border-gray-400 dark:hover:border-gray-500'
                    }`} style={form.priority === k ? { borderColor: v.color, background: `${v.color}15`, color: v.color } : {}} onClick={() => set('priority', k)}>
                      {v.label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Status</label>
                  <select className="py-2.5 px-3 text-sm border-[1.5px] border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white transition-all focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none w-full" value={form.status} onChange={(e) => set('status', e.target.value)}>
                    {COLUMNS.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Due Date</label>
                  <input type="date" className="py-2.5 px-3 text-sm border-[1.5px] border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white transition-all focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none w-full" value={form.due_date} onChange={(e) => set('due_date', e.target.value)} />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Assign To</label>
                <div className="flex flex-wrap gap-2">
                  <button type="button" className={`flex items-center gap-1.5 py-1.5 px-3 border-[1.5px] rounded-full text-[13px] cursor-pointer transition-all ${
                    !form.assignee ? 'border-violet-500 bg-violet-500/10 text-violet-600 dark:text-violet-400 font-semibold' : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:border-violet-500 hover:text-violet-600 dark:hover:text-violet-400'
                  }`} onClick={() => set('assignee', '')}>Unassigned</button>
                  {board.members.map((m) => (
                    <button key={m.id} type="button" className={`flex items-center gap-1.5 py-1.5 px-3 border-[1.5px] rounded-full text-[13px] cursor-pointer transition-all ${
                      String(form.assignee) === String(m.id) ? 'border-violet-500 bg-violet-500/10 text-violet-600 dark:text-violet-400 font-semibold' : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700 text-gray-500 dark:text-gray-400 hover:border-violet-500 hover:text-violet-600 dark:hover:text-violet-400'
                    }`} onClick={() => set('assignee', m.id)}>
                      <span className="w-[22px] h-[22px] rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 text-white text-[11px] font-bold flex items-center justify-center">{(m.name || m.username)[0].toUpperCase()}</span>
                      {m.name || m.username}
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* COMMENTS TAB */}
          {tab === 'comments' && (
            <div className="flex flex-col gap-4 h-full">
              <div className="flex-1 overflow-y-auto flex flex-col gap-3">
                {comments.length === 0 && <div className="text-center text-gray-400 dark:text-gray-500 text-sm py-8 italic">No comments yet. Start the conversation!</div>}
                {comments.map((c) => (
                  <div key={c.id} className="bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-700 rounded-[10px] p-3">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-[13px] font-semibold text-gray-900 dark:text-white flex items-center gap-1.5">
                        {c.author_name}
                        {c.author_role === 'doctor' && <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-600 uppercase tracking-wide">Supervisor</span>}
                      </span>
                      <span className="text-[11px] text-gray-400 dark:text-gray-500 ml-auto">{fmtDate(c.created_at)}</span>
                      <button className="p-1 rounded bg-transparent border-none cursor-pointer text-gray-400 dark:text-gray-500 hover:bg-red-500/10 hover:text-red-500 transition-colors" onClick={() => handleDeleteComment(c.id)} title="Delete"><Trash2 size={13} /></button>
                    </div>
                    <p className="text-[13px] text-gray-500 dark:text-gray-400 leading-relaxed m-0 whitespace-pre-wrap">{c.body}</p>
                  </div>
                ))}
              </div>
              <div className="flex flex-col gap-2 pt-3 border-t border-gray-200 dark:border-gray-700">
                <textarea className="resize-y min-h-[60px] py-2.5 px-3 text-sm border-[1.5px] border-gray-200 dark:border-gray-700 rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white transition-all placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:border-violet-500 focus:ring-2 focus:ring-violet-500/20 outline-none" value={commentBody} onChange={(e) => setCommentBody(e.target.value)} placeholder="Write a comment…" rows={3} onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handlePostComment(); }} />
                <button className="inline-flex items-center justify-center gap-1.5 py-2 px-4 text-sm font-semibold rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" onClick={handlePostComment} disabled={!commentBody.trim() || postingComment}>
                  <Send size={14} /> {postingComment ? 'Posting…' : 'Post'}
                </button>
              </div>
            </div>
          )}

          {/* ATTACHMENTS TAB */}
          {tab === 'attachments' && (
            <div className="flex flex-col gap-4">
              <button className="inline-flex items-center justify-center gap-1.5 py-2 px-4 text-sm font-semibold rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
                <Paperclip size={14} /> {uploading ? 'Uploading…' : 'Upload File'}
              </button>
              <input ref={fileInputRef} type="file" style={{ display: 'none' }} onChange={handleFileSelect} />
              <div className="flex flex-col gap-2.5">
                {attachments.length === 0 && <div className="text-center text-gray-400 dark:text-gray-500 text-sm py-8 italic">No files attached yet.</div>}
                {attachments.map((a) => (
                  <div key={a.id} className="flex items-center gap-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-700 rounded-[10px] p-2.5 px-3 transition-colors hover:bg-gray-50 dark:hover:bg-gray-700/30">
                    <span className="text-2xl flex-shrink-0">{fileIcon(a.extension)}</span>
                    <div className="flex-1 min-w-0 flex flex-col gap-0.5">
                      <a href={a.file_url} target="_blank" rel="noopener noreferrer" className="text-[13px] font-medium text-gray-900 dark:text-white hover:text-violet-600 dark:hover:text-violet-400 hover:underline overflow-hidden text-ellipsis whitespace-nowrap">{a.filename}</a>
                      <span className="text-[11px] text-gray-400 dark:text-gray-500">{fmtSize(a.file_size)} • {a.uploaded_by_name} • {fmtDate(a.created_at)}</span>
                    </div>
                    <button className="p-1.5 rounded bg-transparent border-none cursor-pointer text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-500 dark:hover:text-gray-400 transition-colors" onClick={() => window.open(a.file_url, '_blank')} title="Download"><Download size={13} /></button>
                    <button className="p-1.5 rounded bg-transparent border-none cursor-pointer text-gray-400 dark:text-gray-500 hover:bg-red-500/10 hover:text-red-500 transition-colors" onClick={() => handleDeleteAttachment(a.id)} title="Delete"><Trash2 size={13} /></button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ACTIVITY TAB */}
          {tab === 'activity' && (
            <div className="flex flex-col">
              {loadingActivity && <div className="text-center text-gray-400 dark:text-gray-500 text-sm py-8 italic">Loading activity…</div>}
              {!loadingActivity && activities.length === 0 && <div className="text-center text-gray-400 dark:text-gray-500 text-sm py-8 italic">No activity yet.</div>}
              {!loadingActivity && activities.map((a) => (
                <div key={a.id} className="flex gap-3 py-3 border-b border-gray-200/30 dark:border-gray-700/30 last:border-b-0">
                  <div className="w-2 h-2 rounded-full bg-gray-300 dark:bg-gray-600 mt-1.5 flex-shrink-0" />
                  <div className="flex-1 flex flex-wrap items-baseline gap-1.5 text-[13px] leading-relaxed">
                    <span className="font-semibold text-gray-900 dark:text-white flex items-center gap-1.5">
                      {a.actor_name}
                      {a.actor_role === 'doctor' && <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-600 uppercase tracking-wide">Supervisor</span>}
                    </span>
                    <span className="text-gray-500 dark:text-gray-400">{a.verb}</span>
                    {a.detail && <span className="text-gray-500 dark:text-gray-400 font-medium">{a.detail}</span>}
                    <span className="text-[11px] text-gray-400 dark:text-gray-500 ml-auto">{fmtDate(a.created_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Drawer Footer */}
        <div className="flex items-center gap-2.5 px-5 py-4 border-t border-gray-200/50 dark:border-gray-700/50 bg-gray-50 dark:bg-gray-800/30">
          {!isNew && tab === 'details' && (
            <button className="inline-flex items-center justify-center gap-1.5 py-2 px-4 text-sm font-semibold rounded-lg bg-red-500/10 text-red-500 border border-red-500/20 hover:bg-red-500/20 transition-colors" onClick={() => onDelete(task.id)}>Delete</button>
          )}
          <div style={{ flex: 1 }} />
          <button className="inline-flex items-center justify-center gap-1.5 py-2 px-4 text-sm font-medium rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 border border-gray-200 dark:border-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors" onClick={onClose}>
            {tab === 'details' ? 'Cancel' : 'Close'}
          </button>
          {tab === 'details' && (
            <button className="inline-flex items-center justify-center gap-1.5 py-2 px-4 text-sm font-semibold rounded-lg bg-violet-600 text-white hover:bg-violet-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed" onClick={() => onSave(form)} disabled={isSaving || !valid}>
              {isSaving ? 'Saving…' : isNew ? 'Create Task' : 'Save Changes'}
            </button>
          )}
        </div>
      </aside>
    </div>
  );
}

// ─── Main KanbanBoard ─────────────────────────────────────────────────────────
export default function KanbanBoard({ board, setBoard, canEdit = true }) {
  const [drawer, setDrawer]     = useState(null);
  const [saving, setSaving]     = useState(false);
  const [dragTask, setDragTask] = useState(null);
  const [dragOver, setDragOver] = useState(null);
  const dragNode                = useRef(null);

  const tasksByCol = (colKey) => (board?.tasks || []).filter((t) => t.status === colKey);
  const done  = (board?.tasks || []).filter((t) => t.status === 'done').length;
  const total = (board?.tasks || []).length;
  const pct   = total > 0 ? Math.round((done / total) * 100) : 0;

  const openCreate = (colKey) => setDrawer({ task: { status: colKey } });
  const openEdit   = (task)   => setDrawer({ task });
  const closeDrawer = ()      => setDrawer(null);

  const handleSave = async (form) => {
    setSaving(true);
    try {
      const payload = { title: form.title, description: form.description, priority: form.priority, status: form.status, assignee: form.assignee || null, due_date: form.due_date || null };
      if (!drawer.task.id) {
        const res = await createTask(board.id, payload);
        setBoard((b) => ({ ...b, tasks: [...b.tasks, res.data] }));
      } else {
        const res = await updateTask(board.id, drawer.task.id, payload);
        setBoard((b) => ({ ...b, tasks: b.tasks.map((t) => t.id === res.data.id ? res.data : t) }));
      }
      closeDrawer();
    } finally { setSaving(false); }
  };

  const handleDelete = async (taskId) => {
    if (!window.confirm('Delete this task?')) return;
    await deleteTask(board.id, taskId);
    setBoard((b) => ({ ...b, tasks: b.tasks.filter((t) => t.id !== taskId) }));
    closeDrawer();
  };

  const onDragStart = (task, e) => {
    setDragTask(task);
    dragNode.current = e.currentTarget;
    setTimeout(() => { if (dragNode.current) dragNode.current.style.opacity = '0.3'; dragNode.current.style.transform = 'rotate(2deg)'; }, 0);
  };

  const onDragEnd = () => {
    if (dragNode.current) { dragNode.current.style.opacity = ''; dragNode.current.style.transform = ''; }
    setDragTask(null);
    setDragOver(null);
  };

  const onDrop = async (colKey) => {
    setDragOver(null);
    if (!dragTask || dragTask.status === colKey) return;

    // Save current state for rollback in case API fails
    const prevStatus = dragTask.status;
    const prevBoard = board;

    // Optimistic update: move task in UI immediately
    setBoard((b) => ({
      ...b,
      tasks: b.tasks.map((t) => t.id === dragTask.id ? { ...t, status: colKey } : t),
    }));
    setDragTask(null);

    try {
      const res = await updateTask(board.id, dragTask.id, { status: colKey });
      // Sync with server response
      setBoard((b) => ({ ...b, tasks: b.tasks.map((t) => t.id === res.data.id ? res.data : t) }));
    } catch (err) {
      // Rollback: restore task to its previous status
      setBoard(prevBoard);
      if (import.meta.env.DEV) console.error('Failed to move task:', err);
      alert('Failed to move task. The task has been restored to its previous position.');
    }
  };

  return (
    <div className="p-6 bg-white dark:bg-gray-900 min-h-full flex flex-col gap-4">
      {/* Board Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-white m-0 mb-2">{board.title}</h2>
          <div className="flex items-center gap-1.5 flex-wrap">
            {board.members.map((m) => (
              <span key={m.id} className="w-[30px] h-[30px] rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 text-white text-xs font-bold flex items-center justify-center border-2 border-white dark:border-gray-900 shadow-sm cursor-default" title={m.name}>
                {(m.name || m.username)[0].toUpperCase()}
              </span>
            ))}
            <span className="text-[13px] text-gray-500 dark:text-gray-400">{board.members.map((m) => m.name || m.username).join(', ')}</span>
          </div>
        </div>
        <div className="flex gap-5">
          <div className="flex flex-col items-center bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-[10px] px-4 py-2.5 min-w-[64px]">
            <span className="text-[22px] font-bold text-gray-900 dark:text-white leading-none">{total}</span>
            <span className="text-[11px] text-gray-400 dark:text-gray-500 uppercase tracking-wide mt-0.5">Tasks</span>
          </div>
          <div className="flex flex-col items-center bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-[10px] px-4 py-2.5 min-w-[64px]">
            <span className="text-[22px] font-bold text-gray-900 dark:text-white leading-none">{done}</span>
            <span className="text-[11px] text-gray-400 dark:text-gray-500 uppercase tracking-wide mt-0.5">Done</span>
          </div>
          <div className="flex flex-col items-center bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-[10px] px-4 py-2.5 min-w-[64px]">
            <span className="text-[22px] font-bold leading-none" style={{ color: pct === 100 ? '#22c55e' : '#2563EB' }}>{pct}%</span>
            <span className="text-[11px] text-gray-400 dark:text-gray-500 uppercase tracking-wide mt-0.5">Progress</span>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="h-[5px] bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full transition-[width] duration-500 ease-out" style={{ width: `${pct}%` }} />
      </div>

      {/* Board Grid */}
      <div className="grid grid-cols-4 gap-3.5 items-start max-[1100px]:grid-cols-2 max-[640px]:grid-cols-1">
        {COLUMNS.map((col) => {
          const colTasks = tasksByCol(col.key);
          const isOver   = dragOver === col.key;

          return (
            <div key={col.key} className={`bg-gray-50 dark:bg-gray-800/30 rounded-[14px] flex flex-col min-h-[160px] transition-colors ${isOver ? 'bg-violet-500/10 outline-2 outline-dashed outline-violet-500' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setDragOver((prev) => prev === col.key ? prev : col.key); }}
              onDragLeave={() => setDragOver(null)}
              onDrop={() => onDrop(col.key)}
            >
              <div className="rounded-t-[14px] pt-3 px-3 pb-2" style={{ borderTop: `3px solid ${col.color}` }}>
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: col.color }} />
                  <span className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wide flex-1">{col.label}</span>
                  <span className="bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400 text-[11px] font-bold min-w-[20px] h-5 rounded-full flex items-center justify-center px-[5px]">{colTasks.length}</span>
                </div>
              </div>

              <div className="px-2.5 py-1 flex flex-col gap-2 flex-1">
                {colTasks.map((task) => (
                  <TaskCard key={task.id} task={task} canEdit={canEdit} onEdit={openEdit} onDelete={handleDelete} onDragStart={(e) => onDragStart(task, e)} onDragEnd={onDragEnd} isDragging={dragTask?.id === task.id} />
                ))}
                {colTasks.length === 0 && (
                  <div className="text-center text-gray-400 dark:text-gray-500 text-[13px] py-5 italic">{isOver ? 'Drop here' : 'No tasks'}</div>
                )}
              </div>

              {canEdit && (
               <button className="flex items-center justify-center gap-1.5 w-[calc(100%-20px)] mx-2.5 mb-2.5 py-2 bg-violet-500/5 border-[1.5px] border-dashed border-violet-500/30 rounded-lg text-violet-600 dark:text-violet-400 text-xs font-semibold cursor-pointer transition-all hover:border-violet-500 hover:bg-violet-500/15 hover:shadow-sm" onClick={() => openCreate(col.key)}>
                  <Plus size={15} /> Add Task
                </button>
              )}
            </div>
          );
        })}
      </div>

      {drawer && (
        <TaskDrawer task={drawer.task} board={board} onClose={closeDrawer} onSave={handleSave} onDelete={handleDelete} isSaving={saving} />
      )}
    </div>
  );
}