/**
 * SolverSettingsPage — Dean manages CP-SAT solver settings
 * per (committee_type × semester).
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Plus, Edit2, Trash2, Save, X, RefreshCw, AlertTriangle, Settings as SettingsIcon,
} from 'lucide-react';
import { fetchSolverSettings, createSolverSettings, updateSolverSettings, deleteSolverSettings } from '../../api';
import { COMMITTEE_TYPES } from './constants';

const WEEKDAYS_OPTIONS = [
  { value: 0, label: 'الإثنين' },
  { value: 1, label: 'الثلاثاء' },
  { value: 2, label: 'الأربعاء' },
  { value: 3, label: 'الخميس' },
  { value: 4, label: 'الجمعة' },
  { value: 5, label: 'السبت' },
  { value: 6, label: 'الأحد' },
];

const emptyForm = {
  name: 'افتراضي',
  committee_type: 'seminar_1',
  semester: '',
  date_range_start: '',
  date_range_end: '',
  workdays: [5, 6],
  daily_start: '09:00',
  daily_end: '17:00',
  buffer_between_committees_minutes: 10,
  max_committees_per_doctor: 5,
  solver_timeout_seconds: 30,
  is_active: true,
};

export default function SolverSettingsPage({ onBack }) {
  const [settings, setSettings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState(emptyForm);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetchSolverSettings();
      setSettings(res.data?.results || res.data || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'فشل التحميل');
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

  const startCreate = () => { setCreating(true); setEditingId(null); setDraft(emptyForm); };
  const startEdit = (s) => {
    setEditingId(s.id); setCreating(false);
    setDraft({
      name: s.name,
      committee_type: s.committee_type,
      semester: s.semester,
      date_range_start: s.date_range_start,
      date_range_end: s.date_range_end,
      workdays: s.workdays || [5, 6],
      daily_start: s.daily_start,
      daily_end: s.daily_end,
      buffer_between_committees_minutes: s.buffer_between_committees_minutes,
      max_committees_per_doctor: s.max_committees_per_doctor,
      solver_timeout_seconds: s.solver_timeout_seconds,
      is_active: s.is_active,
    });
  };
  const cancel = () => { setEditingId(null); setCreating(false); setDraft(emptyForm); };

  const toggleWorkday = (val) => {
    setDraft((d) => {
      const set = new Set(d.workdays);
      if (set.has(val)) set.delete(val); else set.add(val);
      return { ...d, workdays: Array.from(set).sort() };
    });
  };

  const handleSave = async () => {
    if (busy) return;
    if (!draft.semester.trim() || !draft.date_range_start || !draft.date_range_end) {
      setToast({ type: 'error', msg: 'جميع الحقول مطلوبة' });
      return;
    }
    setBusy(true);
    try {
      if (creating) {
        await createSolverSettings(draft);
        setToast({ type: 'success', msg: 'تم إنشاء الإعدادات' });
      } else {
        await updateSolverSettings(editingId, draft);
        setToast({ type: 'success', msg: 'تم تحديث الإعدادات' });
      }
      cancel();
      await load();
    } catch (err) {
      const d = err.response?.data;
      const msg = typeof d === 'object'
        ? Object.entries(d).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`).join(' · ')
        : 'فشل الحفظ';
      setToast({ type: 'error', msg });
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (s) => {
    if (busy) return;
    if (!confirm(`حذف إعدادات "${s.name}" (${s.committee_type} - ${s.semester})؟`)) return;
    setBusy(true);
    try {
      await deleteSolverSettings(s.id);
      setToast({ type: 'success', msg: 'تم الحذف' });
      await load();
    } catch {
      setToast({ type: 'error', msg: 'فشل الحذف' });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="solver-settings-page" dir="rtl" style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: '1.6rem', fontWeight: 700, marginBottom: 4, display: 'flex', gap: 10, alignItems: 'center' }}>
            <SettingsIcon size={26} color="#667eea" /> إعدادات الـ Solver
          </h1>
          <p style={{ color: '#888', fontSize: '0.9rem' }}>
            إعدادات الجدولة لكل (نوع لجنة × فصل دراسي). كل نوع له نطاق تواريخ مستقل.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={load} disabled={loading} style={btnSecondary}>
            <RefreshCw size={14} /> تحديث
          </button>
          <button onClick={startCreate} disabled={creating} style={btnPrimary}>
            <Plus size={14} /> إعدادات جديدة
          </button>
        </div>
      </div>

      {error && (
        <div style={{ ...alertStyle, background: '#fee2e2', color: '#991b1b', marginBottom: 16 }}>
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      {creating && (
        <div style={cardStyle}>
          <h3 style={{ marginTop: 0 }}>إعدادات جديدة</h3>
          <SettingsForm draft={draft} setDraft={setDraft} toggleWorkday={toggleWorkday} />
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
            <button onClick={cancel} style={btnSecondary}><X size={14} /> إلغاء</button>
            <button onClick={handleSave} disabled={busy} style={btnPrimary}>
              <Save size={14} /> {busy ? 'جاري الحفظ...' : 'حفظ'}
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>جاري التحميل...</div>
      ) : settings.length === 0 ? (
        <div style={emptyStateStyle}>
          <SettingsIcon size={48} color="#ccc" />
          <h3>لا توجد إعدادات</h3>
          <p>ابدأ بإنشاء إعدادات لكل نوع لجنة</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: 16 }}>
          {settings.map((s) => (
            <div key={s.id} style={cardStyle}>
              {editingId === s.id ? (
                <>
                  <SettingsForm draft={draft} setDraft={setDraft} toggleWorkday={toggleWorkday} />
                  <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 16 }}>
                    <button onClick={cancel} style={btnSecondary}><X size={14} /> إلغاء</button>
                    <button onClick={handleSave} disabled={busy} style={btnPrimary}>
                      <Save size={14} /> حفظ
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                    <div>
                      <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700 }}>{s.name}</h3>
                      <div style={{ fontSize: '0.78rem', color: '#888', marginTop: 4 }}>
                        {s.committee_type_ar} · {s.semester}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button onClick={() => startEdit(s)} style={btnIconSm} title="تعديل">
                        <Edit2 size={14} />
                      </button>
                      <button onClick={() => handleDelete(s)} style={{ ...btnIconSm, color: '#dc2626' }} title="حذف">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 12px', fontSize: '0.82rem' }}>
                    <Field label="نطاق التواريخ" value={`${s.date_range_start} → ${s.date_range_end}`} />
                    <Field label="أيام العمل" value={(s.workdays || []).map(d => WEEKDAYS_OPTIONS.find(w => w.value === d)?.label || d).join('، ')} />
                    <Field label="ساعات العمل" value={`${s.daily_start} - ${s.daily_end}`} />
                    <Field label="الفاصل بين اللجان" value={`${s.buffer_between_committees_minutes} دقيقة`} />
                    <Field label="حد اللجان/دكتور" value={s.max_committees_per_doctor} />
                    <Field label="مهلة الـ Solver" value={`${s.solver_timeout_seconds} ثانية`} />
                  </div>
                  <div style={{ marginTop: 12 }}>
                    <span style={{
                      ...badgeStyle,
                      background: s.is_active ? '#dcfce7' : '#fee2e2',
                      color: s.is_active ? '#166534' : '#991b1b',
                    }}>
                      {s.is_active ? 'فعّالة' : 'معطّلة'}
                    </span>
                  </div>
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
          padding: '12px 24px', borderRadius: 10,
          background: toast.type === 'success' ? '#10b981' : '#ef4444',
          color: '#fff', fontSize: 14, fontWeight: 600, zIndex: 9999,
        }}>{toast.msg}</div>
      )}
    </div>
  );
}

function SettingsForm({ draft, setDraft, toggleWorkday }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
      <FormField label="الاسم">
        <input type="text" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} style={inputStyle} />
      </FormField>
      <FormField label="نوع اللجنة">
        <select value={draft.committee_type} onChange={(e) => setDraft({ ...draft, committee_type: e.target.value })} style={inputStyle}>
          {COMMITTEE_TYPES.map((c) => <option key={c.value} value={c.value}>{c.label_ar}</option>)}
        </select>
      </FormField>
      <FormField label="الفصل الدراسي">
        <input type="text" placeholder="الفصل الثاني 2026" value={draft.semester} onChange={(e) => setDraft({ ...draft, semester: e.target.value })} style={inputStyle} />
      </FormField>
      <FormField label="الحالة">
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem' }}>
          <input type="checkbox" checked={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} />
          فعّالة
        </label>
      </FormField>
      <FormField label="بداية النطاق">
        <input type="date" value={draft.date_range_start} onChange={(e) => setDraft({ ...draft, date_range_start: e.target.value })} style={inputStyle} />
      </FormField>
      <FormField label="نهاية النطاق">
        <input type="date" value={draft.date_range_end} onChange={(e) => setDraft({ ...draft, date_range_end: e.target.value })} style={inputStyle} />
      </FormField>
      <FormField label="بداية اليوم" >
        <input type="time" value={draft.daily_start} onChange={(e) => setDraft({ ...draft, daily_start: e.target.value })} style={inputStyle} />
      </FormField>
      <FormField label="نهاية اليوم">
        <input type="time" value={draft.daily_end} onChange={(e) => setDraft({ ...draft, daily_end: e.target.value })} style={inputStyle} />
      </FormField>
      <FormField label="الفاصل بين اللجان (دقيقة)">
        <input type="number" min="0" value={draft.buffer_between_committees_minutes} onChange={(e) => setDraft({ ...draft, buffer_between_committees_minutes: parseInt(e.target.value) || 0 })} style={inputStyle} />
      </FormField>
      <FormField label="حد اللجان/دكتور">
        <input type="number" min="1" value={draft.max_committees_per_doctor} onChange={(e) => setDraft({ ...draft, max_committees_per_doctor: parseInt(e.target.value) || 1 })} style={inputStyle} />
      </FormField>
      <FormField label="مهلة الـ Solver (ثانية)">
        <input type="number" min="5" value={draft.solver_timeout_seconds} onChange={(e) => setDraft({ ...draft, solver_timeout_seconds: parseInt(e.target.value) || 30 })} style={inputStyle} />
      </FormField>
      <FormField label="أيام العمل">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {WEEKDAYS_OPTIONS.map((w) => (
            <label key={w.value} style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              padding: '4px 8px', borderRadius: 6, fontSize: '0.78rem', cursor: 'pointer',
              background: draft.workdays.includes(w.value) ? '#ede9fe' : '#f1f5f9',
              color: draft.workdays.includes(w.value) ? '#7c3aed' : '#475569',
              border: `1px solid ${draft.workdays.includes(w.value) ? '#c4b5fd' : '#cbd5e1'}`,
            }}>
              <input type="checkbox" checked={draft.workdays.includes(w.value)} onChange={() => toggleWorkday(w.value)} style={{ margin: 0 }} />
              {w.label}
            </label>
          ))}
        </div>
      </FormField>
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <div style={{ fontSize: '0.72rem', color: '#888', marginBottom: 2 }}>{label}</div>
      <div style={{ fontWeight: 600, color: '#1e293b' }}>{value}</div>
    </div>
  );
}

function FormField({ label, children }) {
  return (
    <div>
      <label style={{ display: 'block', fontSize: '0.78rem', color: '#475569', marginBottom: 4, fontWeight: 600 }}>{label}</label>
      {children}
    </div>
  );
}

// ── Styles ──────────────────────────────────────────────────────────────────
const btnPrimary = { padding: '8px 16px', borderRadius: 8, border: 'none', cursor: 'pointer', background: '#667eea', color: '#fff', fontSize: '0.85rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6 };
const btnSecondary = { padding: '8px 16px', borderRadius: 8, border: '1px solid #cbd5e1', cursor: 'pointer', background: '#fff', color: '#475569', fontSize: '0.85rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6 };
const btnIconSm = { padding: 6, borderRadius: 6, border: '1px solid #cbd5e1', cursor: 'pointer', background: '#fff', color: '#475569', display: 'inline-flex', alignItems: 'center' };
const cardStyle = { background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: 20 };
const alertStyle = { padding: '10px 14px', borderRadius: 8, fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 8 };
const badgeStyle = { padding: '2px 10px', borderRadius: 20, fontSize: '0.72rem', fontWeight: 600 };
const inputStyle = { width: '100%', padding: '8px 12px', borderRadius: 8, border: '1.5px solid #cbd5e1', fontSize: '0.88rem', outline: 'none', boxSizing: 'border-box' };
const emptyStateStyle = { textAlign: 'center', padding: 60, color: '#94a3b8' };
