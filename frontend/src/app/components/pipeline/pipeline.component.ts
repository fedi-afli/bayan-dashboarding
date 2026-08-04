import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';

import { FileuploadComponent } from '../fileupload/fileupload.component';
import { MappingviewComponent } from '../mappingview/mappingview.component';
import { PipelinedashboardComponent } from '../pipelinedashboard/pipelinedashboard.component';
import { ChartSpec, ConfirmResponse, MappingResult, UploadResponse } from '../../models/models';

type Stage = 'upload' | 'review' | 'charts';

@Component({
  selector: 'app-pipeline',
  standalone: true,
  imports: [CommonModule, FileuploadComponent, MappingviewComponent, PipelinedashboardComponent],
  templateUrl: './pipeline.component.html',
})
export class PipelineComponent {
  stage: Stage = 'upload';

  jobId: string | null = null;
  mappingResult: MappingResult | null = null;
  charts: ChartSpec[] = [];

  onUploaded(response: UploadResponse): void {
    this.jobId = response.job_id;
    this.mappingResult = response.result;
    this.stage = 'review';
  }

  onConfirmed(response: ConfirmResponse): void {
    this.mappingResult = response.result;
    this.charts = response.charts;
    this.stage = 'charts';
  }

  startOver(): void {
    this.stage = 'upload';
    this.jobId = null;
    this.mappingResult = null;
    this.charts = [];
  }
}
