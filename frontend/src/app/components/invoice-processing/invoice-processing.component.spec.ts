import { ComponentFixture, TestBed } from '@angular/core/testing';

import { InvoiceProcessingComponent } from './invoice-processing.component';

describe('InvoiceProcessingComponent', () => {
  let component: InvoiceProcessingComponent;
  let fixture: ComponentFixture<InvoiceProcessingComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ InvoiceProcessingComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(InvoiceProcessingComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
