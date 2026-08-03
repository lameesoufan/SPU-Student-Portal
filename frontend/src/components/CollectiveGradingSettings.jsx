/**
 * CollectiveGradingSettings
 * رئيس القسم يُفعّل/يُعطّل وضع التقييم الجماعي لكل لجنة
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Settings2, UsersRound } from 'lucide-react';
import { fetchGradingModes, setGradingMode } from '../api';
import {
  EmptyState,
  LoadingState,
  PageAlert,
  PageCard,
  PageHeader,
  PageShell,
} from './ui/PagePrimitives';

export default function CollectiveGradingSettings() {
  const [committees, setCommittees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState('success');
  const [toggling, setToggling] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await fetchGradingModes();
      setCommittees(response.data.committees || []);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'تعذّر تحميل إعدادات التقييم.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleToggle = async (committee) => {
    if (toggling) return;
    setToggling(committee.committee_id);
    setMessage('');
    setError('');

    try {
      const response = await setGradingMode(committee.committee_id, !committee.collective);
      setCommittees((current) => current.map((item) => (
        item.committee_id === committee.committee_id
          ? { ...item, collective: response.data.collective }
          : item
      )));
      setMessage(response.data.message || 'تم تحديث وضع التقييم بنجاح.');
      setMessageType('success');
    } catch (requestError) {
      setMessage(requestError.response?.data?.detail || 'فشل تحديث وضع التقييم.');
      setMessageType('error');
    } finally {
      setToggling(null);
    }
  };

  if (loading) return <LoadingState label="جاري تحميل إعدادات التقييم..." />;

  return (
    <PageShell maxWidth="max-w-5xl">
      <PageHeader
        icon={Settings2}
        title="إعدادات التقييم الجماعي"
        description="حدّد لكل لجنة ما إذا كانت العلامة تُدخل بصورة فردية أو تُحسب كمتوسط لعلامات جميع أعضاء اللجنة."
        badge={`${committees.length} لجنة`}
      />

      <div className="space-y-4">
        {error && <PageAlert>{error}</PageAlert>}
        {message && <PageAlert type={messageType}>{message}</PageAlert>}

        {!committees.length ? (
          <EmptyState
            icon={UsersRound}
            title="لا توجد لجان متاحة"
            description="ستظهر هنا اللجان بعد إنشائها وتوزيع المشاريع عليها."
          />
        ) : (
          <PageCard className="overflow-hidden" padded={false}>
            <div className="divide-y divide-[var(--border-light)]">
              {committees.map((committee) => {
                const busy = toggling === committee.committee_id;
                return (
                  <div
                    key={committee.committee_id}
                    className="flex flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="m-0 text-sm font-black text-[var(--text)] sm:text-base">
                          {committee.committee_type_ar} — {committee.department_ar} — {committee.project_type_ar}
                        </h2>
                        <span className={`rounded-full px-2.5 py-1 text-[11px] font-bold ${
                          committee.collective
                            ? 'bg-[var(--primary-light)] text-[var(--primary)]'
                            : 'bg-[var(--bg-tertiary)] text-[var(--text-muted)]'
                        }`}>
                          {committee.collective ? 'تقييم جماعي' : 'تقييم فردي'}
                        </span>
                      </div>
                      <p className="m-0 mt-1 text-xs text-[var(--text-muted)]">
                        {committee.semester || 'الفصل غير محدد'}
                      </p>
                    </div>

                    <button
                      type="button"
                      role="switch"
                      aria-checked={committee.collective}
                      disabled={busy}
                      onClick={() => handleToggle(committee)}
                      className="inline-flex w-full items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-2.5 transition hover:border-[var(--primary)] disabled:cursor-not-allowed disabled:opacity-60 sm:w-auto"
                    >
                      <span className={`text-xs font-bold ${committee.collective ? 'text-[var(--primary)]' : 'text-[var(--text-muted)]'}`}>
                        {busy ? 'جاري التحديث...' : committee.collective ? 'مُفعّل' : 'مُعطّل'}
                      </span>
                      <span className={`relative h-6 w-11 rounded-full transition ${committee.collective ? 'bg-[var(--primary)]' : 'bg-[var(--bg-quaternary)]'}`}>
                        <span className={`absolute top-1 h-4 w-4 rounded-full bg-white shadow transition ${committee.collective ? 'left-1' : 'left-6'}`} />
                      </span>
                    </button>
                  </div>
                );
              })}
            </div>
          </PageCard>
        )}
      </div>
    </PageShell>
  );
}
