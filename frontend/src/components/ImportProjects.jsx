import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Clipboard,
  Download,
  Eye,
  FileSpreadsheet,
  History,
  PlayCircle,
  UploadCloud,
} from 'lucide-react';
import {
  downloadProjectImportTemplate,
  fetchProjectImportHistory,
  importProjects,
} from '../api';

const formatFileSize = (bytes) => {
  if (!bytes) return '0 KB';
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
};

const normalizeHistory = (payload) => payload?.results || payload || [];

const formatImportError = (payload, fallback) => {
  if (!payload) return fallback;
  let message = payload.error || fallback;
  const details = Array.isArray(payload.details) ? payload.details[0] : payload.details;
  const receivedHeaders = details?.received_headers?.filter(Boolean);
  if (receivedHeaders?.length) {
    message += ` Received headers: ${receivedHeaders.join(', ')}`;
  }
  return message;
};

export default function ImportProjects({ onBack }) {
  const [file, setFile] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]);
  const fileInputRef = useRef(null);

  const canExecute = Boolean(file && preview?.preview_result_id && preview?.valid_rows_count > 0);
  const errors = result?.validation_errors || preview?.validation_errors || [];
  const warnings = result?.warnings || preview?.warnings || [];

  const summary = useMemo(() => result || preview, [result, preview]);
  const supervisorCredentialExport = result?.supervisor_credentials_export;
  const studentCredentialExport = result?.student_credentials_export;

  useEffect(() => {
    loadHistory();
  }, []);

  const loadHistory = async () => {
    try {
      const res = await fetchProjectImportHistory();
      setHistory(normalizeHistory(res.data).slice(0, 6));
    } catch {
      setHistory([]);
    }
  };

  const pickFile = (nextFile) => {
    setFile(nextFile || null);
    setPreview(null);
    setResult(null);
    setError('');
  };

  const handlePreview = async () => {
    if (!file) {
      setError('Please select an XLSX file first.');
      return;
    }
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const res = await importProjects(file, { dry_run: true });
      setPreview(res.data);
    } catch (err) {
      const payload = err.response?.data;
      setPreview(payload?.validation_errors ? payload : null);
      setError(formatImportError(payload, 'Preview failed. Please review the file and try again.'));
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = async () => {
    if (!canExecute) return;
    setLoading(true);
    setError('');
    try {
      const res = await importProjects(file, {
        dry_run: false,
        preview_result_id: preview.preview_result_id,
      });
      setResult(res.data);
      setPreview(null);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      await loadHistory();
    } catch (err) {
      const payload = err.response?.data;
      setResult(payload?.validation_errors ? payload : null);
      setError(formatImportError(payload, 'Import failed. No changes were saved.'));
    } finally {
      setLoading(false);
    }
  };

  const handleTemplateDownload = async () => {
    setError('');
    try {
      const res = await downloadProjectImportTemplate();
      const url = URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.download = 'project_import_template.xlsx';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch {
      setError('Could not download the template. Please try again.');
    }
  };

  const copyErrors = async () => {
    const text = errors.map((item) => `Row ${item.row_number || '-'} - ${item.field_name}: ${item.error_message}`).join('\n');
    if (!text) return;
    await navigator.clipboard.writeText(text);
  };

  const downloadErrorCsv = () => {
    if (!errors.length) return;
    const rows = [
      ['row_number', 'field_name', 'value', 'error_type', 'message'],
      ...errors.map((item) => [
        item.row_number || '',
        item.field_name || '',
        item.row_data?.[item.field_name] ?? '',
        item.error_type || '',
        item.error_message || '',
      ]),
    ];
    const csv = rows.map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'project_import_errors.csv';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const downloadSupervisorCredentialsCsv = () => {
    const exportData = supervisorCredentialExport;
    if (!exportData?.rows?.length) return;
    const columns = exportData.columns || [
      'source_row_number',
      'project_title',
      'department',
      'full_name',
      'username',
      'generated_password',
      'created_or_reused',
      'created_at',
      'notes',
    ];
    const rows = [
      columns,
      ...exportData.rows.map((item) => columns.map((column) => item[column] ?? '')),
    ];
    const csv = rows.map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = exportData.filename || 'supervisor_credentials.csv';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  const downloadStudentCredentialsCsv = () => {
    const exportData = studentCredentialExport;
    if (!exportData?.rows?.length) return;
    const columns = exportData.columns || [
      'university_id',
      'project_title',
      'department',
      'full_name',
      'username',
      'generated_password',
      'created_or_reused',
      'created_at',
      'notes',
    ];
    const rows = [
      columns,
      ...exportData.rows.map((item) => columns.map((column) => item[column] ?? '')),
    ];
    const csv = rows.map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = exportData.filename || 'student_credentials.csv';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-[var(--bg-primary,#f8fafc)] p-6 md:p-8">
      {onBack && (
        <button
          type="button"
          onClick={onBack}
          className="mb-5 rounded-lg border border-[var(--border,#e2e8f0)] bg-[var(--card,#fff)] px-4 py-2 text-sm font-semibold text-[var(--text,#1e293b)] hover:bg-[var(--bg-hover,#f1f5f9)]"
        >
          Back to Dashboard
        </button>
      )}

      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-indigo-50 px-3 py-1 text-xs font-bold text-indigo-700">
            <FileSpreadsheet size={14} /> Super Admin Tool
          </div>
          <h1 className="text-2xl font-bold text-[var(--text,#1e293b)]">Import Projects</h1>
          <p className="mt-1 max-w-2xl text-sm text-[var(--text-secondary,#64748b)]">
            Preview and import assigned student projects from a structured XLSX file. Valid rows can be imported while invalid rows remain downloadable for correction.
          </p>
        </div>
        <button
          type="button"
          onClick={handleTemplateDownload}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-bold text-white hover:bg-indigo-700"
        >
          <Download size={17} /> Download Template
        </button>
      </div>

      {error && (
        <div className="mb-5 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
          <AlertTriangle size={18} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="rounded-lg border border-[var(--border,#e2e8f0)] bg-[var(--card,#fff)] p-5 shadow-sm">
          <label className="mb-2 block text-sm font-bold text-[var(--text,#1e293b)]">Project XLSX File</label>
          <div
            role="button"
            tabIndex={0}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(event) => event.key === 'Enter' && fileInputRef.current?.click()}
            onDragOver={(event) => { event.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragOver(false);
              pickFile(event.dataTransfer.files?.[0]);
            }}
            className={`flex min-h-[180px] cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 text-center transition ${
              dragOver ? 'border-indigo-500 bg-indigo-50' : file ? 'border-emerald-400 bg-emerald-50' : 'border-slate-300 bg-slate-50 hover:border-indigo-400'
            }`}
          >
            <UploadCloud className={file ? 'text-emerald-600' : 'text-slate-400'} size={38} />
            <strong className="mt-3 text-sm text-[var(--text,#1e293b)]">
              {file ? file.name : 'Click to choose or drag an XLSX file here'}
            </strong>
            <span className="mt-1 text-xs text-[var(--text-secondary,#64748b)]">
              {file ? formatFileSize(file.size) : 'Maximum 10 MB. Legacy .xls is intentionally disabled.'}
            </span>
            {!file && (
              <span className="mt-3 max-w-xl text-xs leading-5 text-[var(--text-secondary,#64748b)]">
                Headers may use Arabic labels, English keys, or both together. project_type must be one of: seasonal, graduation_1, graduation_2.
              </span>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx"
              className="hidden"
              onChange={(event) => pickFile(event.target.files?.[0])}
            />
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <button
              type="button"
              onClick={handlePreview}
              disabled={!file || loading}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm font-bold text-indigo-700 hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Eye size={18} /> {loading && !result ? 'Processing...' : 'Preview Import'}
            </button>
            <button
              type="button"
              onClick={handleExecute}
              disabled={!canExecute || loading}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-3 text-sm font-bold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <PlayCircle size={18} /> {preview?.partial_import ? 'Execute Valid Rows' : 'Execute Import'}
            </button>
          </div>

          {summary && (
            <div className="mt-6 grid gap-3 md:grid-cols-4">
              <Metric label="Rows" value={summary.total_rows_processed} />
              <Metric label="Valid" value={summary.valid_rows_count} tone="green" />
              <Metric label="Invalid" value={summary.invalid_rows_count} tone="red" />
              <Metric label={summary.dry_run ? 'Would Create' : 'Created'} value={summary.dry_run ? summary.projects_to_create : summary.created_projects_count} tone="indigo" />
            </div>
          )}

          {preview?.partial_import && (
            <div className="mt-5 flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              <AlertTriangle size={18} className="mt-0.5 shrink-0" />
              <span>
                {preview.valid_rows_count} valid row{preview.valid_rows_count === 1 ? '' : 's'} can be imported now. {preview.invalid_rows_count} invalid row{preview.invalid_rows_count === 1 ? '' : 's'} will be skipped and kept in the error report.
              </span>
            </div>
          )}

          {(result?.status === 'success' || result?.status === 'partial_success') && (
            <div className="mt-5 flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
              <CheckCircle2 size={18} className="mt-0.5 shrink-0" />
              Imported {result.created_projects_count} project{result.created_projects_count === 1 ? '' : 's'} successfully{result.partial_import ? ` and skipped ${result.failed_imports} invalid row${result.failed_imports === 1 ? '' : 's'}` : ''}.
            </div>
          )}

          {supervisorCredentialExport?.available && (
            <div className="mt-5 rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-3 text-sm text-indigo-800">
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <strong className="block">Supervisor credentials export is ready</strong>
                  <span className="mt-1 block">{supervisorCredentialExport.security_note}</span>
                </div>
                <button
                  type="button"
                  onClick={downloadSupervisorCredentialsCsv}
                  className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-bold text-white hover:bg-indigo-700"
                >
                  <Download size={14} /> Supervisor Credentials
                </button>
              </div>
            </div>
          )}

          {studentCredentialExport?.available && (
            <div className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <strong className="block">Student credentials export is ready</strong>
                  <span className="mt-1 block">{studentCredentialExport.security_note}</span>
                </div>
                <button
                  type="button"
                  onClick={downloadStudentCredentialsCsv}
                  className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-2 text-xs font-bold text-white hover:bg-emerald-700"
                >
                  <Download size={14} /> Student Credentials
                </button>
              </div>
            </div>
          )}

          {(errors.length > 0 || warnings.length > 0) && (
            <div className="mt-6">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-base font-bold text-[var(--text,#1e293b)]">Validation Details</h2>
                <div className="flex gap-2">
                  <button type="button" onClick={copyErrors} className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-bold">
                    <Clipboard size={14} /> Copy Errors
                  </button>
                  <button type="button" onClick={downloadErrorCsv} className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-2 text-xs font-bold">
                    <Download size={14} /> CSV
                  </button>
                </div>
              </div>
              <div className="overflow-x-auto rounded-lg border border-[var(--border,#e2e8f0)]">
                <table className="w-full min-w-[720px] border-collapse text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3">Row</th>
                      <th className="px-4 py-3">Field</th>
                      <th className="px-4 py-3">Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...errors, ...warnings].map((item, index) => (
                      <tr key={`${item.level}-${item.row_number}-${item.field_name}-${index}`} className="border-t">
                        <td className="px-4 py-3">
                          <span className={`rounded-full px-2 py-1 text-xs font-bold ${item.level === 'warning' ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-700'}`}>
                            {item.level || 'error'}
                          </span>
                        </td>
                        <td className="px-4 py-3">{item.row_number || '-'}</td>
                        <td className="px-4 py-3 font-medium">{item.field_name || '-'}</td>
                        <td className="px-4 py-3">{item.error_message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>

        <aside className="rounded-lg border border-[var(--border,#e2e8f0)] bg-[var(--card,#fff)] p-5 shadow-sm">
          <div className="mb-4 flex items-center gap-2">
            <History size={18} className="text-indigo-600" />
            <h2 className="text-base font-bold text-[var(--text,#1e293b)]">Recent Imports</h2>
          </div>
          {history.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary,#64748b)]">No project imports yet.</p>
          ) : (
            <div className="space-y-3">
              {history.map((item) => (
                <div key={item.id} className="rounded-lg border border-slate-200 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <strong className="min-w-0 truncate text-sm text-[var(--text,#1e293b)]">{item.filename}</strong>
                    <span className={`rounded-full px-2 py-1 text-[11px] font-bold ${
                      item.status === 'success' ? 'bg-emerald-50 text-emerald-700' : item.status === 'failed' ? 'bg-red-50 text-red-700' : 'bg-slate-100 text-slate-600'
                    }`}>
                      {item.status}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-[var(--text-secondary,#64748b)]">
                    {item.successful_rows} success, {item.failed_rows} failed
                  </p>
                </div>
              ))}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

function Metric({ label, value, tone = 'slate' }) {
  const colors = {
    slate: 'text-slate-700 bg-slate-50 border-slate-200',
    green: 'text-emerald-700 bg-emerald-50 border-emerald-200',
    red: 'text-red-700 bg-red-50 border-red-200',
    indigo: 'text-indigo-700 bg-indigo-50 border-indigo-200',
  };
  return (
    <div className={`rounded-lg border p-4 ${colors[tone] || colors.slate}`}>
      <span className="block text-xs font-bold uppercase tracking-wide opacity-75">{label}</span>
      <strong className="mt-1 block text-2xl">{value ?? 0}</strong>
    </div>
  );
}
