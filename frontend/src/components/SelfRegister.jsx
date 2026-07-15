import React, { useState, useEffect } from 'react';
import { studentSelfRegister } from '../api';
import { useTheme } from '../ThemeContext';

const PARTICLES = [
  { size: 120, bg: 'radial-gradient(circle, var(--primary-light), transparent 70%)', top: '10%', left: '5%', delay: '0s' },
  { size: 80, bg: 'radial-gradient(circle, rgba(99,102,241,0.12), transparent 70%)', top: '60%', right: '10%', delay: '2s' },
  { size: 160, bg: 'radial-gradient(circle, var(--primary-lighter), transparent 70%)', bottom: '15%', left: '20%', delay: '4s' },
  { size: 100, bg: 'radial-gradient(circle, rgba(34,211,238,0.08), transparent 70%)', top: '30%', right: '25%', delay: '6s' },
  { size: 60, bg: 'radial-gradient(circle, var(--accent-bg), transparent 70%)', bottom: '40%', left: '45%', delay: '8s' },
  { size: 140, bg: 'radial-gradient(circle, var(--primary-lighter), transparent 70%)', top: '5%', right: '5%', delay: '10s' },
];

export default function SelfRegister({ onRegistered, onBack }) {
  const { theme } = useTheme();
  const [form, setForm] = useState({ university_id: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [mounted, setMounted] = useState(false);
  const [focusedField, setFocusedField] = useState(null);

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 100);
    return () => clearTimeout(t);
  }, []);

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await studentSelfRegister(form.university_id, form.password);
// JWT tokens are set as HttpOnly cookies by the backend automatically
      const data = res.data;
