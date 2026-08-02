import React, { useEffect, useState } from 'react';
import { AtSign, CheckCircle2, KeyRound, MailCheck, ShieldCheck } from 'lucide-react';
import { confirmEmailChange, requestEmailChange } from '../api';

export default function ChangeEmail({ user, onBack, onChanged }) {
  const [step, setStep] = useState('request');
  const [newEmail, setNewEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [token, setToken] = useState('');
  const [emailHint, setEmailHint] = useState('');
  const [seconds, setSeconds] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    if (seconds <= 0) return undefined;
    const timer = setInterval(() => setSeconds((value) => Math.max(0, value - 1)), 1000);
    return () => clearInterval(timer);
  }, [seconds]);

  const sendCode = async (event) => {
    event.preventDefault();
    setError(''); setSuccess(''); setLoading(true);
    try {
      const response = await requestEmailChange(newEmail.trim(), password);
      setToken(response.data.session_token);
      setEmailHint(response.data.email_hint || newEmail.trim());
      setSeconds(response.data.expires_in_seconds || 600);
      setStep('verify');
      setSuccess(response.data.message || 'تم إرسال رمز التحقق.');
    } catch (err) {
      setError(err.response?.data?.error || 'تعذر إرسال رمز التحقق.');
    } finally { setLoading(false); }
  };

  const verifyCode = async (event) => {
    event.preventDefault();
    setError(''); setLoading(true);
    try {
      const response = await confirmEmailChange(token, code.trim());
      setStep('done');
      setSuccess(response.data.message || 'تم تغيير البريد الإلكتروني بنجاح.');
      if (onChanged) onChanged(response.data.email);
    } catch (err) {
      setError(err.response?.data?.error || 'تعذر تأكيد البريد الإلكتروني.');
    } finally { setLoading(false); }
  };

  const inputClass = 'w-full rounded-xl border border-slate-200 bg-white px-4 py-3.5 outline-none transition focus:border-violet-500 focus:ring-4 focus:ring-violet-100 dark:border-slate-700 dark:bg-slate-900';
  const time = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;

  return (
    <div dir="rtl" className="p-4 md:p-8">
      <div className="mx-auto w-full max-w-2xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl dark:border-slate-800 dark:bg-slate-900">
        <div className="bg-gradient-to-l from-violet-700 to-indigo-600 p-8 text-white">
          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/15"><AtSign size={28} /></div>
          <h1 className="text-2xl font-extrabold">تغيير البريد الإلكتروني</h1>
          <p className="mt-2 text-sm text-white/85">سيتم إرسال رمز تحقق إلى البريد الجديد قبل اعتماده.</p>
        </div>

        <div className="p-7 md:p-9">
          <div className="mb-6 rounded-2xl bg-slate-50 p-4 dark:bg-slate-800/60">
            <span className="block text-xs font-bold text-slate-500">البريد المرتبط حاليًا</span>
            <span className="mt-1 block break-all font-bold">{user?.email || 'لا يوجد بريد إلكتروني مرتبط'}</span>
          </div>
          {error && <div className="mb-5 rounded-xl bg-red-50 p-4 text-sm font-medium text-red-700 dark:bg-red-950/30 dark:text-red-300">{error}</div>}
          {success && <div className="mb-5 rounded-xl bg-emerald-50 p-4 text-sm font-medium text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-300">{success}</div>}

          {step === 'request' && <form onSubmit={sendCode} className="space-y-5">
            <div><label className="mb-2 block text-sm font-bold">البريد الإلكتروني الجديد</label><input className={inputClass} type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} placeholder="name@example.com" required autoComplete="email" /></div>
            <div><label className="mb-2 block text-sm font-bold">كلمة المرور الحالية</label><div className="relative"><KeyRound className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400" size={18}/><input className={`${inputClass} pr-11`} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" /></div></div>
            <div className="flex gap-3 rounded-xl bg-violet-50 p-4 text-sm leading-6 text-violet-900 dark:bg-violet-950/30 dark:text-violet-200"><ShieldCheck className="mt-0.5 shrink-0" size={20}/><span>لن يتغير البريد حتى تُدخل الرمز الذي يصل إلى البريد الجديد.</span></div>
            <div className="flex flex-col-reverse gap-3 sm:flex-row"><button type="submit" disabled={loading} className="flex-1 rounded-xl bg-violet-600 px-5 py-3.5 font-bold text-white hover:bg-violet-700 disabled:opacity-60">{loading ? 'جاري الإرسال...' : 'إرسال رمز التحقق'}</button>{onBack && <button type="button" onClick={onBack} className="rounded-xl border border-slate-200 px-5 py-3.5 font-bold dark:border-slate-700">إلغاء</button>}</div>
          </form>}

          {step === 'verify' && <form onSubmit={verifyCode} className="space-y-5">
            <div className="text-center"><div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-violet-100 text-violet-700 dark:bg-violet-950/40 dark:text-violet-300"><MailCheck size={27}/></div><h2 className="text-xl font-extrabold">أدخل رمز التحقق</h2><p className="mt-2 text-sm text-slate-500">أرسلنا رمزًا من 6 أرقام إلى <strong>{emailHint}</strong></p></div>
            <input className={`${inputClass} text-center text-2xl font-extrabold tracking-[0.45em]`} inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} placeholder="000000" required autoFocus />
            <div className="text-center text-sm text-slate-500">صلاحية الرمز: <strong className="text-violet-700 dark:text-violet-300">{time}</strong></div>
            <button type="submit" disabled={loading || code.length !== 6} className="w-full rounded-xl bg-violet-600 px-5 py-3.5 font-bold text-white hover:bg-violet-700 disabled:opacity-60">{loading ? 'جاري التحقق...' : 'تأكيد البريد الجديد'}</button>
            <button type="button" onClick={() => { setStep('request'); setCode(''); setError(''); setSuccess(''); }} className="w-full rounded-xl border border-slate-200 px-5 py-3.5 font-bold dark:border-slate-700">تغيير البريد أو إعادة الإرسال</button>
          </form>}

          {step === 'done' && <div className="py-5 text-center"><CheckCircle2 className="mx-auto text-emerald-500" size={64}/><h2 className="mt-4 text-2xl font-extrabold">تم تحديث البريد الإلكتروني</h2><p className="mt-2 text-slate-500">أصبح البريد الجديد مرتبطًا بحسابك ويُستخدم لاستعادة كلمة المرور.</p>{onBack && <button type="button" onClick={onBack} className="mt-7 rounded-xl bg-violet-600 px-8 py-3.5 font-bold text-white hover:bg-violet-700">العودة</button>}</div>}
        </div>
      </div>
    </div>
  );
}
