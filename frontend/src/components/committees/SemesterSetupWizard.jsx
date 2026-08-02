/**
 * SemesterSetupWizard — صفحة إعداد الفصل الدراسي الموحّدة
 *
 * تدفّق واحد منظّم يدمج كل المراحل:
 *   ① بيانات الفصل + القاعات + نطاق التواريخ
 *   ② إنشاء 4 SolverSettings تلقائياً (أسابيع متتالية)
 *   ③ توزيع المشاريع (single + multi)
 *   ④ جدولة كل الأنواع دفعة واحدة (CP-SAT × 4)
 *   ⑤ معاينة موحّدة (Gantt واحد بكل الأنواع بألوان مختلفة)
 *   ⑥ Apply All أو Reject All
 *
 * هذا يخفّض الجهد من ~32 نافذة إلى 6 خطوات في صفحة واحدة.
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Calendar, DoorClosed, Users, RefreshCw, Play, Check, X, AlertTriangle,
  Settings as SettingsIcon, Layers, ChevronRight, ChevronLeft, Info, Clock,
  CheckCircle2, FileSpreadsheet, Sparkles,
} from 'lucide-react';
import {
  fetchRooms, fetchDoctors, semesterSetup, scheduleAll, scheduleApplyAll, scheduleRejectAll,
} from '../../api';
import { COMMITTEE_TYPES, COMMITTEE_TYPE_COLORS } from './constants';

const WEEKDAYS = [
  { value: 0, label: 'الإثنين' },
  { value: 1, label: 'الثلاثاء' },
  { value: 2, label: 'الأربعاء' },
  { value: 3, label: 'الخميس' },
  { value: 4, label: 'الجمعة' },
  { value: 5, label: 'السبت' },
  { value: 6, label: 'الأحد' },
];

const STEPS = [
  { id: 1, label: 'الفصل + القاعات', icon: Calendar },
  { id: 2, label: 'نطاق التواريخ', icon: Clock },
  { id: 3, label: 'إعداد + توزيع', icon: SettingsIcon },
  { id: 4, label: 'جدولة الكل', icon: Play },
  { id: 5, label: 'معاينة + تطبيق', icon: CheckCircle2 },
];

export default function SemesterSetupWizard({ onBack }) {
  // ── Wizard state ──
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState(null);

  // ── Form state ──
  const [form, setForm] = useState({
    semester: `Spring ${new Date().getFullYear()}`,
    start_date: '',
    weeks_per_type: 1,
    workdays: [5, 6],
    daily_start: '09:00',
    daily_end: '17:00',
    buffer_minutes: 10,
    max_committees_per_doctor: 5,
    solver_timeout_seconds: 30,
    room_ids: [],
    run_distribution: true,
    scheduling_mode: 'multi',  // 'single' | 'multi' — chosen by dean
  });

  // ── Data ──
  const [rooms, setRooms] = useState([]);
  const [setupResult, setSetupResult] = useState(null);
  const [scheduleResult, setScheduleResult] = useState(null);

  // ── Load rooms on mount ──
  useEffect(() => {
    fetchRooms({ is_active: true })
      .then((res) => setRooms(res.data?.results || res.data || []))
      .catch(() => setRooms([]));
  }, []);

  // ── Auto-dismiss toast ──
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  /* ── Helpers ── */
  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));
  const toggleWorkday = (val) => {
    setForm((f) => {
      const set = new Set(f.workdays);
      if (set.has(val)) set.delete(val); else set.add(val);
      return { ...f, workdays: Array.from(set).sort() };
    });
  };
  const toggleRoom = (roomId) => {
    setForm((f) => {
      const set = new Set(f.room_ids);
      if (set.has(roomId)) set.delete(roomId); else set.add(roomId);
      return { ...f, room_ids: Array.from(set) };
    });
  };

  /* ── Step validation ── */
  const stepValid = (() => {
    if (step === 1) return !!(form.semester && form.room_ids.length > 0);
    if (step === 2) return !!(form.start_date && form.workdays.length > 0 && form.daily_start && form.daily_end);
    if (step === 3) return true;  // setup runs on entering this step
    if (step === 4) return true;  // schedule-all runs on entering
    if (step === 5) return true;
    return false;
  })();

  /* ── Step 3: Run semester setup ── */
  const handleSetup = async () => {
    setBusy(true);
    try {
      let res;
      try {
        res = await semesterSetup({ ...form, scheduling_mode: form.scheduling_mode });
      } catch (err) {
        const response = err.response?.data;
        if (response?.code !== 'redistribution_confirmation_required') throw err;

        const drafts = response.safety?.draft_count || 0;
        const committeesCount = response.safety?.committees_count || 0;
        const confirmed = confirm(
          `توجد ${drafts} مسودة علامات ضمن ${committeesCount} لجنة.\n\n`
          + 'تشغيل الإعداد وإعادة التوزيع سيحذف هذه المسودات. هل تريد المتابعة؟'
        );
        if (!confirmed) {
          setToast({ type: 'info', msg: 'تم إلغاء العملية وحماية مسودات العلامات.' });
          return;
        }
        res = await semesterSetup({
          ...form,
          scheduling_mode: form.scheduling_mode,
          confirm_draft_loss: true,
        });
      }
      setSetupResult(res.data);
      if (res.data.ready_for_scheduling) {
        setToast({ type: 'success', msg: `تم إعداد الفصل بنجاح! ${res.data.committees_total} لجنة جاهزة للجدولة` });
        setStep(4);  // jump to scheduling
      } else {
        setToast({ type: 'warn', msg: 'تم الإعداد لكن لا توجد لجان — أنشئ تشكيلات أولاً' });
      }
    } catch (err) {
      const msg = err.response?.data?.detail || err.response?.data?.errors?.join(', ') || 'فشل الإعداد';
      setToast({ type: 'error', msg });
    } finally { setBusy(false); }
  };

  /* ── Step 4: Run schedule-all ── */
  const handleScheduleAll = async () => {
    setBusy(true);
    try {
      const res = await scheduleAll({
        semester: form.semester,
        committee_types: COMMITTEE_TYPES.map((c) => c.value),
        room_ids: form.room_ids,
      });
      setScheduleResult(res.data);
      setStep(5);
      if (res.data.success) {
        setToast({ type: 'success', msg: `تمت جدولة ${res.data.unified_summary.scheduled_committees} لجنة بنجاح` });
      } else {
        setToast({ type: 'warn', msg: 'بعض الأنواع فشلت — راجع التفاصيل' });
      }
    } catch (err) {
      setToast({ type: 'error', msg: err.response?.data?.detail || 'فشل تشغيل الـ Solver' });
    } finally { setBusy(false); }
  };

  /* ── Step 5: Apply All / Reject All ── */
  const handleApplyAll = async () => {
    if (!confirm('سيتم تطبيق كل الجدولات. متابعة؟')) return;
    setBusy(true);
    try {
      const res = await scheduleApplyAll(form.semester);
      setToast({ type: 'success', msg: `تم تطبيق ${res.data.applied_count} جدولة` });
      setScheduleResult(null);
      setStep(1);  // reset
    } catch (err) {
      setToast({ type: 'error', msg: err.response?.data?.detail || 'فشل التطبيق' });
    } finally { setBusy(false); }
  };

  const handleRejectAll = async () => {
    setBusy(true);
    try {
      await scheduleRejectAll(form.semester);
      setToast({ type: 'info', msg: 'تم رفض كل المعاينات' });
      setScheduleResult(null);
      setStep(4);
    } catch (err) {
      setToast({ type: 'error', msg: 'فشل الرفض' });
    } finally { setBusy(false); }
  };

  return (
    <div className="wizard-page" dir="rtl" style={{ padding: 24, maxWidth: 1300, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <h1 style={{ fontSize: '1.7rem', fontWeight: 700, marginBottom: 4, display: 'flex', gap: 10, alignItems: 'center' }}>
          <Sparkles size={28} color="#667eea" /> معالج إعداد الفصل
        </h1>
        <p style={{ color: '#888', fontSize: '0.9rem' }}>
          إعداد كامل للفصل الدراسي في تدفّق واحد — إعدادات + توزيع + جدولة + تطبيق
        </p>
      </div>

      {/* Stepper */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 30, padding: '0 20px' }}>
        {STEPS.map((s, i) => {
          const isActive = step === s.id;
          const isComplete = step > s.id;
          const Icon = s.icon;
          return (
            <React.Fragment key={s.id}>
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
                flex: '0 0 auto', cursor: isComplete ? 'pointer' : 'default',
              }} onClick={() => isComplete && setStep(s.id)}>
                <div style={{
                  width: 44, height: 44, borderRadius: '50%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: isActive ? '#667eea' : isComplete ? '#10b981' : '#f1f5f9',
                  color: isActive || isComplete ? '#fff' : '#94a3b8',
                  border: `2px solid ${isActive ? '#667eea' : isComplete ? '#10b981' : '#cbd5e1'}`,
                  transition: 'all 0.2s',
                }}>
                  {isComplete ? <Check size={18} /> : <Icon size={18} />}
                </div>
                <span style={{
                  fontSize: '0.78rem', fontWeight: 600,
                  color: isActive ? '#667eea' : isComplete ? '#10b981' : '#94a3b8',
                  textAlign: 'center', maxWidth: 100,
                }}>{s.label}</span>
              </div>
              {i < STEPS.length - 1 && (
                <div style={{
                  flex: 1, height: 2, marginTop: 22, marginLeft: 8, marginRight: 8,
                  background: step > s.id ? '#10b981' : '#e2e8f0',
                }} />
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Step content */}
      <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: 28, minHeight: 400 }}>

        {/* ── Step 1: Semester + Rooms ── */}
        {step === 1 && (
          <Step1SemesterRooms
            form={form} setField={setField}
            rooms={rooms} toggleRoom={toggleRoom}
          />
        )}

        {/* ── Step 2: Date range + workdays ── */}
        {step === 2 && (
          <Step2DateRange form={form} setField={setField} toggleWorkday={toggleWorkday} WEEKDAYS={WEEKDAYS} />
        )}

        {/* ── Step 3: Setup summary (auto-runs setup) ── */}
        {step === 3 && (
          <Step3Setup
            form={form}
            setupResult={setupResult}
            busy={busy}
            onRun={handleSetup}
          />
        )}

        {/* ── Step 4: Schedule All (auto-runs solver) ── */}
        {step === 4 && (
          <Step4ScheduleAll
            form={form}
            setupResult={setupResult}
            scheduleResult={scheduleResult}
            busy={busy}
            onRun={handleScheduleAll}
          />
        )}

        {/* ── Step 5: Preview + Apply ── */}
        {step === 5 && scheduleResult && (
          <Step5PreviewApply
            scheduleResult={scheduleResult}
            busy={busy}
            onApplyAll={handleApplyAll}
            onRejectAll={handleRejectAll}
            onBack={() => setStep(4)}
          />
        )}
      </div>

      {/* Navigation buttons */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 20 }}>
        <button
          onClick={() => step > 1 ? setStep(step - 1) : onBack?.()}
          style={{ ...btnSecondary, opacity: step === 3 || step === 4 ? 0.5 : 1 }}
          disabled={busy || step === 3 || step === 4}
        >
          <ChevronRight size={14} /> السابق
        </button>

        {step < 3 && (
          <button
            onClick={() => stepValid && setStep(step + 1)}
            disabled={!stepValid || busy}
            style={btnPrimary}
          >
            التالي <ChevronLeft size={14} />
          </button>
        )}
      </div>

      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', bottom: 24, left: '50%', transform: 'translateX(-50%)',
          padding: '14px 28px', borderRadius: 10,
          background: toast.type === 'success' ? '#10b981' : toast.type === 'warn' ? '#f59e0b' : toast.type === 'info' ? '#3b82f6' : '#ef4444',
          color: '#fff', fontSize: 14, fontWeight: 600, zIndex: 9999,
          boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
        }}>{toast.msg}</div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 1: Semester + Rooms
