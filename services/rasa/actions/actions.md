## 📂 `actions/` – Toolkit del asistente de reservas

Aquí viven las acciones personalizadas que amplían las capacidades del bot. Úsalas para conectar con Postgres, consultar canchas y registrar métricas de cada charla.

### Acciones disponibles
Las acciones ahora viven en módulos dentro de `actions/` y se re-exportan desde `action_chatbot.py` para que Rasa siga encontrándolas.

- `actions/recommendation_actions.py`
  - `ActionSubmitFieldRecommendationForm`: valida datos del formulario, consulta canchas disponibles en `booking.field` y registra la recomendación en `analytics.*`.
  - `ActionShowRecommendationHistory`: resume las últimas sugerencias del usuario leyendo los logs del chatbot.
  - `ActionLogFieldRecommendationRequest`: prepara el formulario y deja un log de intención.
- `actions/reservation_actions.py`
  - `ActionReprogramReservation`: consulta historial de rentas, destaca la reserva actual y chequea la agenda para explicar si se puede reprogramar.
- `actions/feedback_actions.py`
  - `ActionCheckFeedbackStatus`: consulta comentarios registrados en `analytics.feedback`.
  - `ActionHandleFeedbackRating`: procesa el feedback rápido (like/dislike).
- `actions/session_actions.py`
  - `ActionSessionStart`: inicializa la sesión con la información del usuario y su rol proveniente del token.
  - `ActionCloseChatSession`: marca la conversación como cerrada en `analytics.chatbot`.
  - `ActionEnsureUserRole`: sincroniza el rol del usuario desde metadata.
- `actions/admin_actions.py`
  - `ActionProvideAdminManagementTips`: recomendaciones operativas para gerentes según preferencias y sede administrada.
  - `ActionProvideAdminCampusTopClients`: lista clientes frecuentes del campus asociado al administrador.
  - `ActionProvideAdminFieldUsage`: retorna el uso de canchas por campus.
  - `ActionProvideAdminDemandAlerts`: alertas predictivas de demanda para administradores.
- `actions/intent_actions.py`
  - `ActionLogUserIntent`: registra la intención detectada en analytics.
- `actions/forms.py`
  - `ValidateFieldRecommendationForm`: validaciones del formulario de recomendaciones.

Cada acción utiliza SQLAlchemy y lee las credenciales de la base de datos desde las variables de entorno (`CHATBOT_DATABASE_URL` o `DATABASE_URL`).

Consulta la [documentación oficial de Rasa](https://rasa.com/docs/pro/build/custom-actions) para profundizar en el ciclo de vida de las acciones.
