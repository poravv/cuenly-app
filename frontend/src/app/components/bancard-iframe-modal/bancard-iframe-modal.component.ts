import { Component, OnInit, OnDestroy, Input, Output, EventEmitter } from '@angular/core';

declare var Bancard: any;

@Component({
  selector: 'app-bancard-iframe-modal',
  templateUrl: './bancard-iframe-modal.component.html',
  styleUrls: ['./bancard-iframe-modal.component.scss']
})
export class BancardIframeModalComponent implements OnInit, OnDestroy {
  @Input() formId!: string;
  @Output() completed = new EventEmitter<void>();
  @Output() closed = new EventEmitter<void>();

  private scriptLoaded = false;
  loading = true;
  error = false;

  ngOnInit(): void {
    this.loadBancardScript();
  }

  loadBancardScript(): void {
    // Verificar si el script ya está cargado
    if (typeof Bancard !== 'undefined') {
      this.scriptLoaded = true;
      this.initializeIframe();
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://checkout.bancard.com.py/bancard-checkout-2.1.0.js';
    script.async = true;

    script.onload = () => {
      this.scriptLoaded = true;
      this.loading = false;
      setTimeout(() => this.initializeIframe(), 500);
    };

    script.onerror = (error) => {
      this.error = true;
      this.loading = false;
    };

    document.head.appendChild(script);
  }

  initializeIframe(): void {
    if (typeof Bancard === 'undefined') {
      this.error = true;
      return;
    }

    try {
      Bancard.Cards.createForm('bancard-iframe-container', this.formId, {
        onComplete: () => {
          this.completed.emit();
        },
        onError: (error: any) => {
          // Error handled silently
        }
      });

      this.loading = false;

    } catch (error) {
      this.error = true;
      this.loading = false;
    }
  }

  close(): void {
    this.closed.emit();
  }

  ngOnDestroy(): void {
    // Cleanup: remover el contenedor si existe
    const container = document.getElementById('bancard-iframe-container');
    if (container) {
      container.innerHTML = '';
    }
  }
}
