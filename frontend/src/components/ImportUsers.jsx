import React, { useState, useRef } from 'react';
import { importUsers } from '../api';

/* Premium SVG Icons */
const Icons = {
  FileUp: <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><polyline points="9 15 12 12 15 15"/></svg>,
  UploadAction: <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>,
  Student: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/></svg>,
  Doctor: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>,
  Info: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>,
  ArrowLeft: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
};

export default function ImportUsers({ onBack }) {
  const [role, setRole] = useState('student');
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [isDragOver, setIsDragOver] = useState(false);
  const fileRef = useRef();

  const handleDragOver = (e) => { e.preventDefault(); setIsDragOver(true); };
  const handleDragLeave = () => setIsDragOver(false);
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files?.length > 0) setFile(e.dataTransfer.files[0]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) { setError('يرجى اختيار ملف Excel.'); return; }
    setError(''); setResult(null); setLoading(true);
    try {
      const res = await importUsers(file, role);
      setResult(res.data);
      setFile(null);
      fileRef.current.value = '';
    } catch (err) {
      setError(err.response?.data?.error || 'فشل الاستيراد. حاول مرة أخرى.');
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-[var(--bg,#f8fafc)] p-6 md:p-10">
      {onBack && (
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-sm font-semibold mb-6 px-4 py-2 rounded-xl border border-[var(--border,#e2e8f0)] bg-[var(--card,#fff)] hover:bg-[var(--bg-hover,#f1f5f9)] transition-colors"
        >
          {Icons.ArrowLeft} العودة للوحة التحكم
        </button>
      )}

      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[var(--text,#1e293b)]">استيراد المستخدمين</h1>
        <p className="text-sm text-[var(--text-secondary,#64748b)] mt-1">إنشاء جماعي للطلاب أو الدكاترة باستخدام ملف Excel.</p>
      </div>

      {/* Info Banner */}
      <div className="flex items-start gap-4 bg-[var(--info-bg,#eff6ff)] border border-[var(--primary-border,#bfdbfe)] rounded-2xl py-5 px-6 mb-6">
        <div className="text-[var(--primary,#6366f1)] flex-shrink-0 mt-0.5">{Icons.Info}</div>
        <div className="text-sm leading-relaxed text-[var(--text-secondary,#64748b)]">
          <strong>Important Instructions:</strong> The Excel file must contain exactly three columns:{' '}
          <code className="bg-[var(--bg-code,#f1f5f9)] px-1.5 py-0.5 rounded text-[13px] text-[var(--primary,#6366f1)] font-semibold">full_name</code>,{' '}
          <code className="bg-[var(--bg-code,#f1f5f9)] px-1.5 py-0.5 rounded text-[13px] text-[var(--primary,#6366f1)] font-semibold">identifier</code>, and{' '}
          <code className="bg-[var(--bg-code,#f1f5f9)] px-1.5 py-0.5 rounded text-[13px] text-[var(--primary,#6366f1)] font-semibold">email</code>.
          Imported users must change their temporary password after first login.
        </div>
      </div>

      {/* Form Card */}
      <div className="bg-[var(--card,#fff)] rounded-2xl shadow-md border border-[var(--border,#e2e8f0)] max-w-3xl">
        <div className="p-6">
          <form onSubmit={handleSubmit}>
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3 mb-5" role="alert">{error}</div>
            )}
            {result && (
              <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm rounded-xl px-4 py-3 mb-5" role="status">{result.message}</div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-[1fr_2fr] gap-8 mb-6">
              {/* Role Select */}
              <div className="flex flex-col gap-2">
                <label htmlFor="role-select" className="text-[13px] font-semibold text-[var(--text-secondary,#475569)]">الدور المستهدف</label>
                <select
                  id="role-select"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="h-11 px-4 text-sm border-[1.5px] border-[var(--border,#e2e8f0)] rounded-xl bg-[var(--input-bg,#fff)] text-[var(--text,#1e293b)] outline-none focus:border-[var(--primary,#6366f1)] transition-colors"
                >
                  <option value="student">دفعة الطلاب</option>
                  <option value="doctor">دفعة الهيئة التدريسية / الدكاترة</option>
                </select>
              </div>

              {/* File Drop Zone */}
              <div className="flex flex-col gap-2">
                <label className="text-[13px] font-semibold text-[var(--text-secondary,#475569)]">Upload Spreadsheet (.xlsx, .xls)</label>
                <div
                  onClick={() => fileRef.current.click()}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  className={`flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-xl py-8 px-6 cursor-pointer text-center transition-all duration-200
                    ${isDragOver ? 'border-[var(--primary,#6366f1)] bg-[var(--primary-lighter,#eef2ff)]' :
                      file ? 'border-emerald-400 bg-emerald-50' :
                      'border-[var(--border-dark,#cbd5e1)] bg-[var(--bg-tertiary,#f8fafc)] hover:border-[var(--primary,#6366f1)] hover:bg-[var(--primary-lighter,#eef2ff)]'}`}
                >
                  <div className={`transition-colors ${file ? 'text-emerald-600' : 'text-[var(--text-muted,#94a3b8)]'}`}>
                    {file ? Icons.FileUp : Icons.UploadAction}
                  </div>
                  <div className="flex flex-col gap-1">
                    <span className="text-sm font-bold text-[var(--text,#1e293b)]">{file ? file.name : 'اضغط للرفع أو اسحب وأفلت'}</span>
                    <span className="text-[13px] text-[var(--text-muted,#94a3b8)]">Excel files only (Max 10MB)</span>
                  </div>
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".xlsx,.xls"
                    style={{ display: 'none' }}
                    onChange={(e) => setFile(e.target.files[0] || null)}
                    onClick={(e) => e.stopPropagation()}
                  />
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full h-12 rounded-xl bg-[var(--primary,#6366f1)] text-white font-semibold text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {loading ? 'Processing Import…' : 'بدء عملية الاستيراد'}
            </button>
          </form>
        </div>
      </div>

      {/* Results Table */}
      {result?.users?.length > 0 && (
        <div className="bg-[var(--card,#fff)] rounded-2xl shadow-md border border-[var(--border,#e2e8f0)] mt-6 overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border,#e2e8f0)]">
            <h3 className="text-base font-bold text-[var(--text,#1e293b)]">
              Successfully Imported: {result.users.length} {role === 'student' ? 'طلاب' : 'دكاترة'}
            </h3>
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${role === 'student' ? 'bg-indigo-50 text-indigo-600' : 'bg-emerald-50 text-emerald-600'}`}>
              {role === 'student' ? Icons.Student : Icons.Doctor}
              {role === 'student' ? ' Student' : ' Faculty'}
            </span>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-[var(--bg-tertiary,#f8fafc)]">
                  <th className="px-5 py-3.5 text-left text-xs font-bold uppercase tracking-wide text-[var(--text-muted,#94a3b8)] border-b border-[var(--border,#e2e8f0)]">ت.</th>
                  <th className="px-5 py-3.5 text-left text-xs font-bold uppercase tracking-wide text-[var(--text-muted,#94a3b8)] border-b border-[var(--border,#e2e8f0)]">اسم المستخدم في النظام</th>
                  <th className="px-5 py-3.5 text-left text-xs font-bold uppercase tracking-wide text-[var(--text-muted,#94a3b8)] border-b border-[var(--border,#e2e8f0)]">نوع الحساب</th>
                  <th className="px-5 py-3.5 text-left text-xs font-bold uppercase tracking-wide text-[var(--text-muted,#94a3b8)] border-b border-[var(--border,#e2e8f0)]">نطاق الوصول</th>
                </tr>
              </thead>
              <tbody>
                {result.users.map((u, i) => (
                  <tr key={u.username} className="hover:bg-[var(--bg-hover,#f1f5f9)] transition-colors">
                    <td className="px-5 py-3.5 text-sm font-medium text-[var(--text,#1e293b)] border-b border-[var(--border-light,#f1f5f9)]">{i + 1}</td>
                    <td className="px-5 py-3.5 text-sm font-bold text-[var(--text,#1e293b)] border-b border-[var(--border-light,#f1f5f9)]">{u.username}</td>
                    <td className="px-5 py-3.5 border-b border-[var(--border-light,#f1f5f9)]">
                      <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${role === 'student' ? 'bg-indigo-50 text-indigo-600' : 'bg-emerald-50 text-emerald-600'}`}>
                        {role === 'student' ? Icons.Student : Icons.Doctor}
                        {role === 'student' ? ' Student' : ' Faculty'}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-sm text-[var(--text-muted,#94a3b8)] border-b border-[var(--border-light,#f1f5f9)]">
                      {role === 'student' ? 'وصول قياسي' : 'وصول هيئة تدريسية'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Footer Note */}
          <div className="flex items-start gap-3 px-6 py-4 bg-[var(--bg-tertiary,#f8fafc)] border-t border-[var(--border,#e2e8f0)]">
            <div className="text-[var(--primary,#6366f1)] flex-shrink-0 mt-0.5">{Icons.Info}</div>
            <p className="text-sm text-[var(--text-muted,#94a3b8)] m-0">
              Users have been added to the system database. Share credentials through a secure channel and force a password change on first login.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}