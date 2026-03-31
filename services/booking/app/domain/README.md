# Booking Domain

Este directorio contiene la logica de dominio para el microservicio de `booking`.

## Business
- `business/validations.py`: validaciones del negocio (existencia y reglas de precios).
- `business/managers.py`: carga de datos de manager para negocios y campus.

## Campus
- `campus/builders.py`: construccion de entidad `Campus` con campos, imagenes y caracteristicas.
- `campus/validations.py`: validaciones de campus (horarios, rating, deportes de campos).
- `campus/images.py`: sincronizacion de imagenes del campus.
- `campus/fields.py`: actualizacion de contador de canchas.
- `campus/managers.py`: carga de data de manager para campus.
- `campus/schedules.py`: agregacion de schedules disponibles por campus.

## Field
- `field/validations.py`: reglas de cancha (capacidad, precio, tiempos) y validacion de eliminacion.
- `field/images.py`: validacion y sincronizacion de imagenes de canchas.
- `field/availability.py`: calculo del proximo horario disponible por cancha.
