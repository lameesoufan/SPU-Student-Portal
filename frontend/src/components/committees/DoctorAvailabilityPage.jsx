/**
 * DoctorAvailabilityPage — Dean manages weekly availability + date exceptions
 * for any doctor.
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  RefreshCw, Plus, Trash2, Calendar, AlertTriangle, Users, X, Save,
} from 'lucide-react';
import {
  fetchDoctors, fetchDoctorAvailability, createDoctorAvailability, deleteDoctorAvailability,
  fetchDoctorExceptions, createDoctorException, deleteDoctorException,
} from '../../api';

const WEEKDAYS = [
  { value: 0, label: 'الإثنين' },
  { value: 1, label: 'الثلاثاء' },
  { value: 2, label: 'الأربعاء' },
  { value: 3, label: 'الخميس' },
  { value: 4, label: 'الجمعة' },
  { value: 5, label: 'السبت' },
  { value: 6, label: 'الأحد' },
];

export default function DoctorAvailabilityPage({ onBack }) {
  const [doctors, setDoctors] = useState([]);
  const [selectedDoctor, setSelectedDoctor] = useState(null);
  const [availability, setAvailability] = useState([]);
  const [exceptions, setExceptions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  // New exception form
  const [newExc, setNewExc] = useState({ date: '', exception_type: 'blocked', reason: '' });

  const loadDoctors = useCallback(async () => {
    try {
      const res = await fetchDoctors();
      setDoctors(res.data || []);
      if (res.data?.length && !selectedDoctor) {
        setSelectedDoctor(res.data[0].id);
      }
    } catch {
      setDoctors([]);
    }
  }, []);

  useEffect(() => { loadDoctors(); }, [loadDoctors]);

  const loadDoctorData = useCallback(async () => {
    if (!selectedDoctor) return;
    setLoading(true);
    try {
      const [avRes, excRes] = await Promise.all([
        fetchDoctorAvailability(selectedDoctor),
        fetchDoctorExceptions(selectedDoctor),
      ]);
      setAvailability(avRes.data || []);
      setExceptions(excRes.data || []);
    } catch {
      setAvailability([]);
      setExceptions([]);
    } finally {
      setLoading(false);
    }
  }, [selectedDoctor]);

  useEffect(() => { loadDoctorData(); }, [loadDoctorData]);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  const toggleDay = async (weekday) => {
    if (busy) return;
    setBusy(true);
    try {
      const existing = availability.find(a => a.weekday === weekday);
      if (existing) {
        await deleteDoctorAvailability(existing.id);
        setAvailability(availability.filter(a => a.id !== existing.id));
      } else {
        const res = await createDoctorAvailability({ doctor: selectedDoctor, weekday });
        setAvailability([...availability, res.data]);
      }
    } catch (err) {
      setToast({ type: 'error', msg: err.response?.data?.detail || 'فشل التحديث' });
    } finally {
      setBusy(false);
    }
  };

  const addException = async () => {
    if (busy) return;
    if (!newExc.date) {
      setToast({ type: 'error', msg: 'التاريخ مطلوب' });
      return;
    }
    setBusy(true);
    try {
      const res = await createDoctorException({ doctor: selectedDoctor, ...newExc });
      setExceptions([...exceptions, res.data]);
      setNewExc({ date: '', exception_type: 'blocked', reason: '' });
      setToast({ type: 'success', msg: 'تم إضافة الاستثناء' });
    } catch (err) {
      setToast({ type: 'error', msg: err.response?.data?.detail || 'فشل الإضافة' });
    } finally {
      setBusy(false);
    }
  };

  const removeException = async (id) => {
    if (busy) return;
    setBusy(true);
    try {
      await deleteDoctorException(id);
      setExceptions(exceptions.filter(e => e.id !== id));
    } catch {
      setToast({ type: 'error', msg: 'فشل الحذف' });
    } finally {
      setBusy(false);
    }
  };

  const doctorName = (id) => {
    const d = doctors.find(d => d.id === id);
    return d ? `${d.first_name || ''} ${d.last_name || ''}`.trim() || d.username : `#${id}`;
  };

  return (
    <div className="availability-page" dir="rtl" style={{ padding: 24, maxWidth: 1100, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: '1.6rem', fontWeight: 700, marginBottom: 4, display: 'flex', gap: 10, alignItems: 'center' }}>
          <Users size={26} color="#667eea" /> توفر الدكاترة
        </h1>
        <p style={{ color: '#888', fontSize: '0.9rem' }}>
          إدارة الأيام المتاحة لكل دكتور + استثناءات التواريخ (سفر، مرض، إلخ)
        </p>
      </div>

      {/* Doctor selector */}
      <div style={{ ...cardStyle, marginBottom: 20, display: 'flex', gap: 12, alignItems: 'end' }}>
        <div style={{ flex: 1 }}>
          <label style={labelStyle}>اختر الدكتور</label>
          <select value={selectedDoctor || ''} onChange={(e) => setSelectedDoctor(parseInt(e.target.value))} style={inputStyle}>
            {doctors.map((d) => (
              <option key={d.id} value={d.id}>
                {`${d.first_name || ''} ${d.last_name || ''}`.trim() || d.username} (#{d.id})
              </option>
            ))}
          </select>
        </div>
        <button onClick={loadDoctorData} disabled={loading} style={btnSecondary}>
          <RefreshCw size={14} /> تحديث
        </button>
      </div>

      {selectedDoctor && (
        <>
          {/* Weekly availability */}
          <div style={{ ...cardStyle, marginBottom: 20 }}>
            <h3 style={{ marginTop: 0, marginBottom: 12, fontSize: '1rem', fontWeight: 700 }}>
              📅 التوفر الأسبوعي — {doctorName(selectedDoctor)}
            </h3>
            <p style={{ fontSize: '0.82rem', color: '#888', marginBottom: 16 }}>
              اختر الأيام التي يكون فيها الدكتور متاحاً (طوال اليوم حسب ساعات العمل في الإعدادات)
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {WEEKDAYS.map((w) => {
                const isActive = availability.some(a => a.weekday === w.value);
                return (
                  <button
                    key={w.value}
                    onClick={() => toggleDay(w.value)}
                    disabled={busy}
                    style={{
                      padding: '10px 16px', borderRadius: 8, cursor: 'pointer',
                      fontSize: '0.85rem', fontWeight: 600,
                      border: `1.5px solid ${isActive ? '#667eea' : '#cbd5e1'}`,
                      background: isActive ? '#667eea' : '#fff',
                      color: isActive ? '#fff' : '#475569',
                      transition: 'all 0.2s',
                    }}
                  >
                    {isActive ? '✓ ' : ''}{w.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Date exceptions */}
          <div style={{ ...cardStyle, marginBottom: 20 }}>
            <h3 style={{ marginTop: 0, marginBottom: 12, fontSize: '1rem', fontWeight: 700 }}>
              ⚠️ استثناءات التواريخ
            </h3>
            <p style={{ fontSize: '0.82rem', color: '#888', marginBottom: 16 }}>
              إضافة تواريخ محددة يتجاوز قاعدة التوفر الأسبوعي (سفر، مرض، إجازة، أو توفّر استثنائي)
            </p>

            {/* Add new */}
            <div style={{ display: 'grid', gridTemplateColumns: '140px 140px 1fr auto', gap: 8, marginBottom: 16, alignItems: 'end' }}>
              <div>
                <label style={labelStyle}>التاريخ</label>
                <input type="date" value={newExc.date} onChange={(e) => setNewExc({ ...newExc, date: e.target.value })} style={inputStyle} />
              </div>
              <div>
                <label style={labelStyle}>النوع</label>
                <select value={newExc.exception_type} onChange={(e) => setNewExc({ ...newExc, exception_type: e.target.value })} style={inputStyle}>
                  <option value="blocked">محظور</option>
                  <option value="available">متاح</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>السبب (اختياري)</label>
                <input type="text" placeholder="سفر، مرض..." value={newExc.reason} onChange={(e) => setNewExc({ ...newExc, reason: e.target.value })} style={inputStyle} />
              </div>
              <button onClick={addException} disabled={busy} style={btnPrimary}>
                <Plus size={14} /> إضافة
              </button>
            </div>

            {/* List */}
            {loading ? (
              <div style={{ textAlign: 'center', padding: 20, color: '#888' }}>جاري التحميل...</div>
            ) : exceptions.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 20, color: '#888', fontSize: '0.85rem' }}>لا توجد استثناءات</div>
            ) : (
              <table style={tableStyle}>
                <thead>
                  <tr>
                    <th style={thStyle}>التاريخ</th>
                    <th style={thStyle}>النوع</th>
                    <th style={thStyle}>السبب</th>
                    <th style={{ ...thStyle, textAlign: 'left' }}>حذف</th>
                  </tr>
                </thead>
                <tbody>
                  {exceptions.map((e) => (
                    <tr key={e.id}>
                      <td style={tdStyle}>{e.date}</td>
                      <td style={tdStyle}>
                        <span style={{
                          ...badgeStyle,
                          background: e.exception_type === 'blocked' ? '#fee2e2' : '#dcfce7',
                          color: e.exception_type === 'blocked' ? '#991b1b' : '#166534',
                        }}>
                          {e.exception_type === 'blocked' ? 'محظور' : 'متاح'}
                        </span>
                      </td>
                      <td style={tdStyle}>{e.reason || '—'}</td>
                      <td style={{ ...tdStyle, textAlign: 'left' }}>
                        <button onClick={() => removeException(e.id)} disabled={busy} style={{ ...btnIconSm, color: '#dc2626' }} title="حذف">
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </>
      )}

      {/* Toast */}
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

// ── Styles ──────────────────────────────────────────────────────────────────
const cardStyle = { background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: 20 };
const btnPrimary = { padding: '8px 16px', borderRadius: 8, border: 'none', cursor: 'pointer', background: '#667eea', color: '#fff', fontSize: '0.85rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6 };
const btnSecondary = { padding: '8px 16px', borderRadius: 8, border: '1px solid #cbd5e1', cursor: 'pointer', background: '#fff', color: '#475569', fontSize: '0.85rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6 };
const btnIconSm = { padding: 6, borderRadius: 6, border: '1px solid #cbd5e1', cursor: 'pointer', background: '#fff', color: '#475569', display: 'inline-flex', alignItems: 'center' };
const labelStyle = { display: 'block', fontSize: '0.78rem', color: '#475569', marginBottom: 4, fontWeight: 600 };
const inputStyle = { width: '100%', padding: '8px 12px', borderRadius: 8, border: '1.5px solid #cbd5e1', fontSize: '0.88rem', outline: 'none', boxSizing: 'border-box' };
const tableStyle = { width: '100%', borderCollapse: 'collapse', background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, overflow: 'hidden', fontSize: '0.85rem' };
const thStyle = { padding: '10px 12px', textAlign: 'right', fontSize: '0.75rem', fontWeight: 700, color: '#475569', background: '#f8fafc', borderBottom: '1px solid #e2e8f0' };
const tdStyle = { padding: '10px 12px', fontSize: '0.83rem', color: '#1e293b', borderBottom: '1px solid #f1f5f9' };
const badgeStyle = { padding: '2px 10px', borderRadius: 20, fontSize: '0.72rem', fontWeight: 600 };
