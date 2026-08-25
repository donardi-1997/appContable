# Gato Contable

MVP visual para la operación contable de una discoteca pequeña. Incluye dashboard, ventas y caja, inventario, gastos y un sandbox local de facturación electrónica.

## Ejecutar localmente

No requiere dependencias: abre `index.html` en el navegador. Para servirlo con Node:

```powershell
npx serve .
```

## Siguiente fase

1. Crear API FastAPI y PostgreSQL.
2. Persistir ventas, inventario, gastos y cierres de caja.
3. Integrar un proveedor tecnológico autorizado para facturación electrónica.
4. Sustituir el adaptador sandbox por Factus API y cifrar credenciales.
5. Agregar usuarios/roles y backups automáticos.

El modo sandbox genera consecutivos y CUFE simulados en `localStorage`; no emite documentos válidos ante la DIAN hasta integrar un proveedor autorizado y completar la habilitación tributaria.
