import { Injectable, NgZone } from '@angular/core';
import { environment } from '../../environments/environment';
import { BehaviorSubject, Observable } from 'rxjs';

import { initializeApp, getApps, FirebaseApp } from 'firebase/app';
import {
  getAuth,
  onAuthStateChanged,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
  User,
  Auth
} from 'firebase/auth';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private app: FirebaseApp;
  private auth: Auth;
  private userSubject = new BehaviorSubject<User | null>(null);
  user$: Observable<User | null> = this.userSubject.asObservable();
  private readySubject = new BehaviorSubject<boolean>(false);
  ready$: Observable<boolean> = this.readySubject.asObservable();

  constructor(private zone: NgZone) {
    this.app = getApps().length ? getApps()[0] : initializeApp(environment.firebase);
    this.auth = getAuth(this.app);
    onAuthStateChanged(this.auth, (user: User | null) => {
      // Asegurar cambio dentro de Angular zone
      this.zone.run(() => {
        this.userSubject.next(user);
        this.readySubject.next(true);
      });
    });
  }

  async signInWithGoogle(): Promise<void> {
    const provider = new GoogleAuthProvider();
    
    // Forzar la selección de cuenta en cada login
    provider.setCustomParameters({
      prompt: 'select_account'  // Esto fuerza a Google a mostrar el selector de cuentas
    });
    
    await signInWithPopup(this.auth, provider);
  }

  async signOut(): Promise<void> {
    try {
      // Limpiar Firebase Auth
      await signOut(this.auth);
      
      // Limpiar localStorage y sessionStorage
      localStorage.clear();
      sessionStorage.clear();
      
      // Limpiar cookies de autenticación de Google
      this.clearGoogleAuthCookies();
      
    } catch (error) {
      console.error('Error during sign out:', error);
      // Incluso si hay error, limpiamos todo localmente
      localStorage.clear();
      sessionStorage.clear();
      this.clearGoogleAuthCookies();
    }
  }

  private clearGoogleAuthCookies(): void {
    // Lista de cookies comunes de Google Auth
    const googleCookies = [
      '__Secure-1PSID',
      '__Secure-3PSID', 
      '__Secure-1PAPISID',
      '__Secure-3PAPISID',
      'HSID',
      'SSID', 
      'APISID',
      'SAPISID',
      '1P_JAR',
      'NID'
    ];

    // Intentar limpiar cookies de Google
    googleCookies.forEach(cookieName => {
      // Para el dominio actual
      document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; domain=${window.location.hostname}`;
      // Para Google domains
      document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; domain=.google.com`;
      document.cookie = `${cookieName}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; domain=.accounts.google.com`;
    });
  }

  getCurrentUser(): User | null {
    return this.auth.currentUser;
  }

  async getIdToken(): Promise<string | null> {
    const u = this.auth.currentUser;
    if (!u) return null;
    return await u.getIdToken();
  }
}
