import { Check } from 'lucide-react';

export default function DynamicCheckboxGroup({ field, value, onChange }) {
  const options = field.options || [];
  const selected = Array.isArray(value) ? value : (value || '').split(',').filter(Boolean);
  const selectedSet = new Set(selected);

  const toggle = (option) => {
    const next = selectedSet.has(option)
      ? selected.filter((v) => v !== option)
      : [...selected, option];
    onChange(next);
  };

  const selectAll = () => onChange([...options]);
  const clearAll = () => onChange([]);

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <span className="text-xs font-bold text-[var(--text-secondary)] bg-[var(--bg-tertiary)] rounded-full px-2.5 py-1">
          {selected.length} of {options.length} selected
        </span>
        {options.length > 1 && (
          <div className="flex gap-2">
            <button type="button" className="px-2.5 py-1 text-xs font-bold rounded-full border border-[var(--primary)]/30 bg-[var(--primary)]/10 text-[var(--primary)] cursor-pointer transition-colors hover:bg-[var(--card)] hover:border-[var(--primary)] disabled:opacity-45 disabled:cursor-not-allowed" onClick={selectAll} disabled={selected.length === options.length}>Select all</button>
            <button type="button" className="px-2.5 py-1 text-xs font-bold rounded-full border border-[var(--primary)]/30 bg-[var(--primary)]/10 text-[var(--primary)] cursor-pointer transition-colors hover:bg-[var(--card)] hover:border-[var(--primary)] disabled:opacity-45 disabled:cursor-not-allowed" onClick={clearAll} disabled={selected.length === 0}>Clear</button>
          </div>
        )}
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-2 max-[520px]:grid-cols-1" role="group" aria-label={field.label}>
        {options.map((option) => {
          const checked = selectedSet.has(option);
          return (
            <label key={option} className={`relative flex items-center gap-2.5 min-h-[44px] px-3 py-2.5 border rounded-xl text-sm font-semibold cursor-pointer transition-all duration-150 ${checked ? 'border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]' : 'border-[var(--border)] bg-[var(--card)] hover:border-[var(--primary)]/50 hover:bg-[var(--bg-tertiary)] text-[var(--text)]'}`}>
              <input type="checkbox" checked={checked} onChange={() => toggle(option)} className="absolute opacity-0 pointer-events-none" />
              <span className={`inline-flex items-center justify-center w-5 h-5 rounded-md border-[1.5px] shrink-0 transition-all duration-150 ${checked ? 'border-[var(--primary)] bg-[var(--primary)] text-white' : 'border-[var(--border)] bg-[var(--card)]'}`}>{checked && <Check size={13} strokeWidth={3} />}</span>
              <span className="break-words">{option}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}