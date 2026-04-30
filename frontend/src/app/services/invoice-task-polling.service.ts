import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { interval, startWith, switchMap } from 'rxjs';
import { ApiService } from './api.service';
import { TaskStatusResponse } from '../models/invoice.model';

@Injectable({ providedIn: 'root' })
export class InvoiceTaskPollingService {
  constructor(private apiService: ApiService) {}

  /** Returns an observable that polls a task until the subscriber unsubscribes. */
  pollTask(jobId: string, intervalMs: number = 2000): Observable<TaskStatusResponse> {
    return interval(intervalMs).pipe(
      startWith(0),
      switchMap(() => this.apiService.getTaskStatus(jobId))
    );
  }
}
