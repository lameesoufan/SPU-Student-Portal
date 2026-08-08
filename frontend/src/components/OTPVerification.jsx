import React, { useState, useEffect, useRef } from 'react';
import { Shield, ArrowLeft, RefreshCw, Clock, XCircle, CheckCircle } from 'lucide-react';

export default function OTPVerification({ 
  emailHint, 
  sessionToken, 
  expiresIn, 
  onVerify, 
  onBack, 
  onResend 
}) {
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [timeLeft, setTimeLeft] = useState(expiresIn || 600); // 10 minutes default
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [attemptsRemaining, setAttemptsRemaining] = useState(null);
  const inputRefs = useRef([]);
  const refocusOtpAfterVerify = useRef(false);

  // Restore focus only after verification loading has finished.
  // Focusing while `loading` is true does not work because the OTP inputs are disabled.
  useEffect(() => {
    if (!loading && refocusOtpAfterVerify.current) {
      refocusOtpAfterVerify.current = false;
      inputRefs.current[0]?.focus();
    }
  }, [loading]);

  // Countdown timer
  useEffect(() => {
    if (timeLeft <= 0) return;
    const timer = setInterval(() => {
      setTimeLeft((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [timeLeft]);

  // Format time as MM:SS
  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  // Handle OTP input change
  const handleChange = (index, value) => {
    // Only allow digits
    if (value && !/^\d$/.test(value)) return;

    const newOtp = [...otp];
    newOtp[index] = value;
    setOtp(newOtp);
    setError('');

    // Auto-focus next input
    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }

    // Auto-submit when all 6 digits are entered
    if (newOtp.every(digit => digit !== '') && !newOtp.includes('')) {
      handleSubmit(newOtp.join(''));
    }
  };

  // Handle backspace
  const handleKeyDown = (index, e) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  // Handle paste
  const handlePaste = (e) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (pastedData.length === 6) {
      const newOtp = pastedData.split('');
      setOtp(newOtp);
      inputRefs.current[5]?.focus();
      handleSubmit(pastedData);
    }
  };

  // Submit OTP
  const handleSubmit = async (code = null) => {
    const otpCode = code || otp.join('');
    if (otpCode.length !== 6) {
      setError('Please enter all 6 digits');
      return;
    }

    if (timeLeft <= 0) {
      setError('OTP has expired. Please request a new one.');
      return;
    }

    setLoading(true);
    setError('');
    
    try {
      await onVerify(sessionToken, otpCode);
      setSuccess(true);
    } catch (err) {
      const errorData = err.response?.data;
      setError(errorData?.error || 'Invalid OTP code. Please try again.');
      if (errorData?.attempts_remaining !== undefined) {
        setAttemptsRemaining(errorData.attempts_remaining);
      }
      // Clear OTP on error and refocus after the disabled/loading state is removed.
      setOtp(['', '', '', '', '', '']);
      refocusOtpAfterVerify.current = true;
    } finally {
      setLoading(false);
    }
  };

  // Resend OTP
  const handleResend = async () => {
    setResending(true);
    setError('');
    try {
      await onResend();
      setTimeLeft(600); // Reset timer to 10 minutes
      setOtp(['', '', '', '', '', '']);
      setAttemptsRemaining(null);
      inputRefs.current[0]?.focus();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to resend OTP. Please try again.');
    } finally {
      setResending(false);
    }
  };

  const isExpired = timeLeft <= 0;
  const isWarning = timeLeft <= 120 && timeLeft > 0; // Last 2 minutes

  return (
    <div className="w-full max-w-[420px] max-[900px]:max-w-full">
      <style>{`
        @keyframes pulse-border {
          0%, 100% { box-shadow: 0 0 0 0 rgba(139, 92, 246, 0.4); }
          50% { box-shadow: 0 0 0 4px rgba(139, 92, 246, 0.1); }
        }
        .otp-input:focus {
          animation: pulse-border 1.5s ease-in-out infinite;
        }
      `}</style>

      <div
        className="relative"
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
          {/* Header */}
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={onBack}
                className="w-10 h-10 flex items-center justify-center rounded-[var(--radius)] bg-[var(--bg-secondary)] text-[var(--text-muted)] transition-all duration-200 hover:bg-[var(--bg-tertiary)] hover:text-[var(--text)]"
                aria-label="Go back"
              >
                <ArrowLeft size={18} />
              </button>
              <div className="w-12 h-12 flex items-center justify-center bg-[var(--primary-light)] rounded-[var(--radius-lg)] text-[var(--primary)]">
                <Shield size={28} strokeWidth={2} />
              </div>
            </div>
            <div>
              <h2 className="text-[26px] font-extrabold text-[var(--text)] tracking-[-0.5px] mb-1.5 max-[480px]:text-[22px]">
                Enter Verification Code
              </h2>
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">
                We sent a 6-digit code to<br />
                <span className="font-bold text-[var(--text-secondary)]">{emailHint}</span>
              </p>
            </div>
          </div>

          {/* Timer */}
          <div className={`flex items-center gap-2.5 px-4 py-3 rounded-[var(--radius)] border transition-all duration-300 ${
            isExpired 
              ? 'bg-[var(--danger-bg)] border-[var(--danger-border)] text-[var(--danger)]' 
              : isWarning 
                ? 'bg-[var(--warning-bg)] border-[var(--warning-border)] text-[var(--warning)]'
                : 'bg-[var(--info-bg)] border-[var(--info-border)] text-[var(--info)]'
          }`}>
            <Clock size={16} />
            <span className="text-[13px] font-bold">
              {isExpired ? 'Code expired' : `Expires in ${formatTime(timeLeft)}`}
            </span>
          </div>

          {/* Error/Success Messages */}
          {error && (
            <div className="flex items-center gap-2.5 px-4 py-3 rounded-[var(--radius)] bg-[var(--danger-bg)] border border-[var(--danger-border)] text-[var(--danger)] text-[13px] font-semibold" role="alert">
              <XCircle size={16} />
              <div className="flex flex-col gap-1">
                <span>{error}</span>
                {attemptsRemaining !== null && attemptsRemaining > 0 && (
                  <span className="text-xs opacity-80">{attemptsRemaining} attempt{attemptsRemaining !== 1 ? 's' : ''} remaining</span>
                )}
              </div>
            </div>
          )}

          {success && (
            <div className="flex items-center gap-2.5 px-4 py-3 rounded-[var(--radius)] bg-[var(--success-bg)] border border-[var(--success-border)] text-[var(--success)] text-[13px] font-semibold" role="alert">
              <CheckCircle size={16} />
              Verification successful! Logging in...
            </div>
          )}

          {/* OTP Input */}
          <div className="flex flex-col gap-3">
            <label className="text-[13px] font-bold uppercase tracking-[0.5px] text-[var(--text-muted)]">
              Verification Code
            </label>
            <div className="flex gap-2.5 justify-center" dir="ltr">
              {otp.map((digit, index) => (
                <input
                  key={index}
                  ref={(el) => (inputRefs.current[index] = el)}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleChange(index, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(index, e)}
                  onPaste={index === 0 ? handlePaste : undefined}
                  disabled={loading || success || isExpired}
                  className="otp-input w-12 h-14 text-center text-2xl font-bold border-2 rounded-[var(--radius)] bg-[var(--bg-input)] text-[var(--text)] outline-none transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed focus:border-[var(--primary)] focus:bg-[var(--bg-input-focus)]"
                  style={{
                    borderColor: digit ? 'var(--primary-border)' : 'var(--border)',
                  }}
                  autoFocus={index === 0}
                />
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-col gap-3">
            <button
              onClick={() => handleSubmit()}
              disabled={loading || success || isExpired || otp.some(d => !d)}
              className="flex items-center justify-center gap-2.5 w-full py-3.5 px-5 border-none rounded-[var(--radius)] bg-[var(--primary)] text-white text-[15px] font-bold cursor-pointer transition-all duration-200 hover:bg-[var(--primary-hover)] hover:shadow-[0_6px_20px_var(--primary-shadow)] hover:-translate-y-[1px] active:translate-y-0 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none"
            >
              {loading ? (
                <>
                  <span>Verifying...</span>
                  <span className="w-[18px] h-[18px] border-2 border-white/30 border-t-white rounded-full animate-spin" />
                </>
              ) : (
                'Verify Code'
              )}
            </button>

            <button
              onClick={handleResend}
              disabled={resending || loading || success || !isExpired && timeLeft > 540}
              className="flex items-center justify-center gap-2 w-full py-3 px-5 border border-[var(--border)] rounded-[var(--radius)] bg-[var(--bg-secondary)] text-[var(--text-secondary)] text-[14px] font-bold cursor-pointer transition-all duration-200 hover:bg-[var(--bg-tertiary)] hover:border-[var(--primary-border)] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {resending ? (
                <>
                  <span>Resending...</span>
                  <span className="w-4 h-4 border-2 border-[var(--text-faint)] border-t-[var(--text)] rounded-full animate-spin" />
                </>
              ) : (
                <>
                  <RefreshCw size={16} />
                  Resend Code
                </>
              )}
            </button>
          </div>

          <footer className="text-xs text-[var(--text-faint)] text-center pt-2">
            Didn't receive the code? Check your spam folder or resend.
          </footer>
        </div>
      </div>
    </div>
  );
}
