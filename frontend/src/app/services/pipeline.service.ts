import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../environments/environment';
import {
  ChartDataResponse,
  DatasetOverview,
  DatasetSummary,
  DateRange,
  Quote,
  ReviewResponse,
} from '../models/models';

@Injectable({ providedIn: 'root' })
export class PipelineService {
  private readonly baseUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  uploadFile(file: File): Observable<ReviewResponse> {
    const formData = new FormData();
    formData.append('file', file, file.name);
    return this.http.post<ReviewResponse>(`${this.baseUrl}/datasets/upload`, formData);
  }

  getReview(datasetId: string): Observable<ReviewResponse> {
    return this.http.get<ReviewResponse>(`${this.baseUrl}/datasets/${datasetId}/review`);
  }

  /** mapping: every file column -> schema field, or null to leave it out */
  confirmMapping(datasetId: string, mapping: Record<string, string | null>): Observable<DatasetOverview> {
    return this.http.post<DatasetOverview>(`${this.baseUrl}/datasets/${datasetId}/confirm`, { mapping });
  }

  /** Price of building with this mapping (the server computes it from the resources needed). */
  quote(datasetId: string, mapping: Record<string, string | null>): Observable<Quote> {
    return this.http.post<Quote>(`${this.baseUrl}/datasets/${datasetId}/quote`, { mapping });
  }

  listDatasets(): Observable<DatasetSummary[]> {
    return this.http.get<DatasetSummary[]>(`${this.baseUrl}/datasets`);
  }

  getDataset(datasetId: string): Observable<DatasetOverview> {
    return this.http.get<DatasetOverview>(`${this.baseUrl}/datasets/${datasetId}`);
  }

  saveLayout(datasetId: string, hiddenCharts: string[]): Observable<{ hidden_charts: string[] }> {
    return this.http.put<{ hidden_charts: string[] }>(`${this.baseUrl}/datasets/${datasetId}/layout`, {
      hidden_charts: hiddenCharts,
    });
  }

  deleteDataset(datasetId: string): Observable<unknown> {
    return this.http.delete(`${this.baseUrl}/datasets/${datasetId}`);
  }

  getChartData(datasetId: string, chartName: string, range?: DateRange): Observable<ChartDataResponse> {
    let params = new HttpParams();
    if (range?.from) params = params.set('date_from', range.from);
    if (range?.to) params = params.set('date_to', range.to);
    return this.http.get<ChartDataResponse>(
      `${this.baseUrl}/datasets/${datasetId}/charts/${encodeURIComponent(chartName)}/data`,
      { params }
    );
  }
}

/** Human-readable message out of any API error shape. */
export function apiErrorMessage(err: HttpErrorResponse, fallback: string): string {
  const detail = err.error?.detail;
  if (typeof detail === 'string') return detail;
  if (detail?.errors?.length) return detail.errors.join(' ');
  if (err.status === 0) return 'Can’t reach the server. Is the API running?';
  return fallback;
}
