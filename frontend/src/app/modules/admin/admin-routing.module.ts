import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { AdminPanelComponent } from '../../components/admin-panel/admin-panel.component';
import { PlansManagementComponent } from '../../components/plans-management/plans-management.component';

const routes: Routes = [
    { path: '', component: AdminPanelComponent },
    { path: 'plans', component: PlansManagementComponent }
];

@NgModule({
    imports: [RouterModule.forChild(routes)],
    exports: [RouterModule]
})
export class AdminRoutingModule { }
