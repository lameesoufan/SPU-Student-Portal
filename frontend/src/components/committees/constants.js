// ── Committees shared constants ─────────────────────────────────────────────
// Mirror of backend `committees/models.py` enums. Kept in sync manually.

export const COMMITTEE_TYPES = [
  { value: 'seminar_1',        label_en: 'سيمينار 1',         label_ar: 'سيمينار 1' },
  { value: 'seminar_2',        label_en: 'سيمينار 2',         label_ar: 'سيمينار 2' },
  { value: 'technical',        label_en: 'فنية',         label_ar: 'لجنة فنية' },
  { value: 'final_discussion', label_en: 'المناقشة النهائية',  label_ar: 'مناقشة نهائية' },
];

export const PROJECT_TYPES = [
  { value: 'seasonal',     label_en: 'فصلي',     label_ar: 'فصلي' },
  { value: 'graduation_1', label_en: 'تخرج 1', label_ar: 'تخرج 1' },
  { value: 'graduation_2', label_en: 'تخرج 2', label_ar: 'تخرج 2' },
];

export const DEPARTMENTS = [
  { value: 'software_engineering',    label_en: 'هندسة البرمجيات',    label_ar: 'برمجيات' },
  { value: 'artificial_intelligence', label_en: 'الذكاء الاصطناعي', label_ar: 'ذكاء اصطناعي' },
  { value: 'information_security',    label_en: 'أمن المعلومات',    label_ar: 'أمن سيبراني' },
  { value: 'communications',          label_en: 'الاتصالات',          label_ar: 'اتصالات' },
  { value: 'control_robotics',        label_en: 'التحكم والروبوتات',      label_ar: 'تحكم وروبوتات' },
];

export const COMMITTEE_STATUSES = [
  { value: 'draft',     label_en: 'مسودة',     label_ar: 'مسودة' },
  { value: 'scheduled', label_en: 'مجدولة', label_ar: 'مجدولة' },
  { value: 'completed', label_en: 'منجزة', label_ar: 'منجزة' },
  { value: 'cancelled', label_en: 'ملغاة', label_ar: 'ملغاة' },
];

// ── Lookup helpers ────────────────────────────────────────────────────────────
export const getCommitteeTypeLabel  = (v) => COMMITTEE_TYPES.find(x => x.value === v)?.label_ar  || v;
export const getProjectTypeLabel    = (v) => PROJECT_TYPES.find(x => x.value === v)?.label_ar    || v;
export const getDepartmentLabel     = (v) => DEPARTMENTS.find(x => x.value === v)?.label_ar      || v;
export const getCommitteeStatusLabel = (v) => COMMITTEE_STATUSES.find(x => x.value === v)?.label_ar || v;

// ── Color tokens per committee type (for badges / icons) ─────────────────────
export const COMMITTEE_TYPE_COLORS = {
  seminar_1:        { bg: 'rgba(99, 102, 241, 0.12)',  text: '#818cf8', border: 'rgba(99, 102, 241, 0.25)' },
  seminar_2:        { bg: 'rgba(139, 92, 246, 0.12)',  text: '#a78bfa', border: 'rgba(139, 92, 246, 0.25)' },
  technical:        { bg: 'rgba(14, 165, 233, 0.12)',  text: '#38bdf8', border: 'rgba(14, 165, 233, 0.25)' },
  final_discussion: { bg: 'rgba(245, 158, 11, 0.12)',  text: '#fbbf24', border: 'rgba(245, 158, 11, 0.25)' },
};

export const DEPARTMENT_COLORS = {
  software_engineering:    { bg: 'rgba(16, 185, 129, 0.12)',  text: '#34d399', border: 'rgba(16, 185, 129, 0.25)' },
  artificial_intelligence: { bg: 'rgba(236, 72, 153, 0.12)',  text: '#f472b6', border: 'rgba(236, 72, 153, 0.25)' },
  information_security:    { bg: 'rgba(239, 68, 68, 0.12)',   text: '#f87171', border: 'rgba(239, 68, 68, 0.25)' },
  communications:          { bg: 'rgba(6, 182, 212, 0.12)',   text: '#22d3ee', border: 'rgba(6, 182, 212, 0.25)' },
  control_robotics:        { bg: 'rgba(217, 119, 6, 0.12)',   text: '#fbbf24', border: 'rgba(217, 119, 6, 0.25)' },
};

export const STATUS_COLORS = {
  draft:     { bg: 'rgba(148, 163, 184, 0.12)', text: '#94a3b8', border: 'rgba(148, 163, 184, 0.25)' },
  scheduled: { bg: 'rgba(59, 130, 246, 0.12)',  text: '#60a5fa', border: 'rgba(59, 130, 246, 0.25)' },
  completed: { bg: 'rgba(16, 185, 129, 0.12)',  text: '#34d399', border: 'rgba(16, 185, 129, 0.25)' },
  cancelled: { bg: 'rgba(239, 68, 68, 0.12)',   text: '#f87171', border: 'rgba(239, 68, 68, 0.25)' },
};

export const WORKLOAD_COLORS = {
  low:  { bg: 'rgba(16, 185, 129, 0.12)',  text: '#34d399', label: 'منخفضة' },
  med:  { bg: 'rgba(245, 158, 11, 0.12)',  text: '#fbbf24', label: 'متوسطة' },
  high: { bg: 'rgba(239, 68, 68, 0.12)',   text: '#f87171', label: 'عالية' },
};

// ── Warning level colors ─────────────────────────────────────────────────────
export const WARNING_COLORS = {
  warn: { bg: 'rgba(245, 158, 11, 0.10)', text: '#fbbf24', border: 'rgba(245, 158, 11, 0.20)' },
  info: { bg: 'rgba(59, 130, 246, 0.10)', text: '#60a5fa', border: 'rgba(59, 130, 246, 0.20)' },
  error: { bg: 'rgba(239, 68, 68, 0.10)', text: '#f87171', border: 'rgba(239, 68, 68, 0.20)' },
};
