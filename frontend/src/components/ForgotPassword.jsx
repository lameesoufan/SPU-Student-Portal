import React, { useEffect, useState } from 'react';
import {
  ArrowRight,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  LockKeyhole,
  MailCheck,
  ShieldCheck,
  UserRound,
} from 'lucide-react';
import {
  requestPasswordReset,
  verifyPasswordResetCode,
  confirmPasswordReset,
} from '../api';

const STEPS = [
  { id: 1, label: 'الحساب' },
  { id: 2, label: 'التحقق' },
  { id: 3, label: 'كلمة المرور' },
];

export default function ForgotPassword({ onBack }) {
  const [step, setStep] = useState(1);
  const [identifier, setIdentifier] = useState('');
  const [sessionToken, setSessionToken] = useState('');
  const [emailHint, setEmailHint] = useState('');
  const [code, setCode] = useState('');
  const [form, setForm] = useState({ newPassword: '', confirmPassword: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [resendSeconds, setResendSeconds] = useState(0);

  useEffect(() => {
    if (resendSeconds <= 0) return undefined;
    const timer = window.setInterval(() => {
      setResendSeconds((value) => Math.max(0, value - 1));
    }, 1000);
    return () => window.clearInterval(timer);
  }, [resendSeconds]);

  const sendCode = async (event) => {
    event?.preventDefault();
    if (!identifier.trim()) return;

    setError('');
    setMessage('');
    setLoading(true);
    try {
      const { data } = await requestPasswordReset(identifier.trim());
      setMessage(data.message || 'تم إرسال رمز التحقق إلى البريد الإلكتروني المرتبط بالحساب.');

      if (data.session_token) {
        setSessionToken(data.session_token);
        setEmailHint(data.email_hint || 'البريد الإلكتروني المرتبط بالحساب');
        setStep(2);
        setResendSeconds(60);
      }
    } catch (err) {
      setError(err.response?.data?.error || 'تعذر إرسال رمز التحقق. تحقق من إعدادات البريد ثم حاول مجددًا.');
    } finally {
      setLoading(false);
    }
  };

  const verifyCode = async (event) => {
    event.preventDefault();
    setError('');
    setLoading(true);
    try {
      await verifyPasswordResetCode(sessionToken, code);
      setStep(3);
      setMessage('');
    } catch (err) {
      setError(err.response?.data?.error || 'رمز التحقق غير صحيح.');
    } finally {
      setLoading(false);
    }
  };

  const resetPassword = async (event) => {
    event.preventDefault();
    setError('');

    if (form.newPassword !== form.confirmPassword) {
      setError('كلمتا المرور غير متطابقتين.');
      return;
    }

    setLoading(true);
    try {
      const { data } = await confirmPasswordReset(
        sessionToken,
        code,
        form.newPassword,
        form.confirmPassword,
      );
      setMessage(data.message || 'تم تغيير كلمة المرور بنجاح.');
      setStep(4);
    } catch (err) {
      setError(err.response?.data?.error || 'تعذر تغيير كلمة المرور.');
    } finally {
      setLoading(false);
    }
  };

  const resendCode = () => {
    if (!loading && resendSeconds === 0) sendCode();
  };

  const inputClass =
    'w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-violet-500 focus:ring-4 focus:ring-violet-100';

  const buttonClass =
    'w-full rounded-xl bg-violet-600 px-4 py-3 font-bold text-white shadow-sm transition hover:bg-violet-700 focus:outline-none focus:ring-4 focus:ring-violet-200 disabled:cursor-not-allowed disabled:opacity-60';

  return (
    <div dir="rtl" className="min-h-screen bg-slate-100 px-4 py-8 sm:px-6">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-[460px] items-center justify-center">
        <div className="w-full overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl shadow-slate-200/70">
          <div className="bg-gradient-to-l from-violet-700 to-indigo-600 px-6 py-7 text-center text-white sm:px-8">
            <div className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/15 ring-1 ring-white/20">
              {step === 4 ? <CheckCircle2 size={30} /> : <KeyRound size={29} />}
            </div>
            <h1 className="text-2xl font-extrabold">استعادة كلمة المرور</h1>
            <p className="mt-2 text-sm leading-6 text-violet-100">
              سيتم إرسال رمز التحقق تلقائيًا إلى البريد الإلكتروني المسجل في حسابك.
            </p>
          </div>

          {step !== 4 && (
            <div className="border-b border-slate-100 px-6 py-4 sm:px-8">
              <div className="flex items-center justify-between gap-2">
                {STEPS.map((item, index) => (
                  <React.Fragment key={item.id}>
                    <div className="flex min-w-0 flex-col items-center gap-1.5">
                      <div
                        className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-extrabold transition ${
                          step >= item.id
                            ? 'bg-violet-600 text-white'
                            : 'bg-slate-100 text-slate-400'
                        }`}
                      >
                        {step > item.id ? <CheckCircle2 size={17} /> : item.id}
                      </div>
                      <span className={`text-[11px] font-bold ${step >= item.id ? 'text-violet-700' : 'text-slate-400'}`}>
                        {item.label}
                      </span>
                    </div>
                    {index < STEPS.length - 1 && (
                      <div className={`mb-5 h-0.5 flex-1 ${step > item.id ? 'bg-violet-500' : 'bg-slate-200'}`} />
                    )}
                  </React.Fragment>
                ))}
              </div>
            </div>
          )}

          <div className="px-6 py-6 sm:px-8">
            {error && (
              <div className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold leading-6 text-red-700">
                {error}
              </div>
            )}

            {message && step !== 4 && (
              <div className="mb-5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold leading-6 text-emerald-700">
                {message}
              </div>
            )}

            {step === 1 && (
              <form onSubmit={sendCode} className="space-y-5">
                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-800">اسم المستخدم</label>
                  <div className="relative">
                    <UserRound className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400" size={19} />
                    <input
                      className={`${inputClass} pr-11`}
                      value={identifier}
                      onChange={(event) => setIdentifier(event.target.value)}
                      placeholder="أدخل اسم المستخدم الخاص بك"
                      autoComplete="username"
                      required
                      autoFocus
                    />
                  </div>
                  <p className="mt-2 flex items-start gap-2 text-xs leading-5 text-slate-500">
                    <MailCheck className="mt-0.5 shrink-0 text-violet-500" size={15} />
                    لا تحتاج إلى كتابة البريد الإلكتروني؛ سيأخذ النظام البريد المرتبط باسم المستخدم من قاعدة البيانات.
                  </p>
                </div>
                <button className={buttonClass} disabled={loading || !identifier.trim()}>
                  {loading ? 'جاري إرسال الرمز...' : 'إرسال رمز التحقق'}
                </button>
              </form>
            )}

            {step === 2 && (
              <form onSubmit={verifyCode} className="space-y-5">
                <div className="rounded-xl border border-violet-100 bg-violet-50 px-4 py-3 text-sm leading-6 text-violet-800">
                  أرسلنا رمزًا من 6 أرقام إلى: <span dir="ltr" className="font-extrabold">{emailHint}</span>
                </div>
                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-800">رمز التحقق</label>
                  <input
                    className={`${inputClass} text-center text-2xl font-extrabold tracking-[0.45em]`}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    value={code}
                    onChange={(event) => setCode(event.target.value.replace(/\D/g, ''))}
                    placeholder="000000"
                    required
                    autoFocus
                  />
                </div>
                <button className={buttonClass} disabled={loading || code.length !== 6}>
                  {loading ? 'جاري التحقق...' : 'التحقق من الرمز'}
                </button>
                <button
                  type="button"
                  onClick={resendCode}
                  disabled={loading || resendSeconds > 0}
                  className="w-full rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold text-violet-700 transition hover:bg-violet-50 disabled:cursor-not-allowed disabled:text-slate-400"
                >
                  {resendSeconds > 0 ? `إعادة الإرسال بعد ${resendSeconds} ثانية` : 'إعادة إرسال الرمز'}
                </button>
              </form>
            )}

            {step === 3 && (
              <form onSubmit={resetPassword} className="space-y-5">
                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-800">كلمة المرور الجديدة</label>
                  <div className="relative">
                    <LockKeyhole className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                    <input
                      className={`${inputClass} pr-11 pl-11`}
                      type={showPassword ? 'text' : 'password'}
                      value={form.newPassword}
                      onChange={(event) => setForm({ ...form, newPassword: event.target.value })}
                      minLength={8}
                      autoComplete="new-password"
                      required
                    />
                    <button
                      type="button"
                      className="absolute left-3 top-1/2 -translate-y-1/2 rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                      onClick={() => setShowPassword((value) => !value)}
                      aria-label={showPassword ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور'}
                    >
                      {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="mb-2 block text-sm font-bold text-slate-800">تأكيد كلمة المرور</label>
                  <input
                    className={inputClass}
                    type={showPassword ? 'text' : 'password'}
                    value={form.confirmPassword}
                    onChange={(event) => setForm({ ...form, confirmPassword: event.target.value })}
                    minLength={8}
                    autoComplete="new-password"
                    required
                  />
                </div>

                <div className="flex items-start gap-3 rounded-xl border border-emerald-100 bg-emerald-50 p-4 text-xs leading-6 text-emerald-800">
                  <ShieldCheck className="mt-0.5 shrink-0" size={20} />
                  <span>استخدم 8 أحرف على الأقل، وتجنب اسم المستخدم وكلمات المرور الشائعة.</span>
                </div>

                <button className={buttonClass} disabled={loading}>
                  {loading ? 'جاري حفظ كلمة المرور...' : 'تغيير كلمة المرور'}
                </button>
              </form>
            )}

            {step === 4 && (
              <div className="text-center">
                <div className="mb-5 rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-800">
                  <CheckCircle2 className="mx-auto mb-3" size={40} />
                  <h2 className="text-lg font-extrabold">تم تغيير كلمة المرور</h2>
                  <p className="mt-2 text-sm leading-6">{message}</p>
                </div>
                <button className={buttonClass} onClick={onBack}>العودة إلى تسجيل الدخول</button>
              </div>
            )}

            {step !== 4 && (
              <button
                type="button"
                onClick={onBack}
                className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm font-bold text-slate-500 transition hover:bg-slate-50 hover:text-slate-800"
              >
                <ArrowRight size={17} />
                العودة إلى تسجيل الدخول
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
