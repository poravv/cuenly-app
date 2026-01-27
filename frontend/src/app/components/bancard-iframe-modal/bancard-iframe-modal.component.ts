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
    console.log('🎬 Bancard Modal - Iniciando con form_id:', this.formId);
    this.loadBancardScript();
  }

  loadBancardScript(): void {
    // Verificar si el script ya está cargado
    if (typeof Bancard !== 'undefined') {
      console.log('✅ Script de Bancard ya cargado');
      this.scriptLoaded = true;
      this.initializeIframe();
      return;
    }

    console.log('📥 Cargando script de Bancard...');
    const script = document.createElement('script');
    script.src = 'https://checkout.bancard.com.py/bancard-checkout-2.1.0.js';
    script.async = true;

    script.onload = () => {
      console.log('✅ Script de Bancard cargado exitosamente');
      this.scriptLoaded = true;
      this.loading = false;
      setTimeout(() => this.initializeIframe(), 500);
    };

    script.onerror = (error) => {
      console.error('❌ Error cargando script de Bancard:', error);
      this.error = true;
      this.loading = false;
    };

    document.head.appendChild(script);
  }

  initializeIframe(): void {
    if (typeof Bancard === 'undefined') {
      console.error('❌ Bancard no está definido');
      this.error = true;
      return;
    }

    try {
      console.log('🎯 Inicializando iframe de Bancard con form_id:', this.formId);

      Bancard.Cards.createForm('bancard-iframe-container', this.formId, {
        onComplete: () => {
          console.log('✅ Usuario completó el formulario de Bancard');
          this.completed.emit();
        },
        onError: (error: any) => {
          console.error('❌ Error en iframe de Bancard:', error);
        }
      });

      this.loading = false;

    } catch (error) {
      console.error('❌ Error inicializando iframe:', error);
      this.error = true;
      this.loading = false;
    }
  }

  close(): void {
    console.log('🚪 Cerrando modal de Bancard');
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
