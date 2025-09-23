import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

export interface Notification {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  title?: string;
  message: string;
  duration?: number;
  persistent?: boolean;
  action?: {
    label: string;
    handler: () => void;
  };
}

@Injectable({
  providedIn: 'root'
})
export class NotificationService {
  private notifications$ = new BehaviorSubject<Notification[]>([]);
  
  constructor() {}

  getNotifications(): Observable<Notification[]> {
    return this.notifications$.asObservable();
  }

  private addNotification(notification: Notification): void {
    const notifications = this.notifications$.value;
    notifications.push(notification);
    this.notifications$.next(notifications);

    // Auto-remove after duration if not persistent
    if (!notification.persistent) {
      const duration = notification.duration || this.getDefaultDuration(notification.type);
      setTimeout(() => {
        this.remove(notification.id);
      }, duration);
    }
  }

  private getDefaultDuration(type: string): number {
    const durations = {
      success: 4000,
      info: 5000,
      warning: 6000,
      error: 8000
    };
    return durations[type as keyof typeof durations] || 5000;
  }

  success(message: string, title?: string, options?: Partial<Notification>): void {
    this.addNotification({
      id: this.generateId(),
      type: 'success',
      title: title || 'Éxito',
      message,
      ...options
    });
  }

  error(message: string, title?: string, options?: Partial<Notification>): void {
    this.addNotification({
      id: this.generateId(),
      type: 'error',
      title: title || 'Error',
      message,
      ...options
    });
  }

  warning(message: string, title?: string, options?: Partial<Notification>): void {
    this.addNotification({
      id: this.generateId(),
      type: 'warning',
      title: title || 'Advertencia',
      message,
      ...options
    });
  }

  info(message: string, title?: string, options?: Partial<Notification>): void {
    this.addNotification({
      id: this.generateId(),
      type: 'info',
      title: title || 'Información',
      message,
      ...options
    });
  }

  remove(id: string): void {
    const notifications = this.notifications$.value.filter(n => n.id !== id);
    this.notifications$.next(notifications);
  }

  clear(): void {
    this.notifications$.next([]);
  }

  private generateId(): string {
    return `notification_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}