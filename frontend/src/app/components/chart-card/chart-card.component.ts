import { CommonModule } from '@angular/common';
import {
  AfterViewInit,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  NgZone,
  OnChanges,
  OnDestroy,
  Output,
  SimpleChanges,
  ViewChild,
} from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { Subscription } from 'rxjs';

import { ChartData, ChartSpec, DateRange } from '../../models/models';
import { PipelineService, apiErrorMessage } from '../../services/pipeline.service';
import { formatValue } from '../../format';
import { echarts } from './echarts-setup';
import { buildOption, chartHeight } from './chart-options';

@Component({
  selector: 'app-chart-card',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './chart-card.component.html',
})
export class ChartCardComponent implements OnChanges, AfterViewInit, OnDestroy {
  @Input({ required: true }) datasetId!: string;
  @Input({ required: true }) spec!: ChartSpec;
  @Input() range: DateRange = { from: null, to: null };
  @Output() hide = new EventEmitter<void>();

  @ViewChild('chartEl', { static: true }) chartEl!: ElementRef<HTMLDivElement>;

  data: ChartData | null = null;
  isLoading = true;
  error: string | null = null;
  showTable = false;
  height = 260;

  private chart?: echarts.ECharts;
  private resizeObserver?: ResizeObserver;
  private sub?: Subscription;

  constructor(private pipeline: PipelineService, private zone: NgZone) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['spec'] || changes['range'] || changes['datasetId']) {
      this.load();
    }
  }

  ngAfterViewInit(): void {
    this.zone.runOutsideAngular(() => {
      this.chart = echarts.init(this.chartEl.nativeElement, undefined, { renderer: 'canvas' });
      this.resizeObserver = new ResizeObserver(() => this.chart?.resize());
      this.resizeObserver.observe(this.chartEl.nativeElement);
    });
    this.render();
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
    this.resizeObserver?.disconnect();
    this.chart?.dispose();
  }

  get isEmpty(): boolean {
    if (!this.data) return true;
    if (this.spec.chart_type === 'scatter') return !this.data.points?.length;
    return !this.data.rows?.length;
  }

  get subtitle(): string {
    const d = this.data;
    if (!d) return '';
    if (this.spec.chart_type === 'line' && d.granularity) {
      return { day: 'Per day', week: 'Per week', month: 'Per month', year: 'Per year' }[d.granularity];
    }
    if (d.hidden_groups) {
      const shown = (d.rows ?? []).filter((r) => !r.is_other).length;
      const other = d.rows?.find((r) => r.is_other);
      if (other && this.spec.chart_type === 'bar') {
        const total = formatValue(other.value, this.spec.config.format ?? 'number', { compact: true });
        return `Top ${shown} of ${shown + d.hidden_groups} · the other ${d.hidden_groups} add up to ${total}`;
      }
      return `Top ${shown} of ${shown + d.hidden_groups}`;
    }
    if (this.spec.chart_type === 'scatter') return `Random sample of ${d.points?.length ?? 0} rows`;
    return '';
  }

  fmt(v: number | null): string {
    return formatValue(v, this.spec.config.format ?? 'number');
  }

  toggleTable(): void {
    this.showTable = !this.showTable;
    if (!this.showTable) {
      // the canvas was hidden (0×0) while the table showed
      setTimeout(() => this.chart?.resize());
    }
  }

  private load(): void {
    this.sub?.unsubscribe();
    this.isLoading = true;
    this.error = null;
    this.sub = this.pipeline.getChartData(this.datasetId, this.spec.name, this.range).subscribe({
      next: (res) => {
        this.data = res.data;
        this.isLoading = false;
        this.height = chartHeight(this.spec, this.data);
        // let the new height apply before drawing
        setTimeout(() => this.render());
      },
      error: (err: HttpErrorResponse) => {
        this.isLoading = false;
        this.error = apiErrorMessage(err, 'Couldn’t load this chart.');
      },
    });
  }

  private render(): void {
    if (!this.chart || !this.data || this.isEmpty) {
      this.chart?.clear();
      return;
    }
    const option = buildOption(this.spec, this.data);
    this.zone.runOutsideAngular(() => {
      this.chart!.setOption(option, true);
      this.chart!.resize();
    });
  }
}
