import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  ArrowRight, Plus, RefreshCw, FileDown, Search,
  Eye, Trash2, Calendar, Clock, MapPin, Users, FolderKanban,
  ChevronLeft, ChevronRight, AlertTriangle, CheckCircle2, Inbox,
  Gavel, Building2, BookOpen, X,
} from 'lucide-react';
import {
  fetchCommittees, deleteCommittee, exportCommittees, distributeProjects,
} from '../../api';
import {
  COMMITTEE_TYPES, PROJECT_TYPES, DEPARTMENTS, COMMITTEE_STATUSES,
  COMMITTEE_TYPE_COLORS, DEPARTMENT_COLORS, STATUS_COLORS,
  getCommitteeTypeLabel, getProjectTypeLabel, getDepartmentLabel, getCommitteeStatusLabel,
} from './constants';
import './DistributionTable.css';

const PAGE_SIZE = 10;

function distributionExclusionMessage(exclusions) {
  const total = Number(exclusions?.excluded_students_total || 0);
  const failed = Number(exclusions?.excluded_failed_students || 0);
  const withdrawn = Number(exclusions?.excluded_withdrawn_students || 0);
  const zeroActiveProjects = Number(exclusions?.excluded_projects_zero_active || 0);

  if (!total && !zeroActiveProjects) return '';

  const statusParts = [];
  if (withdrawn) statusParts.push(`${withdrawn} withdrawn`);
  if (failed) statusParts.push(`${failed} failed`);

  const studentPart = total
    ? `${total} students excluded from distribution: ${statusParts.join(', ') || 'inactive status'}.`
    : '';
  const projectPart = zeroActiveProjects
    ? `${zeroActiveProjects} projects with zero active students skipped.`
    : '';

  return [studentPart, projectPart].filter(Boolean).join(' ');
}

/* ────────────────────────────────────────────────────────────────────────── */
/* DistributionTable — matches mockup 03_distribution_table.png                 */
/* Layout: header + mini stats + toolbar + filters + table + pagination          */
/* ────────────────────────────────────────────────────────────────────────── */

