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
  phone?: string;
  ruc?: string;
  address?: string;
  city?: string;
  document_type?: string;
}

// Interface for profile completeness status
export interface ProfileStatus {
  is_complete: boolean;
  missing_fields: string[];
  required_for_subscription: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class UserService {
  private baseUrl = environment.apiUrl;
  private userProfileSubject = new BehaviorSubject<UserProfile | null>(null);
  public userProfile$ = this.userProfileSubject.asObservable();

  // Flag to know if the user is editing their profile
  private isEditingProfile = false;

  constructor(
    private http: HttpClient,
    private observability: ObservabilityService
  ) {
    this.observability.info('UserService initialized', 'UserService', {
      base_url: this.baseUrl
    });
  }

  setEditingProfile(editing: boolean): void {
    this.isEditingProfile = editing;
    this.observability.debug(`Profile editing state set to: ${editing}`, 'UserService');
  }

  isProfileBeingEdited(): boolean {
    return this.isEditingProfile;
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
          // SOLO si no se está editando el perfil para evitar sobrescribir datos
          if (!this.isEditingProfile) {
            this.userProfileSubject.next(profile);
          } else {
            this.observability.debug('Skipping userProfileSubject update because user is editing profile', 'UserService');
          }

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
    if (this.isEditingProfile) {
      this.observability.debug('Skipping profile refresh because user is editing profile', 'UserService');
      // Return current value as observable to satisfy return type, but don't hit API
      // If current value is null, we might need to hit API anyway? 
      // Better to just not do anything if editing, or return EMPTY?
      // Let's defer to getUserProfile which now has the logic to NOT update the subject
      // But we still want to avoid the network call if possible?
      // Actually, sometimes we might need the data in background. 
      // The implementation in getUserProfile handles the "don't overwrite UI" part.
      // So we can still fetch fresh data, just not push it to the subject if editing.
    }

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

  /**
   * NUEVO: Asegurar que el usuario existe en Pagopar
   * Se llama automáticamente después del login de Firebase
   */
  ensurePagoparCustomer(): Observable<any> {
    const url = `/api/subscriptions/ensure-customer`;

    this.observability.debug('Ensuring Pagopar customer', 'UserService', {
      action: 'ensure_pagopar_customer'
    });

    return this.http.post(url, {}).pipe(
      tap({
        next: (response: any) => {
          this.observability.info('Pagopar customer ensured', 'UserService', {
            pagopar_user_id: response.pagopar_user_id,
            already_exists: response.already_exists
          });
        },
        error: (error) => {
          this.observability.error('Error ensuring Pagopar customer', error, 'UserService', {
            action: 'ensure_pagopar_customer'
          });
        }
      })
    );
  }

  updateUserProfile(profileData: Partial<UserProfile>): Observable<any> {
    const url = `/api/user/profile`;
    this.observability.debug('Updating user profile', 'UserService', { profileData });
    return this.http.put(url, profileData).pipe(
      tap({
        next: () => {
          this.observability.info('User profile updated successfully', 'UserService');
          this.refreshUserProfile().subscribe();
        },
        error: (error) => {
          this.observability.error('Error updating user profile', error, 'UserService');
        }
      })
    );
  }

  checkProfileCompleteness(): Observable<ProfileStatus> {
    const url = `/api/user/profile/status`;
    this.observability.debug('Checking profile completeness', 'UserService');
    return this.http.get<ProfileStatus>(url).pipe(
      tap({
        next: (status) => {
          this.observability.debug('Profile status checked', 'UserService', { status });
        },
        error: (error) => {
          this.observability.error('Error checking profile status', error, 'UserService');
        }
      })
    );
  }
}
