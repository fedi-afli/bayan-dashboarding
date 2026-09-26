import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';

import { MappingviewComponent } from './mappingview.component';
import { ReviewResponse } from '../../models/models';

const REVIEW: ReviewResponse = {
  dataset_id: 'd1',
  filename: 'sales.csv',
  row_count: 3,
  status: 'pending',
  quote: {
    credits: 1, exact: 0.51, paid: 0, due: 1, balance: 3,
    lines: [{ key: 'base', label: 'Dashboard setup', detail: '', amount: 0.5 }],
    drivers: { rows: 3, columns: 2, cells: 6, storage_bytes: 200, ai_columns: 1 },
  },
  fields: [
    { name: 'revenue', label: 'Sales amount', type: 'float' },
    { name: 'quantity', label: 'Quantity sold', type: 'integer' },
  ],
  result: {
    mapping: { Montant: 'revenue' },
    columns: [
      { name: 'Montant', type: 'float', examples: [10], target: 'revenue', method: 'synonym', confidence: 1, review_reason: null },
      { name: 'Qte', type: 'integer', examples: [2], target: 'quantity', method: 'llm', confidence: 0.5, review_reason: 'ai_guess' },
    ],
    status: 'needs_review',
    unresolved_columns: [],
    errors: [],
    warnings: [],
    notes: [],
  },
};

describe('MappingviewComponent', () => {
  let fixture: ComponentFixture<MappingviewComponent>;
  let component: MappingviewComponent;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MappingviewComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    }).compileComponents();
    fixture = TestBed.createComponent(MappingviewComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('review', structuredClone(REVIEW));
    fixture.detectChanges();
  });

  it('lists AI guesses first and lets every column be edited', () => {
    expect(component.rows[0].column.name).toBe('Qte');
    expect(component.rows.length).toBe(2);
  });

  function withQuote(q: Partial<ReviewResponse['quote']>) {
    const review = structuredClone(REVIEW);
    review.quote = { ...review.quote, ...q };
    fixture.componentRef.setInput('review', review);
    fixture.detectChanges();
  }

  it('shows the price on the build button', () => {
    withQuote({ credits: 4, due: 4, balance: 10 });
    expect(fixture.nativeElement.textContent).toContain('Build my dashboard · 4 credits');
  });

  it('offers a top-up instead of building when the balance is too low', () => {
    withQuote({ credits: 4, due: 4, balance: 2 });
    expect(component.canAfford).toBeFalse();
    expect(fixture.nativeElement.textContent).toContain('Top up credits');
  });

  it('a rebuild that is already covered costs nothing', () => {
    withQuote({ credits: 3, paid: 3, due: 0, balance: 0 });
    expect(component.due).toBe(0);
    expect(component.canAfford).toBeTrue();
    expect(fixture.nativeElement.textContent).toContain('already covered');
  });

  it('re-quotes when a column changes', fakeAsync(() => {
    const http = TestBed.inject(HttpTestingController);
    component.rows[0].target = null;
    component.onChange(component.rows[0]);
    tick(300);
    const req = http.expectOne((r) => r.url.endsWith('/datasets/d1/quote'));
    expect(req.request.body.mapping['Qte']).toBeNull();
    req.flush({ ...REVIEW.quote, credits: 1, due: 1 });
    expect(component.quoting).toBeFalse();
  }));

  it('a column switched to "don\u2019t use" is shown as not used', () => {
    const matched = component.rows.find((r) => r.column.name === 'Montant')!;
    matched.target = null;
    component.onChange(matched);
    expect(matched.status).toBe('unmatched');
  });

  it('blocks submitting when two columns use the same field', () => {
    component.rows[0].target = 'revenue';
    expect(component.hasDuplicates).toBeTrue();
    expect(component.canSubmit).toBeFalse();
  });
});
