export const PROJECT_TYPES = [
    { value: 'seasonal', label: 'Seasonal' },
    { value: 'graduation_1', label: 'Graduation 1' },
    { value: 'graduation_2', label: 'Graduation 2' },
];

export const getProjectTypeLabel = (value) => {
    const pt = PROJECT_TYPES.find(pt => pt.value === value);
    return pt ? pt.label : value;
};
