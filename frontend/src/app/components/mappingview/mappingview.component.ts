import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnChanges, OnDestroy, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { Subject, Subscription, catchError, debounceTime, of, switchMap } from 'rxjs';

import { ColumnSuggestion, DatasetOverview, Quote, ReviewResponse, SchemaField } from '../../models/models';
import { PipelineService, apiErrorMessage } from '../../services/pipeline.service';
import { AccountService } from '../../services/account.service';

type RowStatus = 'matched' | 'check' | 'unmatched' | 'empty';

interface Row {
  column: ColumnSuggestion;
  target: string | null;
  status: RowStatus;
  examples: string;
}

const STATUS_ORDER: Record<RowStatus, number> = { check: 0, unmatched: 1, matched: 2, empty: 3 };

@Component({
  selector: 'app-mappingview',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './mappingview.component.html',
})
export class MappingviewComponent implements OnChanges, OnDestroy {
  @Input({ required: true }) review!: ReviewResponse;
  /** 'edit' = re-mapping an existing dashboard */
  @Input() mode: 'new' | 'edit' = 'new';

  @Output() confirmed = new EventEmitter<DatasetOverview>();
  @Output() cancelled = new EventEmitter<void>();

  rows: Row[] = [];
  fields: SchemaField[] = [];
  onlyAttention = false;
  isSubmitting = false;
  errorMessage: string | null = null;
  outOfCredits = false;

  /** live price: re-quoted by the server as columns are added or removed */
  quote: Quote | null = null;
  quoting = false;
  showBreakdown = false;
  private remap$ = new Subject<void>();
  private quoteSub: Subscription;

  constructor(private pipeline: PipelineService, private account: AccountService) {
    this.quoteSub = this.remap$
      .pipe(
        debounceTime(300),
        switchMap(() => this.pipeline.quote(this.review.dataset_id, this.currentMapping()).pipe(catchError(() => of(null))))
      )
      .subscribe((q) => {
        this.quoting = false;
        if (q) this.quote = q;
      });
  }

  ngOnDestroy(): void {
    this.quoteSub.unsubscribe();
  }

  ngOnChanges(): void {
    this.quote = this.review.quote ?? null;
    this.outOfCredits = false;
    this.fields = [...this.review.fields].sort((a, b) => a.label.localeCompare(b.label));
    this.rows = this.review.result.columns
      .map((c) => ({
        column: c,
        target: c.target,
        status: this.statusOf(c),
        examples: (c.examples ?? []).map((e) => String(e)).join(' · '),
      }))
      .sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status]);
    this.onlyAttention = this.mode === 'new' && this.attentionCount > 0 && this.rows.length > 12;
  }

  private statusOf(c: ColumnSuggestion): RowStatus {
    if (c.review_reason === 'empty') return 'empty';
    if (c.review_reason === 'ai_guess' || c.review_reason === 'low_confidence') return 'check';
    if (!c.target) return 'unmatched';
    return 'matched';
  }

  get attentionCount(): number {
    return this.rows.filter((r) => r.status === 'check').length;
  }
  get matchedCount(): number {
    return this.rows.filter((r) => r.target).length;
  }
  get shownRows(): Row[] {
    return this.onlyAttention ? this.rows.filter((r) => r.status === 'check' || r.status === 'unmatched') : this.rows;
  }

  statusLabel(s: RowStatus): string {
    return { matched: 'Matched', check: 'AI guess', unmatched: 'Not used', empty: 'Empty' }[s];
  }

  labelOf(name: string | null): string {
    return this.fields.find((f) => f.name === name)?.label ?? name ?? '';
  }

  /** other columns already set to the same field -> can't load */
  duplicateOf(row: Row): string[] {
    if (!row.target) return [];
    return this.rows.filter((r) => r !== row && r.target === row.target).map((r) => r.column.name);
  }

  get hasDuplicates(): boolean {
    return this.rows.some((r) => this.duplicateOf(r).length > 0);
  }

  /** Credits building now would charge (a rebuild only pays what isn't covered yet). */
  get due(): number {
    return this.quote?.due ?? 0;
  }

  get canAfford(): boolean {
    return !this.outOfCredits && (this.quote?.balance ?? 0) >= this.due;
  }

  get canSubmit(): boolean {
    return !this.isSubmitting && !this.quoting && this.matchedCount > 0 && !this.hasDuplicates && this.canAfford;
  }

  plural(n: number, word = 'credit'): string {
    return `${n} ${word}${n === 1 ? '' : 's'}`;
  }

  get buildLabel(): string {
    if (this.isSubmitting) return 'Building your dashboard…';
    if (this.mode === 'edit') return this.due ? `Save & rebuild · ${this.plural(this.due)}` : 'Save & rebuild dashboard';
    return this.due ? `Build my dashboard · ${this.plural(this.due)}` : 'Build my dashboard';
  }

  private currentMapping(): Record<string, string | null> {
    const mapping: Record<string, string | null> = {};
    for (const r of this.rows) mapping[r.column.name] = r.target || null;
    return mapping;
  }

  onChange(row: Row): void {
    // an explicit choice by the user is no longer "a guess to check"
    if (!row.target) {
      if (row.status !== 'empty') row.status = 'unmatched';
    } else if (row.status === 'check' || row.status === 'unmatched') {
      row.status = 'matched';
    }
    this.errorMessage = null;
    this.outOfCredits = false;
    this.quoting = true;
    this.remap$.next();
  }

  submit(): void {
    if (!this.canSubmit) return;
    const mapping = this.currentMapping();

    this.isSubmitting = true;
    this.errorMessage = null;
    this.pipeline.confirmMapping(this.review.dataset_id, mapping).subscribe({
      next: (overview) => {
        this.isSubmitting = false;
        if (overview.credits) this.account.setBalance(overview.credits.balance);
        this.confirmed.emit(overview);
      },
      error: (err: HttpErrorResponse) => {
        this.isSubmitting = false;
        if (err.status === 402) {
          this.outOfCredits = true;
          return;
        }
        this.errorMessage = apiErrorMessage(err, 'Couldn’t load the data. Please try again.');
      },
    });
  }
}
