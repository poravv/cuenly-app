import { Component, OnInit } from '@angular/core';
import { UserService, UserProfile } from '../../services/user.service';
import { NotificationService } from '../../services/notification.service';
import { Observable } from 'rxjs';

@Component({
    selector: 'app-profile',
    templateUrl: './profile.component.html',
    styleUrls: ['./profile.component.scss']
})
export class ProfileComponent implements OnInit {
    profile: UserProfile | null = null;
    editProfile: Partial<UserProfile> = {};
    saving = false;

    constructor(
        private userService: UserService,
        private notificationService: NotificationService
    ) { }

    ngOnInit(): void {
        this.userService.userProfile$.subscribe(profile => {
            if (profile) {
                this.profile = profile;
                this.editProfile = {
                    name: profile.name,
                    phone: profile.phone,
                    ruc: profile.ruc,
                    address: profile.address,
                    city: profile.city,
                    document_type: profile.document_type || 'CI'
                };
            }
        });

        // Cargar perfil si no está en el BehaviorSubject
        if (!this.profile) {
            this.userService.getUserProfile().subscribe();
        }
    }

    saveProfile(): void {
        this.saving = true;
        this.userService.updateUserProfile(this.editProfile).subscribe({
            next: () => {
                this.notificationService.success('Perfil actualizado correctamente');
                this.saving = false;
            },
            error: (err) => {
                console.error('Error al guardar perfil:', err);
                this.notificationService.error(err.error?.detail || 'Error al actualizar el perfil');
                this.saving = false;
            }
        });
    }
}
