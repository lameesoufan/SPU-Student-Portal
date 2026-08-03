import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Download, FileText, GraduationCap, Upload } from 'lucide-react';
import { uploadProjectReport, fetchMyGrades, downloadProjectReport } from '../api';
import { EmptyState, LoadingState, PageAlert, PageHeader, PageShell } from './ui/PagePrimitives';

const S = {
  wrap: { maxWidth: 1100, margin: '0 auto', direction: 'rtl' },
  title: { fontSize: '1.3rem', fontWeight: 700, marginBottom: 20 },
  card: { background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 16, marginBottom: 20, overflow: 'hidden', boxShadow: 'var(--shadow-sm)' },
  head: { padding: '14px 18px', background: 'var(--primary-light)', color: 'var(--text)', fontWeight: 900, borderBottom: '1px solid var(--border)' },
  body: { padding: '18px' },
  section: { marginBottom: 22 },
  sectionTitle: { fontSize: '0.98rem', fontWeight: 900, color: 'var(--text)', marginBottom: 10 },
  tableWrap: { width: '100%', overflowX: 'auto', border: '1px solid var(--border)', borderRadius: 12 },
  table: { width: '100%', borderCollapse: 'collapse', minWidth: 620, fontSize: '0.86rem', background: 'var(--card)' },
  th: { padding: '11px 12px', textAlign: 'right', background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)', fontWeight: 800, whiteSpace: 'nowrap' },
  td: { padding: '11px 12px', textAlign: 'right', borderBottom: '1px solid var(--border-light)', verticalAlign: 'top', color: 'var(--text-secondary)' },
  score: { fontWeight: 900, fontSize: '0.95rem', color: 'var(--primary)' },
  scoreNull: { color: 'var(--text-faint)', fontWeight: 400, fontSize: '0.84rem' },
  memberList: { margin: 0, paddingRight: 18, lineHeight: 1.8 },
  muted: { color: 'var(--text-muted)' },
  total: { display: 'flex', justifyContent: 'space-between', padding: '12px 14px', marginTop: 10, borderRadius: 10, background: 'var(--primary-light)', border: '1px solid var(--primary-border)', fontWeight: 900, fontSize: '1.02rem' },
  uploadBox: { border: '2px dashed var(--primary-border)', borderRadius: 12, padding: '18px', textAlign: 'center', marginTop: 12, cursor: 'pointer', background: 'var(--primary-lighter)' },
  btn: { padding: '8px 16px', borderRadius: 10, border: 'none', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 6 },
  btnOutline: { background: 'var(--card)', color: 'var(--primary)', border: '1px solid var(--primary)' },
  chip: { display: 'inline-block', padding: '2px 10px', borderRadius: 20, fontSize: '0.75rem', fontWeight: 700 },
  error: { color: 'var(--danger-text)', background: 'var(--danger-bg)', border: '1px solid var(--danger-border)', borderRadius: 10, padding: '9px 14px', marginBottom: 12, fontSize: '0.85rem' },
  success: { color: 'var(--success-text)', background: 'var(--success-bg)', border: '1px solid var(--success-border)', borderRadius: 10, padding: '9px 14px', marginBottom: 12, fontSize: '0.85rem' },
};

const GRADE_LABELS = {
  seminar_1: 'سيمينار 1',
  seminar_2: 'سيمينار 2',
  technical: 'لجنة فنية',
  final_discussion: 'مناقشة نهائية',
};

const COMMITTEE_TYPES = ['seminar_1', 'seminar_2', 'technical', 'final_discussion'];
const MAX_SCORES = { seminar_1: 10, seminar_2: 10, technical: 20, final_discussion: 30 };

export default function MyGrades() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const r = await fetchMyGrades();
      setData(r.data);
      setError('');
    } catch (e) {
      setError(e.response?.data?.detail || 'تعذّر تحميل العلامات.');
    } finally {
      if (!silent) setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const refresh = () => load(true);
    const intervalId = window.setInterval(refresh, 60000);
    window.addEventListener('focus', refresh);
    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener('focus', refresh);
    };
  }, [load]);

  if (loading) return <LoadingState label="جاري تحميل العلامات..." />;
  if (error) return <PageShell maxWidth="max-w-5xl"><PageAlert>{error}</PageAlert></PageShell>;

  const projects = data?.projects || [];
  if (!projects.length) return <PageShell maxWidth="max-w-5xl"><PageHeader icon={GraduationCap} title="علاماتي" description="تابع علامات مشروعك ولجان التقييم والتقرير النهائي." /><EmptyState title="لا توجد مشاريع نشطة" description="ستظهر علامتك هنا بعد ربطك بمشروع نشط." /></PageShell>;

  return (
    <PageShell maxWidth="max-w-5xl">
      <PageHeader
        icon={GraduationCap}
        title="علاماتي"
        description="تابع علامات المراحل، أعضاء اللجان، وملف التقرير الخاص بمشروعك."
        badge={`${projects.length} مشروع`}
      />
      <div style={S.wrap}>
        {projects.map((proj) => (
          <ProjectGradeCard key={`${proj.project_source}-${proj.project_id}`} proj={proj} onReload={load} />
        ))}
      </div>
    </PageShell>
  );
}

function getAllCommitteeMembers(committee) {
  if (!committee) return [];

  const people = [committee.chair, ...(committee.members || [])].filter(Boolean);
  const seen = new Set();

  return people.filter((person) => {
    const key = person.id ?? person.email ?? person.name;
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return Boolean(person.name);
  });
}

