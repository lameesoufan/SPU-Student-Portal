/**
 * RoomsManagement — Dean manages committee rooms (CRUD).
 * Simple list with inline create/edit/delete.
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Plus, Edit2, Trash2, Save, X, RefreshCw, AlertTriangle, DoorClosed,
} from 'lucide-react';
import { fetchRooms, createRoom, updateRoom, deleteRoom } from '../../api';

export default function RoomsManagement({ onBack }) {
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
      const res = await fetchRooms();
      setRooms(res.data?.results || res.data || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'تعذر تحميل القاعات');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  const startCreate = () => {
    setCreating(true);
    setDraft({ name: '', capacity: 30, is_active: true, notes: '' });
    setEditingId(null);
  };

  const startEdit = (r) => {
    setEditingId(r.id);
    setCreating(false);
    setDraft({ name: r.name, capacity: r.capacity, is_active: r.is_active, notes: r.notes || '' });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setCreating(false);
    setDraft({ name: '', capacity: 30, is_active: true, notes: '' });
  };

  const handleSave = async () => {
    if (busy) return;
    if (!draft.name.trim()) {
      setToast({ type: 'error', msg: 'اسم القاعة مطلوب' });
      return;
    }
    setBusy(true);
    try {
      if (creating) {
        await createRoom(draft);
        setToast({ type: 'success', msg: 'تم إنشاء القاعة بنجاح' });
      } else if (editingId) {
        await updateRoom(editingId, draft);
        setToast({ type: 'success', msg: 'تم تحديث القاعة بنجاح' });
      }
      cancelEdit();
      await load();
    } catch (err) {
      const msg = err.response?.data?.detail || err.response?.data?.name?.[0] || 'فشل الحفظ';
      setToast({ type: 'error', msg });
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (r) => {
    if (busy) return;
    if (!confirm(`حذف القاعة "${r.name}"؟ لا يمكن التراجع.`)) return;
    setBusy(true);
    try {
      await deleteRoom(r.id);
      setToast({ type: 'success', msg: 'تم حذف القاعة' });
      await load();
    } catch (err) {
      const msg = err.response?.data?.detail || 'فشل الحذف (قد تكون القاعة مستخدمة)';
      setToast({ type: 'error', msg });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rooms-page" dir="rtl" style={{ padding: 24, maxWidth: 1100, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: '1.6rem', fontWeight: 700, marginBottom: 4, display: 'flex', gap: 10, alignItems: 'center' }}>
            <DoorClosed size={26} color="#667eea" /> إدارة القاعات
          </h1>
          <p style={{ color: '#888', fontSize: '0.9rem' }}>إنشاء وتعديل وحذف القاعات المستخدمة في جدولة اللجان</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={() => onNavigate ? onNavigate('dashboard') : onBack?.()} style={btnSecondary}>
            رجوع
          </button>
          <button onClick={load} disabled={loading} style={btnSecondary}>
            <RefreshCw size={14} /> تحديث
          </button>
          <button onClick={startCreate} disabled={creating} style={btnPrimary}>
            <Plus size={14} /> قاعة جديدة
          </button>
        </div>
      </div>

      {error && (
        <div style={{ ...alertStyle, background: '#fee2e2', color: '#991b1b', marginBottom: 16 }}>
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      {/* Create form */}
      {creating && (
        <div style={cardStyle}>
          <h3 style={{ marginTop: 0 }}>قاعة جديدة</h3>
          <RoomForm draft={draft} setDraft={setDraft} />
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button onClick={cancelEdit} style={btnSecondary}><X size={14} /> إلغاء</button>
            <button onClick={handleSave} disabled={busy} style={btnPrimary}>
              <Save size={14} /> {busy ? 'جاري الحفظ...' : 'حفظ'}
            </button>
          </div>
        </div>
      )}

      {/* Rooms list */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>جاري التحميل...</div>
      ) : rooms.length === 0 ? (
        <div style={emptyStateStyle}>
          <DoorClosed size={48} color="#ccc" />
          <h3>لا توجد قاعات</h3>
          <p>ابدأ بإنشاء قاعة جديدة</p>
        </div>
      ) : (
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>الاسم</th>
              <th style={thStyle}>السعة</th>
              <th style={thStyle}>الحالة</th>
              <th style={thStyle}>ملاحظات</th>
              <th style={{ ...thStyle, textAlign: 'left' }}>إجراءات</th>
            </tr>
          </thead>
          <tbody>
            {rooms.map((r) => (
              <tr key={r.id}>
                {editingId === r.id ? (
                  <>
                    <td colSpan={4}>
                      <RoomForm draft={draft} setDraft={setDraft} compact />
                    </td>
                    <td style={{ textAlign: 'left' }}>
                      <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
                        <button onClick={handleSave} disabled={busy} style={btnPrimarySm}>
                          <Save size={12} /> حفظ
                        </button>
                        <button onClick={cancelEdit} style={btnSecondarySm}>
                          <X size={12} /> إلغاء
                        </button>
                      </div>
                    </td>
                  </>
                ) : (
                  <>
                    <td style={tdStyle}><strong>{r.name}</strong></td>
                    <td style={tdStyle}>{r.capacity}</td>
                    <td style={tdStyle}>
                      <span style={{
                        ...badgeStyle,
                        background: r.is_active ? '#dcfce7' : '#fee2e2',
                        color: r.is_active ? '#166534' : '#991b1b',
                      }}>
                        {r.is_active ? 'فعّالة' : 'معطّلة'}
                      </span>
                    </td>
                    <td style={tdStyle}>{r.notes || '—'}</td>
                    <td style={{ ...tdStyle, textAlign: 'left' }}>
                      <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
                        <button onClick={() => startEdit(r)} style={btnIconSm} title="تعديل">
                          <Edit2 size={14} />
                        </button>
                        <button onClick={() => handleDelete(r)} style={{ ...btnIconSm, color: '#dc2626' }} title="حذف">
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
          padding: '12px 24px', borderRadius: 10,
          background: toast.type === 'success' ? '#10b981' : '#ef4444',
          color: '#fff', fontSize: 14, fontWeight: 600, boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
          zIndex: 9999,
        }}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}

function RoomForm({ draft, setDraft, compact }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: compact ? '1fr 100px 100px 2fr' : '1fr 100px 100px 2fr', gap: 8 }}>
      <input
        type="text"
        placeholder="اسم القاعة (مثال: قاعة 201)"
        value={draft.name}
        onChange={(e) => setDraft({ ...draft, name: e.target.value })}
        style={inputStyle}
      />
      <input
        type="number"
        min="1"
        placeholder="السعة"
        value={draft.capacity}
        onChange={(e) => setDraft({ ...draft, capacity: parseInt(e.target.value) || 0 })}
        style={inputStyle}
      />
      <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem' }}>
        <input
          type="checkbox"
          checked={draft.is_active}
          onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })}
        />
        فعّالة
      </label>
      <input
        type="text"
        placeholder="ملاحظات (اختياري)"
        value={draft.notes}
        onChange={(e) => setDraft({ ...draft, notes: e.target.value })}
        style={inputStyle}
      />
    </div>
  );
}

