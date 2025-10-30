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
3. Entrena el modelo:
   ```bash
   rasa data validate
   rasa train
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
   uvicorn app.main:app --host 0.0.0.0 --port 8006
   ```

   El gateway expone la ruta `/api/pichangapp/v1/chatbot/messages`, que requiere un token Bearer válido y reenvía los mensajes al servidor de Rasa.

## 🧪 Datos y dominio

- **`data/nlu.yml`**: Intenciones y ejemplos en español.
- **`data/stories.yml`**: Historias que ilustran formularios y validaciones basadas en credenciales.
- **`data/rules.yml`**: Reglas que responden preguntas frecuentes y activan formularios.
- **`domain/domain.yml`**: Intenciones, entidades, formularios, respuestas y acciones de Chato Bot.

Los patrones heredados de Rasa Studio se conservan en `docs/patterns_backup/` como referencia. Allí encontrarás exactamente los archivos exportados desde Rasa Studio (no se usan en el entrenamiento de `rasa train`).

Consulta `actions/actions.md` para entender el detalle de cada acción personalizada.
