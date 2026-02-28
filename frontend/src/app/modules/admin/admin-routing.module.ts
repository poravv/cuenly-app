import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { AdminLayoutComponent } from '../../components/admin-layout/admin-layout.component';
import { AdminDashboardComponent } from '../../components/admin-dashboard/admin-dashboard.component';
import { AdminUsersComponent } from '../../components/admin-users/admin-users.component';
import { AdminPlansComponent } from '../../components/admin-plans/admin-plans.component';
import { AdminSubscriptionsComponent } from '../../components/admin-subscriptions/admin-subscriptions.component';
import { AdminSystemComponent } from '../../components/admin-system/admin-system.component';
import { AdminAuditComponent } from '../../components/admin-audit/admin-audit.component';

const routes: Routes = [
    {
        path: '',
        component: AdminLayoutComponent,
        children: [
            { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
            { path: 'dashboard', component: AdminDashboardComponent },
            { path: 'usuarios', component: AdminUsersComponent },
            { path: 'planes', component: AdminPlansComponent },
            { path: 'suscripciones', component: AdminSubscriptionsComponent },
            { path: 'sistema', component: AdminSystemComponent },
            { path: 'auditoria', component: AdminAuditComponent },
            // Legacy redirect
            { path: 'plans', redirectTo: 'planes', pathMatch: 'full' }
        ]
    }
];

@NgModule({
    imports: [RouterModule.forChild(routes)],
    exports: [RouterModule]
})
export class AdminRoutingModule { }
