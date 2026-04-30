import { EmailConfig } from '../../models/invoice.model';

export function cloneConfig(cfg: EmailConfig): EmailConfig {
  return JSON.parse(JSON.stringify(cfg));
}

export function parseSynonymsText(raw: string): string[] {
  return (raw || '')
    .split(/[\n,;]+/)
    .map((v) => (v || '').trim())
    .filter((v) => !!v);
}

export function parseSynonymsByLine(raw: string): { [key: string]: string[] } {
  const result: { [key: string]: string[] } = {};
  const lines = (raw || '')
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => !!line);

  lines.forEach((line) => {
    const parts = line.split(':');
    if (parts.length < 2) return;

    const base = (parts.shift() || '').trim();
    const variants = parseSynonymsText(parts.join(':'));
    if (!base || !variants.length) return;

    const uniqueVariants: string[] = [];
    const seen = new Set<string>();
    variants.forEach((variant) => {
      const key = variant.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      uniqueVariants.push(variant);
    });

    if (uniqueVariants.length) {
      result[base] = uniqueVariants;
    }
  });

  return result;
}

export function synonymsToText(value: EmailConfig['search_synonyms']): string {
  if (!value || Array.isArray(value)) return '';

  return Object.keys(value)
    .map((base) => {
      const cleanBase = (base || '').trim();
      const variants = ((value as { [key: string]: string[] })[base] || [])
        .map((v) => (v || '').trim())
        .filter((v) => !!v);
      if (!cleanBase || !variants.length) return '';
      return `${cleanBase}: ${variants.join(', ')}`;
    })
    .filter((line) => !!line)
    .join('\n');
}

export function getSynonymSummary(config: EmailConfig): string {
  if (!config.search_synonyms || Array.isArray(config.search_synonyms)) {
    return 'Sin grupos configurados';
  }
  const groups = Object.keys(config.search_synonyms).filter((base) => !!(base || '').trim());
  return groups.length ? `${groups.length} grupo(s)` : 'Sin grupos configurados';
}

export function mergeSearchTerms(existing: string[], additions: string[]): string[] {
  const normalized = (existing || []).map((t) => (t || '').trim()).filter((t) => !!t);
  const seen = new Set(normalized.map((t) => t.toLowerCase()));
  (additions || []).forEach((term) => {
    const clean = (term || '').trim();
    if (!clean) return;
    const key = clean.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    normalized.push(clean);
  });
  return normalized;
}
