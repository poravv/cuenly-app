import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { InvoiceProcessingComponent } from './components/invoice-processing/invoice-processing.component';
import { UploadComponent } from './components/upload/upload.component';
import { UploadXmlComponent } from './components/upload-xml/upload-xml.component';
import { EmailConfigComponent } from './components/email-config/email-config.component';
import { HelpComponent } from './components/help/help.component';
import { InvoiceExplorerComponent } from './components/invoice-explorer/invoice-explorer.component';
import { InvoicesV2Component } from './components/invoices-v2/invoices-v2.component';
import { LoginComponent } from './components/login/login.component';
import { SubscriptionComponent } from './components/subscription/subscription.component';
import { ExportTemplatesComponent } from './components/export-templates/export-templates.component';
import { TemplateEditorComponent } from './components/export-templates/template-editor.component';
import { TemplateExportComponent } from './components/export-templates/template-export.component';
import { AuthGuard } from './guards/auth.guard';
import { ProfileGuard } from './guards/profile.guard';
import { LoginGuard } from './guards/login.guard';
import { SuspendedComponent } from './components/suspended/suspended.component';
import { AdminGuard } from './guards/admin.guard';
import { PagoparResultComponent } from './components/pagopar-result/pagopar-result.component';

import { PaymentMethodsComponent } from './components/payment-methods/payment-methods.component';
import { ProfileComponent } from './components/profile/profile.component';
import { QueueEventsComponent } from './components/profile/queue-events.component';
import { TermsConditionsComponent } from './components/legal/terms-conditions.component';
import { PrivacyPolicyComponent } from './components/legal/privacy-policy.component';
import { DataRetentionComponent } from './components/legal/data-retention.component';
import { InvoicesShellComponent } from './components/invoices-shell/invoices-shell.component';
import { InvoicesStatsComponent } from './components/invoices-stats/invoices-stats.component';

const routes: Routes = [
  { path: 'login', component: LoginComponent, canActivate: [LoginGuard] },
  { path: 'suspended', component: SuspendedComponent },
  { path: '', component: DashboardComponent, canActivate: [AuthGuard] },

  // Nueva arquitectura de navegación (P1)
  {
    path: 'facturas',
    component: InvoicesShellComponent,
    canActivate: [AuthGuard],
    children: [
      { path: '', redirectTo: 'todas', pathMatch: 'full' },
      { path: 'todas', component: InvoicesV2Component },
      { path: 'explorador', component: InvoiceExplorerComponent },
      { path: 'estadisticas', component: InvoicesStatsComponent },
      { path: 'subir', component: UploadComponent },
      { path: 'subir-xml', component: UploadXmlComponent },
      { path: 'exportar', component: ExportTemplatesComponent },
      { path: 'exportar/new', component: TemplateEditorComponent },
      { path: 'exportar/create', component: TemplateEditorComponent },
      { path: 'exportar/edit/:id', component: TemplateEditorComponent },
      { path: 'exportar/export/:id', component: TemplateExportComponent },
      { path: 'exportar/export', component: TemplateExportComponent },
    ]
  },

  { path: 'automatizacion', redirectTo: 'automatizacion/procesamiento', pathMatch: 'full' },
  { path: 'automatizacion/procesamiento', component: InvoiceProcessingComponent, canActivate: [AuthGuard] },
  { path: 'automatizacion/correos', component: EmailConfigComponent, canActivate: [AuthGuard] },
  { path: 'automatizacion/cola', component: QueueEventsComponent, canActivate: [AuthGuard] },

  { path: 'cuenta', redirectTo: 'cuenta/perfil', pathMatch: 'full' },
  { path: 'cuenta/perfil', component: ProfileComponent, canActivate: [AuthGuard] },
  { path: 'cuenta/suscripcion', component: SubscriptionComponent, canActivate: [AuthGuard, ProfileGuard] },
  { path: 'cuenta/pagos', component: PaymentMethodsComponent, canActivate: [AuthGuard, ProfileGuard] },
  { path: 'cuenta/ayuda', component: HelpComponent, canActivate: [AuthGuard] },

  // Compatibilidad con rutas legacy
  { path: 'manage-invoices', redirectTo: 'automatizacion/procesamiento', pathMatch: 'full' },
  { path: 'upload', redirectTo: 'facturas/subir', pathMatch: 'full' },
  { path: 'upload-xml', redirectTo: 'facturas/subir-xml', pathMatch: 'full' },
  { path: 'invoice-explorer', redirectTo: 'facturas/explorador', pathMatch: 'full' },
  { path: 'invoice-list', redirectTo: 'facturas/todas', pathMatch: 'full' },
  { path: 'email-settings', redirectTo: 'automatizacion/correos', pathMatch: 'full' },
  { path: 'templates-export', redirectTo: 'facturas/exportar', pathMatch: 'full' },
  { path: 'templates-export/new', redirectTo: 'facturas/exportar/new', pathMatch: 'full' },
  { path: 'templates-export/create', redirectTo: 'facturas/exportar/create', pathMatch: 'full' },
  { path: 'templates-export/edit/:id', redirectTo: 'facturas/exportar/edit/:id', pathMatch: 'full' },
  { path: 'templates-export/export/:id', redirectTo: 'facturas/exportar/export/:id', pathMatch: 'full' },
  { path: 'templates-export/export', redirectTo: 'facturas/exportar/export', pathMatch: 'full' },
  { path: 'subscription', redirectTo: 'cuenta/suscripcion', pathMatch: 'full' },
  { path: 'payment-methods', redirectTo: 'cuenta/pagos', pathMatch: 'full' },
  { path: 'profile', redirectTo: 'cuenta/perfil', pathMatch: 'full' },
  { path: 'profile/queue', redirectTo: 'automatizacion/cola', pathMatch: 'full' },
  { path: 'ayuda', redirectTo: 'cuenta/ayuda', pathMatch: 'full' },

  {
    path: 'admin',
    loadChildren: () => import('./modules/admin/admin.module').then(m => m.AdminModule),
    canActivate: [AuthGuard, AdminGuard]
  },
  { path: 'terms', component: TermsConditionsComponent },
  { path: 'privacy', component: PrivacyPolicyComponent },
  { path: 'retention', component: DataRetentionComponent },
  { path: 'pagopar/resultado/:hash', component: PagoparResultComponent, canActivate: [AuthGuard] },
  { path: '**', redirectTo: '', pathMatch: 'full' }
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
