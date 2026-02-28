import { Component, OnInit, OnDestroy } from '@angular/core';
import { UserService, UserProfile } from '../../services/user.service';
import { NotificationService } from '../../services/notification.service';
import { Observable } from 'rxjs';

@Component({
    selector: 'app-profile',
    templateUrl: './profile.component.html',
    styleUrls: ['./profile.component.scss']
})
export class ProfileComponent implements OnInit, OnDestroy {
    profile: UserProfile | null = null;
    editProfile: Partial<UserProfile> = {};
    saving = false;

    validationErrors: { [key: string]: string } = {};

    constructor(
        private userService: UserService,
        private notificationService: NotificationService
    ) { }

    ngOnInit(): void {
        this.userService.setEditingProfile(true);

        this.userService.userProfile$.subscribe(profile => {
            if (profile) {
                this.profile = profile;
                // Solo inicializar el formulario si está vacío o si es la primera carga
                // Como setEditingProfile(true) evita actualizaciones del subject, 
                // esto solo debería ocurrir al cargar la página inicialmente
                if (!this.editProfile.name) {
                    this.editProfile = {
                        name: profile.name,
                        phone: profile.phone,
                        ruc: profile.ruc,
                        address: profile.address,
                        city: profile.city,
                        document_type: profile.document_type || 'CI'
                    };
                }
            }
        });

        // Cargar perfil si no está en el BehaviorSubject
        if (!this.profile) {
            this.userService.getUserProfile().subscribe();
        }
    }

    ngOnDestroy(): void {
        this.userService.setEditingProfile(false);
    }

    validate(): boolean {
        this.validationErrors = {};
        let isValid = true;

        if (!this.editProfile.name?.trim()) {
            this.validationErrors['name'] = 'El nombre es obligatorio';
            isValid = false;
        }

        if (!this.editProfile.phone?.trim()) {
            this.validationErrors['phone'] = 'El teléfono es obligatorio';
            isValid = false;
        } else {
            // Validacion simple: solo numeros, espacios, + y -
            const phoneRegex = /^[0-9+\-\s]+$/;
            if (!phoneRegex.test(this.editProfile.phone)) {
                this.validationErrors['phone'] = 'Formato de teléfono inválido';
                isValid = false;
            }
        }

        if (!this.editProfile.ruc?.trim()) {
            // RUC es opcional en general, pero si se pone, debe ser válido
            // En este contexto, si vamos a forzar perfil completo para pagopar, quizás deberíamos marcarlo siempre
            // Pero por ahora solo validamos si hay valor o si es requerido explicitamente

            // Si queremos forzarlo:
            this.validationErrors['ruc'] = 'El documento es obligatorio';
            isValid = false;
        }

        if (!this.editProfile.address?.trim()) {
            this.validationErrors['address'] = 'La dirección es obligatoria';
            isValid = false;
        }

        if (!this.editProfile.city?.trim()) {
            this.validationErrors['city'] = 'La ciudad es obligatoria';
            isValid = false;
        }

        return isValid;
    }

    saveProfile(): void {
        if (!this.validate()) {
            this.notificationService.error('Por favor corrige los errores en el formulario');
            return;
        }

        this.saving = true;
        this.userService.updateUserProfile(this.editProfile).subscribe({
            next: () => {
                this.notificationService.success('Perfil actualizado correctamente');
                this.saving = false;
                // Actualizar copia local de profile si es necesario, 
                // aunque el backend debería mandar update y getUserProfile (si no estuviera bloqueado)
                // Aquí podríamos actualizar manualmente profile
                if (this.profile) {
                    this.profile = { ...this.profile, ...this.editProfile } as UserProfile;
                }
            },
            error: (err) => {
                this.notificationService.error(err.error?.detail || 'Error al actualizar el perfil');
                this.saving = false;
            }
        });
    }
}