onRegistered({
    username: data.username || form.university_id,
    role: data.role || 'student',
    must_change_password: data.must_change_password ?? true,
    must_change_username: data.must_change_username ?? true,
    department: data.department || '',
});
    } catch (err) {
      setError(err.response?.data?.error || 'Verification failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const isDark = theme === 'dark';

  return (
    <>
      <style>{`
        @keyframes lp-float {
          0%, 100% { opacity: 0; transform: translateY(0) scale(0.8); }
          25% { opacity: 0.6; }
          50% { opacity: 0.4; transform: translateY(-40px) scale(1.1); }
          75% { opacity: 0.5; }
        }
      `}</style>

      <div className="relative min-h-screen w-full flex items-center justify-center overflow-hidden bg-[var(--bg-primary)]">
        {/* Animated background particles */}
        <div className="absolute inset-0 z-0 overflow-hidden pointer-events-none" aria-hidden="true">
          {PARTICLES.map((p, i) => (
            <div
              key={i}
              className="absolute rounded-full opacity-0"
              style={{
                width: p.size,
                height: p.size,
                background: p.bg,
                ...(p.top ? { top: p.top } : {}),
                ...(p.bottom ? { bottom: p.bottom } : {}),
                ...(p.left ? { left: p.left } : {}),
                ...(p.right ? { right: p.right } : {}),
                animation: 'lp-float 12s infinite ease-in-out',
                animationDelay: p.delay,
              }}
            />
          ))}
        </div>

        {/* Gradient overlay */}
        <div
          className="absolute inset-0 z-[1] pointer-events-none"
          style={{
            background: isDark
              ? 'linear-gradient(135deg, rgba(15,17,23,0.55) 0%, rgba(30,32,48,0.45) 50%, rgba(15,17,23,0.60) 100%)'
              : 'linear-gradient(135deg, rgba(248,249,253,0.70) 0%, rgba(241,243,249,0.60) 50%, rgba(248,249,253,0.72) 100%)'
          }}
        />

        {/* Content */}
        <div className="relative z-[2] flex items-center justify-center gap-16 w-full max-w-[1080px] px-6 py-10 max-[900px]:flex-col max-[900px]:gap-8 max-[900px]:max-w-[460px]">
          {/* Left branding panel */}
          <div className={`flex-1 max-w-[440px] flex flex-col gap-8 transition-all duration-700 ease-[cubic-bezier(0.4,0,0.2,1)] ${mounted ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-[30px]'} max-[900px]:hidden`}>
            <div className="inline-flex items-center gap-2.5 px-[18px] py-2.5 bg-[var(--primary-light)] border border-[var(--primary-border)] rounded-[var(--radius)] w-fit text-[var(--primary)] font-extrabold text-sm tracking-widest">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
                <path d="M22 10v6M2 10l10-5 10 5-10 5z" /><path d="M6 12v5c0 2 6 3 6 3s6-1 6-3v-5" />
              </svg>
              <span>SPU</span>
            </div>

            <div>
              <h1 className="text-[36px] font-extrabold text-[var(--text)] leading-[1.15] tracking-[-0.5px]">انضم للبوابة</h1>
              <div className="w-12 h-[3px] bg-[var(--primary)] rounded-[2px] mt-4" />
              <p className="text-base text-[var(--text-muted)] leading-relaxed mt-2">
                تحقق من بيانات دخولك الجامعية<br />واحصل على وصول فوري للمنصة.
              </p>
            </div>

            <div className="flex flex-col gap-5 mt-2">
              <div className="flex items-center gap-4">
                <div className="w-11 h-11 flex items-center justify-center rounded-xl shrink-0" style={{ background: 'linear-gradient(135deg, rgba(34,211,238,0.2), rgba(59,130,246,0.2))' }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#67e8f9' }}>
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  </svg>
                </div>
                <div className="flex flex-col gap-0.5">
                  <strong className="text-sm font-bold text-[var(--text)]">تحقق آمن</strong>
                  <span className="text-[13px] text-[var(--text-muted)]">University ID + Password</span>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="w-11 h-11 flex items-center justify-center rounded-xl shrink-0" style={{ background: 'linear-gradient(135deg, rgba(52,211,153,0.2), rgba(16,185,129,0.2))' }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: '#6ee7b7' }}>
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                </div>
                <div className="flex flex-col gap-0.5">
                  <strong className="text-sm font-bold text-[var(--text)]">وصول فوري</strong>
                  <span className="text-[13px] text-[var(--text-muted)]">بدون وقت انتظار للموافقة</span>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="w-11 h-11 flex items-center justify-center rounded-xl bg-[var(--primary-light)] text-[var(--primary)] shrink-0">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" />
                  </svg>
                </div>
                <div className="flex flex-col gap-0.5">
                  <strong className="text-sm font-bold text-[var(--text)]">جاهز للبدء</strong>
                  <span className="text-[13px] text-[var(--text-muted)]">Browse ideas & build projects</span>
                </div>
              </div>
            </div>
          </div>

          {/* Right card */}
          <div
            className={`relative w-full max-w-[420px] transition-all duration-700 ease-[cubic-bezier(0.4,0,0.2,1)] max-[900px]:max-w-full ${mounted ? 'opacity-100 translate-x-0 scale-100' : 'opacity-0 translate-x-[30px] scale-[0.96]'}`}
            style={{ transitionDelay: mounted ? '0.15s' : '0s' }}
          >
            <div
              className="absolute -top-px -left-px -right-px -bottom-px -z-[1] opacity-40"
              style={{
                borderRadius: 'calc(var(--radius-xl) + 2px)',
                background: 'linear-gradient(135deg, var(--primary-border), transparent 50%, var(--primary-border))'
              }}
              aria-hidden="true"
            />

            <div
              className="bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-xl)] px-9 py-10 backdrop-blur-[20px] flex flex-col gap-7 max-[480px]:px-5 max-[480px]:py-7"
              style={{ boxShadow: 'var(--shadow-lg), 0 0 80px rgba(162,118,190,0.04)' }}
            >
              {/* Mobile-only branding */}
              <div className="hidden max-[900px]:flex items-center gap-3 mb-1">
                <div className="w-11 h-11 flex items-center justify-center bg-[var(--primary-light)] rounded-[var(--radius)] text-[var(--primary)]">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M22 10v6M2 10l10-5 10 5-10 5z" /><path d="M6 12v5c0 2 6 3 6 3s6-1 6-3v-5" />
                  </svg>
                </div>
                <span className="text-lg font-extrabold text-[var(--text)]">بوابة SPU</span>
              </div>

              <div>
                <h2 className="text-[26px] font-extrabold text-[var(--text)] tracking-[-0.5px] mb-1.5 max-[480px]:text-[22px]">تحقق من الطالب</h2>
                <p className="text-sm text-[var(--text-muted)]">تحقق من هويتك لإنشاء حسابك</p>
              </div>

              {/* Info glass - previously sr-info-glass */}
              <div className="flex items-start gap-2.5 p-3 rounded-[var(--radius)] border backdrop-blur-sm text-sm" style={{
                background: 'var(--primary-lighter)',
                borderColor: 'var(--primary-border)',
                color: 'var(--primary)'
              }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 mt-0.5">
                  <circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" />
                </svg>
                <span>أدخل الرقم الجامعي وكلمة المرور للتحقق من أهليتك. سيتم منح الوصول تلقائياً.</span>
              </div>

              <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
                {error && (
                  <div className="flex items-center gap-2.5 px-4 py-3 rounded-[var(--radius)] bg-[var(--danger-bg)] border border-[var(--danger-border)] text-[var(--danger)] text-[13px] font-semibold" role="alert">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
                    </svg>
                    {error}
                  </div>
                )}

                <div className="flex flex-col gap-2">
                  <label
                    htmlFor="university_id"
                    className={`text-[13px] font-bold uppercase tracking-[0.5px] transition-colors duration-200 ${focusedField === 'university_id' ? 'text-[var(--primary)]' : 'text-[var(--text-muted)]'}`}
                  >الرقم الجامعي</label>
                  <div className="relative flex items-center">
                    <svg className={`absolute left-3.5 pointer-events-none transition-colors duration-200 ${focusedField === 'university_id' ? 'text-[var(--primary)]' : 'text-[var(--text-faint)]'}`} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="2" y="5" width="20" height="14" rx="2" /><line x1="2" y1="10" x2="22" y2="10" />
                    </svg>
                    <input
                      id="university_id"
                      type="text"
                      placeholder=" "
                      value={form.university_id}
                      onChange={set('university_id')}
                      onFocus={() => setFocusedField('university_id')}
                      onBlur={() => setFocusedField(null)}
                      required
                      autoComplete="off"
                      className={`w-full py-3.5 pl-11 pr-3.5 border-[1.5px] rounded-[var(--radius)] text-[15px] font-medium text-[var(--text)] bg-[var(--bg-input)] outline-none transition-all duration-200 placeholder:text-[var(--text-faint)] ${
                        focusedField === 'university_id'
                          ? 'border-[var(--primary)] bg-[var(--bg-input-focus)] shadow-[0_0_0_3px_var(--primary-light)]'
                          : form.university_id
                            ? 'border-[var(--primary-border)]'
                            : 'border-[var(--border)]'
                      }`}
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-2">
                  <label
                    htmlFor="sr_password"
                    className={`text-[13px] font-bold uppercase tracking-[0.5px] transition-colors duration-200 ${focusedField === 'password' ? 'text-[var(--primary)]' : 'text-[var(--text-muted)]'}`}
                  >كلمة المرور</label>
                  <div className="relative flex items-center">
                    <svg className={`absolute left-3.5 pointer-events-none transition-colors duration-200 ${focusedField === 'password' ? 'text-[var(--primary)]' : 'text-[var(--text-faint)]'}`} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
                    </svg>
                    <input
                      id="sr_password"
                      type="password"
                      placeholder=" "
                      value={form.password}
                      onChange={set('password')}
                      onFocus={() => setFocusedField('password')}
                      onBlur={() => setFocusedField(null)}
                      required
                      autoComplete="current-password"
                      className={`w-full py-3.5 pl-11 pr-3.5 border-[1.5px] rounded-[var(--radius)] text-[15px] font-medium text-[var(--text)] bg-[var(--bg-input)] outline-none transition-all duration-200 placeholder:text-[var(--text-faint)] ${
                        focusedField === 'password'
                          ? 'border-[var(--primary)] bg-[var(--bg-input-focus)] shadow-[0_0_0_3px_var(--primary-light)]'
                          : form.password
                            ? 'border-[var(--primary-border)]'
                            : 'border-[var(--border)]'
                      }`}
                    />
                  </div>
                </div>

                <button
                  className="group/btn flex items-center justify-center gap-2.5 w-full py-3.5 px-5 border-none rounded-[var(--radius)] bg-[var(--primary)] text-white text-[15px] font-bold cursor-pointer transition-all duration-200 relative hover:bg-[var(--primary-hover)] hover:shadow-[0_6px_20px_var(--primary-shadow)] hover:-translate-y-[1px] active:translate-y-0 disabled:opacity-60 disabled:cursor-not-allowed"
                  type="submit"
                  disabled={loading}
                >
                  <span className="inline-flex items-center">
                    {loading ? 'جاري التحقق...' : 'تحقق وادخل للبوابة'}
                  </span>
                  {loading && (
                    <span className="w-[18px] h-[18px] border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  )}
                  {!loading && (
                    <svg className="shrink-0 transition-transform duration-200 group-hover/btn:translate-x-[3px]" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="5" y1="12" x2="19" y2="12" /><polyline points="12 5 19 12 12 19" />
                    </svg>
                  )}
                </button>

                {/* Back button - previously sr-back-btn */}
                <button
                  type="button"
                  className="flex items-center justify-center gap-2 w-full py-2.5 border border-[var(--border)] rounded-[var(--radius)] bg-transparent text-[var(--text-muted)] text-sm font-medium cursor-pointer transition-all duration-200 hover:bg-[var(--bg-quaternary)]"
                  onClick={onBack}
                >
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
                  </svg>
                  العودة لتسجيل الدخول
                </button>
              </form>

              <footer className="text-xs text-[var(--text-faint)] text-center pt-2">
                &copy; {new Date().getFullYear()} Syrian Private University &middot; Faculty of AI Engineering
              </footer>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}