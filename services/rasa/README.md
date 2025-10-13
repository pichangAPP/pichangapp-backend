# 🤖 Asistente de reservas para PichangApp

Este servicio de Rasa convierte el bot en un concierge deportivo: responde preguntas frecuentes, recomienda canchas según preferencias y registra cada interacción en los esquemas `analytics` de la base de datos.

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
   python -m spacy download es_core_news_md
   ```
3. Entrena el modelo:
   ```bash
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
- **`data/general/*.yml`**: Flujos y NLU en español para saludos, reservas, historial, preguntas frecuentes y más.
- **`domain/general/*.yml`**: Intenciones, entidades, formularios y respuestas ajustadas al negocio deportivo.
- **`actions/action_chatbot.py`**: Conectores SQLAlchemy que consultan y actualizan las tablas analíticas.

Consulta `actions/actions.md` para entender el detalle de cada acción personalizada.
