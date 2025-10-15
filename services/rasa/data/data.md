## 📂 `data/` – Datos de entrenamiento del asistente

En esta carpeta viven los archivos que Rasa usa para entrenar el modelo:

- **`nlu.yml`**: ejemplos de intenciones y entidades que Chato Bot debe reconocer.
- **`stories.yml`**: conversaciones de ejemplo que muestran cómo debe fluir el diálogo.
- **`rules.yml`**: atajos deterministas (por ejemplo, responder a un saludo o activar un formulario).

Los patrones heredados de Rasa Studio se movieron a `../docs/patterns_backup/` para mantenerlos como referencia sin interferir en el entrenamiento.
