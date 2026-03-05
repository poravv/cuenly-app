import { Component, OnInit, OnDestroy, ChangeDetectionStrategy, ChangeDetectorRef } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { NotificationService } from '../../services/notification.service';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';
import { ActivatedRoute, Router } from '@angular/router';

@Component({
    selector: 'app-payment-methods',
    templateUrl: './payment-methods.component.html',
    styleUrls: ['./payment-methods.component.scss'],
    changeDetection: ChangeDetectionStrategy.OnPush
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
        private router: Router,
        private cdr: ChangeDetectorRef
    ) { }

    ngOnInit(): void {
        this.checkRedirect();
        this.loadCards();
    }

    ngOnDestroy(): void { }

    trackByCardAlias(_index: number, card: any): string {
        return card.alias_token || String(_index);
    }

    onCardLogoError(event: Event): void {
        const img = event.target as HTMLImageElement;
        img.style.display = 'none';
        // Show the fallback icon (next sibling)
        const fallback = img.nextElementSibling as HTMLElement;
        if (fallback) {
            fallback.style.display = 'inline-block';
        }
    }

    loadCards(): void {
        this.loading = true;
        this.cdr.markForCheck();
        this.apiService.getCards().subscribe({
            next: (data) => {
                this.cards = data;
                this.loading = false;
                this.cdr.markForCheck();
            },
            error: () => {
                // Silent error for now, maybe user has no pagopar account yet
                this.loading = false;
                this.cdr.markForCheck();
            }
        });
    }

    checkRedirect(): void {
        const status = this.route.snapshot.queryParams['status'];
        if (status === 'add_new_card_success') {
            this.notificationService.success('Tarjeta agregada correctamente');
            this.confirmCard();
        } else if (status === 'add_new_card_fail') {
            const desc = this.route.snapshot.queryParams['description'];
            this.notificationService.error(desc || 'Error al agregar tarjeta');
        }
    }

    confirmCard(): void {
        const currentParams = this.route.snapshot.queryParams;
        const urlTree = this.router.createUrlTree(['/payment-methods'], { queryParams: currentParams });
        const returnUrl = window.location.origin + this.router.serializeUrl(urlTree);

        this.apiService.confirmCard(returnUrl).subscribe({
            next: () => {
                this.loadCards();
                this.notificationService.success('Tarjeta confirmada correctamente');

                const returnPath = currentParams['return'];
                if (returnPath) {
                    setTimeout(() => {
                        this.router.navigateByUrl(returnPath);
                    }, 1500);
                } else {
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
            error: () => {
                this.notificationService.error('Error finalizando catastro de tarjeta');
            }
        });
    }

    openAddCardModal(): void {
        this.processingAdd = true;
        this.cdr.markForCheck();
        const currentParams = this.route.snapshot.queryParams;
        let returnPaths = '/payment-methods';

        const urlTree = this.router.createUrlTree([returnPaths], { queryParams: currentParams });
        const returnUrl = window.location.origin + this.router.serializeUrl(urlTree);

        this.apiService.initAddCard(returnUrl, 'uPay').subscribe({
            next: (res) => {
                const url = `https://www.pagopar.com/upay-iframe/?id-form=${res.hash}`;
                this.iframeUrl = this.sanitizer.bypassSecurityTrustResourceUrl(url);
                this.showAddModal = true;
                this.processingAdd = false;
                this.cdr.markForCheck();
            },
            error: () => {
                this.notificationService.error('Error iniciando proceso de tarjeta');
                this.processingAdd = false;
                this.cdr.markForCheck();
            }
        });
    }

    closeAddModal(): void {
        this.showAddModal = false;
        this.iframeUrl = null;
        this.loadCards();
    }

    deleteCard(card: any): void {
        if (!confirm('¿Seguro que deseas eliminar esta tarjeta?')) return;

        this.loading = true;
        this.cdr.markForCheck();
        this.apiService.deleteCard(card.alias_token).subscribe({
            next: () => {
                this.notificationService.success('Tarjeta eliminada');
                this.loadCards();
            },
            error: (err) => {
                this.notificationService.error('Error eliminando tarjeta');
                this.loading = false;
                this.cdr.markForCheck();
            }
        });
    }

    testPayment(card: any): void {
        const orderHash = prompt("Hash del Pedido (Pagopar):");
        if (!orderHash) return;

        this.loading = true;
        this.cdr.markForCheck();
        this.apiService.testPay(card.alias_token, orderHash).subscribe({
            next: () => {
                this.notificationService.success('Pago de prueba exitoso');
                this.loading = false;
                this.cdr.markForCheck();
            },
            error: (err) => {
                this.notificationService.error('Error en pago de prueba');
                this.loading = false;
                this.cdr.markForCheck();
            }
        });
    }
}
