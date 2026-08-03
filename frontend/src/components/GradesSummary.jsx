/**
 * GradesSummary — العميد يرى ويصدّر علامات كل المشاريع
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import { BarChart3, Download, Filter } from 'lucide-react';
import { fetchGradesSummary, exportGrades } from '../api';
import { EmptyState, LoadingState, PageAlert, PageHeader, PageShell } from './ui/PagePrimitives';

const S = {
  wrap:       { direction: 'rtl' },
  toolbar:    { display: 'flex', gap: 10, alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', padding: 16, background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 16, boxShadow: 'var(--shadow-sm)' },
  title:      { fontSize: '1rem', fontWeight: 800, color: 'var(--text)', marginLeft: 'auto' },
  btn:        { padding: '9px 16px', borderRadius: 10, border: 'none', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 6 },
  btnExport:  { background: 'var(--success)', color: '#fff' },
  btnFilter:  { background: 'var(--primary-light)', color: 'var(--primary)', border: '1px solid var(--primary-border)' },
  semInput:   { padding: '9px 12px', borderRadius: 10, border: '1px solid var(--border)', fontSize: '0.84rem', minWidth: 150, background: 'var(--bg-input)', color: 'var(--text)', outline: 'none' },
  table:      { width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem', background: 'var(--card)' },
  th:         { background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', padding: '11px 12px', textAlign: 'center', fontWeight: 800, whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' },
  td:         { padding: '10px 12px', borderBottom: '1px solid var(--border-light)', textAlign: 'center', verticalAlign: 'middle', color: 'var(--text-secondary)' },
  tdTitle:    { textAlign: 'right', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--text)' },
  tdStudents: { textAlign: 'right', fontSize: '0.78rem', color: 'var(--text-muted)' },
  scoreCell:  { fontWeight: 800, color: 'var(--primary)' },
  nullCell:   { color: 'var(--text-faint)' },
  totalCell:  { fontWeight: 900, color: 'var(--success-text)' },
  evenRow:    { background: 'var(--primary-lighter)' },
  badge:      { display: 'inline-block', padding: '2px 8px', borderRadius: 20, fontSize: '0.72rem', fontWeight: 700 },
  error:      { padding: '10px 14px', background: 'var(--danger-bg)', color: 'var(--danger-text)', border: '1px solid var(--danger-border)', borderRadius: 10, marginBottom: 12, fontSize: '0.85rem' },
  empty:      { textAlign: 'center', padding: 60, color: 'var(--text-muted)' },
};

const DEPT_AR = {
  software_engineering:'برمجيات', artificial_intelligence:'ذكاء اصطناعي',
  information_security:'أمن سيبراني', communications:'اتصالات', control_robotics:'تحكم وروبوتات',
};

const PROJECT_TYPE_AR = {
  semester: 'فصلي',
  graduation_1: 'تخرج 1',
  graduation_2: 'تخرج 2',
};

const DEPT_OPTIONS = [
  { value: '', label: 'كل الأقسام' },
  { value: 'software_engineering', label: 'برمجيات' },
  { value: 'artificial_intelligence', label: 'ذكاء اصطناعي' },
  { value: 'information_security', label: 'أمن سيبراني' },
  { value: 'communications', label: 'اتصالات' },
  { value: 'control_robotics', label: 'تحكم وروبوتات' },
];

const PROJECT_TYPE_OPTIONS = [
  { value: '', label: 'كل الأنواع' },
  { value: 'semester', label: 'فصلي' },
  { value: 'graduation_1', label: 'تخرج 1' },
  { value: 'graduation_2', label: 'تخرج 2' },
];

const COMMITTEE_TYPE_OPTIONS = [
  { value: '', label: 'كل اللجان' },
  { value: 'seminar_1', label: 'سيمينار 1' },
  { value: 'seminar_2', label: 'سيمينار 2' },
  { value: 'technical', label: 'لجنة فنية' },
  { value: 'final_discussion', label: 'مناقشة نهائية' },
];

const COMMITTEE_MAX = {
  seminar_1: 10,
  seminar_2: 10,
  technical: 20,
  final_discussion: 30,
};

const normalizeExportDate = (rawValue) => {
  const value = String(rawValue || '').trim();
  if (!value) return null;

  let year;
  let month;
  let day;

  let match = value.match(/^(\d{4})[\/-](\d{1,2})[\/-](\d{1,2})$/);
  if (match) {
    [, year, month, day] = match;
  } else {
    match = value.match(/^(\d{1,2})[\/-](\d{1,2})[\/-](\d{4})$/);
    if (!match) return null;
    [, day, month, year] = match;
  }

  const y = Number(year);
  const m = Number(month);
  const d = Number(day);
  const candidate = new Date(Date.UTC(y, m - 1, d));
  if (
    candidate.getUTCFullYear() !== y
    || candidate.getUTCMonth() !== m - 1
    || candidate.getUTCDate() !== d
  ) return null;

  return `${String(y).padStart(4, '0')}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
};

async function getExportErrorMessage(error) {
  const fallback = 'فشل التصدير.';
  const payload = error?.response?.data;

  if (payload instanceof Blob) {
    try {
      const parsed = JSON.parse(await payload.text());
      return parsed?.detail || parsed?.error || fallback;
    } catch {
      return fallback;
    }
  }

  return payload?.detail || payload?.error || fallback;
}

export default function GradesSummary() {
  const [data,       setData]       = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [exporting,  setExporting]  = useState(false);
  const [error,      setError]      = useState('');
  const [semester,   setSemester]   = useState('');
  const [department, setDepartment] = useState('');
  const [projectType,setProjectType]= useState('');
  const [committeeType, setCommitteeType] = useState('');
  const [draftSem,   setDraftSem]   = useState('');
  const [draftDept,  setDraftDept]  = useState('');
  const [draftType,  setDraftType]  = useState('');
  const [draftCommittee, setDraftCommittee] = useState('');
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [exportDate, setExportDate] = useState('');
  const [exportProjectType, setExportProjectType] = useState('');
  const calendarInputRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { 
      const r = await fetchGradesSummary(
        semester || undefined,
        department || undefined,
        projectType || undefined,
        committeeType || undefined
      ); 
      setData(r.data); 
    }
    catch (e) { setError(e.response?.data?.detail || 'تعذّر التحميل.'); }
    finally { setLoading(false); }
  }, [semester, department, projectType, committeeType]);

  useEffect(() => { load(); }, [load]);

  const handleExport = async () => {
    if (!committeeType) {
      setError('اختر نوع اللجنة أولاً ثم اضغط تصفية قبل التصدير.');
      return;
    }
    if (!exportProjectType) {
      setError('اختر نوع المشروع: فصلي أو تخرج 1 أو تخرج 2.');
      return;
    }
    if (!exportDate.trim()) {
      setError('حدد تاريخ الوثيقة قبل التصدير.');
      return;
    }

    const normalizedExportDate = normalizeExportDate(exportDate);
    if (!normalizedExportDate) {
      setError('صيغة تاريخ الوثيقة غير صحيحة. استخدم YYYY/MM/DD أو DD/MM/YYYY، أو اختره من أيقونة التقويم.');
      return;
    }

    setExporting(true);
    setError('');
    try {
      const response = await exportGrades(
        semester || undefined,
        department || undefined,
        exportProjectType,
        committeeType,
        normalizedExportDate,
      );
      const url = URL.createObjectURL(new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      }));
      const link = document.createElement('a');
      link.href = url;
      link.download = `grades_${committeeType}_${exportProjectType}_${normalizedExportDate}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setShowExportDialog(false);
    } catch (exportError) {
      setError(await getExportErrorMessage(exportError));
    } finally {
      setExporting(false);
    }
  };

  const projects = data?.projects || [];
  const singleCommitteeMode = Boolean(committeeType);
  const selectedCommitteeLabel = data?.active_committee?.label || COMMITTEE_TYPE_OPTIONS.find(o => o.value === committeeType)?.label || '';
  const selectedCommitteeMax = data?.active_committee?.max_score || COMMITTEE_MAX[committeeType] || null;

  const visibleColumns = singleCommitteeMode
    ? [
        { key: 'student_name', label: 'اسم الطالب' },
        { key: 'student_uid', label: 'الرقم الجامعي' },
        { key: 'title', label: 'عنوان المشروع' },
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

  const getExportColumns = () => {
    if (singleCommitteeMode) {
      return [
        'project_id',
        'title',
        'department',
        'student_name',
        'student_uid',
        'score',
      ];
    } else {
      return [
        'project_id',
        'title',
        'department',
        'student_name',
        'student_uid',
        'seminar_1',
        'seminar_2',
        'technical',
        'final_discussion',
        'report',
        'total',
      ];
    }
  };

  return (
    <PageShell>
      <PageHeader
        icon={BarChart3}
        title="علامات المشاريع"
        description="استعرض علامات المشاريع حسب الفصل والقسم والنوع، ثم صدّر الوثيقة الرسمية."
        badge={`${data?.count ?? 0} سجل`}
      />
      <div style={S.wrap}>
      <div style={S.toolbar}>
        <input
          style={S.semInput}
          placeholder="الفصل الدراسي (اختياري)"
          value={draftSem}
          onChange={(e) => setDraftSem(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && setSemester(draftSem)}
        />
        <select
          style={S.semInput}
          value={draftDept}
          onChange={(e) => setDraftDept(e.target.value)}
        >
          {DEPT_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
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
            setDepartment(draftDept);
            setProjectType(draftType);
            setCommitteeType(draftCommittee);
          }}
        >
          <Filter size={14} /> تصفية
        </button>
        <button
          style={{ ...S.btn, ...S.btnExport }}
          onClick={() => {
            setError('');
            if (!committeeType) {
              setError('اختر نوع اللجنة أولاً ثم اضغط تصفية قبل التصدير.');
              return;
            }
            setExportProjectType(projectType || '');
            setExportDate('');
            setShowExportDialog(true);
          }}
          disabled={exporting || loading}
        >
          {exporting ? 'جاري التصدير...' : <><Download size={14} /> تصدير الوثيقة</>}
        </button>
      </div>

      {error && <PageAlert className="mb-4">{error}</PageAlert>}

      {showExportDialog && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="grades-export-dialog-title"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15,23,42,.48)',
            zIndex: 1000,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 20,
          }}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget && !exporting) setShowExportDialog(false);
          }}
        >
          <div style={{
            width: 'min(540px, 100%)',
            background: 'var(--card)',
            borderRadius: 16,
            padding: 24,
            boxShadow: '0 20px 60px rgba(0,0,0,.22)',
            direction: 'rtl',
          }}>
            <div id="grades-export-dialog-title" style={{ fontSize: 20, fontWeight: 800, marginBottom: 8 }}>
              إعداد وثيقة العلامات
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: 14, lineHeight: 1.8, marginBottom: 18 }}>
              اختر نوع المشروع ثم تاريخ الوثيقة. سيُستخدم القسم ونوع اللجنة المحددان في الفلاتر لطباعة الوثيقة الرسمية.
            </div>

            <div style={{ fontWeight: 700, marginBottom: 10 }}>1. نوع المشروع</div>
            <div style={{ display: 'grid', gap: 10, marginBottom: 20 }}>
              {[
                { value: 'semester', label: 'فصلي' },
                { value: 'graduation_1', label: 'تخرج 1' },
                { value: 'graduation_2', label: 'تخرج 2' },
              ].map((option) => (
                <label key={option.value} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  cursor: 'pointer',
                  border: exportProjectType === option.value ? '2px solid var(--primary)' : '1px solid var(--border)',
                  background: exportProjectType === option.value ? 'var(--primary-light)' : 'var(--bg-input)',
                  borderRadius: 10,
                  padding: '11px 13px',
                }}>
                  <input
                    type="radio"
                    name="export-project-type"
                    value={option.value}
                    checked={exportProjectType === option.value}
                    onChange={(event) => {
                      setExportProjectType(event.target.value);
                      setError('');
                    }}
                  />
                  <span style={{ fontWeight: 600 }}>{option.label}</span>
                </label>
              ))}
            </div>

            <label htmlFor="grades-export-date" style={{ display: 'block', fontWeight: 700, marginBottom: 8 }}>
              2. تاريخ الوثيقة
            </label>
            <div style={{ position: 'relative', marginBottom: 6 }}>
              <input
                id="grades-export-date"
                type="text"
                value={exportDate}
                onChange={(event) => {
                  setExportDate(event.target.value);
                  setError('');
                }}
                placeholder="مثال: 2026/08/02 أو 02/08/2026"
                inputMode="numeric"
                dir="ltr"
                style={{
                  ...S.semInput,
                  width: '100%',
                  boxSizing: 'border-box',
                  paddingLeft: 48,
                  textAlign: 'left',
                }}
              />
              <button
                type="button"
                aria-label="اختيار التاريخ من التقويم"
                title="اختيار التاريخ من التقويم"
                onClick={() => {
                  const input = calendarInputRef.current;
                  if (!input) return;
                  if (typeof input.showPicker === 'function') input.showPicker();
                  else input.click();
                }}
                style={{
                  position: 'absolute',
                  left: 5,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  width: 36,
                  height: 32,
                  border: 'none',
                  borderRadius: 7,
                  background: 'var(--primary-light)',
                  cursor: 'pointer',
                  fontSize: 18,
                }}
              >
                📅
              </button>
              <input
                ref={calendarInputRef}
                type="date"
                value={normalizeExportDate(exportDate) || ''}
                onChange={(event) => {
                  setExportDate(event.target.value);
                  setError('');
                }}
                tabIndex={-1}
                aria-hidden="true"
                style={{ position: 'absolute', width: 1, height: 1, opacity: 0, pointerEvents: 'none' }}
              />
            </div>
            <div style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 20 }}>
              يمكنك كتابة التاريخ يدويًا أو اختياره من أيقونة التقويم.
            </div>

            <div style={{
              borderRadius: 10,
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border)',
              padding: '10px 12px',
              color: 'var(--text-secondary)',
              fontSize: 13,
              marginBottom: 20,
            }}>
              نوع اللجنة: <strong>{COMMITTEE_TYPE_OPTIONS.find((option) => option.value === committeeType)?.label || '—'}</strong>
              {' · '}
              القسم: <strong>{DEPT_OPTIONS.find((option) => option.value === department)?.label || 'كل الأقسام'}</strong>
            </div>

            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-start' }}>
              <button
                type="button"
                style={{ ...S.btn, ...S.btnExport }}
                onClick={handleExport}
                disabled={exporting}
              >
                {exporting ? 'جاري إنشاء الوثيقة...' : 'إنشاء وثيقة الطباعة'}
              </button>
              <button
                type="button"
                style={{ ...S.btn, background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}
                onClick={() => setShowExportDialog(false)}
                disabled={exporting}
              >
                إلغاء
              </button>
            </div>
          </div>
        </div>
      )}

      {loading && <LoadingState label="جاري تحميل العلامات..." />}

      {!loading && projects.length === 0 && (
        <EmptyState title="لا توجد علامات مدخلة" description="ستظهر العلامات هنا بعد أن تبدأ اللجان بإدخال نتائج التقييم." />
      )}

      {!loading && projects.length > 0 && (
        <div style={{ overflowX: 'auto', border: '1px solid var(--border)', borderRadius: 16, boxShadow: 'var(--shadow-sm)' }}>
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
                    ? <span style={S.scoreCell}>{val}<span style={{ color: 'var(--text-faint)', fontWeight: 400 }}>/{max}</span></span>
                    : <span style={S.nullCell}>—</span>;

                return (
                  <tr key={`${p.project_source}-${p.project_id}-${p.student_uid}`}
                      style={isEven ? S.evenRow : {}}>
                    <td style={{ ...S.td, textAlign: 'right' }}>{p.student_name}</td>
                    <td style={S.td}>{p.student_uid}</td>
                    <td style={{ ...S.td, ...S.tdTitle }} title={p.title}>{p.title}</td>
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
    </PageShell>
  );
}