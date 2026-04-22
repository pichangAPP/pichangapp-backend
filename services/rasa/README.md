# 🤖 Chato Bot – Asistente de reservas para PichangApp

Este servicio de Rasa convierte al bot en un concierge deportivo: responde preguntas frecuentes, recomienda canchas según preferencias y registra cada interacción en los esquemas `analytics` de la base de datos.

## 🚀 Capacidades principales

- **Recomendaciones inteligentes**: consulta `booking.field`, `booking.sports` y `booking.campus` para sugerir canchas acordes al deporte, zona y superficie solicitada con un tono barrial y futbolero.
- **Seguimiento analítico**: registra sesiones, intenciones y respuestas en `analytics.chatbot`, `analytics.chatbot_log`, `analytics.intents` y `analytics.recomendation_log`, actualizando métricas como confianza promedio y cantidad de detecciones.
- **Feedback del usuario**: muestra los comentarios más recientes almacenados en `analytics.feedback` sin pedir datos extras al jugador.
- **API segura**: expone un endpoint FastAPI que valida tokens Bearer emitidos por el servicio de Auth para enviar mensajes al bot.

## ⚙️ Configuración

1. Crea un archivo `.env` en la raíz del proyecto (o exporta variables en el entorno) con las credenciales de Postgres y los metadatos del modelo:
   ```env
   CHATBOT_DATABASE_URL=postgresql+psycopg2://usuario:password@host:puerto/pichangapp
   # También se admiten las variables POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD y POSTGRES_PORT.
   # Identificador del modelo que se registrará en analytics.intents
   RASA_SOURCE_MODEL=chato-bot-v1
   # Alternativamente, si trabajas con rutas completas exportadas por Rasa CLI puedes usar:
   # RASA_MODEL_NAME=20240101-123456-chato.tar.gz
   ```
2. Instala dependencias:
   ```bash
   cd services/rasa
   pip install -r requirements.txt
   ```
   El **runtime de referencia** es la imagen Docker `rasa/rasa-pro:3.12.3` (ver `Dockerfile`). Para desarrollo local con `pip`, alinea `rasa-pro` con la misma línea 3.12.x (`pyproject.toml`: `>=3.12.3,<3.13`).
3. Entrena el modelo y deja el `.tar.gz` en `artifacts/models` (requerido para Docker Compose):
   ```bash
   rasa data validate
   rasa train
   mkdir -p artifacts/models && cp models/*.tar.gz artifacts/models/
   ```
4. Levanta el servidor de acciones personalizadas (requiere las variables de entorno anteriores):
   ```bash
   rasa run actions --cors "*"
   ```
5. Inicia el bot localmente para pruebas (el servidor de Rasa se expone en `http://localhost:5005` por defecto):
   ```bash
   rasa shell --endpoints endpoints.yml
   ```
6. Levanta el microservicio HTTP que protege el endpoint del bot:

   ```bash
   uvicorn app.main:app --port 8006 --reload
   ```

   El gateway expone la ruta `/api/pichangapp/v1/chatbot/messages`, que requiere un token Bearer válido y reenvía los mensajes al servidor de Rasa.

## 🪵 Depuración de persistencia

- Las acciones personalizadas ahora emiten logs detallados (`INFO` y `DEBUG`) con los parámetros recibidos, el `session_id` generado y cada inserción en las tablas `analytics`. Asegúrate de ejecutar el servidor de acciones con el nivel de log apropiado:
  ```bash
  rasa run actions --cors "*" --logging-level INFO
  ```
- Si necesitas todavía más detalle, eleva el nivel a `DEBUG` o exporta `LOG_LEVEL=DEBUG` antes de levantar el contenedor. Así podrás ver en consola el flujo completo (apertura de sesión, inserción en `chatbot_log`, creación de `recomendation_log`, etc.) y validar rápidamente qué paso falta en la base de datos.

## 🔐 Inicio de sesión y roles

