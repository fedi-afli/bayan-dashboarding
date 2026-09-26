import type { EChartsCoreOption } from 'echarts/core';

import { ChartData, ChartSpec, ValueFormat } from '../../models/models';
import { formatValue } from '../../format';
import { BRAND, OTHER_COLOR, PALETTE } from './echarts-setup';

const AXIS_LABEL = { color: '#94a3b8', fontSize: 11 };
const SPLIT_LINE = { lineStyle: { color: '#f1f5f9' } };
const TOOLTIP_BASE = {
  backgroundColor: '#0f172a',
  borderWidth: 0,
  textStyle: { color: '#f8fafc', fontSize: 12 },
  extraCssText: 'border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,.15);',
};

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + '…' : s;
}

export function buildOption(spec: ChartSpec, data: ChartData): EChartsCoreOption {
  const fmt: ValueFormat = spec.config.format ?? 'number';
  const short = (v: number) => formatValue(v, fmt, { compact: true });
  const exact = (v: number) => formatValue(v, fmt);

  switch (spec.chart_type) {
    case 'line': {
      const rows = data.rows ?? [];
      return {
        grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
        tooltip: { ...TOOLTIP_BASE, trigger: 'axis', valueFormatter: (v: number) => exact(v) },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: rows.map((r) => r.label),
          axisLabel: AXIS_LABEL,
          axisLine: { lineStyle: { color: '#e2e8f0' } },
          axisTick: { show: false },
        },
        yAxis: { type: 'value', axisLabel: { ...AXIS_LABEL, formatter: short }, splitLine: SPLIT_LINE },
        series: [{
          type: 'line',
          data: rows.map((r) => r.value),
          showSymbol: rows.length < 40,
          symbolSize: 6,
          lineStyle: { width: 2.5, color: BRAND },
          itemStyle: { color: BRAND },
          areaStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [{ offset: 0, color: 'rgba(79,70,229,0.18)' }, { offset: 1, color: 'rgba(79,70,229,0)' }],
            },
          },
        }],
      };
    }

    case 'bar': {
      // "Other" is summarized in the card subtitle instead: as a bar it
      // usually dwarfs the top 10 and flattens every bar worth reading
      const rows = (data.rows ?? []).filter((r) => !r.is_other);
      return {
        grid: { left: 8, right: 56, top: 4, bottom: 4, containLabel: true },
        tooltip: { ...TOOLTIP_BASE, trigger: 'item', formatter: (p: any) => `${p.name}<br/><b>${exact(p.value)}</b>` },
        xAxis: { type: 'value', show: false },
        yAxis: {
          type: 'category',
          inverse: true, // biggest on top
          data: rows.map((r) => r.label),
          axisLabel: { ...AXIS_LABEL, color: '#475569', formatter: (s: string) => truncate(s, 22) },
          axisLine: { show: false },
          axisTick: { show: false },
        },
        series: [{
          type: 'bar',
          barMaxWidth: 18,
          data: rows.map((r) => ({ value: r.value, itemStyle: { color: BRAND, borderRadius: [0, 4, 4, 0] } })),
          label: { show: true, position: 'right', color: '#64748b', fontSize: 11, formatter: (p: any) => short(p.value) },
        }],
      };
    }

    case 'donut': {
      const rows = data.rows ?? [];
      return {
        tooltip: {
          ...TOOLTIP_BASE,
          trigger: 'item',
          formatter: (p: any) => `${p.name}<br/><b>${exact(p.value)}</b> · ${p.percent}%`,
        },
        legend: {
          type: 'scroll',
          orient: 'vertical',
          right: 0,
          top: 'middle',
          icon: 'circle',
          itemWidth: 8,
          itemHeight: 8,
          textStyle: { color: '#475569', fontSize: 12 },
          formatter: (name: string) => truncate(name, 20),
        },
        series: [{
          type: 'pie',
          radius: ['52%', '78%'],
          center: ['32%', '50%'],
          avoidLabelOverlap: true,
          label: { show: false },
          itemStyle: { borderColor: '#fff', borderWidth: 2 },
          data: rows.map((r, i) => ({
            name: r.label,
            value: r.value,
            itemStyle: { color: r.is_other ? OTHER_COLOR : PALETTE[i % PALETTE.length] },
          })),
        }],
      };
    }

    case 'scatter': {
      return {
        grid: { left: 8, right: 16, top: 16, bottom: 24, containLabel: true },
        tooltip: {
          ...TOOLTIP_BASE,
          trigger: 'item',
          formatter: (p: any) => `${spec.config.x}: ${formatValue(p.value[0])}<br/>${spec.config.y}: ${formatValue(p.value[1])}`,
        },
        xAxis: {
          type: 'value', name: String(spec.config.x ?? ''), nameLocation: 'middle', nameGap: 24,
          nameTextStyle: AXIS_LABEL, axisLabel: AXIS_LABEL, splitLine: SPLIT_LINE, scale: true,
        },
        yAxis: { type: 'value', axisLabel: { ...AXIS_LABEL, formatter: (v: number) => formatValue(v, 'number', { compact: true }) }, splitLine: SPLIT_LINE, scale: true },
        series: [{ type: 'scatter', data: data.points ?? [], symbolSize: 5, itemStyle: { color: BRAND, opacity: 0.45 } }],
      };
    }

    default:
      return {};
  }
}

/** Height that keeps bars readable instead of squashing / stretching them. */
export function chartHeight(spec: ChartSpec, data: ChartData | null): number {
  if (spec.chart_type === 'bar') {
    const n = data?.rows?.filter((r) => !r.is_other).length ?? 8;
    return Math.max(110, n * 30 + 16);
  }
  if (spec.chart_type === 'donut') return 220;
  return 260;
}
