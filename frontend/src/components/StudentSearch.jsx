import React, { useState, useEffect, useRef } from 'react';
import { searchStudents } from '../api';
import { Search, Loader2, User } from 'lucide-react';

export default function StudentSearch({ value, onChange, placeholder = 'Search by name or ID…', id }) {
  const [query, setQuery]       = useState(value || '');
  const [results, setResults]   = useState([]);
  const [open, setOpen]         = useState(false);
  const [loading, setLoading]   = useState(false);
  const [localError, setLocalError] = useState('');
  const [searchError, setSearchError] = useState('');
  const debounce                = useRef(null);
  const requestSeq              = useRef(0);
  const wrapRef                 = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => {
      document.removeEventListener('mousedown', handler);
      clearTimeout(debounce.current);
      requestSeq.current += 1;
    };
  }, []);

  useEffect(() => {
    if (!value) setQuery('');
  }, [value]);

  const handleInput = (e) => {
    const q = e.target.value;
    setQuery(q);
    setLocalError('');
    setSearchError('');
    onChange('');

    clearTimeout(debounce.current);
    if (!q.trim()) {
      requestSeq.current += 1;
      setLoading(false);
      setResults([]);
      setOpen(false);
      return;
    }

    debounce.current = setTimeout(async () => {
      const seq = requestSeq.current + 1;
      requestSeq.current = seq;
      setLoading(true);
      try {
        const res = await searchStudents(q);
        if (seq === requestSeq.current) {
          setResults(res.data);
          setOpen(true);
        }
      } catch {
        if (seq === requestSeq.current) {
          setResults([]);
          setSearchError('تعذر البحث عن الطلاب. حاول مرة أخرى.');
          setOpen(true);
        }
      } finally {
        if (seq === requestSeq.current) setLoading(false);
      }
    }, 300);
  };

  const handleSelect = (student) => {
    if (student.available === false || student.has_registered_project) {
      setQuery(student.display);
      setLocalError(
        student.unavailable_reason
          || `الطالب ${student.name || student.username} لديه مشروع مسجل بالفعل ولا يمكن إضافته إلى الفريق.`
      );
      onChange('');
      setOpen(false);
      setResults([]);
      return;
    }

    setLocalError('');
    setQuery(student.display);
    onChange(student.username);
    setOpen(false);
    setResults([]);
  };

  return (
    <div className="relative" ref={wrapRef}>
      {/* Search icon */}
      <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-faint)] pointer-events-none" />

      <input
        id={id}
        type="text"
        className={`w-full pl-10 pr-10 bg-[var(--input-bg)] text-[var(--text)] border rounded-[var(--radius-sm)] px-4 py-2.5 text-sm outline-none focus:ring-1 focus:ring-[var(--primary)] transition-colors placeholder:text-[var(--text-faint)] ${
          value
            ? 'border-[var(--primary)] bg-[var(--primary)]/5'
            : 'border-[var(--border)] focus:border-[var(--primary)]'
        }`}
        value={query}
        onChange={handleInput}
        placeholder={placeholder}
        autoComplete="off"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={open ? `${id || 'student-search'}-results` : undefined}
      />

      {/* Loading spinner */}
      {loading && (
        <Loader2 size={16} className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[var(--primary)] animate-spin pointer-events-none" />
      )}

      {/* Dropdown results */}
      {open && results.length > 0 && (
        <ul
          className="absolute top-[calc(100%+4px)] left-0 right-0 bg-[var(--card)] border border-[var(--border)] rounded-xl shadow-[var(--shadow)] list-none m-0 py-1 z-[200] max-h-[220px] overflow-y-auto"
          role="listbox"
          id={`${id || 'student-search'}-results`}
        >
          {results.map((s) => (
            <li
              key={s.username}
              className={`flex items-center justify-between gap-3 px-3.5 py-2.5 transition-colors ${
                s.available === false || s.has_registered_project
                  ? 'cursor-not-allowed bg-red-500/5 opacity-80'
                  : 'cursor-pointer hover:bg-[var(--bg-tertiary)]'
              }`}
              role="option"
              aria-disabled={s.available === false || s.has_registered_project}
              aria-selected={value === s.username}
              onMouseDown={() => handleSelect(s)}
            >
              <div className="flex items-center gap-2.5 flex-1 min-w-0">
                <div className="w-7 h-7 rounded-full bg-[var(--primary)]/10 flex items-center justify-center text-[var(--primary)] shrink-0">
                  <User size={13} />
                </div>
                <span className="text-sm font-semibold text-[var(--primary)] truncate">{s.name || s.username}</span>
              </div>
              {s.available === false || s.has_registered_project ? (
                <span className="text-xs font-semibold text-red-600 bg-red-500/10 px-2 py-0.5 rounded-full whitespace-nowrap shrink-0">
                  لديه مشروع
                </span>
              ) : (
                <span className="text-xs text-[var(--primary)] bg-[var(--primary)]/10 px-2 py-0.5 rounded-full whitespace-nowrap shrink-0">{s.username}</span>
              )}
            </li>
          ))}
        </ul>
      )}

      {/* Search failure / no results */}
      {open && searchError && !loading && (
        <div className="absolute top-[calc(100%+4px)] left-0 right-0 bg-[var(--card)] border border-red-200 dark:border-red-900 rounded-[var(--radius-sm)] px-4 py-3 text-sm font-semibold text-red-600 dark:text-red-400 z-[200]" role="alert">
          {searchError}
        </div>
      )}
      {open && !searchError && results.length === 0 && !loading && query.trim() && (
        <div className="absolute top-[calc(100%+4px)] left-0 right-0 bg-[var(--card)] border border-[var(--border)] rounded-[var(--radius-sm)] px-4 py-3 text-sm text-[var(--text-muted)] z-[200]">
          No students found
        </div>
      )}

      {localError && (
        <div className="mt-1.5 text-xs font-semibold text-red-600 dark:text-red-400" role="alert">
          {localError}
        </div>
      )}
    </div>
  );
}