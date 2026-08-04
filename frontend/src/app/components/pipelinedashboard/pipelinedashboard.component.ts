import { CommonModule } from '@angular/common';
import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';
import { forkJoin } from 'rxjs';

import { PipelineService } from '../../services/pipeline.service';
import { ChartSpec } from '../../models/models';

interface ChartPanel {
  spec: ChartSpec;
  isLoading: boolean;
  error: string | null;
  rows: Record<string, any>[];
  labelKey: string | null;
  valueKey: string | null;
  maxValue: number;
  showTable: boolean;
}

@Component({
  selector: 'app-pipelinedashboard',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './pipelinedashboard.component.html',
})
export class PipelinedashboardComponent implements OnChanges {
  @Input({ required: true }) jobId!: string;
  @Input({ required: true }) charts: ChartSpec[] = [];

  panels: ChartPanel[] = [];

  constructor(private pipelineService: PipelineService) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['charts'] && this.charts?.length) {
      this.loadAllCharts();
    }
  }

  private loadAllCharts(): void {
    this.panels = this.charts.map((spec) => ({
      spec,
      isLoading: true,
      error: null,
      rows: [],
      labelKey: null,
      valueKey: null,
      maxValue: 0,
      showTable: false,
    }));

    const requests = this.charts.map((chart) =>
      this.pipelineService.getChartData(this.jobId, chart.name)
    );

    forkJoin(requests).subscribe({
      next: (responses) => {
        responses.forEach((res, i) => {
          const panel = this.panels[i];
          panel.isLoading = false;
          panel.rows = res.data ?? [];
          const keys = panel.rows.length ? Object.keys(panel.rows[0]) : [];
          panel.labelKey = keys.find((k) => typeof panel.rows[0][k] === 'string') ?? keys[0] ?? null;
          panel.valueKey =
            keys.find((k) => typeof panel.rows[0][k] === 'number') ?? keys[1] ?? null;
          panel.maxValue = panel.valueKey
            ? Math.max(...panel.rows.map((r) => Number(r[panel.valueKey!]) || 0), 0)
            : 0;
        });
      },
      error: () => {
        this.panels.forEach((p) => {
          p.isLoading = false;
          p.error = 'Failed to load chart data.';
        });
      },
    });
  }

  barWidth(panel: ChartPanel, row: Record<string, any>): string {
    if (!panel.valueKey || panel.maxValue === 0) {
      return '0%';
    }
    const value = Number(row[panel.valueKey]) || 0;
    return `${(value / panel.maxValue) * 100}%`;
  }

  toggleTable(panel: ChartPanel): void {
    panel.showTable = !panel.showTable;
  }

  trackByChartName(_: number, panel: ChartPanel): string {
    return panel.spec.name;
  }
}
