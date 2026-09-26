import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { ReviewResponse } from '../../models/models';
import { PipelineService, apiErrorMessage } from '../../services/pipeline.service';
import { MappingviewComponent } from '../mappingview/mappingview.component';

/** "Edit column matching" for an existing dashboard, or finishing a draft upload. */
@Component({
  selector: 'app-mapping-page',
  standalone: true,
  imports: [CommonModule, RouterLink, MappingviewComponent],
  template: `
    <p *ngIf="error" class="rounded-xl border border-rose-200 bg-rose-50 px-5 py-4 text-sm text-rose-700">
      {{ error }} <a routerLink="/dashboards" class="font-medium underline">Back to dashboards</a>
    </p>
    <div *ngIf="!review && !error" class="mx-auto h-64 max-w-4xl animate-pulse rounded-2xl bg-slate-200/50"></div>
    <app-mappingview
      *ngIf="review"
      [review]="review"
      [mode]="review.status === 'ready' ? 'edit' : 'new'"
      (confirmed)="onConfirmed()"
      (cancelled)="back()"
    ></app-mappingview>
  `,
})
export class MappingPageComponent implements OnInit {
  review: ReviewResponse | null = null;
  error: string | null = null;
  private id = '';

  constructor(private route: ActivatedRoute, private router: Router, private pipeline: PipelineService) {}

  ngOnInit(): void {
    this.id = this.route.snapshot.paramMap.get('id')!;
    this.pipeline.getReview(this.id).subscribe({
      next: (r) => (this.review = r),
      error: (err: HttpErrorResponse) => (this.error = apiErrorMessage(err, 'Couldn’t load this dataset.')),
    });
  }

  back(): void {
    // a draft that was cancelled has no dashboard page yet
    const built = this.review?.status === 'ready';
    this.router.navigate(built ? ['/dashboards', this.id] : ['/dashboards']);
  }

  onConfirmed(): void {
    this.router.navigate(['/dashboards', this.id]);
  }
}
