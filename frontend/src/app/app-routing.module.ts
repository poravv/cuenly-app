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
import { LoginGuard } from './guards/login.guard';
import { SuspendedComponent } from './components/suspended/suspended.component';
import { AdminGuard } from './guards/admin.guard';
import { AdminPanelComponent } from './components/admin-panel/admin-panel.component';
import { PlansManagementComponent } from './components/plans-management/plans-management.component';
import { PaymentMethodsComponent } from './components/payment-methods/payment-methods.component';
import { ProfileComponent } from './components/profile/profile.component';

const routes: Routes = [
  { path: 'login', component: LoginComponent, canActivate: [LoginGuard] },
  { path: 'suspended', component: SuspendedComponent },
  { path: '', component: DashboardComponent, canActivate: [AuthGuard] },
  { path: 'manage-invoices', component: InvoiceProcessingComponent, canActivate: [AuthGuard] },
  { path: 'upload', component: UploadComponent, canActivate: [AuthGuard] },
  { path: 'upload-xml', component: UploadXmlComponent, canActivate: [AuthGuard] },
  { path: 'invoice-explorer', component: InvoiceExplorerComponent, canActivate: [AuthGuard] },
  { path: 'invoice-list', component: InvoicesV2Component, canActivate: [AuthGuard] },
  { path: 'email-settings', component: EmailConfigComponent, canActivate: [AuthGuard] },
  { path: 'templates-export', component: ExportTemplatesComponent, canActivate: [AuthGuard] },
  { path: 'templates-export/new', component: TemplateEditorComponent, canActivate: [AuthGuard] },
  { path: 'templates-export/create', component: TemplateEditorComponent, canActivate: [AuthGuard] },
  { path: 'templates-export/edit/:id', component: TemplateEditorComponent, canActivate: [AuthGuard] },
  { path: 'templates-export/export/:id', component: TemplateExportComponent, canActivate: [AuthGuard] },
  { path: 'templates-export/export', component: TemplateExportComponent, canActivate: [AuthGuard] },
  { path: 'subscription', component: SubscriptionComponent, canActivate: [AuthGuard] },
  { path: 'payment-methods', component: PaymentMethodsComponent, canActivate: [AuthGuard] },
  { path: 'profile', component: ProfileComponent, canActivate: [AuthGuard] },
  { path: 'admin', component: AdminPanelComponent, canActivate: [AuthGuard, AdminGuard] },
  { path: 'admin/plans', component: PlansManagementComponent, canActivate: [AuthGuard, AdminGuard] },
  { path: 'ayuda', component: HelpComponent, canActivate: [AuthGuard] },
  { path: '**', redirectTo: '', pathMatch: 'full' }
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
