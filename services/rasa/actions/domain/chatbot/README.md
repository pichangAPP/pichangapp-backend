# Chatbot Domain (Rasa Actions)

Este directorio concentra utilidades y logica de apoyo para las acciones del chatbot
ubicadas en `modules/` y re-exportadas por `actions/action_chatbot.py`.
La meta es mantener las acciones enfocadas en orquestacion y dejar el detalle aqui.
Las operaciones de IO (HTTP/DB) viven en `actions/services/` o `actions/repositories/`.

## Modulos
- `async_utils.py`: helpers async para ejecutar funciones bloqueantes.
- `analytics.py`: registro de intents y logs en analytics.
- `context.py`: manejo de metadata, tokens y slots.
- `time_utils.py`: parseo de fechas/horas y helpers de tiempo.
- `text_utils.py`: normalizacion de texto compartida por el dominio.
- `preferences.py`: inferencia y resumen de preferencias del usuario.
- `budget.py`: parseo de presupuesto y foco de precio/rating.
- `recommendations.py`: relajacion de filtros y logs de recomendaciones.
- `reservation.py`: lectura de historial y slots desde Reservation.
- `admin.py`: consultas administrativas a analytics y campus.
