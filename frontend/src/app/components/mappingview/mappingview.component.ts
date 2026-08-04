import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Input, OnChanges, OnInit, Output, SimpleChanges } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';

import { PipelineService } from '../../services/pipeline.service';
import { ConfirmResponse, FieldConfirmation, MappingResult } from '../../models/models';

interface ReviewRow {
  source_column: string;
  suggestions: string[];
  target_field: string | null; // null = leave unresolved / skip
}

@Component({
  selector: 'app-mappingview',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './mappingview.component.html',
})
export class MappingviewComponent implements OnInit, OnChanges {
  @Input({ required: true }) jobId!: string;
  @Input({ required: true }) mappingResult!: MappingResult;

  @Output() confirmed = new EventEmitter<ConfirmResponse>();

  schemaFields: string[] = [];
  rows: ReviewRow[] = [];
  isSubmitting = false;
  errorMessage: string | null = null;

  constructor(private pipelineService: PipelineService) {}

  ngOnInit(): void {
    this.pipelineService.getSchemaFields().subscribe({
      next: (fields) => (this.schemaFields = fields),
      error: () => (this.schemaFields = []),
    });
    this.buildRows();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['mappingResult'] && !changes['mappingResult'].firstChange) {
      this.buildRows();
    }
  }

  private buildRows(): void {
    if (!this.mappingResult) {
      this.rows = [];
      return;
    }

    const ambiguous: ReviewRow[] = (this.mappingResult.needs_confirmation ?? []).map((n) => ({
      source_column: n.source,
      suggestions: n.suggestions ?? [],
      target_field: n.suggestions?.[0] ?? null,
    }));

    const ambiguousSources = new Set(ambiguous.map((r) => r.source_column));
    const unresolved: ReviewRow[] = (this.mappingResult.unresolved_columns ?? [])
      .filter((col) => !ambiguousSources.has(col))
      .map((col) => ({ source_column: col, suggestions: [], target_field: null }));

    this.rows = [...ambiguous, ...unresolved];
  }

  get hasReviewItems(): boolean {
    return this.rows.length > 0;
  }

  get alreadyMappedEntries(): [string, string][] {
    return Object.entries(this.mappingResult?.mapping ?? {});
  }

  submit(): void {
    if (this.isSubmitting) {
      return;
    }

    const confirmations: FieldConfirmation[] = this.rows.map((row) => ({
      source_column: row.source_column,
      target_field: row.target_field || null,
    }));

    this.isSubmitting = true;
    this.errorMessage = null;

    this.pipelineService.confirmMapping(this.jobId, confirmations).subscribe({
      next: (response) => {
        this.isSubmitting = false;
        this.confirmed.emit(response);
      },
      error: (err: HttpErrorResponse) => {
        this.isSubmitting = false;
        this.errorMessage = this.extractError(err);
      },
    });
  }

  private extractError(err: HttpErrorResponse): string {
    if (err.error?.detail?.errors) {
      return err.error.detail.errors.join(', ');
    }
    if (typeof err.error?.detail === 'string') {
      return err.error.detail;
    }
    return err.message || 'Failed to confirm mapping.';
  }
}
