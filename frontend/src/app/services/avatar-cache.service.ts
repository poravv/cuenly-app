import { Injectable } from '@angular/core';

/**
 * Servicio para cachear URLs de avatares de Google y manejar fallbacks.
 * Evita el error 429 (Too Many Requests) de Google al cachear la imagen localmente.
 */
@Injectable({
  providedIn: 'root'
})
export class AvatarCacheService {
  private readonly CACHE_KEY = 'cuenly_avatar_cache';
  private readonly CACHE_EXPIRY_KEY = 'cuenly_avatar_cache_expiry';
  private readonly CACHE_DURATION_MS = 24 * 60 * 60 * 1000; // 24 horas
  private readonly FAILED_URLS_KEY = 'cuenly_avatar_failed_urls';
  
  private cachedDataUrl: string | null = null;
  private failedUrls: Set<string> = new Set();

  constructor() {
    this.loadFromLocalStorage();
    this.loadFailedUrls();
  }

  /**
   * Obtiene la URL del avatar, ya sea desde caché o la original
   */
  getAvatarUrl(originalUrl: string | null | undefined): string | null {
    if (!originalUrl) return null;
    
    // Si la URL falló anteriormente, retornar null para usar placeholder
    if (this.failedUrls.has(originalUrl)) {
      return null;
    }
    
    // Si tenemos una versión cacheada y no está expirada, usarla
    if (this.cachedDataUrl && !this.isCacheExpired()) {
      return this.cachedDataUrl;
    }
    
    return originalUrl;
  }

  /**
   * Marca una URL como fallida para no intentar cargarla de nuevo
   */
  markAsFailed(url: string): void {
    if (!url) return;
    this.failedUrls.add(url);
    this.saveFailedUrls();
  }

  /**
   * Almacena una imagen cargada exitosamente como data URL
   */
  async cacheAvatar(imageUrl: string): Promise<void> {
    if (!imageUrl || this.failedUrls.has(imageUrl)) return;
    
    try {
      const response = await fetch(imageUrl, { mode: 'cors' });
      if (!response.ok) {
        this.markAsFailed(imageUrl);
        return;
      }
      
      const blob = await response.blob();
      const reader = new FileReader();
      
      return new Promise((resolve) => {
        reader.onloadend = () => {
          const dataUrl = reader.result as string;
          this.cachedDataUrl = dataUrl;
          this.saveToLocalStorage(dataUrl);
          resolve();
        };
        reader.onerror = () => {
          this.markAsFailed(imageUrl);
          resolve();
        };
        reader.readAsDataURL(blob);
      });
    } catch (error) {
      console.warn('⚠️ No se pudo cachear avatar:', error);
      this.markAsFailed(imageUrl);
    }
  }

  /**
   * Cachea un avatar usando un elemento img existente (más confiable para CORS)
   */
  cacheFromImageElement(img: HTMLImageElement): void {
    try {
      const canvas = document.createElement('canvas');
      canvas.width = img.naturalWidth || 96;
      canvas.height = img.naturalHeight || 96;
      
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      
      ctx.drawImage(img, 0, 0);
      
      const dataUrl = canvas.toDataURL('image/png');
      this.cachedDataUrl = dataUrl;
      this.saveToLocalStorage(dataUrl);
      
      console.log('✅ Avatar cacheado exitosamente');
    } catch (error) {
      // CORS puede bloquear esto, es esperado
      console.warn('⚠️ No se pudo cachear avatar desde img (CORS)');
    }
  }

  /**
   * Verifica si tenemos un avatar válido en caché
   */
  hasCachedAvatar(): boolean {
    return !!this.cachedDataUrl && !this.isCacheExpired();
  }

  /**
   * Obtiene el avatar cacheado
   */
  getCachedAvatar(): string | null {
    if (this.isCacheExpired()) {
      this.clearCache();
      return null;
    }
    return this.cachedDataUrl;
  }

  /**
   * Limpia el caché
   */
  clearCache(): void {
    this.cachedDataUrl = null;
    localStorage.removeItem(this.CACHE_KEY);
    localStorage.removeItem(this.CACHE_EXPIRY_KEY);
  }

  /**
   * Limpia las URLs fallidas (útil para reintentar)
   */
  clearFailedUrls(): void {
    this.failedUrls.clear();
    localStorage.removeItem(this.FAILED_URLS_KEY);
  }

  private loadFromLocalStorage(): void {
    try {
      const cached = localStorage.getItem(this.CACHE_KEY);
      if (cached && !this.isCacheExpired()) {
        this.cachedDataUrl = cached;
      } else {
        this.clearCache();
      }
    } catch (error) {
      console.warn('⚠️ Error cargando avatar desde localStorage');
    }
  }

  private saveToLocalStorage(dataUrl: string): void {
    try {
      localStorage.setItem(this.CACHE_KEY, dataUrl);
      localStorage.setItem(this.CACHE_EXPIRY_KEY, (Date.now() + this.CACHE_DURATION_MS).toString());
    } catch (error) {
      console.warn('⚠️ Error guardando avatar en localStorage');
    }
  }

  private isCacheExpired(): boolean {
    try {
      const expiry = localStorage.getItem(this.CACHE_EXPIRY_KEY);
      if (!expiry) return true;
      return Date.now() > parseInt(expiry, 10);
    } catch {
      return true;
    }
  }

  private loadFailedUrls(): void {
    try {
      const failed = localStorage.getItem(this.FAILED_URLS_KEY);
      if (failed) {
        const urls = JSON.parse(failed) as string[];
        this.failedUrls = new Set(urls);
      }
    } catch {
      this.failedUrls = new Set();
    }
  }

  private saveFailedUrls(): void {
    try {
      localStorage.setItem(this.FAILED_URLS_KEY, JSON.stringify([...this.failedUrls]));
    } catch {
      // Ignorar errores de localStorage
    }
  }
}
