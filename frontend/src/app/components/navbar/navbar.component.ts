import { Component, OnDestroy, OnInit } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { SystemStatus } from '../../models/invoice.model';
import { AuthService } from '../../services/auth.service';
import { UserService, UserProfile } from '../../services/user.service';
import { FirebaseService } from '../../services/firebase.service';
import { User } from 'firebase/auth';
import { Router } from '@angular/router';

@Component({
  selector: 'app-navbar',
  templateUrl: './navbar.component.html',
  styleUrls: ['./navbar.component.scss']
})
export class NavbarComponent implements OnInit, OnDestroy {
  status: SystemStatus | null = null;
  private intervalId: any;
  user: User | null = null;
  userProfile: UserProfile | null = null;
  isProfileDropdownOpen = false;

  constructor(
    private api: ApiService, 
    private auth: AuthService, 
    private userService: UserService,
    private router: Router,
    private firebase: FirebaseService
  ) {}

  ngOnInit(): void {
    // Hacer el componente accesible globalmente para debugging
    (window as any).navbarComponent = this;
    
    // Reaccionar a cambios de autenticación
    this.auth.user$.subscribe(u => {
      this.user = u;
      if (u) {
        this.loadStatus();
        this.loadUserProfile();
        if (!this.intervalId) this.intervalId = setInterval(() => this.loadStatus(), 30000);
      } else {
        if (this.intervalId) { clearInterval(this.intervalId); this.intervalId = null; }
        this.status = null;
        this.userProfile = null;
      }
    });

    // Suscribirse a cambios de perfil publicados por UserService
    this.userService.userProfile$.subscribe(profile => {
      if (profile) {
        this.userProfile = profile;
      }
    });
  }

  ngOnDestroy(): void {
    if (this.intervalId) clearInterval(this.intervalId);
  }

  private loadStatus(): void {
    this.api.getStatus().subscribe({
      next: (s) => (this.status = s),
      error: () => (this.status = this.status) // keep last
    });
  }

  signIn(): void { this.auth.signInWithGoogle(); }
  
  async signOut(): Promise<void> {
    try {
      console.log('🔐 Cerrando sesión...');
      
      // Track logout
      this.firebase.trackLogout();
      
      await this.auth.signOut();
      console.log('✅ Sesión cerrada correctamente');
      
      // Pequeña pausa para asegurar que la limpieza esté completa
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // Opcional: Mostrar mensaje al usuario
      console.log('💡 La próxima vez que inicies sesión podrás seleccionar una cuenta diferente');
      
    } catch (error) {
      console.error('❌ Error al cerrar sesión:', error);
    } finally {
      // Siempre redirigir al login, incluso si hay error
      console.log('🔄 Redirigiendo al login...');
      this.router.navigateByUrl('/login');
    }
  }

  private loadUserProfile(): void {
    console.log('🔍 NavbarComponent: Cargando perfil de usuario...');
    this.userService.getUserProfile().subscribe({
      next: (profile) => {
        console.log('✅ NavbarComponent: Perfil recibido:', profile);
        console.log('🔍 Trial info:', {
          is_trial: profile.is_trial,
          trial_expired: profile.trial_expired,
          trial_days_remaining: profile.trial_days_remaining
        });
        console.log('🔍 Profile picture from API:', profile.picture);
        console.log('🔍 Profile picture from Firebase:', this.user?.photoURL);
        this.userProfile = profile;
      },
      error: (error: any) => {
        console.error('❌ NavbarComponent: Error cargando perfil:', error);
      }
    });
  }

  toggleProfileDropdown(): void {
    this.isProfileDropdownOpen = !this.isProfileDropdownOpen;
  }

  // Método para debugging - puede ser llamado desde la consola del navegador
  public debugUserProfile(): void {
    console.log('🔍 DEBUG: Estado actual del navbar');
    console.log('Firebase User:', this.user);
    console.log('UserProfile:', this.userProfile);
    console.log('Cargando perfil manualmente...');
    this.loadUserProfile();
  }

  // Métodos para debugging de imágenes
  onImageLoad(location: string): void {
    console.log(`✅ Imagen cargada correctamente en: ${location}`);
  }

  onImageError(location: string, event: any): void {
    console.error(`❌ Error cargando imagen en: ${location}`, event);
    console.error('URL de la imagen que falló:', event.target?.src);
  }
}
