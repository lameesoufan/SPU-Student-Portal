/**
 * CollectiveGradingSettings
 * رئيس القسم يُفعّل/يُعطّل وضع التقييم الجماعي لكل لجنة
 */
import React, { useState, useEffect, useCallback } from 'react';
import { fetchGradingModes, setGradingMode } from '../api';

const S = {
  wrap:    { padding: 24, maxWidth: 820, margin: '0 auto', direction: 'rtl' },
  title:   { fontSize: '1.25rem', fontWeight: 700, marginBottom: 6 },
  sub:     { fontSize: '0.85rem', color: '#666', marginBottom: 20 },
  card:    { background: 'var(--card-bg,#fff)', border: '1px solid var(--border,#e5e7eb)', borderRadius: 10, marginBottom: 12, padding: '14px 18px', display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap' },
  info:    { flex: 1, minWidth: 180 },
  name:    { fontWeight: 600, fontSize: '0.93rem' },
  meta:    { fontSize: '0.78rem', color: '#888', marginTop: 2 },
  toggle:  { position: 'relative', display: 'inline-flex', alignItems: 'center', cursor: 'pointer', userSelect: 'none' },
  track:   (on) => ({
    width: 44, height: 24, borderRadius: 12, background: on ? '#667eea' : '#d1d5db',
    transition: 'background .2s', position: 'relative',
  }),
  thumb:   (on) => ({
    position: 'absolute', top: 2, left: on ? 22 : 2,
    width: 20, height: 20, borderRadius: '50%', background: '#fff',
    boxShadow: '0 1px 3px rgba(0,0,0,0.2)', transition: 'left .2s',
  }),
  label:   (on) => ({ marginRight: 10, fontSize: '0.82rem', fontWeight: 600, color: on ? '#667eea' : '#999' }),
  msg:     { padding: '8px 14px', borderRadius: 8, fontSize: '0.82rem' },
  ok:      { background: '#f0fdf4', color: '#166534' },
  err:     { background: '#fff5f5', color: '#c0392b' },
  badge:   (on) => ({
    display: 'inline-block', padding: '2px 10px', borderRadius: 20,
    fontSize: '0.73rem', fontWeight: 600,
    background: on ? '#ede9fe' : '#f3f4f6',
    color: on ? '#6d28d9' : '#6b7280',
  }),
};

const DEPT_AR = {
  software_engineering:'برمجيات', artificial_intelligence:'ذكاء اصطناعي',
  information_security:'أمن سيبراني', communications:'اتصالات', control_robotics:'تحكم وروبوتات',
};

export default function CollectiveGradingSettings({ user }) {
  const [committees, setCommittees] = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState('');
  const [msg,        setMsg]        = useState('');
  const [msgType,    setMsgType]    = useState('');
  const [toggling,   setToggling]   = useState(null); // committee_id being toggled

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const r = await fetchGradingModes();
      setCommittees(r.data.committees || []);
    } catch (e) { setError(e.response?.data?.detail || 'تعذّر التحميل.'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleToggle = async (c) => {
    setToggling(c.committee_id);
    setMsg(''); setMsgType('');
    try {
      const r = await setGradingMode(c.committee_id, !c.collective);
      setMsg(r.data.message); setMsgType('ok');
      setCommittees((prev) =>
        prev.map((x) =>
          x.committee_id === c.committee_id ? { ...x, collective: r.data.collective } : x
        )
      );
    } catch (e) {
      setMsg(e.response?.data?.detail || 'فشل التحديث.'); setMsgType('err');
    } finally { setToggling(null); }
  };

  if (loading) return <div style={{ padding: 40, textAlign: 'center' }}>جاري التحميل...</div>;

  return (
    <div style={S.wrap}>
      <div style={S.title}>إعدادات التقييم الجماعي</div>
      <div style={S.sub}>
        عند تفعيل الوضع الجماعي للجنة، يستطيع جميع أعضائها إدخال علاماتهم المستقلة
        وتُحسب العلامة النهائية كمتوسط لما أدخلوه.
      </div>

      {error && <div style={{ ...S.msg, ...S.err, marginBottom: 16 }}>{error}</div>}
      {msg   && <div style={{ ...S.msg, ...(msgType === 'ok' ? S.ok : S.err), marginBottom: 16 }}>{msg}</div>}

      {committees.length === 0 && (
        <div style={{ textAlign: 'center', color: '#888', padding: 40 }}>لا توجد لجان.</div>
      )}

      {committees.map((c) => (
        <div key={c.committee_id} style={S.card}>
          <div style={S.info}>
            <div style={S.name}>
              {c.committee_type_ar} — {c.department_ar} — {c.project_type_ar}
            </div>
            <div style={S.meta}>
              {c.semester && <span>{c.semester} · </span>}
              <span style={S.badge(c.collective)}>
                {c.collective ? 'جماعي' : 'فردي'}
              </span>
            </div>
          </div>

          {/* Toggle */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={S.label(c.collective)}>
              {c.collective ? 'مُفعَّل' : 'معطَّل'}
            </span>
            <div
              style={S.toggle}
              onClick={() => toggling !== c.committee_id && handleToggle(c)}
              role="switch"
              aria-checked={c.collective}
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && handleToggle(c)}
            >
              <div style={S.track(c.collective)}>
                <div style={S.thumb(c.collective)} />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
