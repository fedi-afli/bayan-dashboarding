import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import {
  ChartDataResponse,
  ChartSpec,
  ConfirmResponse,
  FieldConfirmation,
  UploadResponse,
} from '../models/models';

@Injectable({ providedIn: 'root' })
export class PipelineService {
  private readonly baseUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  uploadFile(file: File): Observable<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    return this.http.post<UploadResponse>(`${this.baseUrl}/pipeline/upload`, formData);
  }

  confirmMapping(jobId: string, confirmations: FieldConfirmation[]): Observable<ConfirmResponse> {
    return this.http.post<ConfirmResponse>(
      `${this.baseUrl}/pipeline/${jobId}/confirm`,
      confirmations
    );
  }

  getSchemaFields(): Observable<string[]> {
    return this.http.get<string[]>(`${this.baseUrl}/schema/fields`);
  }

  // --- Added: needed once a job is confirmed, to (re)fetch resolved charts
  // and pull the row data for each one. Mirrors GET /pipeline/{id}/charts
  // and GET /pipeline/{id}/charts/{chart_name}/data.

  getCharts(jobId: string): Observable<ChartSpec[]> {
    return this.http.get<ChartSpec[]>(`${this.baseUrl}/pipeline/${jobId}/charts`);
  }

  getChartData(jobId: string, chartName: string): Observable<ChartDataResponse> {
    return this.http.get<ChartDataResponse>(
      `${this.baseUrl}/pipeline/${jobId}/charts/${encodeURIComponent(chartName)}/data`
    );
  }
}
