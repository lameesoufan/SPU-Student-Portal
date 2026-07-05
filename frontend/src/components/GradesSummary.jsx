/**
 * GradesSummary — العميد يرى ويصدّر علامات كل المشاريع
 */
import React, { useState, useEffect, useCallback } from 'react';
import { fetchGradesSummary, exportGrades } from '../api';

const S = {
  wrap:       { padding: 24, direction: 'rtl' },
  toolbar:    { display: 'flex', gap: 12, alignItems: 'center', marginBottom: 20, flexWrap: 'wrap' },
  title:      { fontSize: '1.3rem', fontWeight: 700, flex: 1 },
  btn:        { padding: '8px 18px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: '0.87rem', fontWeight: 600 },
  btnExport:  { background: '#10b981', color: '#fff' },
  btnFilter:  { background: '#f0f0ff', color: '#5b5fc7', border: '1.5px solid #c0c7ff' },
  semInput:   { padding: '7px 12px', borderRadius: 8, border: '1.5px solid #c0c7ff', fontSize: '0.87rem', width: 160 },
  table:      { width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' },
  th:         { background: '#4F46E5', color: '#fff', padding: '9px 12px', textAlign: 'center', fontWeight: 600, whiteSpace: 'nowrap' },
  td:         { padding: '8px 12px', borderBottom: '1px solid #e5e7eb', textAlign: 'center', verticalAlign: 'middle' },
  tdTitle:    { textAlign: 'right', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  tdStudents: { textAlign: 'right', fontSize: '0.78rem', color: '#555' },
  scoreCell:  { fontWeight: 600, color: '#4F46E5' },
  nullCell:   { color: '#bbb' },
  totalCell:  { fontWeight: 800, color: '#059669' },
  evenRow:    { background: '#f8f7ff' },
  badge:      { display: 'inline-block', padding: '2px 8px', borderRadius: 20, fontSize: '0.72rem', fontWeight: 600 },
  error:      { padding: '10px 14px', background: '#fff5f5', color: '#c0392b', borderRadius: 8, marginBottom: 12, fontSize: '0.85rem' },
  empty:      { textAlign: 'center', padding: 60, color: '#888' },
};

const DEPT_AR = {
  software_engineering:'برمجيات', artificial_intelligence:'ذكاء اصطناعي',
  information_security:'أمن سيبراني', communications:'اتصالات', control_robotics:'تحكم وروبوتات',
};

export default function GradesSummary() {
  const [data,      setData]      = useState(null);
  const [loading,   setLoading]   = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error,     setError]     = useState('');
  const [semester,  setSemester]  = useState('');
  const [draft,     setDraft]     = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { const r = await fetchGradesSummary(semester || undefined); setData(r.data); }
    catch (e) { setError(e.response?.data?.detail || 'تعذّر التحميل.'); }
    finally { setLoading(false); }
  }, [semester]);

  useEffect(() => { load(); }, [load]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const r   = await exportGrades(semester || undefined);
      const url = URL.createObjectURL(new Blob([r.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `grades${semester ? '_' + semester : ''}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) { setError('فشل التصدير.'); }
    finally { setExporting(false); }
  };

  const projects = data?.projects || [];

  return (
    <div style={S.wrap}>
      <div style={S.toolbar}>
        <div style={S.title}>علامات المشاريع ({data?.count ?? '…'})</div>
        <input
          style={S.semInput}
          placeholder="الفصل الدراسي (اختياري)"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && setSemester(draft)}
        />
        <button style={{ ...S.btn, ...S.btnFilter }} onClick={() => setSemester(draft)}>
          تصفية
        </button>
        <button style={{ ...S.btn, ...S.btnExport }} onClick={handleExport} disabled={exporting || loading}>
          {exporting ? 'جاري التصدير...' : '⬇ تصدير Excel'}
        </button>
      </div>

      {error && <div style={S.error}>{error}</div>}

      {loading && <div style={S.empty}>جاري التحميل...</div>}

      {!loading && projects.length === 0 && (
        <div style={S.empty}>لا توجد علامات مدخلة بعد.</div>
      )}

      {!loading && projects.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={S.table}>
            <thead>
              <tr>
                <th style={S.th}>المشروع</th>
                <th style={S.th}>القسم</th>
                <th style={S.th}>الطالب</th>
                <th style={S.th}>الرقم الجامعي</th>
                <th style={S.th}>سيمينار 1 /10</th>
                <th style={S.th}>سيمينار 2 /10</th>
                <th style={S.th}>لجنة فنية /20</th>
                <th style={S.th}>مناقشة نهائية /30</th>
                <th style={S.th}>تقرير /30</th>
                <th style={S.th}>المجموع /100</th>
              </tr>
            </thead>
            <tbody>
              {projects.map((p, idx) => {
                const isEven = idx % 2 === 0;
                const Score = ({ val, max }) =>
                  val != null
                    ? <span style={S.scoreCell}>{val}<span style={{ color: '#999', fontWeight: 400 }}>/{max}</span></span>
                    : <span style={S.nullCell}>—</span>;

                return (
                  <tr key={`${p.project_source}-${p.project_id}-${p.student_uid}`}
                      style={isEven ? S.evenRow : {}}>
                    <td style={{ ...S.td, ...S.tdTitle }} title={p.title}>{p.title}</td>
                    <td style={S.td}>{DEPT_AR[p.department] || p.department}</td>
                    <td style={{ ...S.td, textAlign: 'right' }}>{p.student_name}</td>
                    <td style={S.td}>{p.student_uid}</td>
                    <td style={S.td}><Score val={p.seminar_1}        max={10} /></td>
                    <td style={S.td}><Score val={p.seminar_2}        max={10} /></td>
                    <td style={S.td}><Score val={p.technical}        max={20} /></td>
                    <td style={S.td}><Score val={p.final_discussion} max={30} /></td>
                    <td style={S.td}><Score val={p.report}           max={30} /></td>
                    <td style={S.td}><span style={S.totalCell}>{p.total}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
