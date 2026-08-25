# La Patrona VIP

Sistema administrativo y contable para la operación de La Patrona VIP. Incluye dashboard, ventas y caja, inventario, gastos y un sandbox local de facturación electrónica.

## Ejecutar localmente

No requiere dependencias: abre `index.html` en el navegador. Para servirlo con Node:

```powershell
npx serve .
```

## API local

La API está en `backend/` y usa SQLite por defecto para desarrollo. Con Python 3.11+:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

La documentación interactiva queda disponible en `http://127.0.0.1:8000/docs`.

Endpoints iniciales: `GET/POST /api/products`, `GET/POST /api/sales`, `GET/POST /api/expenses` y `GET /health`.

## Siguiente fase

1. Crear API FastAPI y PostgreSQL.
2. Persistir ventas, inventario, gastos y cierres de caja.
3. Integrar un proveedor tecnológico autorizado para facturación electrónica.
4. Sustituir el adaptador sandbox por Factus API y cifrar credenciales.
5. Agregar usuarios/roles y backups automáticos.

El modo sandbox genera consecutivos y CUFE simulados en `localStorage`; no emite documentos válidos ante la DIAN hasta integrar un proveedor autorizado y completar la habilitación tributaria.

