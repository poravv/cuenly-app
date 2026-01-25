import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule, FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';

// Components
import { AdminPanelComponent } from '../../components/admin-panel/admin-panel.component';
import { PlansManagementComponent } from '../../components/plans-management/plans-management.component';

// Modules
import { AdminRoutingModule } from './admin-routing.module';

@NgModule({
    declarations: [
        AdminPanelComponent,
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
