import React, { useState } from 'react';
import { changePassword } from '../api';

export default function ChangePassword({ user, onSuccess }) {
  const [form, setForm] = useState({ new_password: '', confirm_password: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (form.new_password !== form.confirm_password) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    try {
      await changePassword(form.new_password, form.confirm_password);
      onSuccess();
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to change password.');
    } finally {
      setLoading(false);
    }
  };

  const set = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  const hintOk = 'text-emerald-600 before:content-["✓"] before:absolute before:left-0 before:text-emerald-600';
  const hintFail = 'text-red-500 before:content-["✗"] before:absolute before:left-0 before:text-red-500';
  const hintDefault = 'text-gray-500 dark:text-gray-400 before:content-["○"] before:absolute before:left-0 before:text-gray-400 dark:before:text-gray-500';

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 p-6">
      <div className="card bg-white dark:bg-gray-800 rounded-2xl shadow-md w-full max-w-[440px] overflow-hidden border border-gray-200 dark:border-gray-700">
        <div className="bg-gradient-to-r from-violet-600 to-indigo-600 text-white text-center py-10 px-8">
          <div className="w-14 h-14 mx-auto mb-4 flex items-center justify-center bg-white/15 rounded-full" aria-hidden="true">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </div>
          <h1 className="text-[22px] font-extrabold m-0 mb-1.5 tracking-tight">Change Your Password</h1>
          <p className="text-[13px] opacity-90 font-medium m-0">You must set a new password before continuing</p>
        </div>

        <div className="card-body p-8">
          <div className="flex items-start gap-3 bg-sky-50 dark:bg-sky-900/20 border-l-4 border-l-violet-500 rounded-md p-4 text-[13px] text-sky-700 dark:text-sky-300 mb-6 leading-relaxed" role="note">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-violet-600 flex-shrink-0 mt-0.5" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="16" x2="12" y2="12" />
              <line x1="12" y1="8" x2="12.01" y2="8" />
            </svg>
            <span>
              Your current password is your university ID (<strong className="font-bold">{user.username}</strong>).
              Please choose a new secure password.
            </span>
          </div>

          {error && <div className="alert alert-error" role="alert">{error}</div>}

          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label htmlFor="new_password">New Password</label>
              <input
                id="new_password"
                className="form-control"
                type="password"
                placeholder="At least 8 characters"
                value={form.new_password}
                onChange={set('new_password')}
                required
                autoComplete="new-password"
              />
            </div>

            <div className="form-group">
              <label htmlFor="confirm_password">Confirm Password</label>
              <input
                id="confirm_password"
                className="form-control"
                type="password"
                placeholder="Repeat your new password"
                value={form.confirm_password}
                onChange={set('confirm_password')}
                required
                autoComplete="new-password"
              />
            </div>

            {/* Password strength hints */}
            <ul className="list-none m-0 mb-6 p-0 flex flex-col gap-2" aria-label="Password requirements">
              <li className={`text-[13px] font-medium pl-6 relative ${form.new_password.length >= 8 ? hintOk : hintDefault}`}>
                At least 8 characters
              </li>
              <li className={`text-[13px] font-medium pl-6 relative ${/[a-zA-Z]/.test(form.new_password) ? hintOk : hintDefault}`}>
                Contains letters
              </li>
              <li className={`text-[13px] font-medium pl-6 relative ${form.new_password !== user.username || !form.new_password ? hintOk : hintFail}`}>
                Not the same as your university ID
              </li>
            </ul>

            <button className="btn btn-primary w-full py-3.5 text-[15px] shadow-[0_4px_12px_rgba(139,92,246,0.25)]" type="submit" disabled={loading}>
              {loading ? (
                <>
                  <span className="spinner"></span>
                  Saving…
                </>
              ) : (
                'Set New Password'
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}