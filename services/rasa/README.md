# 🤖 Chato Bot – Asistente de reservas para PichangApp

Este servicio de Rasa convierte al bot en un concierge deportivo: responde preguntas frecuentes, recomienda canchas según preferencias y registra cada interacción en los esquemas `analytics` de la base de datos.

## 🚀 Capacidades principales
- **Recomendaciones inteligentes**: consulta `booking.field`, `booking.sports` y `booking.campus` para sugerir canchas acordes al deporte, zona y superficie solicitada.
- **Seguimiento analítico**: registra sesiones, intenciones y respuestas en `analytics.chatbot`, `analytics.chatbot_log`, `analytics.intents` y `analytics.recomendation_log`.
- **Feedback del usuario**: muestra los comentarios más recientes almacenados en `analytics.feedback`.
- **Atención integral**: guía sobre reservas, modificaciones, cancelaciones, tarifas y derivaciones con agentes humanos.

## ⚙️ Configuración
1. Crea un archivo `.env` en la raíz del proyecto (o exporta variables en el entorno) con las credenciales de Postgres:
   ```env
   CHATBOT_DATABASE_URL=postgresql+psycopg2://usuario:password@host:puerto/pichangapp
   # También se admiten las variables POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD y POSTGRES_PORT.
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
5. Inicia el bot localmente para pruebas:
   ```bash
   rasa shell --endpoints endpoints.yml
   ```

## 🧪 Datos y dominio
- **`data/nlu.yml`**: Intenciones y ejemplos en español.
- **`data/stories.yml`**: Historias que ilustran formularios y derivaciones humanas.
- **`data/rules.yml`**: Reglas que responden preguntas frecuentes y activan formularios.
- **`domain/domain.yml`**: Intenciones, entidades, formularios, respuestas y acciones de Chato Bot.

Los patrones heredados de Rasa Studio se conservan en `docs/patterns_backup/` como referencia. Allí encontrarás exactamente los archivos exportados desde Rasa Studio (no se usan en el entrenamiento de `rasa train`).

> ℹ️ Si antes usabas los **flows** de Studio notarás que ya no son necesarios: los slots `confirm_human_handoff` y `feedback_rating` ahora se administran internamente por las acciones, por eso aparecen como `controlled` en el dominio. Con esta configuración `rasa data validate` y `rasa train` dejan de exigir flows o mapeos LLM.

Consulta `actions/actions.md` para entender el detalle de cada acción personalizada.