- El microservicio de FastAPI adjunta en el `metadata` los campos `user_id`, `id_user`, `user_role`, `id_role` y el **JWT** (`token`). La acción `action_session_start` enriquece la metadata con los claims del JWT; sin token válido y con enforce activo, no se usa `user_id` desde metadata arbitraria ni se acepta rol admin solo por metadata.
- Las acciones admin usan `resolve_secured_actor` (`actions/domain/chatbot/context.py`). Con **`RASA_ENFORCE_JWT_FOR_ADMIN_ACTIONS=true`** (por defecto), el rol administrador **solo** se acepta si el token se decodifica con `SECRET_KEY` y los claims llevan `id_role` de admin, reduciendo el spoofing contra el webhook.
- Para `rasa shell` o `rasa test` sin token, exporta temporalmente `RASA_ENFORCE_JWT_FOR_ADMIN_ACTIONS=false`. Sin metadata (p. ej. shell), el comportamiento por defecto sigue orientado a jugador (`player`).
- Si el rol o el identificador del usuario no son válidos, el bot responde con un mensaje de reautenticación y detiene la recomendación. Esto evita que se creen registros huérfanos en `analytics.chatbot` y mantiene la trazabilidad de las conversaciones.
- Cada inicio de sesión correcto crea o reactiva una sesión en `analytics.chatbot` y todas las respuestas del bot quedan registradas mediante `analytics.chatbot_log`, `analytics.intents` y `analytics.recomendation_log`.
  - La acción `action_session_start` persiste inmediatamente el inicio de la conversación en `analytics.chatbot` y agrega una fila con `response_type = session_started` en `analytics.chatbot_log`, asegurando que los chats abiertos aparezcan en los tableros aun antes de que se generen recomendaciones.
- La regla `inicializar sesión con metadata` en `data/rules.yml` ejecuta `action_session_start` ni bien se abre un canal, de modo que `ChatSessionRepository` siempre crea o reactiva la sesión aunque el usuario no envíe un saludo inicial. Recuerda reentrenar el modelo (`rasa data validate` + `rasa train`) cuando ajustes `domain.yml`, `data/rules.yml` o `data/nlu.yml` para que el paquete cargado incluya la nueva configuración de slots e intenciones.

## 🧪 Datos y dominio

- **`data/nlu.yml`**: Intenciones y ejemplos en español.
- **`data/stories.yml`**: Historias que ilustran formularios y validaciones basadas en credenciales.
- **`data/rules.yml`**: Reglas que responden preguntas frecuentes y activan formularios.
- **`domain.yml`**: Intenciones, entidades, formularios, respuestas y acciones de Chato Bot.

## 🏷️ Etiquetado de logs reales (admin)

Para que cada release cierre el ciclo con datos reales, usa este flujo semanal:

1. **Exportar fallbacks de admin** desde Postgres:
   ```sql
   SELECT id_chatbot_log,
          message,
          intent_detected,
          intent_confidence,
          metadata ->> 'user_role' AS user_role,
          timestamp
   FROM analytics.chatbot_log
   WHERE timestamp >= NOW() - INTERVAL '5 days'
     AND intent_detected = 'nlu_fallback'
     AND (metadata ->> 'user_role') = 'admin'
   ORDER BY timestamp DESC;
   ```

   También conviene capturar los turnos con `intent_confidence < 0.65`:
   ```sql
   SELECT id_chatbot_log, message, intent_detected, intent_confidence
   FROM analytics.chatbot_log
   WHERE timestamp >= NOW() - INTERVAL '7 days'
     AND (metadata ->> 'user_role') = 'admin'
     AND intent_confidence IS NOT NULL
     AND intent_confidence < 0.65;
   ```

2. **Guardar en CSV** con cabeceras: `id_chatbot_log,message,suggested_intent,entities`.
3. **Etiquetar manualmente** `suggested_intent` (usar solo intents ya existentes en `data/nlu.yml`) y si aplica, marcar entidades Rasa como `[Surco](location)` en el texto.
4. **Appendear** los ejemplos etiquetados al intent correspondiente en `data/nlu.yml` (no crear intents nuevos sin alinear con `domain.yml`).
5. **Reentrenar** (`rasa data validate` + `rasa train`) y verificar en staging con guion admin:
   - "que reservaciones tengo" → `request_admin_reservations_overview`
   - "cuál es la cancha más ocupada este mes" → `request_admin_field_usage`
   - "cómo me fue hoy" → `request_admin_metrics`

Meta por release: bajar el `fallback_rate` para user_role=admin y mantener `intent_confidence` promedio > 0.7.

Los patrones heredados de Rasa Studio se conservan en `docs/patterns_backup/` como referencia. Allí encontrarás exactamente los archivos exportados desde Rasa Studio (no se usan en el entrenamiento de `rasa train`).

Consulta `actions/actions.md` para entender el detalle de cada acción personalizada.

## Checklist de validación y entrenamiento

Tras cambios en dominio, reglas o historias, sigue los pasos de [docs/TRAINING_CHECKLIST.md](docs/TRAINING_CHECKLIST.md) (`rasa data validate`, tests, `rasa train` y variables de entorno).

