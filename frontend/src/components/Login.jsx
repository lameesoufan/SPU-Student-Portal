import React, { useState, useEffect } from 'react';
import { login, setAccessToken, studentLoginRequest, studentLoginVerify } from '../api';
import campusBg from '../assets/campus-bg.png';
import { GraduationCap, Eye, EyeOff, ArrowRight, User, Lock, XCircle, LayoutGrid, Settings, GitBranch } from 'lucide-react';
import OTPVerification from './OTPVerification';

const PARTICLES = [
  { size: 120, bg: 'radial-gradient(circle, var(--primary-light), transparent 70%)', top: '10%', left: '5%', delay: '0s' },
  { size: 80, bg: 'radial-gradient(circle, rgba(99,102,241,0.12), transparent 70%)', top: '60%', right: '10%', delay: '2s' },
  { size: 160, bg: 'radial-gradient(circle, var(--primary-lighter), transparent 70%)', bottom: '15%', left: '20%', delay: '4s' },
  { size: 100, bg: 'radial-gradient(circle, rgba(34,211,238,0.08), transparent 70%)', top: '30%', right: '25%', delay: '6s' },
  { size: 60, bg: 'radial-gradient(circle, var(--accent-bg), transparent 70%)', bottom: '40%', left: '45%', delay: '8s' },
  { size: 140, bg: 'radial-gradient(circle, var(--primary-lighter), transparent 70%)', top: '5%', right: '5%', delay: '10s' },
];

