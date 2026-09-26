import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnChanges, OnDestroy, Output, SimpleChanges } from '@angular/core';
import { Subscription } from 'rxjs';

import { ChartSpec, DateRange } from '../../models/models';
import { PipelineService } from '../../services/pipeline.service';
import { formatValue } from '../../format';

@Component({
  selector: 'app-kpi-tile',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="group relative rounded-2xl border border-slate-200/80 bg-white px-5 py-4 shadow-sm">
      <div class="flex items-center justify-between">
        <p class="truncate text-xs font-medium uppercase tracking-wide text-slate-500">{{ spec.title }}</p>
        <button
          type="button"
          class="-mr-2 rounded-md p-1 text-slate-300 opacity-0 transition-opacity hover:bg-slate-100 hover:text-slate-600 group-hover:opacity-100"
          title="Hide"
          (click)="hide.emit()"
        >
          <svg class="h-3.5 w-3.5" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M5 5l10 10M15 5L5 15" />
          </svg>
        </button>
      </div>
      <div *ngIf="isLoading" class="mt-2 h-8 w-24 animate-pulse rounded bg-slate-100"></div>
      <p *ngIf="!isLoading && !error" class="mt-1 text-2xl font-semibold tabular-nums text-slate-900 sm:text-3xl" [title]="exact">
        {{ display }}
      </p>
      <p *ngIf="!isLoading && error" class="mt-2 text-sm text-rose-500">Unavailable</p>
    </div>
  `,
})
export class KpiTileComponent implements OnChanges, OnDestroy {
  @Input({ required: true }) datasetId!: string;
  @Input({ required: true }) spec!: ChartSpec;
  @Input() range: DateRange = { from: null, to: null };
  @Output() hide = new EventEmitter<void>();

  isLoading = true;
  error = false;
  display = '';
  exact = '';
  private sub?: Subscription;

  constructor(private pipeline: PipelineService) {}

  ngOnChanges(_: SimpleChanges): void {
    this.sub?.unsubscribe();
    this.isLoading = true;
    this.error = false;
    const fmt = this.spec.config.format ?? 'number';
    this.sub = this.pipeline.getChartData(this.datasetId, this.spec.name, this.range).subscribe({
      next: (res) => {
        const v = res.data.value ?? null;
        this.display = formatValue(v, fmt, { compact: true });
        this.exact = formatValue(v, fmt);
        this.isLoading = false;
      },
      error: () => {
        this.error = true;
        this.isLoading = false;
      },
    });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }
}
