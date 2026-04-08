# Reservation Domain

Este directorio contiene la lógica de dominio para el microservicio de `reservation`.

## Rent
- `rent/defaults.py`: construcción de datos derivados de schedules (minutos, periodo, capacidad, notas admin).
- `rent/validations.py`: validaciones de rent (schedule activo, usuario/cancha existentes).
- `rent/hydrator.py`: mapeo a respuestas API (`RentResponse`).
- `rent/payments.py`: generación de códigos y validación de pagos.
- `rent/notifications.py`: payload y publicación de eventos de notificación.
- `rent/field_status.py`: actualización del estado de la cancha por rents.

## Schedule
- `schedule/validations.py`: reglas de validación de horarios y conflictos.
- `schedule/hydrator.py`: mapeo a respuestas API (`ScheduleResponse`).
- `schedule/time_slots.py`: generación de slots por fecha.

### Nota sobre `time_slots`
Se usa una estrategia de *timeline por slots* para evitar `O(n*m)` en la validación de rangos:
- Se generan slots alineados y se indexan por tiempo.
- Los rangos ocupados se convierten a índices y se marcan en un `set`.
- El filtrado final es `O(n + m)`.

Esto hace que el cálculo sea estable incluso con alto volumen de schedules/rents.
