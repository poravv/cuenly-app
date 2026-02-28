import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';

// Layout
import { AdminLayoutComponent } from '../../components/admin-layout/admin-layout.component';

// Pages
import { AdminDashboardComponent } from '../../components/admin-dashboard/admin-dashboard.component';
import { AdminUsersComponent } from '../../components/admin-users/admin-users.component';
import { AdminPlansComponent } from '../../components/admin-plans/admin-plans.component';
import { AdminSubscriptionsComponent } from '../../components/admin-subscriptions/admin-subscriptions.component';
import { AdminSystemComponent } from '../../components/admin-system/admin-system.component';
import { AdminAuditComponent } from '../../components/admin-audit/admin-audit.component';

// Shared components
import { PlansManagementComponent } from '../../components/plans-management/plans-management.component';

// Routing
import { AdminRoutingModule } from './admin-routing.module';

@NgModule({
    declarations: [
        AdminLayoutComponent,
        AdminDashboardComponent,
        AdminUsersComponent,
        AdminPlansComponent,
        AdminSubscriptionsComponent,
        AdminSystemComponent,
        AdminAuditComponent,
        PlansManagementComponent
    ],
    imports: [
        CommonModule,
        AdminRoutingModule,
        ReactiveFormsModule,
        FormsModule,
        RouterModule
    ]
})
export class AdminModule { }
