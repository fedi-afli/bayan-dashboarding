import { ValueFormat } from './models/models';

const full = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });

/**
 * Formats a raw number for display.
 * - compact: 10032628.85 -> "10M" (for KPI tiles / axes); small values stay exact
 * - percent: 0.248 -> "24.8%"
 * Never parses its own output back (that's what turned 20,065,257 into "20").
 */
export function formatValue(
  value: number | null | undefined,
  format: ValueFormat = 'number',
  opts: { compact?: boolean } = {}
): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return '—';
  }
  if (format === 'percent') {
    return `${(value * 100).toLocaleString('en-US', { maximumFractionDigits: 1 })}%`;
  }
  if (opts.compact && Math.abs(value) >= 10_000) {
    return compact.format(value);
  }
  return full.format(value);
}
