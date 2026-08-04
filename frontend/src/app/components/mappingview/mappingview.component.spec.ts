import { ComponentFixture, TestBed } from '@angular/core/testing';

import { MappingviewComponent } from './mappingview.component';

describe('MappingviewComponent', () => {
  let component: MappingviewComponent;
  let fixture: ComponentFixture<MappingviewComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MappingviewComponent]
    })
    .compileComponents();
    
    fixture = TestBed.createComponent(MappingviewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
