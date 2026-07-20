/**
 * GradeEntry — رئيس اللجنة يدخل علامة مستقلة لكل طالب في الفريق.
 * في وضع التقييم الجماعي: كل عضو يُدخل مسودته والعلامة النهائية = المتوسط.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { fetchMyCommitteeGrades, enterBulkGrades, submitGradeDraft, downloadProjectReport } from '../../api';

const S = {
  wrap:        { padding: 24, maxWidth: 960, margin: '0 auto', direction: 'rtl' },
  title:       { fontSize: '1.3rem', fontWeight: 700, marginBottom: 20 },
  committee:   { background: 'var(--card-bg,#fff)', border: '1px solid var(--border,#e5e7eb)', borderRadius: 12, marginBottom: 20, overflow: 'hidden' },
  head:        { padding: '12px 18px', background: 'linear-gradient(135deg,#667eea,#764ba2)', color: '#fff', fontWeight: 700, display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  projectCard: { borderBottom: '1px solid var(--border-light,#f3f4f6)', padding: '14px 18px' },
  projectTitle:{ fontWeight: 600, fontSize: '0.95rem', marginBottom: 10 },
  studentRow:  { display: 'flex', gap: 12, alignItems: 'center', padding: '8px 0', borderBottom: '1px dashed #f0f0f8', flexWrap: 'wrap' },
  studentName: { flex: 1, minWidth: 140, fontSize: '0.88rem', fontWeight: 500 },
  inputGroup:  { display: 'flex', flexDirection: 'column', gap: 3 },
  inputLabel:  { fontSize: '0.73rem', color: '#888' },
  input:       { width: 72, padding: '5px 8px', borderRadius: 7, border: '1.5px solid #c0c7ff', fontSize: '0.9rem', textAlign: 'center' },
  inputDis:    { opacity: 0.4, cursor: 'not-allowed' },
  saveRow:     { display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 12 },
  btn:         { padding: '7px 18px', borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600 },
  btnPrimary:  { background: '#667eea', color: '#fff' },
  btnDl:       { background: '#f0f9ff', color: '#0284c7', border: '1.5px solid #bae6fd', cursor: 'pointer', borderRadius: 8, padding: '6px 12px', fontSize: '0.82rem', fontWeight: 600 },
  badge:       { display: 'inline-block', padding: '2px 8px', borderRadius: 20, fontSize: '0.72rem', fontWeight: 600, marginRight: 4 },
  savedBadge:  { background: '#dcfce7', color: '#166534' },
  warnBadge:   { background: '#fff7ed', color: '#92400e' },
  noBadge:     { background: '#fee2e2', color: '#991b1b' },
  msg:         { padding: '8px 14px', borderRadius: 8, fontSize: '0.83rem', marginBottom: 8 },
  msgErr:      { background: '#fff5f5', color: '#c0392b' },
  msgOk:       { background: '#f0fdf4', color: '#166534' },
  leaderStar:  { color: '#f59e0b', marginLeft: 4 },
};

const CTYPE_AR = {
  seminar_1:'سيمينار 1', seminar_2:'سيمينار 2',
  technical:'لجنة فنية', final_discussion:'مناقشة نهائية',
};
const MAX_MAIN = { seminar_1:10, seminar_2:10, technical:20, final_discussion:30 };

export default function GradeEntry() {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try   { const r = await fetchMyCommitteeGrades(); setData(r.data); }
    catch (e) { setError(e.response?.data?.detail || 'تعذّر التحميل.'); }
    finally   { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div style={{ padding: 40, textAlign: 'center' }}>جاري التحميل...</div>;
  if (error)   return <div style={{ ...S.msg, ...S.msgErr, margin: 24 }}>{error}</div>;

  const committees = data?.committees || [];
  if (!committees.length)
    return <div style={{ padding: 24, textAlign: 'center', color: '#888' }}>لا توجد لجان مسندة إليك كرئيس.</div>;

  return (
    <div style={S.wrap}>
      <div style={S.title}>إدخال العلامات</div>
      {committees.map((c) => (
        <CommitteeSection key={c.committee_id} committee={c} onReload={load} />
      ))}
    </div>
  );
}

function CommitteeSection({ committee: c, onReload }) {
  const isFinal    = c.committee_type === 'final_discussion';
  const collective = c.collective_mode;
  return (
    <div style={S.committee}>
      <div style={S.head}>
        <span>{CTYPE_AR[c.committee_type]} — {c.department_ar} {c.semester ? `(${c.semester})` : ''}</span>
        <span style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {collective && (
            <span style={{ fontSize: '0.76rem', background: 'rgba(255,255,255,0.2)', padding: '2px 9px', borderRadius: 20 }}>
              🤝 تقييم جماعي
            </span>
          )}
          <span style={{ fontSize: '0.82rem', opacity: 0.85 }}>
            /{MAX_MAIN[c.committee_type]}{isFinal ? ' + تقرير /30' : ''}
          </span>
        </span>
      </div>
      {c.projects.length === 0 && (
        <div style={{ padding: '14px 18px', color: '#aaa', fontSize: '0.85rem' }}>لا مشاريع.</div>
      )}
      {c.projects.map((p) => (
        <ProjectSection key={`${p.source}-${p.id}`} project={p} committee={c} onReload={onReload} />
      ))}
    </div>
  );
}

function ProjectSection({ project: p, committee: c, onReload }) {
  const isFinal = c.committee_type === 'final_discussion';
  const maxMain = MAX_MAIN[c.committee_type];

  // state: { [student_id]: { score_main, score_report, notes } }
  const buildInitial = () => {
    const init = {};
    p.students.forEach((s) => {
      // في الوضع الجماعي نستخدم my_draft، وإلا grade النهائية
      const src = c.collective_mode ? s.my_draft : s.grade;
      init[s.student_id] = {
        score_main:   src?.score_main   ?? '',
        score_report: src?.score_report ?? '',
        notes:        src?.notes || '',
      };
    });
    return init;
  };

  const [scores,     setScores]     = useState(buildInitial);
  const [saving,     setSaving]     = useState(false);
  const [msg,        setMsg]        = useState('');
  const [msgType,    setMsgType]    = useState('');
  const [downloading,setDown]       = useState(false);
  const [confirmUpdate, setConfirmUpdate] = useState(false);

  const setField = (studentId, field, val) =>
    setScores((prev) => ({ ...prev, [studentId]: { ...prev[studentId], [field]: val } }));

  const handleSave = async () => {
    setSaving(true); setMsg(''); setMsgType('');

    const grades = p.students.map((s) => {
      const vals = scores[s.student_id] || {};
      const item = {
        student_id: s.student_id,
        score_main: vals.score_main === '' ? 0 : Number(vals.score_main),
        notes:      vals.notes || '',
      };
      if (isFinal) item.score_report = vals.score_report === '' ? 0 : Number(vals.score_report);
      return item;
    });

    try {
      if (c.collective_mode) {
        // وضع جماعي → draft
        await submitGradeDraft({
          committee_id:   c.committee_id,
          project_source: p.source,
          project_id:     p.id,
          committee_type: c.committee_type,
          semester:       c.semester,
          grades,
        });
        setMsg('تم حفظ مسودتك. العلامة النهائية ستُحسب بعد اكتمال تقييمات الأعضاء.'); setMsgType('ok');
        setConfirmUpdate(false);
      } else {
        // وضع فردي → bulk final
        await enterBulkGrades({
          project_source: p.source,
          project_id:     p.id,
          committee_type: c.committee_type,
          committee_id:   c.committee_id,
          semester:       c.semester,
          grades,
          confirm_update: confirmUpdate,  // إضافة حقل التأكيد على مستوى المشروع
        });
        setMsg('تم حفظ العلامات.'); setMsgType('ok');
        setConfirmUpdate(false);
      }
      onReload();
    } catch (e) {
      const d = e.response?.data;
      // إذا كانت الاستجابة تطلب تأكيد
      if (e.response?.status === 409 && d?.requires_confirmation) {
        setMsg(d.message || 'توجد علامات مدخلة سابقاً. هل تريد تغيير العلامات بالتأكيد؟');
        setMsgType('warn');
        setSaving(false);
        return; // نخرج بدون رمي خطأ
      }
      setMsg(typeof d === 'string' ? d : d?.detail || JSON.stringify(d) || 'فشل الحفظ.');
      setMsgType('err');
      setConfirmUpdate(false);
    } finally { 
      setSaving(false);
    }
  };

  const handleDownload = async () => {
    setDown(true);
    try {
      const r   = await downloadProjectReport(p.source, p.id);
      const url = URL.createObjectURL(new Blob([r.data]));
      const a   = document.createElement('a');
      a.href = url; a.download = p.report?.original_name || 'report'; a.click();
      URL.revokeObjectURL(url);
    } catch { setMsg('فشل تحميل التقرير.'); setMsgType('err'); }
    finally { setDown(false); }
  };

  return (
    <div style={S.projectCard}>
      {/* عنوان المشروع + حالة التقرير */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 6 }}>
        <span style={S.projectTitle}>{p.title || `مشروع #${p.id}`}</span>
        {p.all_graded && <span style={{ ...S.badge, ...S.savedBadge }}>✔ علامات مكتملة</span>}
        {isFinal && (
          p.report_uploaded
            ? <span style={{ ...S.badge, ...S.savedBadge }}>✔ التقرير مرفوع</span>
            : <span style={{ ...S.badge, ...S.noBadge }}>✘ التقرير غير مرفوع</span>
        )}
        {isFinal && p.report_uploaded && (
          <button style={S.btnDl} onClick={handleDownload} disabled={downloading}>
            {downloading ? '...' : '⬇ تحميل التقرير'}
          </button>
        )}
      </div>

      {msg && (
        <div style={{ 
          ...S.msg, 
          ...(msgType === 'ok' ? S.msgOk : msgType === 'warn' ? { background: '#fffbeb', color: '#92400e' } : S.msgErr), 
          marginBottom: 8 
        }}>
          {msg}
          {msgType === 'warn' && (
            <div style={{ marginTop: 8, display: 'flex', gap: 10 }}>
              <button
                style={{ ...S.btn, ...S.btnPrimary }}
                onClick={() => {
                  setConfirmUpdate(true);
                  setMsg('');
                  setTimeout(() => handleSave(), 100);
                }}
              >
                نعم، تغيير العلامة
              </button>
              <button
                style={{ ...S.btn, background: '#e5e7eb', color: '#374151' }}
                onClick={() => {
                  setMsg('');
                  setMsgType('');
                  setConfirmUpdate(false);
                }}
              >
                لا، إلغاء
              </button>
            </div>
          )}
        </div>
      )}

      {/* صف هيدر الأعمدة */}
      <div style={{ display: 'flex', gap: 12, padding: '4px 0', fontSize: '0.75rem', color: '#888', fontWeight: 600 }}>
        <span style={{ flex: 1 }}>الطالب</span>
        <span style={{ width: 72, textAlign: 'center' }}>العلامة /{maxMain}</span>
        {isFinal && <span style={{ width: 72, textAlign: 'center' }}>التقرير /30</span>}
        <span style={{ width: 100 }}>ملاحظات</span>
      </div>

      {/* صف لكل طالب */}
      {p.students.map((s) => {
        const vals   = scores[s.student_id] || {};
        const noRep  = isFinal && !p.report_uploaded;

        return (
          <div key={s.student_id} style={S.studentRow}>
            <span style={S.studentName}>
              {s.is_leader && <span style={S.leaderStar}>★</span>}
              {s.student_name}
              {/* في الوضع الجماعي: أظهر مسودتي + العلامة النهائية (المتوسط) */}
              {c.collective_mode && s.my_draft && (
                <span style={{ ...S.badge, background: '#ede9fe', color: '#7c3aed', fontSize: '0.68rem', marginRight: 6 }}>
                  مسودتي: {s.my_draft.score_main ?? '—'}
                </span>
              )}
              {s.grade && (
                <span style={{ ...S.badge, ...S.savedBadge, fontSize: '0.68rem', marginRight: 6 }}>
                  {c.collective_mode ? 'متوسط: ' : ''}{s.grade.score_main ?? '—'}{isFinal ? ` + ${s.grade.score_report ?? '—'}` : ''}
                </span>
              )}
            </span>

            {/* علامة رئيسية */}
            <div style={S.inputGroup}>
              <input
                style={S.input}
                type="number" min={0} max={maxMain}
                value={vals.score_main}
                onChange={(e) => setField(s.student_id, 'score_main', e.target.value)}
                placeholder={`0-${maxMain}`}
              />
            </div>

            {/* علامة التقرير (مناقشة نهائية فقط) */}
            {isFinal && (
              <div style={S.inputGroup}>
                <input
                  style={{ ...S.input, ...(noRep ? S.inputDis : {}) }}
                  type="number" min={0} max={30}
                  value={vals.score_report}
                  onChange={(e) => setField(s.student_id, 'score_report', e.target.value)}
                  disabled={noRep}
                  title={noRep ? 'انتظر حتى يرفع الطلاب التقرير' : ''}
                  placeholder="0-30"
                />
              </div>
            )}

            {/* ملاحظات */}
            <input
              style={{ ...S.input, width: 100, fontSize: '0.78rem' }}
              type="text"
              value={vals.notes}
              onChange={(e) => setField(s.student_id, 'notes', e.target.value)}
              placeholder="ملاحظة (اختياري)"
            />
          </div>
        );
      })}

      <div style={S.saveRow}>
        <button
          style={{ ...S.btn, ...S.btnPrimary }}
          onClick={handleSave}
          disabled={saving}
        >
          {saving
            ? 'جاري الحفظ...'
            : c.collective_mode
              ? 'حفظ مسودتي'
              : 'حفظ علامات المشروع'
          }
        </button>
      </div>
    </div>
  );
}
