import { CommonModule } from '@angular/common';
import { Component, EventEmitter, Output } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';

import { PipelineService } from '../../services/pipeline.service';
import { UploadResponse } from '../../models/models';

@Component({
  selector: 'app-fileupload',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './fileupload.component.html',
})
export class FileuploadComponent {
  @Output() uploaded = new EventEmitter<UploadResponse>();

  selectedFile: File | null = null;
  isUploading = false;
  errorMessage: string | null = null;

  constructor(private pipelineService: PipelineService) {}

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedFile = input.files?.[0] ?? null;
    this.errorMessage = null;
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    const file = event.dataTransfer?.files?.[0];
    if (file) {
      this.selectedFile = file;
      this.errorMessage = null;
    }
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
  }

  upload(): void {
    if (!this.selectedFile || this.isUploading) {
      return;
    }

    this.isUploading = true;
    this.errorMessage = null;

    this.pipelineService.uploadFile(this.selectedFile).subscribe({
      next: (response) => {
        this.isUploading = false;
        this.uploaded.emit(response);
      },
      error: (err: HttpErrorResponse) => {
        this.isUploading = false;
        this.errorMessage = this.extractError(err);
      },
    });
  }

  private extractError(err: HttpErrorResponse): string {
    if (typeof err.error?.detail === 'string') {
      return err.error.detail;
    }
    if (err.error?.detail?.errors) {
      return err.error.detail.errors.join(', ');
    }
    return err.message || 'Upload failed. Please try again.';
  }
}
