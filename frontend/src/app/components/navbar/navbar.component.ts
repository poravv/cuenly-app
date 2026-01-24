import { Component, OnDestroy, OnInit } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { SystemStatus } from '../../models/invoice.model';
import { AuthService } from '../../services/auth.service';
import { UserService, UserProfile } from '../../services/user.service';
import { FirebaseService } from '../../services/firebase.service';
import { AvatarCacheService } from '../../services/avatar-cache.service';
import { User } from 'firebase/auth';
import { Router } from '@angular/router';
import { ToastrService } from 'ngx-toastr';
import { FileTransferService } from '../../services/file-transfer.service';

@Component({
  selector: 'app-navbar',
  templateUrl: './navbar.component.html',
  styleUrls: ['./navbar.component.scss']
})
export class NavbarComponent implements OnInit, OnDestroy {
  status: SystemStatus | null = null;
  // Estado del Modal de Carga
  isUploading = false;
  uploadState: 'processing' | 'success' | 'error' = 'processing';
  uploadMessage = '';
  uploadedInvoiceId?: string;

  private intervalId: any;
  user: User | null = null;
  userProfile: UserProfile | null = null;
  isProfileDropdownOpen = false;
  
  // Control de imagen de perfil
  profileImageFailed = false;
  cachedAvatarUrl: string | null = null;

  constructor(
    private api: ApiService,
    private auth: AuthService,
    private userService: UserService,
    private router: Router,
    private firebase: FirebaseService,
    private toastr: ToastrService,
    private fileTransfer: FileTransferService,
    private avatarCache: AvatarCacheService
  ) { }

  ngOnInit(): void {
    // Hacer el componente accesible globalmente para debugging
    (window as any).navbarComponent = this;
    
    // Cargar avatar cacheado si existe
    this.cachedAvatarUrl = this.avatarCache.getCachedAvatar();

    // Reaccionar a cambios de autenticación
    this.auth.user$.subscribe(u => {
      this.user = u;
      if (u) {
        this.loadStatus();
        this.loadUserProfile();
        // Resetear estado de imagen al cambiar de usuario
        this.profileImageFailed = false;
        if (!this.intervalId) this.intervalId = setInterval(() => this.loadStatus(), 30000);
      } else {
        if (this.intervalId) { clearInterval(this.intervalId); this.intervalId = null; }
        this.status = null;
        this.userProfile = null;
        this.profileImageFailed = false;
        this.cachedAvatarUrl = null;
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
    if (this.router.url === '/profile') {
      return;
    }
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
  onImageLoad(location: string, event?: any): void {
    console.log(`✅ Imagen cargada correctamente en: ${location}`);
    
    // Intentar cachear la imagen cuando carga exitosamente
    if (event?.target && !this.avatarCache.hasCachedAvatar()) {
      this.avatarCache.cacheFromImageElement(event.target);
      this.cachedAvatarUrl = this.avatarCache.getCachedAvatar();
    }
    
    // Asegurar que no está marcada como fallida
    this.profileImageFailed = false;
  }

  onImageError(location: string, event: any): void {
    console.error(`❌ Error cargando imagen en: ${location}`, event);
    console.error('URL de la imagen que falló:', event.target?.src);
    
    // Marcar la URL como fallida y ocultar la imagen rota
    const failedUrl = event.target?.src;
    if (failedUrl) {
      this.avatarCache.markAsFailed(failedUrl);
    }
    
    // Ocultar la imagen rota
    if (event.target) {
      event.target.style.display = 'none';
    }
    
    // Mostrar placeholder
    this.profileImageFailed = true;
  }
  
  /**
   * Obtiene la URL del avatar a mostrar (cacheada o original)
   */
  getAvatarUrl(): string | null {
    // Prioridad: caché local > perfil API > Firebase
    if (this.cachedAvatarUrl) {
      return this.cachedAvatarUrl;
    }
    return this.userProfile?.picture || this.user?.photoURL || null;
  }
  
  /**
   * Determina si se debe mostrar el placeholder en lugar de la imagen
   */
  shouldShowPlaceholder(): boolean {
    return this.profileImageFailed || !this.getAvatarUrl();
  }

  async onFileSelected(event: any): Promise<void> {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    // Convertir FileList a Array
    const fileList: File[] = Array.from(files);

    // Validar extensiones
    const validFiles: File[] = [];
    let hasInvalid = false;

    for (const file of fileList) {
      const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
      const isXml = file.type === 'text/xml' || file.type === 'application/xml' || file.name.toLowerCase().endsWith('.xml');
      const isImage = file.type.startsWith('image/') || /\.(jpg|jpeg|png|webp)$/i.test(file.name);

      if (isPdf || isXml || isImage) {
        if (file.size <= 10 * 1024 * 1024) {
          validFiles.push(file);
        } else {
          this.toastr.warning(`El archivo ${file.name} es demasiado grande (max 10MB) y fue omitido.`);
        }
      } else {
        hasInvalid = true;
      }
    }

    if (hasInvalid) {
      this.toastr.warning('Algunos archivos tienen formato no soportado (use PDF, XML o Imágenes) y fueron omitidos.');
    }

    if (validFiles.length === 0) {
      event.target.value = '';
      return;
    }

    // Redirigir a página de carga masiva
    this.fileTransfer.setFiles(validFiles);

    // Determinar a dónde redirigir basado en el tipo predominante
    const xmlCount = validFiles.filter(f => f.name.toLowerCase().endsWith('.xml')).length;

    // Si la mayoría son XML, ir a upload-xml, si no, ir a upload (PDF/Images)
    if (xmlCount > validFiles.length / 2) {
      this.router.navigate(['/upload-xml']);
    } else {
      this.router.navigate(['/upload']);
    }

    // Reset input
    event.target.value = '';
  }

  closeUploadModal(): void {
    if (this.uploadState === 'success' && this.uploadedInvoiceId) {
      this.router.navigate(['/invoice-explorer']);
    }
    this.isUploading = false;
    this.uploadState = 'processing';
    this.uploadMessage = '';
    this.uploadedInvoiceId = undefined;
  }
}