// ── Inline styles ───────────────────────────────────────────────────────────
const btnPrimary = {
  padding: '8px 16px', borderRadius: 8, border: 'none', cursor: 'pointer',
  background: '#667eea', color: '#fff', fontSize: '0.85rem', fontWeight: 600,
  display: 'inline-flex', alignItems: 'center', gap: 6,
};
const btnPrimarySm = { ...btnPrimary, padding: '5px 10px', fontSize: '0.78rem' };
const btnSecondary = {
  padding: '8px 16px', borderRadius: 8, border: '1px solid #cbd5e1', cursor: 'pointer',
  background: '#fff', color: '#475569', fontSize: '0.85rem', fontWeight: 600,
  display: 'inline-flex', alignItems: 'center', gap: 6,
};
const btnSecondarySm = { ...btnSecondary, padding: '5px 10px', fontSize: '0.78rem' };
const btnIconSm = {
  padding: 6, borderRadius: 6, border: '1px solid #cbd5e1', cursor: 'pointer',
  background: '#fff', color: '#475569', display: 'inline-flex', alignItems: 'center',
};
const cardStyle = {
  background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12,
  padding: 20, marginBottom: 16,
};
const alertStyle = {
  padding: '10px 14px', borderRadius: 8, fontSize: '0.85rem',
  display: 'flex', alignItems: 'center', gap: 8,
};
const tableStyle = {
  width: '100%', borderCollapse: 'collapse', background: '#fff',
  border: '1px solid #e2e8f0', borderRadius: 12, overflow: 'hidden',
};
const thStyle = {
  padding: '12px 14px', textAlign: 'right', fontSize: '0.78rem',
  fontWeight: 700, color: '#475569', background: '#f8fafc', borderBottom: '1px solid #e2e8f0',
};
const tdStyle = {
  padding: '12px 14px', fontSize: '0.88rem', color: '#1e293b', borderBottom: '1px solid #f1f5f9',
};
const badgeStyle = {
  padding: '2px 10px', borderRadius: 20, fontSize: '0.72rem', fontWeight: 600,
};
const inputStyle = {
  padding: '8px 12px', borderRadius: 8, border: '1.5px solid #cbd5e1',
  fontSize: '0.88rem', outline: 'none',
};
const emptyStateStyle = {
  textAlign: 'center', padding: 60, color: '#94a3b8',
};
