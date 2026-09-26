import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';

import { PipelineService } from './pipeline.service';

describe('PipelineService', () => {
  let service: PipelineService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(PipelineService);
    http = TestBed.inject(HttpTestingController);
  });

  it('sends the date range as query params', () => {
    service.getChartData('abc', 'trend', { from: '2024-01-01', to: '2024-03-31' }).subscribe();
    const req = http.expectOne((r) => r.url.endsWith('/datasets/abc/charts/trend/data'));
    expect(req.request.params.get('date_from')).toBe('2024-01-01');
    expect(req.request.params.get('date_to')).toBe('2024-03-31');
    req.flush({ chart: {}, data: {} });
  });

  it('omits empty date bounds', () => {
    service.getChartData('abc', 'trend', { from: null, to: null }).subscribe();
    const req = http.expectOne((r) => r.url.endsWith('/charts/trend/data'));
    expect(req.request.params.keys()).toEqual([]);
    req.flush({ chart: {}, data: {} });
  });
});