function ProjectGradeCard({ proj, onReload }) {
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState('');
  const [msgType, setMsgType] = useState('');
  const [downloading, setDown] = useState(false);
  const fileRef = useRef();

  const gradeMap = proj.grades || {};
  const committeeMap = proj.committees || {};
  const fdGrade = gradeMap.final_discussion;

  const handleUpload = async (file) => {
    if (!file) return;
    setUploading(true);
    setMsg('');
    setMsgType('');
    try {
      const fd = new FormData();
      fd.append('project_source', proj.project_source);
      fd.append('project_id', proj.project_id);
      fd.append('semester', gradeMap?.seminar_1?.semester || '');
      fd.append('file', file);
      await uploadProjectReport(fd);
      setMsg('تم رفع التقرير بنجاح.');
      setMsgType('success');
      onReload();
    } catch (e) {
      setMsg(e.response?.data?.detail || 'فشل رفع التقرير.');
      setMsgType('error');
    } finally {
      setUploading(false);
    }
  };

  const handleDownload = async () => {
    setDown(true);
    try {
      const r = await downloadProjectReport(proj.project_source, proj.project_id);
      const url = URL.createObjectURL(new Blob([r.data]));
      const name = proj.report?.original_name || 'report';
      const a = document.createElement('a');
      a.href = url;
      a.download = name;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setMsg('فشل تحميل التقرير.');
      setMsgType('error');
    } finally {
      setDown(false);
    }
  };

  return (
    <div style={S.card}>
      <div style={S.head} className="flex items-center gap-2"><FileText size={17} className="text-[var(--primary)]" />{proj.project_title}</div>
      <div style={S.body}>
        {msg && <div style={msgType === 'success' ? S.success : S.error}>{msg}</div>}

        <section style={S.section}>
          <div style={S.sectionTitle}>جدول العلامات</div>
          <div style={S.tableWrap}>
            <table style={S.table}>
              <thead>
                <tr>
                  <th style={S.th}>المرحلة</th>
                  <th style={S.th}>العلامة</th>
                  <th style={S.th}>العلامة العظمى</th>
                  <th style={S.th}>الحالة</th>
                </tr>
              </thead>
              <tbody>
                {COMMITTEE_TYPES.map((ct) => {
                  const grade = gradeMap[ct];
                  const entered = grade?.score_main != null;
                  return (
                    <tr key={ct}>
                      <td style={S.td}>{GRADE_LABELS[ct]}</td>
                      <td style={S.td}>{entered ? <span style={S.score}>{grade.score_main}</span> : <span style={S.scoreNull}>لم تُدخَل بعد</span>}</td>
                      <td style={S.td}>{MAX_SCORES[ct]}</td>
                      <td style={S.td}>{entered ? 'مدخلة' : 'بانتظار الإدخال'}</td>
                    </tr>
                  );
                })}
                <tr>
                  <td style={S.td}>تقرير المشروع</td>
                  <td style={S.td}>{fdGrade?.score_report != null ? <span style={S.score}>{fdGrade.score_report}</span> : <span style={S.scoreNull}>لم تُدخَل بعد</span>}</td>
                  <td style={S.td}>30</td>
                  <td style={S.td}>{fdGrade?.score_report != null ? 'مدخلة' : 'بانتظار الإدخال'}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div style={S.total}>
            <span>المجموع الكلي</span>
            <span style={{ color: 'var(--primary)' }}>{proj.total_score} / 100</span>
          </div>
        </section>

        <section style={S.section}>
          <div style={S.sectionTitle}>جدول اللجان</div>
          <div style={S.tableWrap}>
            <table style={S.table}>
              <thead>
                <tr>
                  <th style={S.th}>المرحلة</th>
                  <th style={S.th}>أعضاء اللجنة</th>
                  <th style={S.th}>التاريخ والوقت</th>
                  <th style={S.th}>المكان</th>
                </tr>
              </thead>
              <tbody>
                {COMMITTEE_TYPES.map((ct) => {
                  const committee = committeeMap[ct];
                  const members = getAllCommitteeMembers(committee);
                  const timeText = [committee?.start_time, committee?.end_time].filter(Boolean).join(' - ');
                  const place = committee?.room_name || committee?.location;

                  return (
                    <tr key={ct}>
                      <td style={S.td}>{GRADE_LABELS[ct]}</td>
                      <td style={S.td}>
                        {members.length ? (
                          <ul style={S.memberList}>
                            {members.map((member) => <li key={member.id ?? member.email ?? member.name}>{member.name}</li>)}
                          </ul>
                        ) : (
                          <span style={S.scoreNull}>لم تُحدَّد اللجنة بعد</span>
                        )}
                      </td>
                      <td style={S.td}>
                        {committee?.date || timeText ? (
                          <div>
                            {committee?.date && <div>{committee.date}</div>}
                            {timeText && <div style={S.muted}>{timeText}</div>}
                          </div>
                        ) : <span style={S.scoreNull}>غير محدد</span>}
                      </td>
                      <td style={S.td}>{place || <span style={S.scoreNull}>غير محدد</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: 6, color: 'var(--text-secondary)' }}>
            تقرير المشروع
            {proj.report_uploaded && (
              <span style={{ ...S.chip, background: 'var(--success-bg)', color: 'var(--success-text)', marginRight: 8 }}>✔ مرفوع</span>
            )}
          </div>

          {proj.report_uploaded && (
            <div style={{ marginBottom: 8, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{proj.report.original_name}</span>
              <button style={{ ...S.btn, ...S.btnOutline }} onClick={handleDownload} disabled={downloading}>
                {downloading ? 'جاري التحميل...' : <><Download size={14} /> تحميل التقرير</>}
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
              : <span style={{ color: 'var(--primary)' }} className="inline-flex items-center justify-center gap-2"><Upload size={16} />{proj.report_uploaded ? 'تحديث التقرير' : 'رفع تقرير المشروع'} (PDF/Word/ZIP، حتى 10 MB)</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
