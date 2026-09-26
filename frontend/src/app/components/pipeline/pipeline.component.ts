import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { Router } from '@angular/router';

import { FileuploadComponent } from '../fileupload/fileupload.component';
import { MappingviewComponent } from '../mappingview/mappingview.component';
import { DatasetOverview, ReviewResponse } from '../../models/models';

/** New dashboard flow: upload -> check columns -> dashboard page. */
@Component({
  selector: 'app-pipeline',
  standalone: true,
  imports: [CommonModule, FileuploadComponent, MappingviewComponent],
  templateUrl: './pipeline.component.html',
})
export class PipelineComponent {
  review: ReviewResponse | null = null;

  constructor(private router: Router) {}

  get step(): number {
    return this.review ? 2 : 1;
  }

  onUploaded(review: ReviewResponse): void {
    this.review = review;
  }

  onConfirmed(overview: DatasetOverview): void {
    this.router.navigate(['/dashboards', overview.id]);
  }

  startOver(): void {
    this.review = null;
  }
}
