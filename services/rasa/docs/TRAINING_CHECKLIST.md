# Checklist: validación y entrenamiento (Rasa)

Ejecuta estos pasos **después** de cambios en `domain.yml`, `data/*.yml` o acciones que afecten flujos o políticas.

## Antes de entrenar

1. **Variables de entorno**
   - `SECRET_KEY` / `ALGORITHM`: deben coincidir con el servicio de auth que firma los JWT enviados por FastAPI (`app/api/v1/chat_routes.py`).
   - `RASA_ENFORCE_JWT_FOR_ADMIN_ACTIONS` (default `true`): en producción déjalo activo para que las acciones admin exijan JWT válido y rol desde claims.
   - Para `rasa test` o `rasa shell` **sin** token en metadata, exporta temporalmente:
     ```bash
     set RASA_ENFORCE_JWT_FOR_ADMIN_ACTIONS=false
     ```
     (Linux/macOS: `export RASA_ENFORCE_JWT_FOR_ADMIN_ACTIONS=false`)

2. **Validar datos**
   ```bash
   cd services/rasa
   rasa data validate
   ```

3. **Tests conversacionales** (opcional pero recomendado)
   ```bash
   rasa test --stories tests/stories_test.yml --model artifacts/models
   ```
   Con enforce en `false` si los tests no envían JWT.

## Entrenamiento

Los modelos activos viven en **`artifacts/models/`** (Compose monta ese directorio en el contenedor). Tras `rasa train`, el CLI suele escribir en `models/` en la raíz del proyecto; copia el `.tar.gz` a `artifacts/models/` o usa un script equivalente al de CI.

```bash
cd services/rasa
rasa train
mkdir -p artifacts/models
cp models/*.tar.gz artifacts/models/
```

Vuelve a desplegar o asegúrate de que el volumen `artifacts/models` del servicio `rasa` en Compose tenga al menos un `.tar.gz`.

## Post-despliegue

- Probar **jugador**: recomendación, precios, promociones.
- Probar **admin** vía API con Bearer válido: métricas, clientes top, uso de canchas.
- Confirmar que el webhook de Rasa no sea público sin la capa FastAPI + JWT en entornos reales.

## CI (GitHub Actions)

En el repositorio existe [`.github/workflows/rasa.yml`](../../../.github/workflows/rasa.yml): **no entrena** (eso lo haces en local); ejecuta `rasa data validate` y `rasa test --stories` con `--model artifacts/models` usando la imagen `rasa/rasa-pro:3.12.3`. Debe existir **al menos un `.tar.gz`** versionado en `artifacts/models/` (si `.gitignore` lo oculta, usa `git add -f`).

Configura el secret **`RASA_PRO_LICENSE`** en GitHub (Settings → Secrets) con tu licencia Rasa Pro; sin él el job fallará. Los tests usan `RASA_ENFORCE_JWT_FOR_ADMIN_ACTIONS=false` para no exigir JWT en metadata.
