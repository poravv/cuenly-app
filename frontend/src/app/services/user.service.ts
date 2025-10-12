import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, BehaviorSubject } from 'rxjs';
import { tap } from 'rxjs/operators';
import { environment } from '../../environments/environment';
import { ObservabilityService } from './observability.service';

export interface UserProfile {
  email: string;
  name: string;
  picture: string;
  role: string;
  is_admin: boolean;
  status: string;
  is_trial: boolean;
  trial_expires_at: string | null;
  trial_expired: boolean;
  trial_days_remaining: number;
  can_process: boolean;
  ai_invoices_processed: number;
  ai_invoices_limit: number;
  ai_limit_reached: boolean;
  email_processing_start_date?: string;
}

@Injectable({
  providedIn: 'root'
})
export class UserService {
  private baseUrl = environment.apiUrl;
  private userProfileSubject = new BehaviorSubject<UserProfile | null>(null);
  public userProfile$ = this.userProfileSubject.asObservable();

  constructor(
    private http: HttpClient,
    private observability: ObservabilityService
  ) { 
    this.observability.info('UserService initialized', 'UserService', {
      base_url: this.baseUrl
    });
  }

  getUserProfile(): Observable<UserProfile> {
    // Usar /api como prefijo que ya está configurado en el proxy
    const url = `/api/user/profile`;
    
    // Log API call initiation
    this.observability.debug('Calling getUserProfile', 'UserService', {
      api_url: url,
      action: 'get_user_profile'
    });
    const startTime = performance.now();
    
    return this.http.get<UserProfile>(url).pipe(
      tap({
        next: (profile) => {
          const responseTime = performance.now() - startTime;
          
          // Log successful API call
          this.observability.logApiCall('GET', url, responseTime, true, {
            user_email: profile.email,
            is_trial: profile.is_trial,
            trial_expired: profile.trial_expired,
            ai_limit_reached: profile.ai_limit_reached
          });
          
          // Publicar el perfil para que otros componentes reaccionen (navbar, banners)
          this.userProfileSubject.next(profile);
          
          this.observability.debug('User profile loaded successfully', 'UserService', {
            user_email: profile.email,
            status: profile.status,
            role: profile.role
          });
        },
        error: (error) => {
          const responseTime = performance.now() - startTime;
          
          this.observability.logApiCall('GET', url, responseTime, false, {
            error_message: error.message,
            status_code: error.status
          });
          
          this.observability.error('Failed to load user profile', error, 'UserService', {
            api_url: url,
            action: 'get_user_profile'
          });
        }
      })
    );
  }

  refreshUserProfile(): Observable<UserProfile> {
    this.observability.debug('Refreshing user profile', 'UserService', {
      action: 'refresh_user_profile'
    });
    return this.getUserProfile();
  }

  getCurrentProfile(): UserProfile | null {
    return this.userProfileSubject.value;
  }

  // Método para actualizar el perfil después de procesar facturas
  updateProfileAfterProcessing(): void {
    this.observability.debug('Updating profile after processing', 'UserService', {
      action: 'update_profile_after_processing'
    });
    
    this.refreshUserProfile().subscribe({
      next: (profile) => {
        this.observability.info('Profile updated after processing', 'UserService', {
          user_email: profile.email,
          ai_invoices_processed: profile.ai_invoices_processed,
          ai_invoices_limit: profile.ai_invoices_limit,
          ai_limit_reached: profile.ai_limit_reached
        });
      },
      error: (error) => {
        this.observability.error('Error updating profile after processing', error, 'UserService', {
          action: 'update_profile_after_processing'
        });
      }
    });
  }
}
