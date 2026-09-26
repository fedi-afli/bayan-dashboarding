import { formatValue } from './format';

describe('formatValue', () => {
  it('keeps large values intact (regression: KPI showed "20" for 20,065,257)', () => {
    expect(formatValue(20065257.7)).toBe('20,065,257.7');
  });

  it('compacts large values only when asked', () => {
    expect(formatValue(10032628.85, 'currency', { compact: true })).toBe('10M');
    expect(formatValue(2919.99, 'currency', { compact: true })).toBe('2,919.99');
  });

  it('formats ratios as percentages', () => {
    expect(formatValue(0.248, 'percent')).toBe('24.8%');
  });

  it('shows a dash for missing values', () => {
    expect(formatValue(null)).toBe('—');
  });
});
