import { CommonModule } from '@angular/common';
import { Component, EventEmitter, OnDestroy, Output } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';

import { PipelineService, apiErrorMessage } from '../../services/pipeline.service';
import { ReviewResponse } from '../../models/models';

const ACCEPTED = ['.csv', '.tsv', '.txt', '.xlsx', '.xls', '.xlsm', '.json'];
const MAX_MB = 50;

@Component({
  selector: 'app-fileupload',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './fileupload.component.html',
})
export class FileuploadComponent implements OnDestroy {
  @Output() uploaded = new EventEmitter<ReviewResponse>();

  accept = ACCEPTED.join(',');
  selectedFile: File | null = null;
  isUploading = false;
  isDragging = false;
  errorMessage: string | null = null;
  slowHint = false;
  private slowTimer?: ReturnType<typeof setTimeout>;

  constructor(private pipelineService: PipelineService) {}

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.pick(input.files?.[0] ?? null);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragging = false;
    this.pick(event.dataTransfer?.files?.[0] ?? null);
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragging = true;
  }

  private pick(file: File | null): void {
    this.errorMessage = null;
    if (!file) return;
    const ext = '.' + (file.name.split('.').pop() ?? '').toLowerCase();
    if (!ACCEPTED.includes(ext)) {
      this.errorMessage = 'Please pick a CSV, Excel or JSON file.';
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      this.errorMessage = `This file is larger than ${MAX_MB} MB.`;
      return;
    }
    this.selectedFile = file;
  }

  upload(): void {
    if (!this.selectedFile || this.isUploading) return;

    this.isUploading = true;
    this.errorMessage = null;
    this.slowHint = false;
    this.slowTimer = setTimeout(() => (this.slowHint = true), 4000);

    this.pipelineService.uploadFile(this.selectedFile).subscribe({
      next: (response) => {
        this.done();
        this.uploaded.emit(response);
      },
      error: (err: HttpErrorResponse) => {
        this.done();
        this.errorMessage = apiErrorMessage(err, 'Upload failed. Please try again.');
      },
    });
  }

  private done(): void {
    this.isUploading = false;
    clearTimeout(this.slowTimer);
  }

  ngOnDestroy(): void {
    clearTimeout(this.slowTimer);
  }
}
