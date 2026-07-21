/**
 * HodGradesSummary — رئيس القسم يرى علامات مشاريع قسمه مع إمكانية الفلترة
 */
import React, { useState, useEffect, useCallback } from 'react';
import { fetchHodGradesSummary } from '../api';

const S = {
  wrap:       { padding: 24, direction: 'rtl' },
  toolbar:    { display: 'flex', gap: 12, alignItems: 'center', marginBottom: 20, flexWrap: 'wrap' },
  title:      { fontSize: '1.3rem', fontWeight: 700, flex: 1 },
  btn:        { padding: '8px 18px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: '0.87rem', fontWeight: 600 },
  btnFilter:  { background: '#f0f0ff', color: '#5b5fc7', border: '1.5px solid #c0c7ff' },
  semInput:   { padding: '7px 12px', borderRadius: 8, border: '1.5px solid #c0c7ff', fontSize: '0.87rem', width: 160 },
  table:      { width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' },
  th:         { background: '#4F46E5', color: '#fff', padding: '9px 12px', textAlign: 'center', fontWeight: 600, whiteSpace: 'nowrap' },
  td:         { padding: '8px 12px', borderBottom: '1px solid #e5e7eb', textAlign: 'center', verticalAlign: 'middle' },
  tdTitle:    { textAlign: 'right', maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  scoreCell:  { fontWeight: 600, color: '#4F46E5' },
  nullCell:   { color: '#bbb' },
  totalCell:  { fontWeight: 800, color: '#059669' },
  evenRow:    { background: '#f8f7ff' },
  error:      { padding: '10px 14px', background: '#fff5f5', color: '#c0392b', borderRadius: 8, marginBottom: 12, fontSize: '0.85rem' },
  empty:      { textAlign: 'center', padding: 60, color: '#888' },
};

const PROJECT_TYPE_AR = {
  semester: 'فصلي',
  graduation_1: 'تخرج 1',
  graduation_2: 'تخرج 2',
};

const PROJECT_TYPE_OPTIONS = [
  { value: '', label: 'كل الأنواع' },
  { value: 'semester', label: 'فصلي' },
  { value: 'graduation_1', label: 'تخرج 1' },
  { value: 'graduation_2', label: 'تخرج 2' },
];

const COMMITTEE_TYPE_OPTIONS = [
  { value: '',                label: 'كل اللجان' },
  { value: 'seminar_1',       label: 'سيمينار 1' },
  { value: 'seminar_2',       label: 'سيمينار 2' },
  { value: 'technical',       label: 'لجنة فنية' },
  { value: 'final_discussion',label: 'مناقشة نهائية' },
];

// الحد الأقصى لكل نوع لجنة (لعرضه بجانب العلامة)
const COMMITTEE_MAX = {
  seminar_1: 10,
  seminar_2: 10,
  technical: 20,
  final_discussion: 30,
};

export default function HodGradesSummary() {
  const [data,          setData]          = useState(null);
  const [loading,       setLoading]       = useState(true);
  const [error,         setError]         = useState('');
  const [semester,      setSemester]      = useState('');
  const [projectType,   setProjectType]   = useState('');
  const [committeeType, setCommitteeType] = useState('');
  const [draftSem,      setDraftSem]      = useState('');
  const [draftType,     setDraftType]     = useState('');
  const [draftCommittee,setDraftCommittee]= useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const r = await fetchHodGradesSummary(
        semester || undefined,
        projectType || undefined,
        committeeType || undefined
      );
      setData(r.data);
    }
    catch (e) { setError(e.response?.data?.detail || 'تعذّر التحميل.'); }
    finally { setLoading(false); }
  }, [semester, projectType, committeeType]);

  useEffect(() => { load(); }, [load]);

  const projects = data?.projects || [];
  // وضع فلتر لجنة محدد: عرض عمود علامة واحد فقط
  const singleCommitteeMode = Boolean(committeeType);
  const selectedCommitteeLabel = data?.active_committee?.label || COMMITTEE_TYPE_OPTIONS.find(o => o.value === committeeType)?.label || '';
  const selectedCommitteeMax = data?.active_committee?.max_score || COMMITTEE_MAX[committeeType] || null;

  const visibleColumns = singleCommitteeMode
    ? [
        { key: 'student_name', label: 'اسم الطالب' },
        { key: 'title', label: 'عنوان المشروع' },
        { key: 'student_uid', label: 'الرقم الجامعي' },
        { key: 'score', label: `علامة ${selectedCommitteeLabel || 'اللجنة'}${selectedCommitteeMax ? ` /${selectedCommitteeMax}` : ''}` },
      ]
    : [
        { key: 'student_name', label: 'اسم الطالب' },
        { key: 'title', label: 'عنوان المشروع' },
        { key: 'student_uid', label: 'الرقم الجامعي' },
        { key: 'seminar_1', label: 'سيمينار 1 /10' },
        { key: 'seminar_2', label: 'سيمينار 2 /10' },
        { key: 'technical', label: 'لجنة فنية /20' },
        { key: 'final_discussion', label: 'مناقشة نهائية /30' },
        { key: 'report', label: 'تقرير /30' },
        { key: 'total', label: 'المجموع /100' },
      ];

  return (
    <div style={S.wrap}>
      <div style={S.toolbar}>
        <div style={S.title}>علامات مشاريع القسم ({data?.count ?? '…'})</div>
        <input
          style={S.semInput}
          placeholder="الفصل الدراسي (اختياري)"
          value={draftSem}
          onChange={(e) => setDraftSem(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && setSemester(draftSem)}
        />
        <select
          style={S.semInput}
          value={draftType}
          onChange={(e) => setDraftType(e.target.value)}
        >
          {PROJECT_TYPE_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <select
          style={S.semInput}
          value={draftCommittee}
          onChange={(e) => setDraftCommittee(e.target.value)}
        >
          {COMMITTEE_TYPE_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <button
          style={{ ...S.btn, ...S.btnFilter }}
          onClick={() => {
            setSemester(draftSem);
            setProjectType(draftType);
            setCommitteeType(draftCommittee);
          }}
        >
          تصفية
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
                {visibleColumns.map((column) => (
                  <th key={column.key} style={S.th}>{column.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {projects.map((p, idx) => {
                const isEven = idx % 2 === 0;
                const Score = ({ val, max }) =>
                  val != null
                    ? <span style={S.scoreCell}>{val}<span style={{ color: '#999', fontWeight: 400 }}>{max != null ? `/${max}` : ''}</span></span>
                    : <span style={S.nullCell}>—</span>;

                return (
                  <tr key={`${p.project_source}-${p.project_id}-${p.student_uid}`}
                      style={isEven ? S.evenRow : {}}>
                    <td style={{ ...S.td, textAlign: 'right' }}>{p.student_name}</td>
                    <td style={{ ...S.td, ...S.tdTitle }} title={p.title}>{p.title}</td>
                    <td style={S.td}>{p.student_uid}</td>
                    {singleCommitteeMode
                      ? <td style={S.td}><Score val={p.score} max={selectedCommitteeMax} /></td>
                      : <>
                          <td style={S.td}><Score val={p.seminar_1}        max={10} /></td>
                          <td style={S.td}><Score val={p.seminar_2}        max={10} /></td>
                          <td style={S.td}><Score val={p.technical}        max={20} /></td>
                          <td style={S.td}><Score val={p.final_discussion} max={30} /></td>
                          <td style={S.td}><Score val={p.report}           max={30} /></td>
                          <td style={S.td}><span style={S.totalCell}>{p.total}</span></td>
                        </>
                    }
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
