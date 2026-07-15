import React, { useState, useEffect } from 'react';
import { changeUsername, fetchUsernameSuggestions } from '../api';

export default function ChangeUsername({ user, onSuccess }) {
  const [newUsername, setNewUsername] = useState('');
  const [suggestions, setSuggestions] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingSuggestions, setLoadingSuggestions] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoadingSuggestions(true);
    fetchUsernameSuggestions()
      .then((res) => {
        if (!cancelled) {
          setSuggestions(res.data.suggestions || []);
          if (res.data.suggestions?.length > 0) {
            setNewUsername(res.data.suggestions[0]);
          }
        }
      })
      .catch(() => {
        if (!cancelled) setSuggestions([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingSuggestions(false);
      });
    return () => { cancelled = true; };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!newUsername.trim()) {
      setError('Please enter a username.');
      return;
    }

    setLoading(true);
    try {
      await changeUsername(newUsername.trim());
      onSuccess(newUsername.trim());
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to change username.');
    } finally {
      setLoading(false);
    }
  };

  const isValid = /^[A-Za-z0-9_]{3,30}$/.test(newUsername);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 p-6">
      <div className="card bg-white dark:bg-gray-800 rounded-2xl shadow-md w-full max-w-[440px] overflow-hidden border border-gray-200 dark:border-gray-700">
        <div className="bg-gradient-to-r from-violet-600 to-indigo-600 text-white text-center py-10 px-8">
          <div className="w-14 h-14 mx-auto mb-4 flex items-center justify-center bg-white/15 rounded-full" aria-hidden="true">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
          <h1 className="text-[22px] font-extrabold m-0 mb-1.5 tracking-tight">اختر اسم المستخدم</h1>
          <p className="text-[13px] opacity-90 font-medium m-0">اختر اسم مستخدم يمكنك تذكره بسهولة</p>
        </div>

        <div className="card-body p-8">
          <div className="flex items-start gap-3 bg-sky-50 dark:bg-sky-900/20 border-l-4 border-l-violet-500 rounded-md p-4 text-[13px] text-sky-700 dark:text-sky-300 mb-6 leading-relaxed" role="note">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-violet-600 flex-shrink-0 mt-0.5" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="16" x2="12" y2="12" />
              <line x1="12" y1="8" x2="12.01" y2="8" />
            </svg>
            <span>
              Your current username is <strong className="font-bold">{user.username}</strong>.
              You can change it once to something easier to remember. Letters, numbers, and underscores only.
            </span>
          </div>

          {error && (
            <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 text-[13px] font-semibold mb-4" role="alert">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
              </svg>
              {error}
            </div>
          )}

          {!loadingSuggestions && suggestions.length > 0 && (
            <div className="mb-5">
              <p className="text-[13px] font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-2">اقتراحات</p>
              <div className="flex flex-wrap gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => { setNewUsername(s); setError(''); }}
                    className={`px-3.5 py-1.5 rounded-lg text-[13px] font-semibold border cursor-pointer transition-all duration-150 ${
                      newUsername === s
                        ? 'bg-violet-100 dark:bg-violet-900/40 border-violet-400 dark:border-violet-600 text-violet-700 dark:text-violet-300'
                        : 'bg-gray-50 dark:bg-gray-700 border-gray-200 dark:border-gray-600 text-gray-600 dark:text-gray-300 hover:border-violet-300 hover:text-violet-600 dark:hover:border-violet-500 dark:hover:text-violet-300'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="form-group mb-5">
              <label htmlFor="new_username" className="text-[13px] font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                New Username
              </label>
              <input
                id="new_username"
                className="form-control mt-1.5"
                type="text"
                placeholder="مثال: dr_ahmad أو الرقم الجامعي"
                value={newUsername}
                onChange={(e) => { setNewUsername(e.target.value); setError(''); }}
                required
                autoComplete="off"
                autoFocus
              />
            </div>

            <ul className="list-none m-0 mb-6 p-0 flex flex-col gap-2" aria-label="Username requirements">
              <li className={`text-[13px] font-medium pl-6 relative ${newUsername.length >= 3 ? 'text-emerald-600 before:content-["✓"] before:absolute before:left-0 before:text-emerald-600' : 'text-gray-500 dark:text-gray-400 before:content-["○"] before:absolute before:left-0 before:text-gray-400 dark:before:text-gray-500'}`}>
                At least 3 characters
              </li>
              <li className={`text-[13px] font-medium pl-6 relative ${isValid ? 'text-emerald-600 before:content-["✓"] before:absolute before:left-0 before:text-emerald-600' : 'text-gray-500 dark:text-gray-400 before:content-["○"] before:absolute before:left-0 before:text-gray-400 dark:before:text-gray-500'}`}>
                Only English letters, numbers, and underscores
              </li>
              <li className={`text-[13px] font-medium pl-6 relative ${newUsername.length <= 30 && newUsername.length > 0 ? 'text-emerald-600 before:content-["✓"] before:absolute before:left-0 before:text-emerald-600' : 'text-gray-500 dark:text-gray-400 before:content-["○"] before:absolute before:left-0 before:text-gray-400 dark:before:text-gray-500'}`}>
                Maximum 30 characters
              </li>
            </ul>

            <button
              className="btn btn-primary w-full py-3.5 text-[15px] shadow-[0_4px_12px_rgba(139,92,246,0.25)] disabled:opacity-60 disabled:cursor-not-allowed"
              type="submit"
              disabled={loading || !isValid}
            >
              {loading ? (
                <>
                  <span className="spinner"></span>
                  جاري الحفظ...
                </>
              ) : (
                'تعيين اسم المستخدم'
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}