import { describe, expect, it } from 'vitest';
import {
  PROJECT_TYPES,
  DEPARTMENTS,
  getProjectTypeLabel,
  getDepartmentLabel,
} from '../constants.js';

describe('project type constants', () => {
  it('defines exactly the three supported project types', () => {
    expect(PROJECT_TYPES.map((item) => item.value)).toEqual([
      'seasonal',
      'graduation_1',
      'graduation_2',
    ]);
  });

  it.each([
    ['seasonal', 'Seasonal'],
    ['graduation_1', 'Graduation 1'],
    ['graduation_2', 'Graduation 2'],
  ])('maps %s to its label', (value, label) => {
    expect(getProjectTypeLabel(value)).toBe(label);
  });

  it('returns unknown project type values unchanged', () => {
    expect(getProjectTypeLabel('custom_type')).toBe('custom_type');
  });

  it('does not contain duplicate project type values', () => {
    const values = PROJECT_TYPES.map((item) => item.value);
    expect(new Set(values).size).toBe(values.length);
  });
});

describe('department constants', () => {
  it('defines all five supported departments', () => {
    expect(DEPARTMENTS.map((item) => item.value)).toEqual([
      'software_engineering',
      'artificial_intelligence',
      'information_security',
      'communications',
      'control_robotics',
    ]);
  });

  it.each([
    ['software_engineering', 'برمجيات'],
    ['artificial_intelligence', 'ذكاء اصطناعي'],
    ['information_security', 'أمن سيبراني'],
    ['communications', 'اتصالات'],
    ['control_robotics', 'تحكم وروبوتات'],
  ])('maps %s to its Arabic label', (value, label) => {
    expect(getDepartmentLabel(value)).toBe(label);
  });

  it('returns unknown department values unchanged', () => {
    expect(getDepartmentLabel('other')).toBe('other');
  });

  it('does not contain duplicate department values', () => {
    const values = DEPARTMENTS.map((item) => item.value);
    expect(new Set(values).size).toBe(values.length);
  });
});
