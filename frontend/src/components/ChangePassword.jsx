import React, { useState } from 'react';
import { changePassword } from '../api';
import { Eye, EyeOff, KeyRound, ShieldCheck } from 'lucide-react';

export default function ChangePassword({ user, onSuccess, onBack }) {
  const forced = Boolean(user?.must_change_password);
  const [form, setForm] = useState({ current_password: '', new_password: '', confirm_password: '' });
  const [show, setShow] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault(); setError(''); setSuccess('');
    if (form.new_password !== form.confirm_password) { setError('كلمتا المرور غير متطابقتين.'); return; }
    setLoading(true);
    try {
      await changePassword(form.new_password, form.confirm_password, form.current_password);
      setSuccess('تم تغيير كلمة المرور بنجاح.');
      setForm({ current_password: '', new_password: '', confirm_password: '' });
      if (onSuccess) setTimeout(onSuccess, 700);
    } catch (err) { setError(err.response?.data?.error || 'تعذر تغيير كلمة المرور.'); }
    finally { setLoading(false); }
  };

  const input = 'w-full rounded-xl border border-slate-200 bg-white px-4 py-3.5 outline-none focus:border-violet-500 focus:ring-4 focus:ring-violet-100 dark:border-slate-700 dark:bg-slate-900';
  return <div dir="rtl" className={forced ? 'min-h-screen flex items-center justify-center bg-slate-50 p-6 dark:bg-slate-950' : 'p-4 md:p-8'}>
    <div className="mx-auto w-full max-w-2xl overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-xl dark:border-slate-800 dark:bg-slate-900">
      <div className="bg-gradient-to-l from-violet-700 to-indigo-600 p-8 text-white"><div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-white/15"><KeyRound size={28}/></div><h1 className="text-2xl font-extrabold">تغيير كلمة المرور</h1><p className="mt-2 text-sm text-white/85">استخدم كلمة مرور قوية لا تستعملها في حساب آخر.</p></div>
      <form onSubmit={submit} className="space-y-5 p-7 md:p-9">
        {error && <div className="rounded-xl bg-red-50 p-4 text-sm text-red-700">{error}</div>}
        {success && <div className="rounded-xl bg-emerald-50 p-4 text-sm text-emerald-700">{success}</div>}
        {!forced && <div><label className="mb-2 block text-sm font-bold">كلمة المرور الحالية</label><input className={input} type={show?'text':'password'} value={form.current_password} onChange={e=>setForm({...form,current_password:e.target.value})} required autoComplete="current-password"/></div>}
        <div><label className="mb-2 block text-sm font-bold">كلمة المرور الجديدة</label><div className="relative"><input className={`${input} pl-12`} type={show?'text':'password'} value={form.new_password} onChange={e=>setForm({...form,new_password:e.target.value})} minLength={8} required autoComplete="new-password"/><button type="button" className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" onClick={()=>setShow(v=>!v)}>{show?<EyeOff size={19}/>:<Eye size={19}/>}</button></div></div>
        <div><label className="mb-2 block text-sm font-bold">تأكيد كلمة المرور الجديدة</label><input className={input} type={show?'text':'password'} value={form.confirm_password} onChange={e=>setForm({...form,confirm_password:e.target.value})} minLength={8} required autoComplete="new-password"/></div>
        <div className="flex gap-3 rounded-xl bg-violet-50 p-4 text-sm leading-6 text-violet-900 dark:bg-violet-950/30 dark:text-violet-200"><ShieldCheck className="mt-0.5 shrink-0" size={20}/><span>8 أحرف على الأقل، تحتوي على أحرف، ولا تكون مطابقة لاسم المستخدم.</span></div>
        <div className="flex flex-col-reverse gap-3 sm:flex-row"><button type="submit" disabled={loading} className="flex-1 rounded-xl bg-violet-600 px-5 py-3.5 font-bold text-white hover:bg-violet-700 disabled:opacity-60">{loading?'جاري الحفظ...':'حفظ كلمة المرور الجديدة'}</button>{onBack && !forced && <button type="button" onClick={onBack} className="rounded-xl border border-slate-200 px-5 py-3.5 font-bold dark:border-slate-700">إلغاء</button>}</div>
      </form>
    </div>
  </div>;
}
