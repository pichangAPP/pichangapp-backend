# 📁 `patterns_backup/` – Flujos heredados de Rasa Studio

Estos archivos son una copia literal de los *patterns* generados en Rasa Studio.
Se mantienen solo como referencia histórica y para reutilizarlos si decides volver
al modelo de flujos. No forman parte del proceso de entrenamiento de Rasa Open Source
(`rasa train`).

Cada YAML contiene exactamente lo que exportó Studio. Algunos flujos son muy cortos
(o incluso solo llaman a una acción personalizada) y por eso pueden parecer "vacíos".
Si necesitas activarlos de nuevo, vuelve a copiar los archivos a `data/` y
`domain/` y adapta sus acciones/respuestas según tu nueva configuración.
