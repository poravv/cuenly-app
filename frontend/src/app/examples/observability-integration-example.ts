// Ejemplo de integración del ObservabilityService en otros componentes
// Este es un ejemplo de cómo integrar el servicio de observabilidad en cualquier componente Angular

import { Component, OnInit } from '@angular/core';
import { ObservabilityService } from '../services/observability.service';
import { ApiService } from '../services/api.service';

@Component({
  selector: 'app-example',
  template: '<div>Ejemplo de Observabilidad</div>' // Template inline para evitar archivo externo
})
export class ExampleComponent implements OnInit {

  constructor(
    private apiService: ApiService,
    private observability: ObservabilityService
  ) {}

  ngOnInit(): void {
    // Log page view
    this.observability.logPageView('ExampleComponent');
    
    // Log component initialization
    this.observability.info('Component initialized', 'ExampleComponent');
    
    // Measure component initialization performance
    this.observability.measureOperation('component_init', 'ExampleComponent', () => {
      this.loadInitialData();
    });
  }

  private loadInitialData(): void {
    // Log user action
    this.observability.logUserAction('load_initial_data', 'ExampleComponent');

    const startTime = performance.now();
    
    this.apiService.getStatus().subscribe({
      next: (data: any) => {
        const responseTime = performance.now() - startTime;
        
        // Log successful API call
        this.observability.logApiCall('GET', '/api/status', responseTime, true, {
          status: data.status
        });
        
        // Log business event if needed
        this.observability.info('Status loaded successfully', 'ExampleComponent', {
          status: data.status
        });
      },
      error: (error: any) => {
        const responseTime = performance.now() - startTime;
        
        // Log failed API call
        this.observability.logApiCall('GET', '/api/status', responseTime, false, {
          error_message: error.message
        });
        
        // Log error with context
        this.observability.error('Failed to load status', error, 'ExampleComponent', {
          attempted_endpoint: '/api/status',
          action: 'loadInitialData'
        });
      }
    });
  }

  onUserButtonClick(): void {
    // Log user interaction
    this.observability.logUserAction('button_click', 'ExampleComponent', {
      button_id: 'main-action-btn'
    });

    // Measure performance of user action
    this.observability.measureOperation('user_action_processing', 'ExampleComponent', () => {
      this.processUserAction();
    });
  }

  private processUserAction(): void {
    try {
      // Simulate some processing
      const result = this.someBusinessLogic();
      
      // Log successful processing
      this.observability.info('User action processed successfully', 'ExampleComponent', {
        result_id: result.id,
        processing_type: 'user_interaction'
      });
      
    } catch (error) {
      // Log processing error
      this.observability.error('User action processing failed', error as Error, 'ExampleComponent', {
        action: 'processUserAction'
      });
    }
  }

  private someBusinessLogic(): any {
    // Simulate business logic
    return { id: Math.random().toString(36) };
  }

  // Example of logging form validation errors
  onFormValidationError(errors: any): void {
    this.observability.warn('Form validation failed', 'ExampleComponent', {
      validation_errors: errors,
      form_name: 'example_form'
    });
  }

  // Example of logging performance metric
  onExpensiveOperation(): void {
    const operation = this.observability.measureOperation(
      'expensive_calculation',
      'ExampleComponent',
      () => {
        // Simulate expensive operation
        let sum = 0;
        for (let i = 0; i < 1000000; i++) {
          sum += Math.random();
        }
        return sum;
      }
    );

    this.observability.debug('Expensive operation completed', 'ExampleComponent', {
      result: operation
    });
  }

  // Example of async operation logging
  async onAsyncOperation(): Promise<void> {
    try {
      const result = await this.observability.measureOperation(
        'async_data_processing',
        'ExampleComponent',
        async () => {
          // Simulate async operation
          await new Promise(resolve => setTimeout(resolve, 1000));
          return await this.apiService.getStatus().toPromise();
        }
      );

      this.observability.info('Async operation completed', 'ExampleComponent', {
        result_status: result?.status || 'unknown'
      });

    } catch (error) {
      this.observability.error('Async operation failed', error as Error, 'ExampleComponent', {
        operation: 'async_data_processing'
      });
    }
  }
}

// ========================================
// INTERCEPTOR PARA API CALLS AUTOMÁTICOS
// ========================================

import { Injectable } from '@angular/core';
import { HttpInterceptor, HttpRequest, HttpHandler, HttpEvent, HttpResponse, HttpErrorResponse } from '@angular/common/http';
import { Observable } from 'rxjs';
import { tap } from 'rxjs/operators';

@Injectable()
export class ObservabilityInterceptor implements HttpInterceptor {

  constructor() {
    // Importar dinámicamente el servicio para evitar dependencias circulares
  }

  intercept(req: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    const startTime = performance.now();
    
    return next.handle(req).pipe(
      tap(
        (event) => {
          if (event instanceof HttpResponse) {
            const duration = performance.now() - startTime;
            
            // Log básico en consola (para evitar dependencias circulares)
            console.log(`[API] ${req.method} ${req.urlWithParams} - ${duration}ms - ${event.status}`);
          }
        },
        (error) => {
          if (error instanceof HttpErrorResponse) {
            const duration = performance.now() - startTime;
            
            // Log básico en consola
            console.error(`[API ERROR] ${req.method} ${req.urlWithParams} - ${duration}ms - ${error.status}`);
          }
        }
      )
    );
  }
}

// Para registrar el interceptor en app.module.ts:
/*
import { HTTP_INTERCEPTORS } from '@angular/common/http';
import { ObservabilityInterceptor } from './interceptors/observability.interceptor';

@NgModule({
  providers: [
    {
      provide: HTTP_INTERCEPTORS,
      useClass: ObservabilityInterceptor,
      multi: true
    }
  ]
})
export class AppModule { }
*/