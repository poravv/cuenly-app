import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, BehaviorSubject } from 'rxjs';
import { environment } from '../../environments/environment';

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

  constructor(private http: HttpClient) { 
    console.log('🔍 UserService: Inicializado con baseUrl:', this.baseUrl);
  }

  getUserProfile(): Observable<UserProfile> {
    // Usar /api como prefijo que ya está configurado en el proxy
    const url = `/api/user/profile`;
    console.log('🔍 UserService: Llamando a getUserProfile()');
    console.log('🔍 API URL:', url);
    return this.http.get<UserProfile>(url);
  }

  refreshUserProfile(): Observable<UserProfile> {
    return this.getUserProfile();
  }

  getCurrentProfile(): UserProfile | null {
    return this.userProfileSubject.value;
  }

  // Método para actualizar el perfil después de procesar facturas
  updateProfileAfterProcessing(): void {
    this.refreshUserProfile().subscribe({
      next: (profile) => {
        console.log('Perfil actualizado después del procesamiento', profile);
      },
      error: (error) => {
        console.error('Error actualizando perfil:', error);
      }
    });
  }
}