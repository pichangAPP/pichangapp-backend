# Artefactos del servicio Rasa

- **`models/`**: paquetes `.tar.gz` producidos por `rasa train`. En Docker Compose este directorio se monta en el contenedor como `/app/artifacts/models` para no inflar la imagen.
- **`eval/`**: informes y gráficos de `rasa test` u otras evaluaciones; no forman parte del runtime del bot.

Entrenar escribiendo aquí:

```bash
cd services/rasa
rasa train --out artifacts/models
```

Las salidas de test puedes dirigirlas a `artifacts/eval` según flags de `rasa test` o moviendo los informes tras ejecutarlos.
