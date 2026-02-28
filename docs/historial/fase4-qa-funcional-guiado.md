# Fase 4 - QA Funcional Guiado

Fecha: 2026-02-24  
Estado: `EJECUTADO`

## Alcance validado

- Matcher robusto de nomenclaturas con normalización `NFKD`.
- Variantes con y sin tilde.
- Uso de sinónimos por tenant.
- Fallback opcional por remitente.
- Fallback opcional por nombre de adjunto.
- Banderas de búsqueda IMAP por rango (`SINCE` / `BEFORE`).

## Evidencia automática ejecutada

Comandos:

- `PYTHONPATH=backend python3 -m pytest backend/tests/test_phase4_nomenclature_matching.py -q`
- `PYTHONPATH=backend python3 -m pytest backend/tests/test_phase4_imap_search_fallback.py -q`
- `PYTHONPATH=backend python3 -m pytest backend/tests -q`

Resultados:

- `test_phase4_nomenclature_matching.py`: `10 passed`
- `test_phase4_imap_search_fallback.py`: `4 passed`
- `backend/tests` completo: `24 passed`

## Matriz de casos funcionales (resultado real)

Salida ejecutada sobre el matcher:

```text
Asunto tilde: matched=True source=subject term=factura electronica
Asunto sin tilde: matched=True source=subject term=factura electronica
Sinonimo facturacion: matched=True source=subject term=facturación
Fallback sender OFF: matched=False source=None term=None
Fallback sender ON: matched=True source=sender term=facturación
Fallback adjunto OFF: matched=False source=None term=None
Fallback adjunto ON: matched=True source=attachment term=comprobante
```

Conclusión funcional:

- Se confirma comportamiento esperado:
  - asunto robusto con/sin acentos
  - sinónimos efectivos por tenant
  - fallback activado/desactivado respeta configuración
  - trazabilidad de fuente de match (`subject`, `sender`, `attachment`)

## Guía de QA manual UI (paso a paso)

Ruta: `Configuración de Correos`

Caso 1 - Sinónimos por tenant:

1. Editar una cuenta de correo.
2. Agregar término base `factura electronica`.
3. Agregar sinónimos `facturación, documento electrónico`.
4. Guardar.
5. Verificar en card resumen que aparezca `N grupo(s) de sinónimos`.

Caso 2 - Fallback por remitente:

1. Activar `fallback remitente`.
2. Guardar.
3. Enviar/probar correo con asunto no coincidente pero remitente que contenga `facturacion`.
4. Verificar en backend logs/cola que el correo sea detectado y encolado.

Caso 3 - Fallback por adjunto:

1. Activar `fallback adjunto`.
2. Guardar.
3. Enviar/probar correo con asunto no coincidente y adjunto `comprobante_*.xml`.
4. Verificar detección/encolado.

Caso 4 - Control de falsos positivos:

1. Desactivar ambos fallbacks.
2. Usar correo con asunto no coincidente.
3. Verificar que no se detecte.

## Riesgos residuales y siguiente ajuste recomendado

- Riesgo: nombres de adjuntos con formatos MIME poco estándar pueden variar entre servidores IMAP.
- Acción recomendada: añadir más fixtures de `BODYSTRUCTURE` reales por proveedor (Gmail, Outlook, cPanel) y extender parser si aparece un caso no cubierto.
