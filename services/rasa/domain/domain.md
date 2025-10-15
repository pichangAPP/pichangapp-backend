## 📂 `domain/` – Memoria y respuestas de Chato Bot

El dominio reúne todo lo que el asistente necesita para conversar:

- **Intenciones** y **entidades** disponibles.
- **Slots** que guardan información clave (usuario, preferencias, etc.).
- **Formularios** que recopilan datos paso a paso.
- **Respuestas** predefinidas y la lista de **acciones personalizadas**.

Ahora todo vive en un único archivo `domain.yml`, listo para que `rasa train` lo procese sin mezclar formatos de Rasa Studio.

> Nota: los slots heredados de los flows (`confirm_human_handoff` y `feedback_rating`) se mantienen como `controlled` para que puedan completarse desde las acciones sin requerir mapeos LLM.
