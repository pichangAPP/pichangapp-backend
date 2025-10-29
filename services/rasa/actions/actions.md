## 📂 `actions/` – Toolkit del asistente de reservas

Aquí viven las acciones personalizadas que amplían las capacidades del bot. Úsalas para conectar con Postgres, consultar canchas, registrar métricas o derivar la conversación a un humano.

### Acciones disponibles
- `action_chatbot.py`
  - `ActionSubmitFieldRecommendationForm`: valida los datos capturados en el formulario, consulta las canchas disponibles en `booking.field` y registra la recomendación en los esquemas `analytics.*`.
  - `ActionShowRecommendationHistory`: resume las últimas sugerencias del usuario leyendo los logs del chatbot.
  - `ActionCheckFeedbackStatus`: consulta los comentarios registrados en `analytics.feedback` para un usuario.
  - `ActionCloseChatSession`: marca la conversación como cerrada en `analytics.chatbot`.
- `action_human_handoff.py`: comparte un resumen de los últimos mensajes y permite derivar la conversación a un agente humano.

Cada acción utiliza SQLAlchemy y lee las credenciales de la base de datos desde las variables de entorno (`CHATBOT_DATABASE_URL` o `DATABASE_URL`).

Consulta la [documentación oficial de Rasa](https://rasa.com/docs/pro/build/custom-actions) para profundizar en el ciclo de vida de las acciones.
