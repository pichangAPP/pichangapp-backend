## 📂 `domain/` – Memoria y respuestas de Chato Bot

El dominio reúne todo lo que el asistente necesita para conversar:

- **Intenciones** y **entidades** disponibles.
- **Slots** que guardan información clave (usuario, preferencias, etc.).
- **Formularios** que recopilan datos paso a paso.
- **Respuestas** predefinidas y la lista de **acciones personalizadas**.

Ahora todo vive en un único archivo `domain.yml`, listo para que `rasa train` lo procese sin mezclar formatos de Rasa Studio.
