export const PROJECT_TYPES = [
    { value: 'seasonal', label: 'Seasonal' },
    { value: 'graduation_1', label: 'Graduation 1' },
    { value: 'graduation_2', label: 'Graduation 2' },
];

export const getProjectTypeLabel = (value) => {
    const pt = PROJECT_TYPES.find(pt => pt.value === value);
    return pt ? pt.label : value;
};

export const DEPARTMENTS = [
    { value: 'software_engineering',    label: 'برمجيات' },
    { value: 'artificial_intelligence', label: 'ذكاء اصطناعي' },
    { value: 'information_security',    label: 'أمن سيبراني' },
    { value: 'communications',          label: 'اتصالات' },
    { value: 'control_robotics',        label: 'تحكم وروبوتات' },
];

export const getDepartmentLabel = (value) => {
    const d = DEPARTMENTS.find(d => d.value === value);
    return d ? d.label : value;
};