export default function Login({ onLogin, onRegister, onForgotPassword }) {
  const [form, setForm] = useState({ username: '', password: '' });
  const [errors, setErrors] = useState({ username: '', password: '' });
  const [serverError, setServerError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [focusedField, setFocusedField] = useState(null);
  const [shaking, setShaking] = useState(false);
  
  // OTP state
  const [showOTP, setShowOTP] = useState(false);
  const [otpData, setOtpData] = useState(null);

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 100);
    return () => clearTimeout(t);
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setServerError('');
    setErrors({ username: '', password: '' });

    let hasError = false;
    const newErrors = { username: '', password: '' };
    if (!form.username.trim()) {
      newErrors.username = 'Please enter your university ID';
      hasError = true;
    }
    if (!form.password.trim()) {
      newErrors.password = 'Please enter your password';
      hasError = true;
    }
    if (hasError) {
      setErrors(newErrors);
      setShaking(true);
      setTimeout(() => setShaking(false), 400);
      return;
    }

    setLoading(true);
    try {
      // Check if username is numeric (student) or not (doctor/admin/hod)
      const isStudent = /^\d+$/.test(form.username.trim());
      
      if (isStudent) {
        // Student login - use OTP flow
        const res = await studentLoginRequest(form.username.trim(), form.password);
        const data = res.data;

        // First login still uses OTP. Later logins can return a direct JWT response.
        if (data.session_token) {
          setOtpData({
            sessionToken: data.session_token,
            emailHint: data.email_hint,
            expiresIn: data.expires_in_seconds,
            universityId: form.username.trim(),
          });
          setShowOTP(true);
          return;
        }

        if (data.access) {
          setAccessToken(data.access);
          onLogin({
            username: data.username || form.username.trim(),
            role: data.role,
            must_change_password: data.must_change_password,
            must_change_username: data.must_change_username ?? true,
            department: data.department,
          });
          return;
        }

        throw new Error('Unexpected student login response.');
      } else {
        // Doctor/Admin/HOD login - use regular login
        const res = await login(form.username.trim(), form.password);
        const data = res.data;

        // حفظ الـ access token بالإضافة للكوكيز
        if (data.access) {
          setAccessToken(data.access);
        }

        onLogin({
          username: data.username || form.username.trim(),
          role: data.role,
          must_change_password: data.must_change_password,
          must_change_username: data.must_change_username ?? true,
          department: data.department,
        });
      }
    } catch (err) {
      setServerError(err.response?.data?.error || err.response?.data?.detail || 'Invalid credentials. Please try again.');
      setShaking(true);
      setTimeout(() => setShaking(false), 400);
    } finally {
      setLoading(false);
    }
  };

  const handleOTPVerify = async (sessionToken, code) => {
    const res = await studentLoginVerify(sessionToken, code);
    const data = res.data;

    // حفظ الـ access token بالإضافة للكوكيز
    if (data.access) {
      setAccessToken(data.access);
    }

    onLogin({
      username: data.username || form.username.trim(),
      role: data.role,
      must_change_password: data.must_change_password,
      must_change_username: data.must_change_username ?? true,
      department: data.department,
    });
  };

  const handleOTPBack = () => {
    setShowOTP(false);
    setOtpData(null);
    setForm({ username: '', password: '' });
  };

  const handleOTPResend = async () => {
    const res = await studentLoginRequest(otpData.universityId, form.password);
    const data = res.data;
    
    // Update OTP data with new session token and expiry
    setOtpData({
      sessionToken: data.session_token,
      emailHint: data.email_hint,
      expiresIn: data.expires_in_seconds,
      universityId: otpData.universityId,
    });
  };

  const isDark = true;

  // Show OTP verification screen if needed
  if (showOTP && otpData) {
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

        <div data-theme="dark" className="group relative min-h-screen w-full flex items-center justify-center overflow-hidden bg-[var(--bg-primary)]">
          {/* University campus background image */}
          <div
            className="absolute inset-0 z-0 bg-cover bg-center bg-no-repeat scale-105 transition-transform duration-[8000ms] ease-linear group-hover:scale-[1.08]"
            style={{
              backgroundImage: `url(${campusBg})`,
              filter: isDark ? 'blur(1px) brightness(0.7)' : 'blur(1px) brightness(0.85)',
            }}
            aria-hidden="true"
          />

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

          {/* OTP Verification Component */}
          <div className="relative z-[2] flex items-center justify-center w-full max-w-[1080px] px-6 py-10">
            <OTPVerification
              emailHint={otpData.emailHint}
              sessionToken={otpData.sessionToken}
              expiresIn={otpData.expiresIn}
              onVerify={handleOTPVerify}
              onBack={handleOTPBack}
              onResend={handleOTPResend}
            />
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <style>{`
        @keyframes lp-float {
          0%, 100% { opacity: 0; transform: translateY(0) scale(0.8); }
          25% { opacity: 0.6; }
          50% { opacity: 0.4; transform: translateY(-40px) scale(1.1); }
          75% { opacity: 0.5; }
        }
        @keyframes lpShake {
          0%, 100% { transform: translateX(0); }
          20% { transform: translateX(-8px); }
          40% { transform: translateX(8px); }
          60% { transform: translateX(-6px); }
          80% { transform: translateX(6px); }
        }
      `}</style>

      <div data-theme="dark" className="group relative min-h-screen w-full flex items-center justify-center overflow-hidden bg-[var(--bg-primary)]">

        {/* University campus background image */}
        <div
          className="absolute inset-0 z-0 bg-cover bg-center bg-no-repeat scale-105 transition-transform duration-[8000ms] ease-linear group-hover:scale-[1.08]"
          style={{
            backgroundImage: `url(${campusBg})`,
            filter: isDark ? 'blur(1px) brightness(0.7)' : 'blur(1px) brightness(0.85)',
          }}
          aria-hidden="true"
        />

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
              <GraduationCap size={28} strokeWidth={2} className="shrink-0" />
              <span>SPU</span>
            </div>

            <div>
              <h1 className="text-[36px] font-extrabold text-[var(--text)] leading-[1.15] tracking-[-0.5px]">Syrian Private University</h1>
              <div className="w-12 h-[3px] bg-[var(--primary)] rounded-[2px] mt-4" />
              <p className="text-base text-[var(--text-muted)] leading-relaxed mt-2">
                Everything you need to manage<br />your graduation project — in one place.
              </p>
            </div>

            <div className="flex flex-col gap-5 mt-2">
              <div className="flex items-center gap-4">
                <div className="w-11 h-11 flex items-center justify-center rounded-xl bg-[var(--primary-light)] text-[var(--primary)] shrink-0">
                  <LayoutGrid size={20} />
                </div>
                <div className="flex flex-col gap-0.5">
                  <strong className="text-sm font-bold text-[var(--text)]">Kanban Boards</strong>
                  <span className="text-[13px] text-[var(--text-muted)]">Track tasks visually</span>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="w-11 h-11 flex items-center justify-center rounded-xl bg-[var(--primary-light)] text-[var(--primary)] shrink-0">
                  <Settings size={20} />
                </div>
                <div className="flex flex-col gap-0.5">
                  <strong className="text-sm font-bold text-[var(--text)]">Workflow Automation</strong>
                  <span className="text-[13px] text-[var(--text-muted)]">Streamline your process</span>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <div className="w-11 h-11 flex items-center justify-center rounded-xl bg-[var(--primary-light)] text-[var(--primary)] shrink-0">
                  <GitBranch size={20} />
                </div>
                <div className="flex flex-col gap-0.5">
                  <strong className="text-sm font-bold text-[var(--text)]">GitLab Integration</strong>
                  <span className="text-[13px] text-[var(--text-muted)]">Code & commit tracking</span>
                </div>
              </div>
            </div>
          </div>

          {/* Right login card (Glassmorphism) */}
          <div
            className={`relative w-full max-w-[420px] transition-all duration-700 ease-[cubic-bezier(0.4,0,0.2,1)] max-[900px]:max-w-full ${mounted ? 'opacity-100 translate-x-0 scale-100' : 'opacity-0 translate-x-[30px] scale-[0.96]'} ${shaking ? '[animation:lpShake_0.4s_ease-in-out]' : ''}`}
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
                  <GraduationCap size={32} strokeWidth={2} />
                </div>
                <span className="text-lg font-extrabold text-[var(--text)]">SPU Portal</span>
              </div>

              <div>
                <h2 className="text-[26px] font-extrabold text-[var(--text)] tracking-[-0.5px] mb-1.5 max-[480px]:text-[22px]">Welcome back</h2>
                <p className="text-sm text-[var(--text-muted)]">Sign in to your academic portal</p>
              </div>

              <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
                {serverError && (
                  <div className="flex items-center gap-2.5 px-4 py-3 rounded-[var(--radius)] bg-[var(--danger-bg)] border border-[var(--danger-border)] text-[var(--danger)] text-[13px] font-semibold" role="alert">
                    <XCircle size={16} />
                    {serverError}
                  </div>
                )}

                <div className="flex flex-col gap-2">
                  <label
                    htmlFor="username"
                    className={`text-[13px] font-bold uppercase tracking-[0.5px] transition-colors duration-200 ${focusedField === 'username' ? 'text-[var(--primary)]' : 'text-[var(--text-muted)]'}`}
                  >Username</label>
                  <div className="relative flex items-center">
                    <User size={18} className={`absolute left-3.5 pointer-events-none transition-colors duration-200 ${focusedField === 'username' ? 'text-[var(--primary)]' : 'text-[var(--text-faint)]'}`} />
                    <input
                      id="username"
                      type="text"
                      placeholder=" "
                      value={form.username}
                      onChange={(e) => { setForm({ ...form, username: e.target.value }); setErrors({ ...errors, username: '' }); }}
                      onFocus={() => setFocusedField('username')}
                      onBlur={() => setFocusedField(null)}
                      required
                      autoComplete="username"
                      className={`w-full py-3.5 pl-11 pr-3.5 border-[1.5px] rounded-[var(--radius)] text-[15px] font-medium text-[var(--text)] bg-[var(--bg-input)] outline-none transition-all duration-200 placeholder:text-[var(--text-faint)] ${
                        errors.username
                          ? 'border-[#ef4444] shadow-[0_0_0_3px_rgba(239,68,68,0.1)]'
                          : focusedField === 'username'
                            ? 'border-[var(--primary)] bg-[var(--bg-input-focus)] shadow-[0_0_0_3px_var(--primary-light)]'
                            : form.username
                              ? 'border-[var(--primary-border)]'
                              : 'border-[var(--border)]'
                      }`}
                    />
                  </div>
                  {errors.username && <span className="block text-[#ef4444] text-xs mt-1 px-1">{errors.username}</span>}
                </div>

                <div className="flex flex-col gap-2">
                  <label
                    htmlFor="password"
                    className={`text-[13px] font-bold uppercase tracking-[0.5px] transition-colors duration-200 ${focusedField === 'password' ? 'text-[var(--primary)]' : 'text-[var(--text-muted)]'}`}
                  >Password</label>
                  <div className="relative flex items-center">
                    <Lock size={18} className={`absolute left-3.5 pointer-events-none transition-colors duration-200 ${focusedField === 'password' ? 'text-[var(--primary)]' : 'text-[var(--text-faint)]'}`} />
                    <input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      placeholder=" "
                      value={form.password}
                      onChange={(e) => { setForm({ ...form, password: e.target.value }); setErrors({ ...errors, password: '' }); }}
                      onFocus={() => setFocusedField('password')}
                      onBlur={() => setFocusedField(null)}
                      required
                      autoComplete="current-password"
                      className={`w-full py-3.5 pl-11 pr-10 border-[1.5px] rounded-[var(--radius)] text-[15px] font-medium text-[var(--text)] bg-[var(--bg-input)] outline-none transition-all duration-200 placeholder:text-[var(--text-faint)] ${
                        errors.password
                          ? 'border-[#ef4444] shadow-[0_0_0_3px_rgba(239,68,68,0.1)]'
                          : focusedField === 'password'
                            ? 'border-[var(--primary)] bg-[var(--bg-input-focus)] shadow-[0_0_0_3px_var(--primary-light)]'
                            : form.password
                              ? 'border-[var(--primary-border)]'
                              : 'border-[var(--border)]'
                      }`}
                    />
                    <button
                      type="button"
                      className="absolute right-3 top-1/2 -translate-y-1/2 bg-transparent border-none text-[var(--text-muted)] cursor-pointer p-1 flex items-center justify-center transition-colors duration-200 z-[2] hover:text-[var(--text-secondary)]"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      tabIndex={-1}
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                  {errors.password && <span className="block text-[#ef4444] text-xs mt-1 px-1">{errors.password}</span>}
                  {onForgotPassword && <button type="button" onClick={onForgotPassword} className="mt-1 self-start bg-transparent border-none p-0 text-sm font-bold text-[var(--primary)] hover:underline">هل نسيت كلمة المرور؟</button>}
                </div>

                <button
                  className="group/btn flex items-center justify-center gap-2.5 w-full py-3.5 px-5 border-none rounded-[var(--radius)] bg-[var(--primary)] text-white text-[15px] font-bold cursor-pointer transition-all duration-200 relative hover:bg-[var(--primary-hover)] hover:shadow-[0_6px_20px_var(--primary-shadow)] hover:-translate-y-[1px] active:translate-y-0 disabled:opacity-60 disabled:cursor-not-allowed"
                  type="submit"
                  disabled={loading}
                >
                  <span className="inline-flex items-center">
                    {loading ? 'Signing in...' : 'Sign In'}
                  </span>
                  {loading && (
                    <span className="w-[18px] h-[18px] border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  )}
                  {!loading && <ArrowRight size={18} className="shrink-0 transition-transform duration-200 group-hover/btn:translate-x-[3px]" />}
                </button>
              </form>

              {onRegister && (
                <div className="flex items-center justify-center gap-2 text-sm text-[var(--text-muted)] font-medium flex-wrap">
                  <span>New to the portal?</span>
                  <button type="button" onClick={onRegister} className="inline-flex items-center gap-1.5 text-[var(--primary)] font-bold bg-transparent border-none cursor-pointer text-sm p-0 transition-all duration-200 hover:underline hover:gap-2">
                    Create your account
                    <ArrowRight size={14} />
                  </button>
                </div>
              )}

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