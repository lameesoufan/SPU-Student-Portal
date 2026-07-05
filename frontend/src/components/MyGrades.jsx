import React, { useState, useEffect, useCallback, useRef } from 'react';
import { uploadProjectReport, fetchMyGrades, downloadProjectReport } from '../api';

/* ── simple inline styles to avoid a separate CSS file ── */
const S = {
  wrap:      { padding: '24px', maxWidth: 800, margin: '0 auto', direction: 'rtl' },
  title:     { fontSize: '1.3rem', fontWeight: 700, marginBottom: 20 },
  card:      { background: 'var(--card-bg,#fff)', border: '1px solid var(--border,#e5e7eb)', borderRadius: 12, marginBottom: 20, overflow: 'hidden' },
  head:      { padding: '12px 18px', background: 'linear-gradient(135deg,#667eea,#764ba2)', color: '#fff', fontWeight: 700 },
  body:      { padding: '14px 18px' },
  row:       { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--border-light,#f3f4f6)', fontSize: '0.87rem' },
  label:     { color: 'var(--text-secondary,#666)', flex: 1 },
  score:     { fontWeight: 700, fontSize: '1rem', color: '#667eea' },
  scoreNull: { color: '#bbb', fontWeight: 400, fontSize: '0.85rem' },
  total:     { display: 'flex', justifyContent: 'space-between', padding: '10px 0 0', fontWeight: 700, fontSize: '1.05rem' },
  uploadBox: { border: '2px dashed #c0c7ff', borderRadius: 10, padding: '18px', textAlign: 'center', marginTop: 12, cursor: 'pointer', background: '#f8f7ff' },
  btn:       { padding: '8px 18px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600 },
  btnPrimary:{ background: '#667eea', color: '#fff' },
  btnOutline:{ background: '#fff', color: '#667eea', border: '1.5px solid #667eea' },
  chip:      { display: 'inline-block', padding: '2px 10px', borderRadius: 20, fontSize: '0.75rem', fontWeight: 600 },
  error:     { color: '#c0392b', background: '#fff5f5', borderRadius: 8, padding: '8px 14px', marginBottom: 12, fontSize: '0.85rem' },
  success:   { color: '#166534', background: '#f0fdf4', borderRadius: 8, padding: '8px 14px', marginBottom: 12, fontSize: '0.85rem' },
};

const GRADE_LABELS = {
  seminar_1:        'سيمينار 1',
  seminar_2:        'سيمينار 2',
  technical:        'لجنة فنية',
  final_discussion: 'مناقشة نهائية',
};
const MAX_SCORES = { seminar_1: 10, seminar_2: 10, technical: 20, final_discussion: 30, report: 30 };

export default function MyGrades() {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try { const r = await fetchMyGrades(); setData(r.data); }
    catch (e) { setError(e.response?.data?.detail || 'تعذّر تحميل العلامات.'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div style={{ padding: 40, textAlign: 'center' }}>جاري التحميل...</div>;
  if (error)   return <div style={{ ...S.error, margin: 24 }}>{error}</div>;
  const projects = data?.projects || [];
  if (!projects.length) return <div style={{ padding: 24, textAlign: 'center', color: '#888' }}>لا توجد مشاريع نشطة.</div>;

  return (
    <div style={S.wrap}>
      <div style={S.title}>علاماتي</div>
      {projects.map((proj) => (
        <ProjectGradeCard key={`${proj.project_source}-${proj.project_id}`} proj={proj} onReload={load} />
      ))}
    </div>
  );
}

function ProjectGradeCard({ proj, onReload }) {
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg]             = useState('');
  const [msgType, setMsgType]     = useState('');
  const [downloading, setDown]    = useState(false);
  const fileRef = useRef();

  // grades هي الآن { committee_type: gradeObj } بدل array
  const gradeMap = proj.grades || {};
  const fdGrade  = gradeMap['final_discussion'];

  const handleUpload = async (file) => {
    if (!file) return;
    setUploading(true);
    setMsg(''); setMsgType('');
    try {
      const fd = new FormData();
      fd.append('project_source', proj.project_source);
      fd.append('project_id',     proj.project_id);
      fd.append('semester',       gradeMap?.seminar_1?.semester || '');
      fd.append('file', file);
      await uploadProjectReport(fd);
      setMsg('تم رفع التقرير بنجاح.'); setMsgType('success');
      onReload();
    } catch (e) {
      setMsg(e.response?.data?.detail || 'فشل رفع التقرير.'); setMsgType('error');
    } finally { setUploading(false); }
  };

  const handleDownload = async () => {
    setDown(true);
    try {
      const r = await downloadProjectReport(proj.project_source, proj.project_id);
      const url  = URL.createObjectURL(new Blob([r.data]));
      const name = proj.report?.original_name || 'report';
      const a    = document.createElement('a');
      a.href = url; a.download = name; a.click();
      URL.revokeObjectURL(url);
    } catch { setMsg('فشل تحميل التقرير.'); setMsgType('error'); }
    finally { setDown(false); }
  };

  return (
    <div style={S.card}>
      <div style={S.head}>{proj.project_title}</div>
      <div style={S.body}>

        {msg && <div style={msgType === 'success' ? S.success : S.error}>{msg}</div>}

        {['seminar_1','seminar_2','technical'].map((ct) => {
          const g = gradeMap[ct];
          return (
            <div key={ct} style={S.row}>
              <span style={S.label}>{GRADE_LABELS[ct]}</span>
              <span>
                {g?.score_main != null
                  ? <span style={S.score}>{g.score_main} / {MAX_SCORES[ct]}</span>
                  : <span style={S.scoreNull}>لم تُدخَل بعد</span>}
              </span>
            </div>
          );
        })}

        <div style={S.row}>
          <span style={S.label}>مناقشة نهائية</span>
          <span>
            {fdGrade?.score_main != null
              ? <span style={S.score}>{fdGrade.score_main} / 30</span>
              : <span style={S.scoreNull}>لم تُدخَل بعد</span>}
          </span>
        </div>

        <div style={S.row}>
          <span style={S.label}>تقرير المشروع</span>
          <span>
            {fdGrade?.score_report != null
              ? <span style={S.score}>{fdGrade.score_report} / 30</span>
              : <span style={S.scoreNull}>لم تُدخَل بعد</span>}
          </span>
        </div>

        <div style={S.total}>
          <span>المجموع الكلي</span>
          <span style={{ color: '#667eea' }}>{proj.total_score} / 100</span>
        </div>

        {/* رفع التقرير */}
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 6, color: '#555' }}>
            تقرير المشروع
            {proj.report_uploaded && (
              <span style={{ ...S.chip, background: '#dcfce7', color: '#166534', marginRight: 8 }}>
                ✔ مرفوع
              </span>
            )}
          </div>

          {proj.report_uploaded && (
            <div style={{ marginBottom: 8, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.82rem', color: '#555' }}>{proj.report.original_name}</span>
              <button style={{ ...S.btn, ...S.btnOutline }} onClick={handleDownload} disabled={downloading}>
                {downloading ? '...' : 'تحميل'}
              </button>
            </div>
          )}

          <div
            style={S.uploadBox}
            onClick={() => fileRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); handleUpload(e.dataTransfer.files[0]); }}
          >
            <input
              ref={fileRef}
              type="file"
              style={{ display: 'none' }}
              accept=".pdf,.doc,.docx,.zip,.rar"
              onChange={(e) => handleUpload(e.target.files[0])}
            />
            {uploading
              ? <span>جاري الرفع...</span>
              : <span style={{ color: '#667eea' }}>
                  {proj.report_uploaded ? 'تحديث التقرير' : 'رفع تقرير المشروع'} (PDF/Word/ZIP، حتى 10 MB)
                </span>
            }
          </div>
        </div>

      </div>
    </div>
  );
}
