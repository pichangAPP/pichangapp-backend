## 📂 `actions/` – Toolkit del asistente de reservas

Aquí viven las acciones personalizadas que amplían las capacidades del bot. Úsalas para conectar con Postgres, consultar canchas y registrar métricas de cada charla.

### Acciones disponibles
- `action_chatbot.py`
  - `ActionSubmitFieldRecommendationForm`: valida los datos capturados en el formulario, consulta las canchas disponibles en `booking.field` y registra la recomendación en los esquemas `analytics.*`.
  - `ActionShowRecommendationHistory`: resume las últimas sugerencias del usuario leyendo los logs del chatbot.
  - `ActionCheckFeedbackStatus`: consulta los comentarios registrados en `analytics.feedback` para un usuario.
  - `ActionCloseChatSession`: marca la conversación como cerrada en `analytics.chatbot`.
  - `ActionSessionStart`: inicializa la sesión con la información del usuario y su rol proveniente del token.
  - `ActionProvideAdminManagementTips`: ofrece recomendaciones operativas formales para gerentes según las preferencias detectadas y la sede administrada.
  - `ActionProvideAdminCampusTopClients`: consulta el endpoint de analytics para listar a los clientes que más rentan en el campus asociado al administrador.

Cada acción utiliza SQLAlchemy y lee las credenciales de la base de datos desde las variables de entorno (`CHATBOT_DATABASE_URL` o `DATABASE_URL`).

Consulta la [documentación oficial de Rasa](https://rasa.com/docs/pro/build/custom-actions) para profundizar en el ciclo de vida de las acciones.
