import { Component, OnInit, OnDestroy } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ActivatedRoute, Router } from '@angular/router';

@Component({
    selector: 'app-payment-methods',
    templateUrl: './payment-methods.component.html',
    styleUrls: ['./payment-methods.component.scss']
})
export class PaymentMethodsComponent implements OnInit, OnDestroy {
    loading = false;
    cards: any[] = [];

    // Add Card State
    showAddModal = false;
    iframeUrl: SafeResourceUrl | null = null;
    processingAdd = false;

    constructor(
        private apiService: ApiService,
        private notificationService: NotificationService,
        private sanitizer: DomSanitizer,
        private route: ActivatedRoute,
        private router: Router
    ) { }

    ngOnInit(): void {
        this.checkRedirect();
        this.loadCards();
    }

    ngOnDestroy(): void { }

    loadCards(): void {
        this.loading = true;
        this.apiService.getCards().subscribe({
            next: (data) => {
                this.cards = data;
                this.loading = false;
            },
            error: (err) => {
                console.error('Error loading cards:', err);
                // Silent error for now, maybe user has no pagopar account yet
                this.loading = false;
            }
        });
    }

    checkRedirect(): void {
        // Check if we returned from Pagopar iframe redirect
        // URL param 'status' usually?
        // Actually our return_url logic might handle this or we need to check params.
        // The previous implementation used return_url logic.
        // If we set return_url to current page, we might see params.
        // The PDF says: redirects to return_id?status=add_new_card_success

        const status = this.route.snapshot.queryParams['status'];
        if (status === 'add_new_card_success') {
            this.notificationService.success('Tarjeta agregada correctamente');
            // Must confirm card!
            this.confirmCard();
        } else if (status === 'add_new_card_fail') {
            const desc = this.route.snapshot.queryParams['description'];
            this.notificationService.error(desc || 'Error al agregar tarjeta');
        }
    }

    confirmCard(): void {
        // We pass the same return_url we used.
        const currentParams = this.route.snapshot.queryParams;
        const urlTree = this.router.createUrlTree(['/payment-methods'], { queryParams: currentParams });
        const returnUrl = window.location.origin + this.router.serializeUrl(urlTree);

        this.apiService.confirmCard(returnUrl).subscribe({
            next: () => {
                this.loadCards();
                this.notificationService.success('Tarjeta confirmada correctamente');

                // Check for return param to redirect back
                const returnPath = currentParams['return'];
                if (returnPath) {
                    setTimeout(() => {
                        this.router.navigateByUrl(returnPath);
                    }, 1500); // Small delay to let user see success message
                } else {
                    // Remove query params
                    this.router.navigate([], {
                        queryParams: {
                            'status': null,
                            'description': null,
                            'token': null,
                            'return': null
                        },
                        queryParamsHandling: 'merge'
                    });
                }
            },
            error: (err) => {
                console.error(err);
                this.notificationService.error('Error finalizando catastro de tarjeta');
            }
        });
    }

    openAddCardModal(): void {
        this.processingAdd = true;
        // Preserve current query params (like return=/subscription)
        const currentParams = this.route.snapshot.queryParams;
        let returnPaths = '/payment-methods';

        // Construct return URL with existing params
        const urlTree = this.router.createUrlTree([returnPaths], { queryParams: currentParams });
        const returnUrl = window.location.origin + this.router.serializeUrl(urlTree);

        // Default to uPay as per recommendation
        this.apiService.initAddCard(returnUrl, 'uPay').subscribe({
            next: (res) => {
                // Construct iframe URL: https://www.pagopar.com/upay-iframe/?id-form={hash}
                // Note: For sandbox it might be different, but let's assume standard logic or use base from settings?
                // Actually, the Iframe URL logic is usually fixed but domains change. 
                // Sandbox pagopar: "https://www.pagopar.com/upay-iframe/" ???
                // Wait, the PDF says: "iframe src='https://www.pagopar.com/upay-iframe/?id-form={json.resultado}'"
                // It doesn't specify Sandbox URL for iframe. Usually it is the same.

                const url = `https://www.pagopar.com/upay-iframe/?id-form=${res.hash}`;
                this.iframeUrl = this.sanitizer.bypassSecurityTrustResourceUrl(url);
                this.showAddModal = true;
                this.processingAdd = false;
            },
            error: (err) => {
                console.error(err);
                this.notificationService.error('Error iniciando proceso de tarjeta');
                this.processingAdd = false;
            }
        });
    }

    closeAddModal(): void {
        this.showAddModal = false;
        this.iframeUrl = null;
        this.loadCards(); // Reload just in case
    }

    deleteCard(card: any): void {
        if (!confirm('¿Seguro que deseas eliminar esta tarjeta?')) return;

        this.loading = true;
        this.apiService.deleteCard(card.alias_token).subscribe({
            next: () => {
                this.notificationService.success('Tarjeta eliminada');
                this.loadCards();
            },
            error: (err) => {
                this.notificationService.error('Error eliminando tarjeta');
                this.loading = false;
            }
        });
    }

    testPayment(card: any): void {
        const orderHash = prompt("Hash del Pedido (Pagopar):");
        if (!orderHash) return;

        this.loading = true;
        this.apiService.testPay(card.alias_token, orderHash).subscribe({
            next: () => {
                this.notificationService.success('Pago de prueba exitoso');
                this.loading = false;
            },
            error: (err) => {
                this.notificationService.error('Error en pago de prueba');
                this.loading = false;
            }
        });
    }
}
