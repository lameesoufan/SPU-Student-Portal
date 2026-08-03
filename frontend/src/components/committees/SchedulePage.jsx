/**
 * SchedulePage — صفحة جدولة اللجان المبسّطة
 *
 * تدفّق مبسّط:
 *   ① اختر نوع اللجنة (سيمينار 1، 2، فنية، نهائية)
 *   ② حدد نطاق التوزيع: تاريخ البداية + النهاية + ساعات اليوم + مدة المناقشة
 *   ③ اضغط "معاينة الجدولة"
 *   ④ راجع Gantt + Apply
 *
 * القاعات: كل القاعات المدخلة تُستخدم تلقائياً
 * الخوارزمية تحسب تلقائياً كم يوم تحتاج + تقلل عدد القاعات
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  RefreshCw, Play, Check, X, AlertTriangle, Clock, Calendar, DoorClosed,
  Users, ChevronDown, History,
} from 'lucide-react';
import {
  schedulePreview, scheduleApply, scheduleReject, fetchSchedulingRuns,
} from '../../api';
import { COMMITTEE_TYPES, COMMITTEE_TYPE_COLORS } from './constants';
import { PageHeader, PageShell, secondaryButtonClass } from '../ui/PagePrimitives';

const WEEKDAYS = [
  { value: 0, label: 'الإثنين' },
  { value: 1, label: 'الثلاثاء' },
  { value: 2, label: 'الأربعاء' },
  { value: 3, label: 'الخميس' },
  { value: 4, label: 'الجمعة' },
  { value: 5, label: 'السبت' },
  { value: 6, label: 'الأحد' },
];

export default function SchedulePage({ onBack }) {
  // ── Form state (simplified) ──
  const [committeeType, setCommitteeType] = useState('seminar_1');
  const [semester, setSemester] = useState('');
  const [dateRangeStart, setDateRangeStart] = useState('');
  const [dateRangeEnd, setDateRangeEnd] = useState('');
  const [dailyStart, setDailyStart] = useState('09:00');
  const [dailyEnd, setDailyEnd] = useState('17:00');
  const [discussionDuration, setDiscussionDuration] = useState(15);
  const [bufferMinutes, setBufferMinutes] = useState(10);
  const [workdays, setWorkdays] = useState([5, 6]);

  // ── Result state ──
  const [previewing, setPreviewing] = useState(false);
  const [previewResult, setPreviewResult] = useState(null);
  const [applying, setApplying] = useState(false);
  const [toast, setToast] = useState(null);

  // ── Runs history ──
  const [runs, setRuns] = useState([]);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [expandedRunId, setExpandedRunId] = useState(null);

  const loadRuns = useCallback(async () => {
    if (!committeeType || !semester) return;
    setLoadingRuns(true);
    try {
      const res = await fetchSchedulingRuns({ committee_type: committeeType, semester });
      setRuns(res.data || []);
    } catch {
      setRuns([]);
    } finally {
      setLoadingRuns(false);
    }
  }, [committeeType, semester]);

  useEffect(() => { loadRuns(); }, [loadRuns]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  const toggleWorkday = (val) => {
    setWorkdays((prev) => {
      const set = new Set(prev);
      if (set.has(val)) set.delete(val); else set.add(val);
      return Array.from(set).sort();
    });
  };

  // ── Preview ──
  const handlePreview = async () => {
    if (previewing) return;
    if (!semester || !dateRangeStart || !dateRangeEnd) {
      setToast({ type: 'error', msg: 'الفصل + نطاق التواريخ مطلوبة' });
      return;
    }
    setPreviewing(true);
    setPreviewResult(null);
    try {
      const payload = {
        committee_type: committeeType,
        semester,
        // Inline params — no need for pre-created SolverSettings
        date_range_start: dateRangeStart,
        date_range_end: dateRangeEnd,
        daily_start: dailyStart,
        daily_end: dailyEnd,
        buffer_minutes: bufferMinutes,
        discussion_duration: discussionDuration,
        workdays,
        timeout_seconds: 30,
      };
      const res = await schedulePreview(payload);
      setPreviewResult(res.data);
      if (res.data.success) {
        setToast({ type: 'success', msg: `تم إنشاء المعاينة (${res.data.solver_status}, ${res.data.wall_time?.toFixed(2)}ث)` });
      } else {
        setToast({ type: 'error', msg: 'فشل إنشاء المعاينة — راجع التقرير' });
      }
      await loadRuns();
    } catch (err) {
      setToast({ type: 'error', msg: err.response?.data?.detail || 'فشل الاتصال بالخادم' });
    } finally {
      setPreviewing(false);
    }
  };

  // ── Apply ──
  const handleApply = async () => {
    if (!previewResult?.success || !previewResult.run_id) return;
    if (!confirm('سيتم مسح الجدولة السابقة وتطبيق هذه الخطة. متابعة؟')) return;
    setApplying(true);
    try {
      await scheduleApply(previewResult.run_id);
      setToast({ type: 'success', msg: 'تم تطبيق الجدولة بنجاح' });
      setPreviewResult(null);
      await loadRuns();
    } catch (err) {
      setToast({ type: 'error', msg: err.response?.data?.detail || 'فشل التطبيق' });
    } finally {
      setApplying(false);
    }
  };

  // ── Reject ──
  const handleReject = async () => {
    if (!previewResult?.run_id) return;
    try {
      await scheduleReject(previewResult.run_id);
      setToast({ type: 'info', msg: 'تم رفض المعاينة' });
      setPreviewResult(null);
      await loadRuns();
    } catch {
      setToast({ type: 'error', msg: 'فشل الرفض' });
    }
  };

  return (
    <PageShell maxWidth="max-w-[1400px]">
      <PageHeader
        icon={Calendar}
        title="جدولة اللجان"
        description="اختر نوع اللجنة والفصل والنطاق الزمني، ثم أنشئ معاينة قبل تطبيق الجدول."
        badge={`${runs.length} عمليات`}
        actions={onBack ? <button type="button" onClick={onBack} className={secondaryButtonClass}>رجوع</button> : null}
      />
      <div className="schedule-page" dir="rtl">

      {/* Simplified form */}
      <div style={{ ...cardStyle, marginBottom: 20 }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 16 }}>
          {/* Committee type */}
          <div>
            <label style={labelStyle}>① نوع اللجنة *</label>
            <select value={committeeType} onChange={(e) => setCommitteeType(e.target.value)} style={inputStyle}>
              {COMMITTEE_TYPES.map((c) => <option key={c.value} value={c.value}>{c.label_ar}</option>)}
            </select>
          </div>
          {/* Semester */}
          <div>
            <label style={labelStyle}>الفصل الدراسي *</label>
            <input type="text" placeholder="الفصل الثاني 2026" value={semester}
              onChange={(e) => setSemester(e.target.value)} style={inputStyle} />
          </div>
          {/* Discussion duration */}
          <div>
            <label style={labelStyle}>② مدة المناقشة (دقيقة) *</label>
            <input type="number" min="5" step="5" value={discussionDuration}
              onChange={(e) => setDiscussionDuration(parseInt(e.target.value) || 15)} style={inputStyle} />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 16, marginBottom: 16 }}>
          <div>
            <label style={labelStyle}>② من تاريخ *</label>
            <input type="date" value={dateRangeStart}
              onChange={(e) => setDateRangeStart(e.target.value)} style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>② إلى تاريخ *</label>
            <input type="date" value={dateRangeEnd}
              onChange={(e) => setDateRangeEnd(e.target.value)} style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>② ساعة البداية *</label>
            <input type="time" value={dailyStart}
              onChange={(e) => setDailyStart(e.target.value)} style={inputStyle} />
          </div>
          <div>
            <label style={labelStyle}>② ساعة النهاية *</label>
            <input type="time" value={dailyEnd}
              onChange={(e) => setDailyEnd(e.target.value)} style={inputStyle} />
          </div>
        </div>

        {/* Workdays */}
        <div style={{ marginBottom: 16 }}>
          <label style={labelStyle}>أيام العمل المتاحة (الخوارزمية تختار منها)</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {WEEKDAYS.map((w) => {
              const selected = workdays.includes(w.value);
              return (
                <button key={w.value} onClick={() => toggleWorkday(w.value)} style={{
                  padding: '8px 14px', borderRadius: 8, cursor: 'pointer',
                  border: `1.5px solid ${selected ? 'var(--primary)' : 'var(--border)'}`,
                  background: selected ? 'var(--primary)' : 'var(--bg-input)',
                  color: selected ? '#fff' : 'var(--text-secondary)',
                  fontSize: '0.82rem', fontWeight: 600,
                }}>
                  {selected ? '✓ ' : ''}{w.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Buffer + Preview button */}
        <div style={{ display: 'flex', gap: 16, alignItems: 'end', justifyContent: 'space-between' }}>
          <div style={{ maxWidth: 200 }}>
            <label style={labelStyle}>الفاصل بين اللجان (دقيقة)</label>
            <input type="number" min="0" value={bufferMinutes}
              onChange={(e) => setBufferMinutes(parseInt(e.target.value) || 0)} style={inputStyle} />
          </div>
          <button onClick={handlePreview} disabled={previewing || !semester || !dateRangeStart || !dateRangeEnd}
            style={{ ...btnPrimary, padding: '12px 28px', fontSize: '1rem' }}>
            {previewing ? <><RefreshCw size={16} className="animate-spin" /> جاري المعاينة...</> : <><Play size={16} /> معاينة الجدولة</>}
          </button>
        </div>

        {/* Hint */}
        <div style={{ marginTop: 16, padding: 12, background: 'var(--info-bg)', borderRadius: 8, fontSize: '0.82rem', color: 'var(--info-text)', display: 'flex', gap: 8 }}>
          <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <strong>ملاحظة:</strong> كل القاعات المدخلة في النظام تُستخدم تلقائياً. الخوارزمية تحاول تقليل عدد القاعات المستخدمة (مثلاً 5 لجان → 5 قاعات). مدة كل لجنة = (عدد مشاريعها × مدة المناقشة) + الفاصل.
          </div>
        </div>
      </div>

      {/* Preview result */}
      {previewResult && (
        <div style={{ ...cardStyle, marginBottom: 20 }}>
          {previewResult.success ? (
            <>
              {/* Summary */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: '#10b981' }}>✅ معاينة جاهزة</h3>
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', marginTop: 4 }}>
                    {previewResult.solver_status} · {previewResult.wall_time?.toFixed(2)} ثانية · run #{previewResult.run_id}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={handleReject} disabled={applying} style={btnSecondary}><X size={14} /> رفض</button>
                  <button onClick={handleApply} disabled={applying} style={btnSuccess}>
                    {applying ? <><RefreshCw size={14} className="animate-spin" /> جاري التطبيق...</> : <><Check size={14} /> تطبيق الجدولة</>}
                  </button>
                </div>
              </div>

              {/* Stats */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 16 }}>
                <StatBox icon={<Calendar size={16} />} label="اللجان المجدولة" value={previewResult.summary_stats?.scheduled_committees || 0} color="var(--primary)" />
                <StatBox icon={<Calendar size={16} />} label="الأيام المستخدمة" value={`${previewResult.summary_stats?.days_used || 0}/${previewResult.summary_stats?.total_days_available || 0}`} color="var(--success)" />
                <StatBox icon={<DoorClosed size={16} />} label="القاعات المستخدمة" value={`${previewResult.summary_stats?.rooms_used || 0}/${previewResult.summary_stats?.total_rooms_available || 0}`} color="#f59e0b" />
                <StatBox icon={<Clock size={16} />} label="زمن الحل" value={`${(previewResult.wall_time || 0).toFixed(2)}ث`} color="#8b5cf6" />
              </div>

              {/* Warnings */}
              {previewResult.warnings?.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                  {previewResult.warnings.map((w, i) => (
                    <div key={i} style={{ background: 'var(--info-bg)', border: '1px solid var(--info-border)', borderRadius: 8, padding: '8px 12px', marginBottom: 6, fontSize: '0.82rem', color: 'var(--info-text)', display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                      <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 2 }} />
                      <span>{w.message_ar}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Gantt */}
              <GanttChart plan={previewResult.plan} />

              {/* Assignments table */}
              <AssignmentsTable assignments={previewResult.plan?.assignments || []} />
            </>
          ) : (
            <>
              <h3 style={{ margin: 0, marginBottom: 12, fontSize: '1.1rem', fontWeight: 700, color: '#ef4444', display: 'flex', alignItems: 'center', gap: 8 }}>
                <AlertTriangle size={18} /> فشل إنشاء المعاينة
              </h3>
              <InfeasibilityReport report={previewResult.infeasibility_report || []} />
            </>
          )}
        </div>
      )}

      {/* Runs history */}
      <div style={{ ...cardStyle, marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
            <History size={16} /> سجل العمليات ({runs.length})
          </h3>
          <button onClick={loadRuns} disabled={loadingRuns} style={btnSecondary}><RefreshCw size={13} /> تحديث</button>
        </div>
        {loadingRuns ? (
          <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)' }}>جاري التحميل...</div>
        ) : runs.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)', fontSize: '0.85rem' }}>لا توجد عمليات سابقة</div>
        ) : (
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>#</th><th style={thStyle}>النوع</th><th style={thStyle}>الفصل</th>
                <th style={thStyle}>الحالة</th><th style={thStyle}>المحلّل</th><th style={thStyle}>الزمن</th>
                <th style={thStyle}>بواسطة</th><th style={thStyle}>التاريخ</th><th style={thStyle}></th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <React.Fragment key={r.id}>
                  <tr>
                    <td style={tdStyle}>#{r.id}</td>
                    <td style={tdStyle}>{r.committee_type_ar}</td>
                    <td style={tdStyle}>{r.semester}</td>
                    <td style={tdStyle}><StatusBadge status={r.status} /></td>
                    <td style={tdStyle}>{r.solver_status || '—'}</td>
                    <td style={tdStyle}>{r.solver_wall_time_sec?.toFixed(2) || 0}ث</td>
                    <td style={tdStyle}>{r.requested_by_name || '—'}</td>
                    <td style={tdStyle}>{new Date(r.requested_at).toLocaleString('ar-IQ', { dateStyle: 'short', timeStyle: 'short' })}</td>
                    <td style={tdStyle}>
                      <button onClick={() => setExpandedRunId(expandedRunId === r.id ? null : r.id)} style={btnIconSm} title="عرض التفاصيل">
                        <ChevronDown size={14} style={{ transform: expandedRunId === r.id ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
                      </button>
                    </td>
                  </tr>
                  {expandedRunId === r.id && (
                    <tr>
                      <td colSpan={9} style={{ padding: 16, background: 'var(--bg-tertiary)' }}>
                        {r.status === 'failed' && r.infeasibility_report?.length > 0 ? (
                          <InfeasibilityReport report={r.infeasibility_report} />
                        ) : r.plan_json?.assignments?.length ? (
                          <>
                            <div style={{ marginBottom: 12, fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                              <strong>{r.plan_json.assignments.length}</strong> لجنة مُجدوَلة ·
                              أيام: {r.summary_stats?.days_used}/{r.summary_stats?.total_days_available} ·
                              قاعات: {r.summary_stats?.rooms_used}/{r.summary_stats?.total_rooms_available}
                            </div>
                            <AssignmentsTable assignments={r.plan_json.assignments} />
                          </>
                        ) : (
                          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>لا توجد تفاصيل</div>
                        )}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
          padding: '12px 24px', borderRadius: 10,
          background: toast.type === 'success' ? '#10b981' : toast.type === 'info' ? '#3b82f6' : '#ef4444',
          color: '#fff', fontSize: 14, fontWeight: 600, zIndex: 9999,
          boxShadow: '0 8px 24px rgba(0,0,0,0.2)',
        }}>{toast.msg}</div>
      )}
      </div>
    </PageShell>
  );
}

// ── Gantt Chart ──────────────────────────────────────────────────────────────
function GanttChart({ plan }) {
  const assignments = plan?.assignments || [];
  if (assignments.length === 0) return <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)' }}>لا توجد لجان مُجدوَلة</div>;

  const byDate = {};
  assignments.forEach((a) => {
    if (!byDate[a.date]) byDate[a.date] = {};
    if (!byDate[a.date][a.room_name]) byDate[a.date][a.room_name] = [];
    byDate[a.date][a.room_name].push(a);
  });
  const allRooms = [...new Set(assignments.map(a => a.room_name))].sort();
  const toMin = (t) => { const [h, m] = t.split(':').map(Number); return h * 60 + m; };
  const minMin = Math.min(...assignments.map(a => toMin(a.start_time)));
  const maxMin = Math.max(...assignments.map(a => toMin(a.end_time)));
  const daySpan = maxMin - minMin;

  return (
    <div style={{ marginTop: 16, marginBottom: 24 }}>
      <h4 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: 12 }}>خريطة الجدولة (Gantt)</h4>
      {Object.entries(byDate).map(([date, roomsData]) => {
        const d = new Date(date);
        const dateLabel = d.toLocaleDateString('ar-IQ', { weekday: 'long', day: 'numeric', month: 'short' });
        return (
          <div key={date} style={{ marginBottom: 20, border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
            <div style={{ background: 'var(--bg-tertiary)', padding: '8px 14px', fontWeight: 700, fontSize: '0.88rem' }}>📅 {dateLabel}</div>
            {allRooms.map((roomName) => {
              const roomAssignments = (roomsData[roomName] || []).sort((a, b) => a.start_time.localeCompare(b.start_time));
              return (
                <div key={roomName} style={{ display: 'flex', borderBottom: '1px solid var(--border-light)' }}>
                  <div style={{ width: 120, padding: '10px 14px', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)', background: '#fafbfc' }}>🚪 {roomName}</div>
                  <div style={{ flex: 1, position: 'relative', height: 50, background: '#fafbfc' }}>
                    {Array.from({ length: Math.ceil(daySpan / 60) + 1 }).map((_, i) => {
                      const hour = Math.floor(minMin / 60) + i;
                      const left = ((hour * 60 - minMin) / daySpan) * 100;
                      if (left < 0 || left > 100) return null;
                      return (
                        <div key={i} style={{ position: 'absolute', left: `${left}%`, top: 0, bottom: 0, borderRight: '1px dashed #e2e8f0' }}>
                          <div style={{ position: 'absolute', top: 2, right: 4, fontSize: '0.7rem', color: '#94a3b8' }}>{String(hour).padStart(2, '0')}:00</div>
                        </div>
                      );
                    })}
                    {roomAssignments.map((a) => {
                      const startMin = toMin(a.start_time);
                      const endMin = toMin(a.end_time);
                      const left = ((startMin - minMin) / daySpan) * 100;
                      const width = ((endMin - startMin) / daySpan) * 100;
                      const color = COMMITTEE_TYPE_COLORS[a.committee_type] || COMMITTEE_TYPE_COLORS.seminar_1;
                      return (
                        <div key={`${a.committee_id}`} title={`${a.start_time}-${a.end_time} | ${a.committee_type_ar} | ${a.doctors.map(d => d.name).join(', ')}`}
                          style={{ position: 'absolute', top: 4, bottom: 4, left: `${left}%`, width: `${width}%`, background: color.bg, color: color.text, border: `1.5px solid ${color.border}`, borderRadius: 6, padding: '2px 6px', fontSize: '0.7rem', fontWeight: 600, overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis', display: 'flex', alignItems: 'center' }}>
                          {a.start_time}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}

// ── Assignments table ────────────────────────────────────────────────────────
function AssignmentsTable({ assignments }) {
  return (
    <div style={{ marginTop: 16 }}>
      <h4 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: 12 }}>تفاصيل الجدولة ({assignments.length})</h4>
      <div style={{ overflowX: 'auto' }}>
        <table style={tableStyle}>
          <thead>
            <tr>
              <th style={thStyle}>#</th><th style={thStyle}>التاريخ</th><th style={thStyle}>الوقت</th>
              <th style={thStyle}>القاعة</th><th style={thStyle}>النوع</th><th style={thStyle}>الدكاترة</th>
              <th style={thStyle}>المشاريع</th><th style={thStyle}>المدة</th>
            </tr>
          </thead>
          <tbody>
            {assignments.map((a, idx) => {
              const color = COMMITTEE_TYPE_COLORS[a.committee_type] || COMMITTEE_TYPE_COLORS.seminar_1;
              return (
                <tr key={a.committee_id}>
                  <td style={tdStyle}>{idx + 1}</td>
                  <td style={tdStyle}>{a.date}</td>
                  <td style={tdStyle}><strong>{a.start_time}</strong> - {a.end_time}</td>
                  <td style={tdStyle}>🚪 {a.room_name}</td>
                  <td style={tdStyle}>
                    <span style={{ padding: '2px 8px', borderRadius: 20, fontSize: '0.72rem', fontWeight: 600, background: color.bg, color: color.text, border: `1px solid ${color.border}` }}>{a.committee_type_ar}</span>
                  </td>
                  <td style={tdStyle}>{a.doctors.map(d => `${d.name}${d.role === 'chair' ? ' 👑' : ''}`).join('، ')}</td>
                  <td style={tdStyle}>{a.projects_count} مشروع</td>
                  <td style={tdStyle}>{a.duration_minutes} دقيقة</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── Infeasibility Report ─────────────────────────────────────────────────────
function InfeasibilityReport({ report }) {
  if (!report || report.length === 0) return <div style={{ padding: 14, color: 'var(--text-muted)', fontSize: '0.85rem' }}>لا توجد تفاصيل عن سبب الفشل</div>;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {report.map((r, i) => {
        const colors = {
          error: { bg: '#fef2f2', border: '#fecaca', text: '#991b1b' },
          warn: { bg: '#fffbeb', border: '#fde68a', text: '#92400e' },
          info: { bg: '#eff6ff', border: '#bfdbfe', text: '#1e40af' },
        };
        const c = colors[r.level] || colors.error;
        return (
          <div key={i} style={{ background: c.bg, border: `1px solid ${c.border}`, borderRadius: 8, padding: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <AlertTriangle size={16} color={c.text} />
              <strong style={{ color: c.text, fontSize: '0.85rem' }}>{r.code}</strong>
              <span style={{ fontSize: '0.7rem', color: c.text, opacity: 0.7 }}>({r.level})</span>
            </div>
            {/* Render conflict details as cards if available */}
            {r.conflict_details && r.conflict_details.length > 0 ? (
              <div style={{ marginBottom: 8 }}>
                <div style={{ fontSize: '0.85rem', color: 'var(--text)', marginBottom: 8 }}>{r.message_ar.split('\n')[0]}</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {r.conflict_details.map((cd, j) => (
                    <div key={j} style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 6, padding: 10 }}>
                      <div style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text)', marginBottom: 6 }}>
                        لجنة #{cd.committee_id}
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {cd.doctors.map((doc, k) => {
                          // Parse doctor name and availability
                          const match = doc.match(/(.+) \(متاح: (.+)\)/);
                          const name = match ? match[1] : doc;
                          const days = match ? match[2] : '';
                          const isUnavailable = days === 'لا يوجد' || days === '';
                          return (
                            <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem' }}>
                              <span style={{ fontWeight: 500, color: 'var(--text-secondary)', minWidth: 120 }}>{name}</span>
                              <span style={{ color: isUnavailable ? '#dc2626' : '#0369a1' }}>
                                {isUnavailable ? 'غير متاح إطلاقاً' : `متاح: ${days}`}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div style={{ fontSize: '0.85rem', color: 'var(--text)', marginBottom: r.suggestions_ar?.length ? 8 : 0, whiteSpace: 'pre-line' }}>{r.message_ar}</div>
            )}
            {r.suggestions_ar?.length > 0 && (
              <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                <strong>اقتراحات:</strong>
                <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                  {r.suggestions_ar.map((s, j) => <li key={j}>{s}</li>)}
                </ul>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    pending: { bg: '#f1f5f9', color: 'var(--text-secondary)', label: 'معلّق' },
    preview: { bg: '#dbeafe', color: 'var(--info-text)', label: 'معاينة' },
    applied: { bg: '#dcfce7', color: '#166534', label: 'مُطبَّق' },
    rejected: { bg: '#fee2e2', color: '#991b1b', label: 'مرفوض' },
    failed: { bg: '#fef2f2', color: '#991b1b', label: 'فشل' },
  };
  const c = map[status] || map.pending;
  return <span style={{ padding: '2px 10px', borderRadius: 20, fontSize: '0.72rem', fontWeight: 600, background: c.bg, color: c.color }}>{c.label}</span>;
}

function StatBox({ icon, label, value, color }) {
  return (
    <div style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border)', borderRadius: 10, padding: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
      <div style={{ width: 36, height: 36, borderRadius: 8, background: `${color}20`, color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{icon}</div>
      <div>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{label}</div>
        <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text)' }}>{value}</div>
      </div>
    </div>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────────
const cardStyle = { background: 'var(--card)', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 16, padding: 20, boxShadow: 'var(--shadow-sm)' };
const btnPrimary = { padding: '10px 18px', borderRadius: 10, border: 'none', cursor: 'pointer', background: 'var(--primary)', color: '#fff', fontSize: '0.85rem', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 6 };
const btnSecondary = { padding: '10px 18px', borderRadius: 10, border: '1px solid var(--border)', cursor: 'pointer', background: 'var(--card)', color: 'var(--text-secondary)', fontSize: '0.85rem', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 6 };
const btnSuccess = { padding: '10px 18px', borderRadius: 10, border: 'none', cursor: 'pointer', background: 'var(--success)', color: '#fff', fontSize: '0.85rem', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 6 };
const btnIconSm = { padding: 7, borderRadius: 9, border: '1px solid var(--border)', cursor: 'pointer', background: 'var(--card)', color: 'var(--text-secondary)', display: 'inline-flex', alignItems: 'center' };
const labelStyle = { display: 'block', fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: 6, fontWeight: 700 };
const inputStyle = { width: '100%', padding: '9px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'var(--bg-input)', color: 'var(--text)', fontSize: '0.88rem', outline: 'none', boxSizing: 'border-box' };
const tableStyle = { width: '100%', borderCollapse: 'collapse', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden', fontSize: '0.85rem' };
const thStyle = { padding: '10px 12px', textAlign: 'right', fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-secondary)', background: 'var(--bg-tertiary)', borderBottom: '1px solid var(--border)' };
const tdStyle = { padding: '10px 12px', fontSize: '0.83rem', color: 'var(--text-secondary)', borderBottom: '1px solid var(--border-light)' };
