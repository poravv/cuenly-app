import { Component, OnInit, OnDestroy, HostListener } from '@angular/core';
import { Router, NavigationEnd } from '@angular/router';
import { Subscription } from 'rxjs';
import { filter } from 'rxjs/operators';

interface MenuItem {
  path: string;
  icon: string;
  label: string;
}

@Component({
  selector: 'app-admin-layout',
  templateUrl: './admin-layout.component.html',
  styleUrls: ['./admin-layout.component.scss']
})
export class AdminLayoutComponent implements OnInit, OnDestroy {
  sidebarOpen = true;
  currentRoute = 'dashboard';
  isMobile = false;

  menuItems: MenuItem[] = [
    { path: 'dashboard', icon: 'bi-speedometer2', label: 'Dashboard' },
    { path: 'usuarios', icon: 'bi-people', label: 'Usuarios' },
    { path: 'planes', icon: 'bi-credit-card', label: 'Planes' },
    { path: 'suscripciones', icon: 'bi-receipt', label: 'Suscripciones' },
    { path: 'sistema', icon: 'bi-gear', label: 'Sistema' },
    { path: 'auditoria', icon: 'bi-shield-check', label: 'Auditoría' },
  ];

  private routerSub!: Subscription;

  constructor(private router: Router) {}

  ngOnInit(): void {
    this.checkMobile();
    if (this.isMobile) this.sidebarOpen = false;

    // Track current route
    this.routerSub = this.router.events.pipe(
      filter((e): e is NavigationEnd => e instanceof NavigationEnd)
    ).subscribe(event => {
      const segments = event.urlAfterRedirects.split('/');
      this.currentRoute = segments[segments.length - 1] || 'dashboard';
      if (this.isMobile) this.sidebarOpen = false;
    });

    // Set initial route
    const segments = this.router.url.split('/');
    this.currentRoute = segments[segments.length - 1] || 'dashboard';
  }

  ngOnDestroy(): void {
    this.routerSub?.unsubscribe();
  }

  @HostListener('window:resize')
  onResize(): void {
    this.checkMobile();
    if (this.isMobile) this.sidebarOpen = false;
    else this.sidebarOpen = true;
  }

  private checkMobile(): void {
    this.isMobile = window.innerWidth < 768;
  }

  toggleSidebar(): void {
    this.sidebarOpen = !this.sidebarOpen;
  }

  closeSidebar(): void {
    if (this.isMobile) this.sidebarOpen = false;
  }

  isActive(path: string): boolean {
    return this.currentRoute === path;
  }

  trackByPath(_index: number, item: MenuItem): string {
    return item.path;
  }
}
