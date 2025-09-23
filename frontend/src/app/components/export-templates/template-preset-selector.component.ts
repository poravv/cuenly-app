import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { ExportTemplateService } from '../../services/export-template.service';

@Component({
  selector: 'app-template-preset-selector',
  templateUrl: './template-preset-selector.component.html',
  styleUrls: ['./template-preset-selector.component.scss']
})
export class TemplatePresetSelectorComponent implements OnInit {
  presets: any = {};
  recommendations: any = {};
  loading = true;
  creating = false;
  selectedPreset: string | null = null;
  customName = '';

  constructor(
    private exportTemplateService: ExportTemplateService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.loadPresets();
  }

  loadPresets(): void {
    this.loading = true;
    this.exportTemplateService.getTemplatePresets().subscribe({
      next: (response: any) => {
        this.presets = response.presets || {};
        this.recommendations = response.recommendations || {};
        this.loading = false;
      },
      error: (error: any) => {
        console.error('Error cargando presets:', error);
        this.loading = false;
      }
    });
  }

  selectPreset(presetKey: string): void {
    this.selectedPreset = presetKey;
    this.customName = this.presets[presetKey]?.name || '';
  }

  createTemplate(): void {
    if (!this.selectedPreset) return;

    this.creating = true;
    
    const request = {
      preset: this.selectedPreset,
      name: this.customName.trim() || undefined
    };

    this.exportTemplateService.createFromPreset(request).subscribe({
      next: (response: any) => {
        if (response.success) {
          // Redirigir al editor del template creado
          this.router.navigate(['/templates-export/edit', response.template_id]);
        }
      },
      error: (error: any) => {
        console.error('Error creando template:', error);
        this.creating = false;
      }
    });
  }

  goToAdvancedMode(): void {
    this.router.navigate(['/templates-export/new']);
  }

  getPresetIcon(groupType: string): string {
    const icons: { [key: string]: string } = {
      'contable': '📊',
      'ejecutivo': '💼', 
      'detallado': '🔍',
      'simple': '📋'
    };
    return icons[groupType] || '⚙️';
  }

  getPresetColor(groupType: string): string {
    const colors: { [key: string]: string } = {
      'contable': 'success',
      'ejecutivo': 'primary',
      'detallado': 'info', 
      'simple': 'secondary'
    };
    return colors[groupType] || 'light';
  }

  getPresetColorHex(groupType: string): string {
    const colors: { [key: string]: string } = {
      'contable': '#198754',  // green
      'ejecutivo': '#0d6efd', // blue
      'detallado': '#0dcaf0', // cyan
      'simple': '#6c757d'     // gray
    };
    return colors[groupType] || '#6c757d';
  }

  getRecommendationBadge(presetKey: string): string | null {
    for (const [userType, recommendedPreset] of Object.entries(this.recommendations)) {
      if (recommendedPreset === presetKey) {
        const badges: { [key: string]: string } = {
          'new_user': '👤 Nuevo Usuario',
          'accountant': '🧮 Contadores',
          'business_owner': '💼 Empresarios',
          'auditor': '🔍 Auditores'
        };
        return badges[userType] || null;
      }
    }
    return null;
  }

  cancel(): void {
    this.router.navigate(['/templates-export']);
  }

  getPresetsArray(): any[] {
    return Object.keys(this.presets).map(key => ({ key, value: this.presets[key] }));
  }
}