import React, { useState, useRef } from 'react';
import { uploadReferenceDb } from '../api';

/* Premium SVG Icons (matching ImportUsers.jsx style) */
const Icons = {
  FileUp: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><polyline points="9 15 12 12 15 15"/></svg>,
  UploadAction: <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>,
  Info: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>,
  Check: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>,
  Alert: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
  ArrowLeft: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>,
  Database: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/></svg>
};

const ACCEPTED_EXTS = ['.xlsx', '.xls', '.csv'];
const MAX_SIZE_MB = 10;

export default function UploadReference({ onBack }) {
  const [file, setFile]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult]   = useState(null);
  const [error, setError]     = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const fileRef = useRef();

  const validateFile = (f) => {
    if (!f) return 'Please select a file.';
    const ext = '.' + (f.name.split('.').pop() || '').toLowerCase();
    if (!ACCEPTED_EXTS.includes(ext)) {
      return `Unsupported file type "${ext}". Allowed: ${ACCEPTED_EXTS.join(', ')}`;
    }
    if (f.size > MAX_SIZE_MB * 1024 * 1024) {
      return `File is too large. Max ${MAX_SIZE_MB} MB.`;
    }
    return '';
  };

  const handleDragOver  = (e) => { e.preventDefault(); setIsDragOver(true); };
  const handleDragLeave = ()   => setIsDragOver(false);
  const handleDrop      = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files?.length > 0) {
      const f = e.dataTransfer.files[0];
      const err = validateFile(f);
      if (err) { setError(err); return; }
      setFile(f); setError(''); setResult(null);
    }
  };

  const handleFileChange = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const err = validateFile(f);
    if (err) { setError(err); return; }
    setFile(f); setError(''); setResult(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) { setError('Please select a file first.'); return; }
    setError(''); setResult(null); setLoading(true);
    try {
      const res = await uploadReferenceDb(file);
      setResult(res.data);
      setFile(null);
      if (fileRef.current) fileRef.current.value = '';
    } catch (err) {
      const errData = err.response?.data;
      setError(
        errData?.error
        || errData?.detail
        || (errData?.details && JSON.stringify(errData.details))
        || 'Upload failed. Please verify the backend endpoint /api/upload-reference/ is implemented.'
      );
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-[var(--bg,#f8fafc)] p-6 md:p-10">
      {onBack && (
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-sm font-semibold mb-6 px-4 py-2 rounded-xl border border-[var(--border,#e2e8f0)] bg-[var(--card,#fff)] hover:bg-[var(--bg-hover,#f1f5f9)] transition-colors"
        >
          {Icons.ArrowLeft} Back to Dashboard
        </button>
      )}

      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <div className="p-3 rounded-2xl bg-[var(--primary-bg,#eef2ff)] text-[var(--primary,#6366f1)]">
          {Icons.Database}
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[var(--text,#1e293b)]">Upload Student Reference Database</h1>
          <p className="text-sm text-[var(--text-secondary,#64748b)] mt-1">
            Upload the official student reference file used to verify self-registrations.
          </p>
        </div>
      </div>

      {/* Info Banner */}
      <div className="flex items-start gap-4 bg-[var(--info-bg,#eff6ff)] border border-[var(--primary-border,#bfdbfe)] rounded-2xl py-5 px-6 mb-6">
        <div className="text-[var(--primary,#6366f1)] flex-shrink-0 mt-0.5">{Icons.Info}</div>
        <div className="text-sm leading-relaxed text-[var(--text-secondary,#64748b)]">
          <strong>How it works:</strong> When a student tries to self-register, the system checks their
          university ID and password against this reference database. Only students found here can create
          accounts. Supported formats:{' '}
          <code className="bg-[var(--bg-code,#f1f5f9)] px-1.5 py-0.5 rounded text-[13px] text-[var(--primary,#6366f1)] font-semibold">.xlsx</code>,{' '}
          <code className="bg-[var(--bg-code,#f1f5f9)] px-1.5 py-0.5 rounded text-[13px] text-[var(--primary,#6366f1)] font-semibold">.xls</code>,{' '}
          <code className="bg-[var(--bg-code,#f1f5f9)] px-1.5 py-0.5 rounded text-[13px] text-[var(--primary,#6366f1)] font-semibold">.csv</code>.
          Max size: {MAX_SIZE_MB} MB.
        </div>
      </div>

      {/* Form Card */}
      <div className="bg-[var(--card,#fff)] rounded-2xl shadow-md border border-[var(--border,#e2e8f0)] max-w-3xl">
        <div className="p-6">
          <form onSubmit={handleSubmit}>
            {error && (
              <div className="flex items-start gap-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3 mb-5" role="alert">
                <span className="flex-shrink-0 mt-0.5">{Icons.Alert}</span>
                <span>{error}</span>
              </div>
            )}

            {result && (
              <div className="flex items-start gap-3 bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm rounded-xl px-4 py-3 mb-5" role="status">
                <span className="flex-shrink-0 mt-0.5">{Icons.Check}</span>
                <div>
                  <strong>Upload successful.</strong>{' '}
                  {result.message || result.detail || 'Reference database has been updated.'}
                  {typeof result.count === 'number' && (
                    <span className="block mt-1 text-xs">Records processed: {result.count}</span>
                  )}
                </div>
              </div>
            )}

            {/* Drag & Drop zone */}
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileRef.current?.click()}
              className={`cursor-pointer border-2 border-dashed rounded-2xl py-10 px-6 text-center transition-colors mb-5 ${
                isDragOver
                  ? 'border-[var(--primary,#6366f1)] bg-[var(--primary-bg,#eef2ff)]'
                  : 'border-[var(--border,#cbd5e1)] hover:border-[var(--primary,#6366f1)] hover:bg-[var(--bg-hover,#f8fafc)]'
              }`}
            >
              <div className="flex justify-center mb-3 text-[var(--primary,#6366f1)]">
                {Icons.UploadAction}
              </div>
              {file ? (
                <div>
                  <p className="text-sm font-semibold text-[var(--text,#1e293b)]">{file.name}</p>
                  <p className="text-xs text-[var(--text-secondary,#64748b)] mt-1">
                    {(file.size / 1024).toFixed(1)} KB · Click to replace
                  </p>
                </div>
              ) : (
                <div>
                  <p className="text-sm font-semibold text-[var(--text,#1e293b)]">
                    Drag &amp; drop your reference file here
                  </p>
                  <p className="text-xs text-[var(--text-secondary,#64748b)] mt-1">
                    or click to browse · {ACCEPTED_EXTS.join(', ')}
                  </p>
                </div>
              )}
              <input
                ref={fileRef}
                type="file"
                accept={ACCEPTED_EXTS.join(',')}
                onChange={handleFileChange}
                className="hidden"
              />
            </div>

            {/* Submit */}
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => { setFile(null); setResult(null); setError(''); if (fileRef.current) fileRef.current.value = ''; }}
                disabled={!file || loading}
                className="px-5 py-2.5 rounded-xl text-sm font-semibold border border-[var(--border,#e2e8f0)] text-[var(--text-secondary,#64748b)] hover:bg-[var(--bg-hover,#f1f5f9)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Clear
              </button>
              <button
                type="submit"
                disabled={!file || loading}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-[var(--primary,#6366f1)] text-white hover:bg-[var(--primary-dark,#4f46e5)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none">
                      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25"/>
                      <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
                    </svg>
                    Uploading...
                  </>
                ) : (
                  <>
                    {Icons.FileUp}
                    Upload Reference
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}