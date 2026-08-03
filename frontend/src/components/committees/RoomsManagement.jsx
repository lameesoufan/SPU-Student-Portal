/**
 * RoomsManagement — إدارة قاعات اللجان.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle,
  DoorClosed,
  Edit2,
  Plus,
  RefreshCw,
  Save,
  Trash2,
  X,
} from 'lucide-react';
import { createRoom, deleteRoom, fetchRooms, updateRoom } from '../../api';
import {
  EmptyState,
  LoadingState,
  PageAlert,
  PageCard,
  PageHeader,
  PageShell,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from '../ui/PagePrimitives';

export default function RoomsManagement({ onBack, onNavigate }) {
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [draft, setDraft] = useState({ name: '', capacity: 30, is_active: true, notes: '' });
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetchRooms();
      setRooms(response.data?.results || response.data || []);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'تعذر تحميل القاعات.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!toast) return undefined;
    const timer = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(timer);
  }, [toast]);

  const resetDraft = () => {
    setEditingId(null);
    setCreating(false);
    setDraft({ name: '', capacity: 30, is_active: true, notes: '' });
  };

  const startCreate = () => {
    setCreating(true);
    setEditingId(null);
    setDraft({ name: '', capacity: 30, is_active: true, notes: '' });
  };

  const startEdit = (room) => {
    setEditingId(room.id);
    setCreating(false);
    setDraft({
      name: room.name,
      capacity: room.capacity,
      is_active: room.is_active,
      notes: room.notes || '',
    });
  };

  const handleSave = async () => {
    if (busy) return;
    if (!draft.name.trim()) {
      setToast({ type: 'error', msg: 'اسم القاعة مطلوب.' });
      return;
    }

    setBusy(true);
    try {
      if (creating) {
        await createRoom(draft);
        setToast({ type: 'success', msg: 'تم إنشاء القاعة بنجاح.' });
      } else if (editingId) {
        await updateRoom(editingId, draft);
        setToast({ type: 'success', msg: 'تم تحديث القاعة بنجاح.' });
      }
      resetDraft();
      await load();
    } catch (requestError) {
      const message = requestError.response?.data?.detail
        || requestError.response?.data?.name?.[0]
        || 'فشل حفظ القاعة.';
      setToast({ type: 'error', msg: message });
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (room) => {
    if (busy || !window.confirm(`حذف القاعة «${room.name}»؟ لا يمكن التراجع عن هذا الإجراء.`)) return;
    setBusy(true);
    try {
      await deleteRoom(room.id);
      setToast({ type: 'success', msg: 'تم حذف القاعة.' });
      await load();
    } catch (requestError) {
      setToast({
        type: 'error',
        msg: requestError.response?.data?.detail || 'تعذر حذف القاعة؛ قد تكون مستخدمة في جدول حالي.',
      });
    } finally {
      setBusy(false);
    }
  };

  if (loading && !rooms.length) return <LoadingState label="جاري تحميل القاعات..." />;

  return (
    <PageShell>
      <PageHeader
        icon={DoorClosed}
        title="إدارة القاعات"
        description="أنشئ القاعات وعدّل سعتها وحالتها قبل استخدامها في جدولة اللجان."
        badge={`${rooms.length} قاعة`}
        actions={(
          <>
            <button type="button" onClick={() => (onNavigate ? onNavigate('dashboard') : onBack?.())} className={secondaryButtonClass}>
              رجوع
            </button>
            <button type="button" onClick={load} disabled={loading} className={secondaryButtonClass}>
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
              تحديث
            </button>
            <button type="button" onClick={startCreate} disabled={creating} className={primaryButtonClass}>
              <Plus size={15} />
              قاعة جديدة
            </button>
          </>
        )}
      />

      <div className="space-y-4">
        {error && <PageAlert><AlertTriangle size={16} className="hidden" />{error}</PageAlert>}

        {creating && (
          <PageCard>
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <h2 className="m-0 text-base font-black text-[var(--text)]">إضافة قاعة جديدة</h2>
                <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">أدخل اسم القاعة والسعة والملاحظات الاختيارية.</p>
              </div>
              <button type="button" onClick={resetDraft} className="flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--border)] text-[var(--text-muted)] hover:bg-[var(--bg-hover)]">
                <X size={16} />
              </button>
            </div>
            <RoomForm draft={draft} setDraft={setDraft} />
            <div className="mt-4 flex justify-end gap-2">
              <button type="button" onClick={resetDraft} className={secondaryButtonClass}>إلغاء</button>
              <button type="button" onClick={handleSave} disabled={busy} className={primaryButtonClass}>
                <Save size={15} />
                {busy ? 'جاري الحفظ...' : 'حفظ القاعة'}
              </button>
            </div>
          </PageCard>
        )}

        {!rooms.length ? (
          <EmptyState
            icon={DoorClosed}
            title="لا توجد قاعات"
            description="ابدأ بإنشاء قاعة جديدة لتصبح متاحة في شاشة الجدولة."
          />
        ) : (
          <PageCard padded={false} className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] border-collapse text-sm">
                <thead className="bg-[var(--bg-tertiary)] text-[var(--text-muted)]">
                  <tr>
                    <th className="px-4 py-3 text-right text-xs font-black">اسم القاعة</th>
                    <th className="px-4 py-3 text-right text-xs font-black">السعة</th>
                    <th className="px-4 py-3 text-right text-xs font-black">الحالة</th>
                    <th className="px-4 py-3 text-right text-xs font-black">ملاحظات</th>
                    <th className="px-4 py-3 text-left text-xs font-black">إجراءات</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-light)]">
                  {rooms.map((room) => (
                    <tr key={room.id} className="transition hover:bg-[var(--bg-hover)]">
                      {editingId === room.id ? (
                        <>
                          <td colSpan={4} className="px-4 py-3">
                            <RoomForm draft={draft} setDraft={setDraft} compact />
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex justify-end gap-2">
                              <button type="button" onClick={handleSave} disabled={busy} className="btn btn-primary px-3 py-2 text-xs">
                                <Save size={13} /> حفظ
                              </button>
                              <button type="button" onClick={resetDraft} className="btn btn-ghost border border-[var(--border)] px-3 py-2 text-xs">
                                <X size={13} /> إلغاء
                              </button>
                            </div>
                          </td>
                        </>
                      ) : (
                        <>
                          <td className="px-4 py-3 font-bold text-[var(--text)]">{room.name}</td>
                          <td className="px-4 py-3 text-[var(--text-secondary)]">{room.capacity}</td>
                          <td className="px-4 py-3">
                            <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${
                              room.is_active
                                ? 'bg-[var(--success-bg)] text-[var(--success-text)]'
                                : 'bg-[var(--danger-bg)] text-[var(--danger-text)]'
                            }`}>
                              {room.is_active ? 'فعّالة' : 'معطّلة'}
                            </span>
                          </td>
                          <td className="max-w-[320px] truncate px-4 py-3 text-[var(--text-muted)]">{room.notes || '—'}</td>
                          <td className="px-4 py-3">
                            <div className="flex justify-end gap-2">
                              <button type="button" onClick={() => startEdit(room)} title="تعديل" className="flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--border)] text-[var(--primary)] hover:bg-[var(--primary-light)]">
                                <Edit2 size={15} />
                              </button>
                              <button type="button" onClick={() => handleDelete(room)} title="حذف" className="flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--danger-border)] text-[var(--danger-text)] hover:bg-[var(--danger-bg)]">
                                <Trash2 size={15} />
                              </button>
                            </div>
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </PageCard>
        )}
      </div>

      {toast && (
        <div className={`fixed bottom-6 left-1/2 z-[100] -translate-x-1/2 rounded-xl px-5 py-3 text-sm font-bold text-white shadow-2xl ${toast.type === 'success' ? 'bg-emerald-600' : 'bg-rose-600'}`}>
          {toast.msg}
        </div>
      )}
    </PageShell>
  );
}

function RoomForm({ draft, setDraft, compact = false }) {
  return (
    <div className={`grid gap-3 ${compact ? 'lg:grid-cols-[1fr_120px_120px_1.4fr]' : 'md:grid-cols-2 lg:grid-cols-[1fr_140px_140px_1.4fr]'}`}>
      <input
        type="text"
        placeholder="اسم القاعة، مثال: قاعة 201"
        value={draft.name}
        onChange={(event) => setDraft({ ...draft, name: event.target.value })}
        className={inputClass}
      />
      <input
        type="number"
        min="1"
        placeholder="السعة"
        value={draft.capacity}
        onChange={(event) => setDraft({ ...draft, capacity: Number.parseInt(event.target.value, 10) || 0 })}
        className={inputClass}
      />
      <label className="flex min-h-[42px] cursor-pointer items-center gap-2 rounded-xl border border-[var(--border)] bg-[var(--bg-input)] px-3 text-sm font-semibold text-[var(--text-secondary)]">
        <input
          type="checkbox"
          checked={draft.is_active}
          onChange={(event) => setDraft({ ...draft, is_active: event.target.checked })}
          className="accent-[var(--primary)]"
        />
        قاعة فعّالة
      </label>
      <input
        type="text"
        placeholder="ملاحظات اختيارية"
        value={draft.notes}
        onChange={(event) => setDraft({ ...draft, notes: event.target.value })}
        className={inputClass}
      />
    </div>
  );
}
