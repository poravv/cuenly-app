import { Component } from '@angular/core';
import { Router } from '@angular/router';

@Component({
  selector: 'app-invoices-shell',
  templateUrl: './invoices-shell.component.html',
  styleUrls: ['./invoices-shell.component.scss']
})
export class InvoicesShellComponent {
  constructor(private router: Router) { }

  isRouteActive(prefixes: string[]): boolean {
    const currentPath = this.router.url.split('?')[0];
    return prefixes.some(prefix => currentPath === prefix || currentPath.startsWith(`${prefix}/`));
  }
}

