import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';

@Component({
    selector: 'app-pagopar-result',
    templateUrl: './pagopar-result.component.html',
    styleUrls: ['./pagopar-result.component.scss']
})
export class PagoparResultComponent implements OnInit {
    loading = true;
    orderStatus: any = null;
    error: string | null = null;
    hash: string | null = null;

    constructor(
        private route: ActivatedRoute,
        private router: Router,
        private apiService: ApiService,
        private notificationService: NotificationService
    ) { }

    ngOnInit(): void {
        this.hash = this.route.snapshot.paramMap.get('hash');
        if (this.hash) {
            this.validateOrder();
        } else {
            this.error = 'No se proporcionó un hash de pedido válido.';
            this.loading = false;
        }
    }

    validateOrder(): void {
        this.loading = true;
        this.apiService.validatePagoparOrder(this.hash!).subscribe({
            next: (data) => {
                this.orderStatus = data;
                this.loading = false;

                if (data.respuesta && data.resultado && data.resultado.length > 0) {
                    const detail = data.resultado[0];
                    if (detail.pagado) {
                        this.notificationService.success('¡Pago completado con éxito!');
                    } else if (detail.cancelado) {
                        this.notificationService.error('El pedido fue cancelado.');
                    }
                }
            },
            error: () => {
                this.error = 'No pudimos verificar el estado de tu pedido. Por favor, contacta a soporte.';
                this.loading = false;
            }
        });
    }

    goToDashboard(): void {
        this.router.navigate(['/']);
    }
}