export default function DistributionTable({ onBack, onNavigate, filterTemplateId }) {
  const [committees, setCommittees] = useState([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [busy, setBusy]             = useState(false);
  const [toast, setToast]           = useState(null);

  // Filters
  const [search, setSearch]         = useState('');
  const [fType, setFType]           = useState('');
  const [fDept, setFDept]           = useState('');
  const [fProj, setFProj]           = useState('');
  const [fStatus, setFStatus]       = useState('');
  const [fTemplate, setFTemplate]   = useState(filterTemplateId || '');

  // Pagination
  const [page, setPage]             = useState(1);

  /* ── Load committees ─────────────────────────────────────────────────── */
  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await fetchCommittees();
      setCommittees(res.data?.results || res.data || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'تعذر تحميل قائمة اللجان.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Auto-dismiss toast
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  /* ── Filtered + paginated ────────────────────────────────────────────── */
  const filtered = useMemo(() => {
    return committees.filter((c) => {
      if (fType && c.committee_type !== fType) return false;
      if (fDept && c.department !== fDept) return false;
      if (fProj && c.project_type !== fProj) return false;
      if (fStatus && c.status !== fStatus) return false;
      if (fTemplate && c.template_id !== parseInt(fTemplate, 10)) return false;
      if (search.trim()) {
        const q = search.toLowerCase();
        const haystack = [
          c.committee_type_ar, c.department_ar, c.project_type_ar,
          c.sequence_number, c.semester, c.location || '',
          (c.chair?.full_name || c.chair?.username || ''),
          ...((c.members || []).map(m => m.full_name || m.username)),
        ].join(' ').toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [committees, fType, fDept, fProj, fStatus, fTemplate, search]);

  useEffect(() => { setPage(1); }, [fType, fDept, fProj, fStatus, fTemplate, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageItems  = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  /* ── Actions ─────────────────────────────────────────────────────────── */
  const handleDelete = async (c) => {
    if (busy) return;
    if (!confirm(`Delete committee #${c.sequence_number} (${c.committee_type_ar} - ${c.department_ar})? Cannot be undone.`)) return;
    setBusy(true);
    try {
      await deleteCommittee(c.id);
      setCommittees((prev) => prev.filter((x) => x.id !== c.id));
      setToast({ type: 'success', msg: 'تم حذف اللجنة.' });
    } catch (err) {
      setToast({ type: 'error', msg: err.response?.data?.detail || 'فشل الحذف.' });
    } finally { setBusy(false); }
  };

  const handleDistribute = async () => {
    if (busy) return;
    if (!confirm('هل تريد تشغيل خوارزمية توزيع المشاريع على جميع اللجان؟')) return;
    setBusy(true);
    try {
      const res = await distributeProjects({ dry_run: false });
      const distributed    = res.data?.distributed_projects    ?? 0;
      const undistributed  = res.data?.undistributed_projects  ?? 0;
      const processed      = res.data?.processed_templates     ?? 0;
      const exclusionMsg   = distributionExclusionMessage(res.data?.exclusions);
      const msg = undistributed > 0
        ? `Distributed ${distributed} projects across ${processed} compositions. (${undistributed} projects without suitable committee — review alerts.)`
        : `Successfully distributed ${distributed} projects across ${processed} compositions.`;
      setToast({ type: 'success', msg: [msg, exclusionMsg].filter(Boolean).join(' ') });
      await load();
    } catch (err) {
      setToast({ type: 'error', msg: 'فشل التوزيع.' });
    } finally { setBusy(false); }
  };

  const handleExport = async (format) => {
    if (busy) return;
    setBusy(true);
    try {
      const res = await exportCommittees(format);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `committees_${new Date().toISOString().slice(0,10)}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setToast({ type: 'success', msg: `${format.toUpperCase()} تم تصديره بنجاح.` });
    } catch {
      setToast({ type: 'error', msg: 'فشل التصدير.' });
    } finally { setBusy(false); }
  };

  const clearFilters = () => {
    setSearch(''); setFType(''); setFDept(''); setFProj(''); setFStatus(''); setFTemplate('');
  };

  const hasFilters = !!(search || fType || fDept || fProj || fStatus || fTemplate);

  /* ── Stats ───────────────────────────────────────────────────────────── */
  const stats = useMemo(() => ({
    total:       committees.length,
    scheduled:   committees.filter(c => c.status === 'scheduled').length,
    drafts:      committees.filter(c => c.status === 'draft').length,
    completed:   committees.filter(c => c.status === 'completed').length,
    projects:    committees.reduce((s, c) => s + (c.projects_count || 0), 0),
  }), [committees]);

  /* ── Render ──────────────────────────────────────────────────────────── */
  return (
    <div className="cdt-page" dir="rtl">
      {/* Header */}
      <div className="cdt-header">
        <div className="cdt-header-left">
          <div className="cdt-header-icon">
            <FolderKanban size={22} />
          </div>
          <div>
            <h1 className="cdt-header-title">قائمة اللجان</h1>
            <p className="cdt-header-sub">
              استعرض جميع اللجان المنشأة من التشكيلات، وابحث وصفِّ النتائج، وافتح أي لجنة لعرض تفاصيلها.
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="cdt-back" onClick={onBack}>
            <ArrowRight size={14} /> لوحة اللجان
          </button>
          <button
            className="cdt-btn cdt-btn-primary"
            onClick={() => onNavigate && onNavigate('committees-template-form')}
          >
            <Plus size={14} /> تشكيلة جديدة
          </button>
        </div>
      </div>

      {/* Mini stats */}
      <div className="cdt-stats">
        <div className="cdt-stat">
          <div className="cdt-stat-icon is-purple"><FolderKanban size={18} /></div>
          <div>
            <div className="cdt-stat-value">{stats.total}</div>
            <div className="cdt-stat-label">إجمالي اللجان</div>
          </div>
        </div>
        <div className="cdt-stat">
          <div className="cdt-stat-icon is-amber"><Inbox size={18} /></div>
          <div>
            <div className="cdt-stat-value">{stats.drafts}</div>
            <div className="cdt-stat-label">مسودة</div>
          </div>
        </div>
        <div className="cdt-stat">
          <div className="cdt-stat-icon is-blue"><Calendar size={18} /></div>
          <div>
            <div className="cdt-stat-value">{stats.scheduled}</div>
            <div className="cdt-stat-label">مجدولة</div>
          </div>
        </div>
        <div className="cdt-stat">
          <div className="cdt-stat-icon is-green"><CheckCircle2 size={18} /></div>
          <div>
            <div className="cdt-stat-value">{stats.completed}</div>
            <div className="cdt-stat-label">منجزة</div>
          </div>
        </div>
        <div className="cdt-stat">
          <div className="cdt-stat-icon is-red"><FolderKanban size={18} /></div>
          <div>
            <div className="cdt-stat-value">{stats.projects}</div>
            <div className="cdt-stat-label">المشاريع الموزعة</div>
          </div>
        </div>
      </div>

      {/* Toolbar */}
      <div className="cdt-toolbar">
        <div className="cdt-toolbar-left">
          <button
            className="cdt-btn cdt-btn-success"
            onClick={handleDistribute}
            disabled={busy || committees.length === 0}
          >
            {busy ? <RefreshCw size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            Distribute Projects
          </button>
          <button className="cdt-btn" onClick={() => handleExport('xlsx')} disabled={busy}>
            <FileDown size={14} /> إكسل
          </button>
          {/* PDF export button removed as per requirements */}
        </div>
        <div className="cdt-toolbar-right">
          <button className="cdt-btn" onClick={load} disabled={loading}>
            <RefreshCw size={13} /> تحديث
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="cdt-filters">
        <div className="cdt-search">
          <Search size={15} className="cdt-search-icon" />
          <input
            type="search"
            placeholder="ابحث برقم اللجنة أو عضو الهيئة التدريسية أو الموقع..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select className="cdt-select" value={fType}   onChange={(e) => setFType(e.target.value)}>
          <option value="">جميع أنواع اللجان</option>
          {COMMITTEE_TYPES.map((c) => <option key={c.value} value={c.value}>{c.label_ar}</option>)}
        </select>
        <select className="cdt-select" value={fDept}   onChange={(e) => setFDept(e.target.value)}>
          <option value="">جميع الأقسام</option>
          {DEPARTMENTS.map((d) => <option key={d.value} value={d.value}>{d.label_ar}</option>)}
        </select>
        <select className="cdt-select" value={fProj}   onChange={(e) => setFProj(e.target.value)}>
          <option value="">جميع أنواع المشاريع</option>
          {PROJECT_TYPES.map((p) => <option key={p.value} value={p.value}>{p.label_ar}</option>)}
        </select>
        <select className="cdt-select" value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
          <option value="">جميع الحالات</option>
          {COMMITTEE_STATUSES.map((s) => <option key={s.value} value={s.value}>{s.label_ar}</option>)}
        </select>
        {hasFilters && (
          <button className="cdt-btn" onClick={clearFilters}>
            <X size={13} /> مسح عوامل التصفية
          </button>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="cdt-error">
          <AlertTriangle size={16} /> {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="cdt-loading">
          <div className="cdt-spinner" /> جارٍ تحميل اللجان…
        </div>
      )}

      {/* Table */}
      {!loading && !error && (
        <>
          {pageItems.length === 0 ? (
            <div className="cdt-table-wrap">
              <div className="cdt-empty">
                <div className="cdt-empty-icon"><FolderKanban size={28} /></div>
                <h3>{hasFilters ? 'لا توجد نتائج مطابقة' : 'لا توجد لجان بعد'}</h3>
                <p>
                  {hasFilters
                    ? 'جرّب تعديل عوامل التصفية أو مسحها.'
                    : 'Start by creating a new composition to generate committees automatically.'}
                </p>
                {!hasFilters && (
                  <button
                    className="cdt-btn cdt-btn-primary"
                    onClick={() => onNavigate && onNavigate('committees-template-form')}
                  >
                    <Plus size={14} /> إنشاء تشكيلة
                  </button>
                )}
              </div>
            </div>
          ) : (
            <div className="cdt-table-wrap">
              <div className="cdt-table-scroll">
                <table className="cdt-table">
                  <thead>
                    <tr>
                      <th>اللجنة</th>
                      <th>الحالة</th>
                      <th>الجدولة (يدوية)</th>
                      <th>مجدولة (CP-SAT)</th>
                      <th>الهيئة التدريسية</th>
                      <th>المشاريع</th>
                      <th style={{ textAlign: 'left' }}>الإجراءات</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pageItems.map((c) => {
                      const cTypeColor = COMMITTEE_TYPE_COLORS[c.committee_type] || {};
                      const deptColor  = DEPARTMENT_COLORS[c.department] || {};
                      const statusColor = STATUS_COLORS[c.status] || {};
                      const chair = c.chair;
                      const members = c.members || [];
                      const allDoctors = [chair, ...members].filter(Boolean);
                      const displayDoctors = allDoctors.slice(0, 4);
                      const extraCount = Math.max(0, allDoctors.length - 4);
                      const chairName = chair?.full_name || chair?.username || '—';

                      return (
                        <tr
                          key={c.id}
                          onClick={() => onNavigate && onNavigate('committee-detail', { id: c.id })}
                        >
                          {/* Title cell */}
                          <td>
                            <div className="cdt-title-cell">
                              <div
                                className="cdt-seq"
                                style={{ background: cTypeColor.text || 'var(--primary)' }}
                                title={c.committee_type_ar}
                              >
                                #{String(c.sequence_number || '').padStart(3, '0')}
                              </div>
                              <div className="cdt-title-text">
                                <span className="cdt-title-main">
                                  {c.committee_type_ar} — {c.department_ar}
                                </span>
                                <span className="cdt-title-sub">
                                  {c.project_type_ar} · {c.semester || '—'}
                                </span>
                              </div>
                            </div>
                          </td>

                          {/* Status */}
                          <td>
                            <span
                              className="cdt-badge"
                              style={{
                                background: statusColor.bg,
                                color: statusColor.text,
                                borderColor: statusColor.border,
                              }}
                            >
                              <span
                                className="cdt-badge-dot"
                                style={{ background: statusColor.text }}
                              />
                              {getCommitteeStatusLabel(c.status)}
                            </span>
                          </td>

                          {/* Schedule */}
                          <td>
                            <div className="cdt-schedule">
                              {c.date ? (
                                <span className="cdt-schedule-row">
                                  <Calendar size={12} /> {c.date}
                                </span>
                              ) : (
                                <span className="cdt-schedule-row is-empty">
                                  <Calendar size={12} /> لا يوجد تاريخ
                                </span>
                              )}
                              {c.time && (
                                <span className="cdt-schedule-row">
                                  <Clock size={12} /> {c.time}
                                </span>
                              )}
                              {c.location ? (
                                <span className="cdt-schedule-row">
                                  <MapPin size={12} /> {c.location}
                                </span>
                              ) : (
                                <span className="cdt-schedule-row is-empty">
                                  <MapPin size={12} /> لا توجد قاعة
                                </span>
                              )}
                            </div>
                          </td>

                          {/* Scheduled (CP-SAT) */}
                          <td>
                            {c.scheduled_start ? (
                              <div className="cdt-schedule">
                                <span className="cdt-schedule-row" style={{ color: '#0369a1', fontWeight: 600 }}>
                                  <Calendar size={12} /> {new Date(c.scheduled_start).toLocaleDateString('ar-IQ', { day: '2-digit', month: 'short' })}
                                </span>
                                <span className="cdt-schedule-row" style={{ color: '#0369a1', fontWeight: 600 }}>
                                  <Clock size={12} /> {new Date(c.scheduled_start).toLocaleTimeString('ar-IQ', { hour: '2-digit', minute: '2-digit' })} - {new Date(c.scheduled_end).toLocaleTimeString('ar-IQ', { hour: '2-digit', minute: '2-digit' })}
                                </span>
                                {c.room && (
                                  <span className="cdt-schedule-row">
                                    <MapPin size={12} /> {c.room_detail?.name || c.room_name || c.room}
                                  </span>
                                )}
                                {c.manually_scheduled && (
                                  <span style={{ fontSize: 10, color: '#f59e0b', fontWeight: 600 }}>✎ معدّل يدوياً</span>
                                )}
                              </div>
                            ) : (
                              <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>—</span>
                            )}
                          </td>

                          {/* Doctors */}
                          <td>
                            <div className="cdt-doctors" title={`Chair: ${chairName}`}>
                              {displayDoctors.map((d, i) => {
                                const name = d?.full_name || d?.username || '?';
                                const initial = name.charAt(0).toUpperCase();
                                return (
                                  <div
                                    key={d?.id || i}
                                    className={`cdt-doctor-avatar-sm ${i === 0 ? 'is-chair' : ''}`}
                                    title={i === 0 ? `Chair: ${name}` : `Member: ${name}`}
                                  >
                                    {initial}
                                  </div>
                                );
                              })}
                              {extraCount > 0 && (
                                <span className="cdt-doctors-extra">+{extraCount}</span>
                              )}
                              {allDoctors.length === 0 && (
                                <span style={{ fontSize: 11, color: 'var(--text-faint)' }}>—</span>
                              )}
                            </div>
                          </td>

                          {/* Project count */}
                          <td>
                            <span className="cdt-count">
                              <FolderKanban size={12} /> {c.projects_count || 0}
                            </span>
                          </td>

                          {/* Actions */}
                          <td onClick={(e) => e.stopPropagation()}>
                            <div className="cdt-actions-cell">
                              <button
                                className="cdt-action-btn is-primary"
                                title="عرض التفاصيل"
                                onClick={() => onNavigate && onNavigate('committee-detail', { id: c.id })}
                              >
                                <Eye size={15} />
                              </button>
                              <button
                                className="cdt-action-btn is-danger"
                                title="حذف"
                                onClick={() => handleDelete(c)}
                                disabled={busy}
                              >
                                <Trash2 size={15} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Pagination */}
          {filtered.length > 0 && (
            <div className="cdt-pagination">
              <div className="cdt-pagination-info">
                Showing {(page - 1) * PAGE_SIZE + 1} - {Math.min(page * PAGE_SIZE, filtered.length)} of {filtered.length} committees
              </div>
              <div className="cdt-pagination-controls">
                <button
                  className="cdt-page-btn"
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page === 1}
                >
                  <ChevronRight size={14} />
                </button>
                {Array.from({ length: totalPages }).slice(0, 7).map((_, i) => {
                  const p = i + 1;
                  return (
                    <button
                      key={p}
                      className={`cdt-page-btn ${p === page ? 'is-active' : ''}`}
                      onClick={() => setPage(p)}
                    >
                      {p}
                    </button>
                  );
                })}
                {totalPages > 7 && <span style={{ color: 'var(--text-muted)' }}>…</span>}
                <button
                  className="cdt-page-btn"
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                  disabled={page === totalPages}
                >
                  <ChevronLeft size={14} />
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Toast */}
      {toast && (
        <div className={`cdt-toast ${toast.type === 'success' ? 'is-success' : 'is-error'}`}>
          {toast.type === 'success' ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
          {toast.msg}
        </div>
      )}
    </div>
  );
}
