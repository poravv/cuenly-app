import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { DashboardComponent } from './components/dashboard/dashboard.component';
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

const routes: Routes = [
  { path: 'login', component: LoginComponent, canActivate: [LoginGuard] },
  { path: '', component: DashboardComponent, canActivate: [AuthGuard] },
  { path: 'upload', component: UploadComponent, canActivate: [AuthGuard] },
  { path: 'upload-xml', component: UploadXmlComponent, canActivate: [AuthGuard] },
  { path: 'invoice-explorer', component: InvoiceExplorerComponent, canActivate: [AuthGuard] },
  { path: 'invoice-list', component: InvoicesV2Component, canActivate: [AuthGuard] },
  { path: 'email-config', component: EmailConfigComponent, canActivate: [AuthGuard] },
  { path: 'templates-export', component: ExportTemplatesComponent, canActivate: [AuthGuard] },
  { path: 'templates-export/new', component: TemplateEditorComponent, canActivate: [AuthGuard] },
  { path: 'templates-export/create', component: TemplateEditorComponent, canActivate: [AuthGuard] },
  { path: 'templates-export/edit/:id', component: TemplateEditorComponent, canActivate: [AuthGuard] },
  { path: 'templates-export/export/:id', component: TemplateExportComponent, canActivate: [AuthGuard] },
  { path: 'templates-export/export', component: TemplateExportComponent, canActivate: [AuthGuard] },
  { path: 'subscription', component: SubscriptionComponent, canActivate: [AuthGuard] },
  { path: 'ayuda', component: HelpComponent, canActivate: [AuthGuard] },
  { path: '**', redirectTo: '', pathMatch: 'full' }
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
