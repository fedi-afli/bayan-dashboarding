import { CommonModule } from '@angular/common';
import { Component, HostListener, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { ChartSpec, DatasetOverview, DateRange } from '../../models/models';
import { PipelineService, apiErrorMessage } from '../../services/pipeline.service';
import { ChartCardComponent } from '../chart-card/chart-card.component';
import { KpiTileComponent } from '../kpi-tile/kpi-tile.component';

interface Preset {
  id: string;
  label: string;
  months?: number;
  days?: number;
}

const PRESETS: Preset[] = [
  { id: 'all', label: 'All time' },
  { id: '12m', label: '12 months', months: 12 },
  { id: '3m', label: '3 months', months: 3 },
  { id: '30d', label: '30 days', days: 30 },
];

const GROUPS: { title: string; types: ChartSpec['chart_type'][] }[] = [
  { title: 'Key numbers', types: ['kpi'] },
  { title: 'Trends', types: ['line'] },
  { title: 'Breakdowns', types: ['bar', 'donut'] },
  { title: 'Advanced', types: ['scatter'] },
];

function iso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, ChartCardComponent, KpiTileComponent],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent implements OnInit {
  dataset: DatasetOverview | null = null;
  loadError: string | null = null;

  hidden = new Set<string>();
  range: DateRange = { from: null, to: null };
  activePreset = 'all';
  presets = PRESETS;
  groups = GROUPS;

  customizeOpen = false;
  menuOpen = false;
  confirmDelete = false;

  constructor(
    private route: ActivatedRoute,
    private router: Router,
    private pipeline: PipelineService
  ) {}

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id')!;
    this.pipeline.getDataset(id).subscribe({
      next: (ds) => {
        this.dataset = ds;
        this.hidden = new Set(ds.hidden_charts);
      },
      error: (err: HttpErrorResponse) => {
        this.loadError =
          err.status === 404 ? 'This dashboard doesn’t exist (anymore).' : apiErrorMessage(err, 'Couldn’t load this dashboard.');
      },
    });
  }

  // ---------- sections ----------
  private visible(types: ChartSpec['chart_type'][]): ChartSpec[] {
    return (this.dataset?.charts ?? []).filter((c) => types.includes(c.chart_type) && !this.hidden.has(c.name));
  }
  get kpis() { return this.visible(['kpi']); }
  get trends() { return this.visible(['line']); }
  get panels() { return this.visible(['bar', 'donut', 'scatter']); }
  get hiddenCount() { return this.hidden.size; }

  chartsIn(types: ChartSpec['chart_type'][]): ChartSpec[] {
    return (this.dataset?.charts ?? []).filter((c) => types.includes(c.chart_type));
  }

  trackByName(_: number, c: ChartSpec) { return c.name; }

  // ---------- date range ----------
  applyPreset(p: Preset): void {
    this.activePreset = p.id;
    if (p.id === 'all' || !this.dataset?.date_max) {
      this.range = { from: null, to: null };
      return;
    }
    const end = new Date(this.dataset.date_max + 'T00:00:00Z');
    const start = new Date(end);
    if (p.months) start.setUTCMonth(start.getUTCMonth() - p.months);
    if (p.days) start.setUTCDate(start.getUTCDate() - p.days + 1);
    this.range = { from: iso(start), to: this.dataset.date_max };
  }

  onCustomRange(from: string, to: string): void {
    this.activePreset = 'custom';
    this.range = { from: from || null, to: to || null };
  }

  get rangeLabel(): string {
    const d = this.dataset;
    if (!d?.date_min) return '';
    const fmt = (s: string) =>
      new Date(s + 'T00:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
    return `${fmt(this.range.from ?? d.date_min)} – ${fmt(this.range.to ?? d.date_max!)}`;
  }

  // ---------- layout ----------
  isVisible(c: ChartSpec): boolean {
    return !this.hidden.has(c.name);
  }

  toggle(c: ChartSpec): void {
    this.hidden.has(c.name) ? this.hidden.delete(c.name) : this.hidden.add(c.name);
    this.hidden = new Set(this.hidden);
    this.saveLayout();
  }

  hideChart(c: ChartSpec): void {
    this.hidden = new Set(this.hidden).add(c.name);
    this.saveLayout();
  }

  resetLayout(): void {
    this.hidden = new Set((this.dataset?.charts ?? []).filter((c) => !c.default_visible).map((c) => c.name));
    this.saveLayout();
  }

  private saveLayout(): void {
    if (!this.dataset) return;
    this.pipeline.saveLayout(this.dataset.id, [...this.hidden]).subscribe();
  }

  // ---------- actions ----------
  deleteDashboard(): void {
    if (!this.dataset) return;
    this.pipeline.deleteDataset(this.dataset.id).subscribe(() => this.router.navigate(['/dashboards']));
  }

  @HostListener('document:keydown.escape')
  closeOverlays(): void {
    this.customizeOpen = false;
    this.menuOpen = false;
    this.confirmDelete = false;
  }
}
