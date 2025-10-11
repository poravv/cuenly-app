import { NgModule } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { HttpClientModule, HTTP_INTERCEPTORS } from '@angular/common/http';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';

import { DashboardComponent } from './components/dashboard/dashboard.component';
import { UploadComponent } from './components/upload/upload.component';
import { UploadXmlComponent } from './components/upload-xml/upload-xml.component';
import { EmailConfigComponent } from './components/email-config/email-config.component';
import { NavbarComponent } from './components/navbar/navbar.component';
import { FooterComponent } from './components/footer/footer.component';
import { HelpComponent } from './components/help/help.component';
import { InvoiceExplorerComponent } from './components/invoice-explorer/invoice-explorer.component';
import { InvoicesV2Component } from './components/invoices-v2/invoices-v2.component';
import { LoginComponent } from './components/login/login.component';
import { SubscriptionComponent } from './components/subscription/subscription.component';
import { TrialBannerComponent } from './components/trial-banner/trial-banner.component';
import { ExportTemplatesComponent } from './components/export-templates/export-templates.component';
import { TemplateEditorComponent } from './components/export-templates/template-editor.component';
import { TemplateExportComponent } from './components/export-templates/template-export.component';
import { NotificationContainerComponent } from './components/shared/notification-container/notification-container.component';
import { AdminPanelComponent } from './components/admin-panel/admin-panel.component';
import { PlansManagementComponent } from './components/plans-management/plans-management.component';
import { SuspendedComponent } from './components/suspended/suspended.component';
import { AppComponent } from './app.component';
import { AppRoutingModule } from './app-routing.module';
import { AuthInterceptor } from './interceptors/auth.interceptor';
import { TrialInterceptor } from './interceptors/trial.interceptor';
import { InvoiceProcessingComponent } from './components/invoice-processing/invoice-processing.component';

@NgModule({
  declarations: [
    AppComponent,
    DashboardComponent,
    UploadComponent,
    UploadXmlComponent,
    EmailConfigComponent,
    NavbarComponent,
    FooterComponent,
    HelpComponent,
    InvoiceExplorerComponent,
    InvoicesV2Component,
    LoginComponent,
    SubscriptionComponent,
    TrialBannerComponent,
    ExportTemplatesComponent,
    TemplateEditorComponent,
    TemplateExportComponent,
    NotificationContainerComponent,
    AdminPanelComponent,
    PlansManagementComponent,
    SuspendedComponent,
    InvoiceProcessingComponent
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    HttpClientModule,
    ReactiveFormsModule,
    FormsModule,
    BrowserAnimationsModule
  ],
  providers: [
    { provide: HTTP_INTERCEPTORS, useClass: AuthInterceptor, multi: true },
    { provide: HTTP_INTERCEPTORS, useClass: TrialInterceptor, multi: true }
  ],
  bootstrap: [AppComponent]
})
export class AppModule { }
