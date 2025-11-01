# PichangApp Backend

## Auth Microservice Endpoints

| Endpoint                           | Método | API          | Función                                                   |
|------------------------------------|--------|-----------------------|--------------------------------------------------|
| `/api/pichangapp/v1/auth/register`| `POST`  | `auth_routes`   | Registra tanto a un usuario como un administrador.     |
| `/api/pichangapp/v1/auth/login`   | `POST`  | `auth_routes`   | Loguea a players y a admins                            |
| `/api/pichangapp/v1/users` | `GET`  | `user_routes`   | Obtiene toda la lista de usuarios   |
| `/api/pichangapp/v1/users/{user_id}` | `GET`  | `user_routes`   | Obtiene al usuario del id correspondiente"   |
| `/api/pichangapp/v1/users/active` | `GET`  | `user_routes`   | Obtiene toda la lista de usuarios de estado "active"   |
| `/api/pichangapp/v1/users/roles/{role_id}` | `GET`  | `user_routes`   | Obtiene toda la lista de usuarios pertenecientes a ese "role_id" |
| `/api/pichangapp/v1/users/{user_id}` | `PUT`  | `user_routes`   | Actualizar los datos MODIFICABLES de un usuario"   |

## Reservation Microservice Endpoints
### Schedule

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/reservation?field_id=1&day_of_week=Monday&status=reserved` | `GET` | `schedule_routes` | Obtiene todos los horarios de base de datos, además de ofrecer filtros opcionales por parámetro. |

> **Nota:** El parametro `field_id` es opcional y entero, `day_of_week` se refiere a un día de semana y `status` define a los estados de reservaciones a obtener.

#### Response

```json
[
  {
    "day_of_week": "Thursday",
    "start_time": "2025-10-30T08:00:00-05:00",
    "end_time": "2025-10-30T09:00:00-05:00",
    "status": "reserved",
    "price": "85.00",
    "id_field": 1,
    "id_user": null,
    "id_schedule": 2,
    "field": {
        "id_field": 1,
        "field_name": "Cancha Principal de Fútbol 7",
        "capacity": 14,
        "surface": "Grass sintético",
        "measurement": "60x40 m",
        "price_per_hour": "90.00",
        "status": "active",
        "open_time": "07:00:00",
        "close_time": "23:00:00",
        "minutes_wait": "10.00",
        "id_sport": 2,
        "id_campus": 1
    },
    "user": null
  }
]
```

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/reservation/time-slots?field_id=1&date=2025-10-31` | `GET` | `schedule_routes` | Obtiene todos los horarios para la vista de reservación. |

> **Nota:** El parametro `field_id` es obligatorio y entero, `date` es opcional en la petición y acepta valores en formato ISO `YYYY-MM-DD`. Si no lo incluyes, el servicio utiliza la fecha actual.

#### Response

```json
[
    {
        "start_time": "2025-10-31T10:00:00-05:00",
        "end_time": "2025-10-31T11:00:00-05:00",
        "status": "available",
        "price": "85.00"
    }
]
```

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/schedules/available?field_id=7&day_of_week=Friday` | `GET` | `schedule_routes` | Devuelve los horarios reservables filtrando conflictos con rentas activas. |
| `/api/pichangapp/v1/schedules/{schedule_id}` | `GET` | `schedule_routes` | Devuelve un horario por su identificador. |

> **Nota:** `field_id` (**obligatorio**), `day_of_week` (opcional), `status` (opcional): Permite filtrar por el estado original del horario antes de aplicar las reglas de disponibilidad. `exclude_rent_statuses` (opcional): Lista de estados de renta que no deberían bloquear un horario. Por defecto excluye `cancelled`, pero puedes añadir más estados repitiendo el parámetro (`&exclude_rent_statuses=cancelled&exclude_rent_statuses=refunded`).

#### Response

```json
[
  {
    "id_schedule": 42,
    "day_of_week": "friday",
    "start_time": "2024-05-17T18:00:00Z",
    "end_time": "2024-05-17T19:00:00Z",
    "status": "available",
    "price": 120.0,
    "id_field": 7,
    "id_user": null,
    "field": {
      "id_field": 7,
      "field_name": "Cancha Sintética A",
      "capacity": 10,
      "surface": "synthetic",
      "measurement": "20x40",
      "price_per_hour": 120.0,
      "status": "active",
      "open_time": "08:00:00",
      "close_time": "23:00:00",
      "minutes_wait": 15,
      "id_sport": 1,
      "id_campus": 3
    },
    "user": null
  }
]
```

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/schedules/` | `POST` | `schedule_routes` | Crear un nuevo horario. |
| `/api/pichangapp/v1/schedules/` | `PUT` | `schedule_routes` | Actualizar el horario. |

> **Nota:** El parametro `id_user` es opcional y entero,

#### Request

```json
{
  "day_of_week": "Friday",
  "start_time": "2025-10-31T20:00:00",
  "end_time": "2025-10-31T21:00:00",
  "status": "pending",
  "price": 90.00,
  "id_field": 1,
  "id_user":5
}

```

#### Response

```json
{
    "day_of_week": "Friday",
    "start_time": "2025-10-31T20:00:00-05:00",
    "end_time": "2025-10-31T21:00:00-05:00",
    "status": "pending",
    "price": "90.00",
    "id_field": 1,
    "id_user": 5,
    "id_schedule": 14,
    "field": {
        "id_field": 1,
        "field_name": "Cancha Principal de Fútbol 7",
        "capacity": 14,
        "surface": "Grass sintético",
        "measurement": "60x40 m",
        "price_per_hour": "90.00",
        "status": "active",
        "open_time": "07:00:00",
        "close_time": "23:00:00",
        "minutes_wait": "10.00",
        "id_sport": 2,
        "id_campus": 1
    },
    "user": {
        "id_user": 5,
        "name": "Leonel Alessandro",
        "lastname": "Ortega Espinoza",
        "email": "ortega1@gmail.com",
        "phone": "922113925",
        "imageurl": null,
        "status": "active"
    }
}

```
### Rents