## Red y Docker Compose

El gateway del chatbot es el puerto **8006** (FastAPI). En despliegues reales conviene **no publicar** hacia Internet los puertos internos de Rasa (5005) ni del action server (5055); en `docker-compose.yml` del monorepo hay una nota junto al servicio `rasa` para revisar el mapeo `5055:5055` en producción.

El servicio `rasa` monta **`./services/rasa/artifacts/models` → `/app/artifacts/models`**: ese directorio es la fuente principal del modelo en runtime.

Comportamiento del `entrypoint` al iniciar:

1. Carga desde `/app/artifacts/models` (`RASA_MODEL_DIR`) y selecciona el `.tar.gz` más reciente.
2. Si `artifacts/models` está vacío, toma el `.tar.gz` más reciente de `/app/models` (`RASA_FALLBACK_MODEL_DIR`, montado desde `./services/rasa/models`) y lo copia a `artifacts/models`.
3. Si no encuentra modelo, falla el arranque con error claro (**no entrena automáticamente**).

Por defecto se excluye `nlu_smoke_test.tar.gz` de la selección automática (`RASA_EXCLUDED_MODELS_REGEX`).

**Kafka UI** ya no arranca por defecto: usa el perfil `messaging-debug` para depurar tópicos, por ejemplo:

```bash
docker compose --profile messaging-debug up -d kafka-ui
```

## Recursos en VM (variables opcionales en `.env` del monorepo)

En `docker-compose.yml` hay límites `deploy.resources` parametrizables para aliviar OOM en máquinas pequeñas. Ejemplos (ajusta según RAM real):

| Variable | Uso típico |
|----------|------------|
| `RASA_MEM_LIMIT` / `RASA_MEM_RESERVATION` | Servicio `rasa` (NLU + Core + acciones + FastAPI en un contenedor) |
| `RASA_CPUS_LIMIT` / `RASA_CPUS_RESERVATION` | CPU del servicio `rasa` |
| `POSTGRES_MEM_LIMIT` / `POSTGRES_MEM_RESERVATION` | Postgres |
| `KAFKA_MEM_LIMIT` / `KAFKA_CPUS_LIMIT` | Broker Kafka |
| `ZOOKEEPER_MEM_LIMIT` | Zookeeper |
| `SHARED_VENV_MEM_LIMIT` | Imagen de build `shared-venv` |

Orientación muy aproximada: **8 GB RAM** en la VM para un stack completo con Rasa es un mínimo incómodo; **16 GB** es más holgado. Si hace falta, baja `RASA_MEM_LIMIT` y revisa que el modelo siga cargando sin OOM.

## Estructura de artefactos

- **`artifacts/models/`**: modelos `.tar.gz` servidos por `rasa run` (variable `RASA_MODEL_DIR` o `RASA_MODEL_PATH` en el contenedor si necesitas un archivo concreto).
- **`artifacts/eval/`**: salidas de evaluación (`rasa test`, informes); no se usan en runtime.

Detalle en [artifacts/README.md](artifacts/README.md).

## GitHub Actions (licencia e imagen Docker)

El workflow [`.github/workflows/rasa.yml`](../../.github/workflows/rasa.yml) solo ejecuta **`rasa data validate`** (coherencia de `domain.yml`, `data/*.yml`, etc.). **No sube ni usa modelos** en el repo; no hace falta Git LFS.

Los **story tests** (`rasa test --stories`) requieren un modelo entrenado: ejecútalos **en local** después de `rasa train` y con el `.tar.gz` en `artifacts/models/` (ver [docs/TRAINING_CHECKLIST.md](docs/TRAINING_CHECKLIST.md)).

### 1. Variable `RASA_PRO_LICENSE` (obligatoria)

Tu `.env` local **no** llega a GitHub. Crea un **secret** en el repositorio:

1. GitHub → **Settings** del repo → **Secrets and variables** → **Actions**.
2. **New repository secret**.
3. **Name:** `RASA_PRO_LICENSE`.
4. **Secret:** el mismo valor que en tu `.env` (licencia Rasa Pro).
5. **Add secret**.

Sin este secret, el job fallará con `license.not_found`.

### 2. Descarga de la imagen (“Pulling from rasa/rasa-pro…”)

La primera vez, Docker **descarga** la imagen `rasa/rasa-pro:3.12.3`; puede tardar varios minutos. Es normal; en ejecuciones siguientes a veces va más rápido por caché del runner.
