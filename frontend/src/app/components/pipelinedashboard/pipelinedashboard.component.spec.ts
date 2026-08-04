import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PipelinedashboardComponent } from './pipelinedashboard.component';

describe('PipelinedashboardComponent', () => {
  let component: PipelinedashboardComponent;
  let fixture: ComponentFixture<PipelinedashboardComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PipelinedashboardComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(PipelinedashboardComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