// ═══════════════════════════════════════════════════════════════════════════
function Step1SemesterRooms({ form, setField, rooms, toggleRoom }) {
  return (
    <div>
      <h2 style={{ marginTop: 0, marginBottom: 20, fontSize: '1.2rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Calendar size={20} color="#667eea" /> بيانات الفصل + القاعات
      </h2>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
        <div>
          <label style={labelStyle}>الفصل الدراسي *</label>
          <input type="text" value={form.semester}
            onChange={(e) => setField('semester', e.target.value)}
            placeholder="الفصل الثاني 2026" style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>عدد الأسابيع لكل نوع لجنة</label>
          <select value={form.weeks_per_type}
            onChange={(e) => setField('weeks_per_type', parseInt(e.target.value))}
            style={inputStyle}>
            <option value={1}>1 أسبوع (افتراضي)</option>
            <option value={2}>2 أسبوع</option>
          </select>
        </div>
      </div>

      <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6 }}>
        <DoorClosed size={18} color="#667eea" /> القاعات ({form.room_ids.length} مختارة)
      </h3>
      {rooms.length === 0 ? (
        <div style={emptyStyle}>
          <DoorClosed size={32} color="#ccc" />
          <p>لا توجد قاعات فعّالة. أنشئ قاعات من صفحة "القاعات" أولاً.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 10 }}>
          {rooms.map((r) => {
            const selected = form.room_ids.includes(r.id);
            return (
              <button key={r.id} onClick={() => toggleRoom(r.id)} style={{
                padding: '14px 16px', borderRadius: 10, cursor: 'pointer',
                border: `1.5px solid ${selected ? '#667eea' : '#cbd5e1'}`,
                background: selected ? '#ede9fe' : '#fff',
                color: selected ? '#667eea' : '#475569',
                fontSize: '0.88rem', fontWeight: 600,
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                transition: 'all 0.2s',
              }}>
                <span>{r.name}</span>
                <span style={{ fontSize: '0.75rem', opacity: 0.7 }}>سعة {r.capacity}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* Scheduling Mode Selection */}
      <div style={{ marginTop: 24 }}>
        <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
          <Layers size={18} color="#667eea" /> طريقة التوزيع
        </h3>
        <p style={{ fontSize: '0.82rem', color: '#888', marginBottom: 12 }}>
          هل نفس اللجنة تقيّم المشروع في كل الأنواع الأربعة، أم لجان مختلفة لكل نوع؟
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <button
            onClick={() => setField('scheduling_mode', 'single')}
            style={{
              padding: 14, borderRadius: 10, cursor: 'pointer',
              border: `2px solid ${form.scheduling_mode === 'single' ? '#667eea' : '#cbd5e1'}`,
              background: form.scheduling_mode === 'single' ? '#ede9fe' : '#fff',
              color: form.scheduling_mode === 'single' ? '#667eea' : '#475569',
              fontSize: '0.85rem', fontWeight: 600, textAlign: 'right',
            }}
          >
            <div style={{ marginBottom: 4 }}>● نفس اللجنة للأنواع الأربعة</div>
            <div style={{ fontSize: '0.75rem', opacity: 0.8, fontWeight: 400 }}>
              نفس الأطباء يقيّمون المشروع في 4 جلسات بأنواع مختلفة
            </div>
          </button>
          <button
            onClick={() => setField('scheduling_mode', 'multi')}
            style={{
              padding: 14, borderRadius: 10, cursor: 'pointer',
              border: `2px solid ${form.scheduling_mode === 'multi' ? '#667eea' : '#cbd5e1'}`,
              background: form.scheduling_mode === 'multi' ? '#ede9fe' : '#fff',
              color: form.scheduling_mode === 'multi' ? '#667eea' : '#475569',
              fontSize: '0.85rem', fontWeight: 600, textAlign: 'right',
            }}
          >
            <div style={{ marginBottom: 4 }}>● لجان مختلفة لكل نوع</div>
            <div style={{ fontSize: '0.75rem', opacity: 0.8, fontWeight: 400 }}>
              كل نوع لجنة له تشكيلة منفصلة بأطباء مختلفين
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 2: Date range + workdays
// ═══════════════════════════════════════════════════════════════════════════
function Step2DateRange({ form, setField, toggleWorkday, WEEKDAYS }) {
  const startDate = form.start_date ? new Date(form.start_date) : null;

  return (
    <div>
      <h2 style={{ marginTop: 0, marginBottom: 20, fontSize: '1.2rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Clock size={20} color="#667eea" /> نطاق التواريخ وأيام العمل
      </h2>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
        <div>
          <label style={labelStyle}>تاريخ بداية الأسبوع الأول *</label>
          <input type="date" value={form.start_date}
            onChange={(e) => setField('start_date', e.target.value)} style={inputStyle} />
          <small style={hintStyle}>سيتم إنشاء 4 نطاقات تلقائياً (أسبوع لكل نوع لجنة)</small>
        </div>
        <div>
          <label style={labelStyle}>ساعات العمل اليومية</label>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input type="time" value={form.daily_start}
              onChange={(e) => setField('daily_start', e.target.value)} style={inputStyle} />
            <span style={{ color: '#888' }}>-</span>
            <input type="time" value={form.daily_end}
              onChange={(e) => setField('daily_end', e.target.value)} style={inputStyle} />
          </div>
        </div>
      </div>

      {/* Auto-generated date ranges preview */}
      {startDate && (
        <div style={{ ...cardStyle, marginBottom: 20, background: '#f0f9ff', borderColor: '#bae6fd' }}>
          <h4 style={{ margin: '0 0 10px 0', fontSize: '0.9rem', color: '#0369a1', display: 'flex', alignItems: 'center', gap: 6 }}>
            <Info size={15} /> النطاقات المُولَّدة تلقائياً (4 أنواع لجان):
          </h4>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            {COMMITTEE_TYPES.map((ct, i) => {
              const ws = new Date(startDate); ws.setDate(ws.getDate() + i * 7 * form.weeks_per_type);
              const we = new Date(ws); we.setDate(we.getDate() + 7 * form.weeks_per_type - 1);
              return (
                <div key={ct.value} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.82rem' }}>
                  <span style={{ padding: '2px 8px', borderRadius: 6, background: COMMITTEE_TYPE_COLORS[ct.value]?.bg || '#eee', color: COMMITTEE_TYPE_COLORS[ct.value]?.text || '#666', fontWeight: 600 }}>
                    {ct.label_ar}
                  </span>
                  <span style={{ color: '#0369a1' }}>
                    {ws.toISOString().slice(0, 10)} ← {we.toISOString().slice(0, 10)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div style={{ marginBottom: 20 }}>
        <label style={labelStyle}>أيام العمل الأسبوعية *</label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {WEEKDAYS.map((w) => {
            const selected = form.workdays.includes(w.value);
            return (
              <button key={w.value} onClick={() => toggleWorkday(w.value)} style={{
                padding: '10px 18px', borderRadius: 8, cursor: 'pointer',
                border: `1.5px solid ${selected ? '#667eea' : '#cbd5e1'}`,
                background: selected ? '#667eea' : '#fff',
                color: selected ? '#fff' : '#475569',
                fontSize: '0.85rem', fontWeight: 600,
              }}>
                {selected ? '✓ ' : ''}{w.label}
              </button>
            );
          })}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
        <div>
          <label style={labelStyle}>الفاصل بين اللجان (دقيقة)</label>
          <input type="number" min="0" value={form.buffer_minutes}
            onChange={(e) => setField('buffer_minutes', parseInt(e.target.value))} style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>حد اللجان/دكتور</label>
          <input type="number" min="1" value={form.max_committees_per_doctor}
            onChange={(e) => setField('max_committees_per_doctor', parseInt(e.target.value))} style={inputStyle} />
        </div>
        <div>
          <label style={labelStyle}>مهلة الـ Solver (ثانية)</label>
          <input type="number" min="5" value={form.solver_timeout_seconds}
            onChange={(e) => setField('solver_timeout_seconds', parseInt(e.target.value))} style={inputStyle} />
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 3: Run setup
// ═══════════════════════════════════════════════════════════════════════════
function Step3Setup({ form, setupResult, busy, onRun }) {
  return (
    <div style={{ textAlign: 'center', padding: '40px 20px' }}>
      <SettingsIcon size={56} color="#667eea" style={{ marginBottom: 16 }} />
      <h2 style={{ marginTop: 0, marginBottom: 8 }}>جاهز للإعداد</h2>
      <p style={{ color: '#888', marginBottom: 24, maxWidth: 500, margin: '0 auto 24px' }}>
        سيتم إنشاء 4 SolverSettings (أسابيع متتالية) + توزيع المشاريع على التشكيلات الموجودة.
      </p>

      {setupResult && (
        <div style={{ ...cardStyle, textAlign: 'right', marginBottom: 24 }}>
          <h4 style={{ marginTop: 0, marginBottom: 12 }}>نتيجة الإعداد:</h4>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, fontSize: '0.88rem' }}>
            <Stat label="إعدادات منشأة" value={setupResult.settings_created} color="#10b981" />
            <Stat label="إعدادات محدّثة" value={setupResult.settings_updated} color="#3b82f6" />
            <Stat label="قاعات مختارة" value={setupResult.rooms_selected} color="#667eea" />
            <Stat label="إجمالي اللجان" value={setupResult.committees_total} color="#f59e0b" />
          </div>
          {setupResult.distribution && (
            <div style={{ marginTop: 12, fontSize: '0.82rem', color: '#475569' }}>
              <strong>توزيع:</strong> {setupResult.distribution.distributed_projects} مشروع موزَّع
              {setupResult.distribution.single_mode_committees_created > 0 && (
                <span> · {setupResult.distribution.single_mode_committees_created} لجنة من وضع single</span>
              )}
            </div>
          )}
        </div>
      )}

      <button onClick={onRun} disabled={busy} style={{ ...btnPrimary, padding: '14px 32px', fontSize: '1rem' }}>
        {busy ? <><RefreshCw size={16} className="animate-spin" /> جاري الإعداد...</> : <><Play size={16} /> تشغيل الإعداد + التوزيع</>}
      </button>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 4: Schedule All
// ═══════════════════════════════════════════════════════════════════════════
function Step4ScheduleAll({ form, setupResult, scheduleResult, busy, onRun }) {
  return (
    <div style={{ textAlign: 'center', padding: '40px 20px' }}>
      <Layers size={56} color="#667eea" style={{ marginBottom: 16 }} />
      <h2 style={{ marginTop: 0, marginBottom: 8 }}>جدولة كل الأنواع دفعة واحدة</h2>
      <p style={{ color: '#888', marginBottom: 24, maxWidth: 500, margin: '0 auto 24px' }}>
        سيتم تشغيل CP-SAT لكل من الأنواع الأربعة بالتسلسل.
        قد يستغرق هذا عدة ثوانٍ إلى دقائق حسب حجم البيانات.
      </p>

      {setupResult && (
        <div style={{ ...cardStyle, marginBottom: 20, textAlign: 'right' }}>
          <h4 style={{ marginTop: 0, marginBottom: 10 }}>اللجان الجاهزة للجدولة:</h4>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: '0.85rem' }}>
            {Object.entries(setupResult.committees_per_type || {}).map(([type, count]) => (
              <div key={type} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 10px', background: '#f8fafc', borderRadius: 6 }}>
                <span>{COMMITTEE_TYPE_COLORS[type] ? type.replace('_', ' ') : type}</span>
                <strong>{count} لجنة</strong>
              </div>
            ))}
          </div>
        </div>
      )}

      <button onClick={onRun} disabled={busy} style={{ ...btnPrimary, padding: '14px 32px', fontSize: '1rem' }}>
        {busy ? <><RefreshCw size={16} className="animate-spin" /> جاري الجدولة (4 أنواع)...</> : <><Play size={16} /> جدولة الكل</>}
      </button>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 5: Preview + Apply
// ═══════════════════════════════════════════════════════════════════════════
function Step5PreviewApply({ scheduleResult, busy, onApplyAll, onRejectAll, onBack }) {
  const summary = scheduleResult.unified_summary || {};
  return (
    <div>
      <h2 style={{ marginTop: 0, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
        <CheckCircle2 size={22} color="#10b981" /> معاينة موحّدة + تطبيق
      </h2>

      {/* Summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        <StatBox icon={<Calendar size={16} />} label="اللجان المجدولة" value={summary.scheduled_committees || 0} color="#10b981" />
        <StatBox icon={<Layers size={16} />} label="أنواع ناجحة" value={`${summary.types_succeeded || 0}/${(summary.types_succeeded || 0) + (summary.types_failed || 0)}`} color="#667eea" />
        <StatBox icon={<Clock size={16} />} label="زمن الحل الكلي" value={`${(summary.total_wall_time || 0).toFixed(2)}ث`} color="#f59e0b" />
        <StatBox icon={<DoorClosed size={16} />} label="أيام/قاعات" value={`${summary.days_used || 0}ي / ${summary.rooms_used || 0}ق`} color="#8b5cf6" />
      </div>

      {/* Per-type results */}
      <div style={{ marginBottom: 20 }}>
        <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: 10 }}>النتائج حسب النوع:</h3>
        {scheduleResult.results?.map((r, i) => (
          <div key={i} style={{
            ...cardStyle,
            marginBottom: 8, padding: '10px 14px',
            borderLeft: `4px solid ${r.success ? '#10b981' : '#ef4444'}`,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <strong style={{ fontSize: '0.88rem' }}>{r.committee_type_ar}</strong>
                {r.success ? (
                  <span style={{ marginRight: 8, color: '#10b981', fontSize: '0.78rem' }}>
                    ✅ {r.summary_stats?.scheduled_committees || 0} لجنة · {r.wall_time?.toFixed(2)}ث
                  </span>
                ) : (
                  <span style={{ marginRight: 8, color: '#ef4444', fontSize: '0.78rem' }}>❌ فشل</span>
                )}
              </div>
              <span style={{ fontSize: '0.78rem', color: '#888' }}>
                {r.committees_count !== undefined ? `${r.committees_count} لجنة متاحة` : ''}
              </span>
            </div>
            {!r.success && r.infeasibility_report?.length > 0 && (
              <div style={{ marginTop: 8, fontSize: '0.78rem', color: '#991b1b' }}>
                {r.infeasibility_report.map((rep, j) => (
                  <div key={j}>• {rep.message_ar}</div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Warnings */}
      {scheduleResult.warnings?.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          {scheduleResult.warnings.map((w, i) => (
            <div key={i} style={{
              background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 8,
              padding: '8px 12px', marginBottom: 6, fontSize: '0.82rem', color: '#1e40af',
              display: 'flex', alignItems: 'flex-start', gap: 6,
            }}>
              <Info size={14} style={{ flexShrink: 0, marginTop: 2 }} />
              <span>{w.message_ar}</span>
            </div>
          ))}
        </div>
      )}

      {/* Unified Gantt */}
      {scheduleResult.unified_assignments?.length > 0 && (
        <UnifiedGantt assignments={scheduleResult.unified_assignments} />
      )}

      {/* Apply / Reject buttons */}
      <div style={{ display: 'flex', gap: 10, justifyContent: 'center', marginTop: 24 }}>
        <button onClick={onBack} disabled={busy} style={btnSecondary}>
          <ChevronRight size={14} /> رجوع
        </button>
        <button onClick={onRejectAll} disabled={busy} style={btnSecondary}>
          <X size={14} /> رفض الكل
        </button>
        <button onClick={onApplyAll} disabled={busy || summary.types_succeeded === 0}
          style={{ ...btnSuccess, padding: '12px 28px', fontSize: '0.95rem' }}>
          {busy ? <><RefreshCw size={14} className="animate-spin" /> جاري التطبيق...</> : <><Check size={14} /> تطبيق الكل</>}
        </button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Unified Gantt Chart — 4 committee types in one chart with different colors
// ═══════════════════════════════════════════════════════════════════════════
function UnifiedGantt({ assignments }) {
  if (!assignments || assignments.length === 0) {
    return <div style={{ textAlign: 'center', padding: 20, color: '#888' }}>لا توجد لجان مُجدوَلة</div>;
  }

  // Group by date, then by room
  const byDate = {};
  assignments.forEach((a) => {
    if (!byDate[a.date]) byDate[a.date] = {};
    if (!byDate[a.date][a.room_name]) byDate[a.date][a.room_name] = [];
    byDate[a.date][a.room_name].push(a);
  });
  const allRooms = [...new Set(assignments.map((a) => a.room_name))].sort();

  // Time range
  const toMin = (t) => { const [h, m] = t.split(':').map(Number); return h * 60 + m; };
  const minMin = Math.min(...assignments.map((a) => toMin(a.start_time)));
  const maxMin = Math.max(...assignments.map((a) => toMin(a.end_time)));
  const daySpan = maxMin - minMin;

  return (
    <div style={{ marginBottom: 24 }}>
      <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: 12 }}>خريطة الجدولة الموحّدة (Gantt)</h3>

      {/* Legend */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
        {COMMITTEE_TYPES.map((ct) => {
          const color = COMMITTEE_TYPE_COLORS[ct.value] || {};
          return (
            <div key={ct.value} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem' }}>
              <div style={{ width: 14, height: 14, borderRadius: 3, background: color.bg, border: `1.5px solid ${color.border}` }} />
              <span>{ct.label_ar}</span>
            </div>
          );
        })}
      </div>

      {Object.entries(byDate).map(([date, roomsData]) => {
        const d = new Date(date);
        const dateLabel = d.toLocaleDateString('ar-IQ', { weekday: 'long', day: 'numeric', month: 'short' });
        return (
          <div key={date} style={{ marginBottom: 16, border: '1px solid #e2e8f0', borderRadius: 10, overflow: 'hidden' }}>
            <div style={{ background: '#f1f5f9', padding: '8px 14px', fontWeight: 700, fontSize: '0.88rem' }}>
              📅 {dateLabel}
            </div>
            {allRooms.map((roomName) => {
              const roomAssignments = (roomsData[roomName] || []).sort((a, b) => a.start_time.localeCompare(b.start_time));
              return (
                <div key={roomName} style={{ display: 'flex', borderBottom: '1px solid #f1f5f9' }}>
                  <div style={{ width: 120, padding: '10px 14px', fontSize: '0.82rem', fontWeight: 600, color: '#475569', background: '#fafbfc' }}>
                    🚪 {roomName}
                  </div>
                  <div style={{ flex: 1, position: 'relative', height: 50, background: '#fafbfc' }}>
                    {Array.from({ length: Math.ceil(daySpan / 60) + 1 }).map((_, i) => {
                      const hour = Math.floor(minMin / 60) + i;
                      const left = ((hour * 60 - minMin) / daySpan) * 100;
                      if (left < 0 || left > 100) return null;
                      return (
                        <div key={i} style={{ position: 'absolute', left: `${left}%`, top: 0, bottom: 0, borderRight: '1px dashed #e2e8f0' }}>
                          <div style={{ position: 'absolute', top: 2, right: 4, fontSize: '0.7rem', color: '#94a3b8' }}>
                            {String(hour).padStart(2, '0')}:00
                          </div>
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
                        <div key={`${a.committee_id}`} title={`${a.start_time}-${a.end_time} | ${a.committee_type_ar} | ${a.doctors.map((d) => d.name).join(', ')}`}
                          style={{
                            position: 'absolute', top: 4, bottom: 4, left: `${left}%`, width: `${width}%`,
                            background: color.bg, color: color.text, border: `1.5px solid ${color.border}`,
                            borderRadius: 6, padding: '2px 6px', fontSize: '0.7rem', fontWeight: 600,
                            overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis',
                            display: 'flex', alignItems: 'center',
                          }}>
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

// ═══════════════════════════════════════════════════════════════════════════
// Small components
// ═══════════════════════════════════════════════════════════════════════════
function Stat({ label, value, color = '#475569' }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 10px', background: '#f8fafc', borderRadius: 6 }}>
      <span style={{ color: '#475569' }}>{label}</span>
      <strong style={{ color }}>{value}</strong>
    </div>
  );
}

function StatBox({ icon, label, value, color }) {
  return (
    <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
      <div style={{ width: 36, height: 36, borderRadius: 8, background: `${color}20`, color, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {icon}
      </div>
      <div>
        <div style={{ fontSize: '0.72rem', color: '#888' }}>{label}</div>
        <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1e293b' }}>{value}</div>
      </div>
    </div>
  );
}

// ── Styles ──────────────────────────────────────────────────────────────────
const btnPrimary = { padding: '10px 18px', borderRadius: 8, border: 'none', cursor: 'pointer', background: '#667eea', color: '#fff', fontSize: '0.9rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6 };
const btnSecondary = { padding: '10px 18px', borderRadius: 8, border: '1px solid #cbd5e1', cursor: 'pointer', background: '#fff', color: '#475569', fontSize: '0.9rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6 };
const btnSuccess = { padding: '10px 18px', borderRadius: 8, border: 'none', cursor: 'pointer', background: '#10b981', color: '#fff', fontSize: '0.9rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 6 };
const labelStyle = { display: 'block', fontSize: '0.82rem', color: '#475569', marginBottom: 4, fontWeight: 600 };
const inputStyle = { width: '100%', padding: '8px 12px', borderRadius: 8, border: '1.5px solid #cbd5e1', fontSize: '0.9rem', outline: 'none', boxSizing: 'border-box' };
const hintStyle = { display: 'block', fontSize: '0.75rem', color: '#888', marginTop: 4 };
const cardStyle = { background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, padding: 16 };
const emptyStyle = { textAlign: 'center', padding: 40, color: '#94a3b8' };
