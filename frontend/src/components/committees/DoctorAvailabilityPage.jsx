/**
 * DoctorAvailabilityPage — إدارة توفر الدكاترة والاستثناءات.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Plus, RefreshCw, Trash2, Users } from 'lucide-react';
import {
  createDoctorAvailability,
  createDoctorException,
  deleteDoctorAvailability,
  deleteDoctorException,
  fetchDoctorAvailability,
  fetchDoctorExceptions,
  fetchDoctors,
} from '../../api';
import {
  EmptyState,
  LoadingState,
  PageCard,
  PageHeader,
  PageShell,
  inputClass,
  primaryButtonClass,
  secondaryButtonClass,
} from '../ui/PagePrimitives';

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
  const [newException, setNewException] = useState({ date: '', exception_type: 'blocked', reason: '' });

  const loadDoctors = useCallback(async () => {
    try {
      const response = await fetchDoctors();
      const items = response.data || [];
      setDoctors(items);
      setSelectedDoctor((current) => current || items[0]?.id || null);
    } catch {
      setDoctors([]);
    }
  }, []);

  const loadDoctorData = useCallback(async () => {
    if (!selectedDoctor) return;
    setLoading(true);
    try {
      const [availabilityResponse, exceptionsResponse] = await Promise.all([
        fetchDoctorAvailability(selectedDoctor),
        fetchDoctorExceptions(selectedDoctor),
      ]);
      setAvailability(availabilityResponse.data || []);
      setExceptions(exceptionsResponse.data || []);
    } catch {
      setAvailability([]);
      setExceptions([]);
    } finally {
      setLoading(false);
    }
  }, [selectedDoctor]);

  useEffect(() => { loadDoctors(); }, [loadDoctors]);
  useEffect(() => { loadDoctorData(); }, [loadDoctorData]);
  useEffect(() => {
    if (!toast) return undefined;
    const timer = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(timer);
  }, [toast]);

  const toggleDay = async (weekday) => {
    if (busy) return;
    setBusy(true);
    try {
      const existing = availability.find((item) => item.weekday === weekday);
      if (existing) {
        await deleteDoctorAvailability(existing.id);
        setAvailability((current) => current.filter((item) => item.id !== existing.id));
      } else {
        const response = await createDoctorAvailability({ doctor: selectedDoctor, weekday });
        setAvailability((current) => [...current, response.data]);
      }
    } catch (requestError) {
      setToast({ type: 'error', msg: requestError.response?.data?.detail || 'فشل تحديث التوفر.' });
    } finally {
      setBusy(false);
    }
  };

  const addException = async () => {
    if (busy) return;
    if (!newException.date) {
      setToast({ type: 'error', msg: 'حدد تاريخ الاستثناء أولًا.' });
      return;
    }

    setBusy(true);
    try {
      const response = await createDoctorException({ doctor: selectedDoctor, ...newException });
      setExceptions((current) => [...current, response.data]);
      setNewException({ date: '', exception_type: 'blocked', reason: '' });
      setToast({ type: 'success', msg: 'تمت إضافة الاستثناء.' });
    } catch (requestError) {
      setToast({ type: 'error', msg: requestError.response?.data?.detail || 'فشلت إضافة الاستثناء.' });
    } finally {
      setBusy(false);
    }
  };

  const removeException = async (id) => {
    if (busy) return;
    setBusy(true);
    try {
      await deleteDoctorException(id);
      setExceptions((current) => current.filter((item) => item.id !== id));
    } catch {
      setToast({ type: 'error', msg: 'فشل حذف الاستثناء.' });
    } finally {
      setBusy(false);
    }
  };

  const selectedDoctorData = doctors.find((doctor) => doctor.id === selectedDoctor);
  const selectedDoctorName = selectedDoctorData
    ? `${selectedDoctorData.first_name || ''} ${selectedDoctorData.last_name || ''}`.trim() || selectedDoctorData.username
    : '';

  if (!doctors.length && !selectedDoctor) {
    return (
      <PageShell>
        <PageHeader icon={Users} title="توفر الدكاترة" description="إدارة الأيام المتاحة والاستثناءات الخاصة بكل دكتور." />
        <EmptyState icon={Users} title="لا يوجد دكاترة" description="يجب إضافة الدكاترة إلى النظام قبل ضبط أوقات التوفر." />
      </PageShell>
    );
  }

  return (
    <PageShell maxWidth="max-w-6xl">
      <PageHeader
        icon={Users}
        title="توفر الدكاترة"
        description="حدد أيام التوفر الأسبوعية وأضف استثناءات السفر أو المرض أو التوفر الاستثنائي."
        badge={`${doctors.length} دكتور`}
        actions={onBack ? <button type="button" onClick={onBack} className={secondaryButtonClass}>رجوع</button> : null}
      />

      <div className="space-y-4">
        <PageCard>
          <div className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
            <div>
              <label className="mb-2 block text-xs font-bold text-[var(--text-secondary)]">اختر الدكتور</label>
              <select
                value={selectedDoctor || ''}
                onChange={(event) => setSelectedDoctor(Number.parseInt(event.target.value, 10))}
                className={inputClass}
              >
                {doctors.map((doctor) => (
                  <option key={doctor.id} value={doctor.id}>
                    {`${doctor.first_name || ''} ${doctor.last_name || ''}`.trim() || doctor.username}
                  </option>
                ))}
              </select>
            </div>
            <button type="button" onClick={loadDoctorData} disabled={loading} className={secondaryButtonClass}>
              <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
              تحديث
            </button>
          </div>
        </PageCard>

        <PageCard>
          <div className="mb-4">
            <h2 className="m-0 text-base font-black text-[var(--text)]">التوفر الأسبوعي — {selectedDoctorName}</h2>
            <p className="m-0 mt-1 text-xs leading-6 text-[var(--text-muted)]">اضغط على اليوم لتفعيله أو تعطيله. ساعات اليوم تُؤخذ من إعدادات الجدولة.</p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
            {WEEKDAYS.map((weekday) => {
              const active = availability.some((item) => item.weekday === weekday.value);
              return (
                <button
                  key={weekday.value}
                  type="button"
                  onClick={() => toggleDay(weekday.value)}
                  disabled={busy}
                  className={`rounded-xl border px-3 py-3 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-60 ${
                    active
                      ? 'border-[var(--primary)] bg-[var(--primary)] text-white shadow-[var(--shadow-sm)]'
                      : 'border-[var(--border)] bg-[var(--bg-input)] text-[var(--text-secondary)] hover:border-[var(--primary)] hover:bg-[var(--primary-light)]'
                  }`}
                >
                  {active ? '✓ ' : ''}{weekday.label}
                </button>
              );
            })}
          </div>
        </PageCard>

        <PageCard>
          <div className="mb-4">
            <h2 className="m-0 text-base font-black text-[var(--text)]">استثناءات التواريخ</h2>
            <p className="m-0 mt-1 text-xs leading-6 text-[var(--text-muted)]">الاستثناء يتغلب على قاعدة التوفر الأسبوعية لتاريخ محدد.</p>
          </div>

          <div className="grid gap-3 border-b border-[var(--border-light)] pb-5 md:grid-cols-[150px_150px_1fr_auto] md:items-end">
            <div>
              <label className="mb-2 block text-xs font-bold text-[var(--text-secondary)]">التاريخ</label>
              <input type="date" value={newException.date} onChange={(event) => setNewException({ ...newException, date: event.target.value })} className={inputClass} />
            </div>
            <div>
              <label className="mb-2 block text-xs font-bold text-[var(--text-secondary)]">النوع</label>
              <select value={newException.exception_type} onChange={(event) => setNewException({ ...newException, exception_type: event.target.value })} className={inputClass}>
                <option value="blocked">محظور</option>
                <option value="available">متاح</option>
              </select>
            </div>
            <div>
              <label className="mb-2 block text-xs font-bold text-[var(--text-secondary)]">السبب</label>
              <input type="text" placeholder="سفر، مرض، إجازة..." value={newException.reason} onChange={(event) => setNewException({ ...newException, reason: event.target.value })} className={inputClass} />
            </div>
            <button type="button" onClick={addException} disabled={busy} className={primaryButtonClass}>
              <Plus size={15} /> إضافة
            </button>
          </div>

          {loading ? (
            <LoadingState label="جاري تحميل الاستثناءات..." />
          ) : !exceptions.length ? (
            <div className="py-10 text-center text-sm text-[var(--text-muted)]">لا توجد استثناءات لهذا الدكتور.</div>
          ) : (
            <div className="mt-4 overflow-x-auto rounded-xl border border-[var(--border)]">
              <table className="w-full min-w-[620px] border-collapse text-sm">
                <thead className="bg-[var(--bg-tertiary)] text-[var(--text-muted)]">
                  <tr>
                    <th className="px-4 py-3 text-right text-xs font-black">التاريخ</th>
                    <th className="px-4 py-3 text-right text-xs font-black">النوع</th>
                    <th className="px-4 py-3 text-right text-xs font-black">السبب</th>
                    <th className="px-4 py-3 text-left text-xs font-black">الإجراء</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-light)]">
                  {exceptions.map((exception) => (
                    <tr key={exception.id} className="hover:bg-[var(--bg-hover)]">
                      <td className="px-4 py-3 font-semibold text-[var(--text)]">{exception.date}</td>
                      <td className="px-4 py-3">
                        <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${
                          exception.exception_type === 'blocked'
                            ? 'bg-[var(--danger-bg)] text-[var(--danger-text)]'
                            : 'bg-[var(--success-bg)] text-[var(--success-text)]'
                        }`}>
                          {exception.exception_type === 'blocked' ? 'محظور' : 'متاح'}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-[var(--text-muted)]">{exception.reason || '—'}</td>
                      <td className="px-4 py-3 text-left">
                        <button type="button" onClick={() => removeException(exception.id)} disabled={busy} className="flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--danger-border)] text-[var(--danger-text)] hover:bg-[var(--danger-bg)]">
                          <Trash2 size={15} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </PageCard>
      </div>

      {toast && (
        <div className={`fixed bottom-6 left-1/2 z-[100] -translate-x-1/2 rounded-xl px-5 py-3 text-sm font-bold text-white shadow-2xl ${toast.type === 'success' ? 'bg-emerald-600' : 'bg-rose-600'}`}>
          {toast.msg}
        </div>
      )}
    </PageShell>
  );
}
