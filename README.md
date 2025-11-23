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
| `/api/pichangapp/v1/reservation/schedules?field_id=1&day_of_week=Monday&status=reserved` | `GET` | `schedule_routes` | Obtiene todos los horarios de la base de datos con filtros opcionales por cancha, día o estado. |
| `/api/pichangapp/v1/reservation/schedules/time-slots?field_id=1&date=2025-10-31` | `GET` | `schedule_routes` | Devuelve los horarios disponibles en formato de "time slots" para la fecha indicada. |
| `/api/pichangapp/v1/reservation/schedules/available?field_id=7&day_of_week=Friday` | `GET` | `schedule_routes` | Devuelve los horarios reservables aplicando las reglas de disponibilidad y exclusión de estados de renta. |
| `/api/pichangapp/v1/reservation/schedules/{schedule_id}` | `GET` | `schedule_routes` | Devuelve un horario por su identificador. |
| `/api/pichangapp/v1/reservation/schedules` | `POST` | `schedule_routes` | Crea un nuevo horario. |
| `/api/pichangapp/v1/reservation/schedules/{schedule_id}` | `PUT` | `schedule_routes` | Actualiza los datos de un horario existente. |
| `/api/pichangapp/v1/reservation/schedules/{schedule_id}` | `DELETE` | `schedule_routes` | Elimina un horario. |

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
| `/api/pichangapp/v1/reservation/schedules/time-slots?field_id=1&date=2025-10-31` | `GET` | `schedule_routes` | Obtiene todos los horarios para la vista de reservación. |

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
| `/api/pichangapp/v1/reservation/schedules/available?field_id=7&day_of_week=Friday` | `GET` | `schedule_routes` | Devuelve los horarios reservables filtrando conflictos con rentas activas. |

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

> **Nota:** El parámetro `id_user` es opcional en la creación/actualización de horarios.

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

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/reservation/rents?status=reserved&schedule_id=12` | `GET` | `rent_routes` | Obtiene todas las rentas con filtros opcionales por estado o por horario. |
| `/api/pichangapp/v1/reservation/rents/fields/{field_id}` | `GET` | `rent_routes` | Lista las rentas asociadas a una cancha específica. |
| `/api/pichangapp/v1/reservation/rents/users/{user_id}` | `GET` | `rent_routes` | Lista las rentas asociadas a un usuario. |
| `/api/pichangapp/v1/reservation/rents/campus/{campus_id}` | `GET` | `rent_routes` | Lista las rentas asociadas a un campus. |
| `/api/pichangapp/v1/reservation/rents/users/{user_id}/history` | `GET` | `rent_routes` | Devuelve el historial de rentas de un usuario (ordenado de más reciente a más antiguo). |
| `/api/pichangapp/v1/reservation/rents/{rent_id}` | `GET` | `rent_routes` | Devuelve una renta por su identificador. |
| `/api/pichangapp/v1/reservation/rents` | `POST` | `rent_routes` | Crea una nueva renta. |
| `/api/pichangapp/v1/reservation/rents/{rent_id}` | `PUT` | `rent_routes` | Actualiza una renta existente. |
| `/api/pichangapp/v1/reservation/rents/{rent_id}` | `DELETE` | `rent_routes` | Elimina una renta. |

## Booking Microservice Endpoints

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/booking/businesses` | `GET` | `business_routes` | Lista todos los negocios. |
| `/api/pichangapp/v1/booking/businesses` | `POST` | `business_routes` | Crea un nuevo negocio. |
| `/api/pichangapp/v1/booking/businesses/nearby?latitude=-12.05&longitude=-77.05` | `GET` | `business_routes` | Lista negocios cercanos a las coordenadas dadas. |
| `/api/pichangapp/v1/booking/businesses/managers/{manager_id}` | `GET` | `business_routes` | Obtiene el negocio administrado por el `manager_id`. |
| `/api/pichangapp/v1/booking/businesses/{business_id}` | `GET` | `business_routes` | Devuelve un negocio por su identificador. |
| `/api/pichangapp/v1/booking/businesses/{business_id}` | `PUT` | `business_routes` | Actualiza un negocio. |
| `/api/pichangapp/v1/booking/businesses/{business_id}` | `DELETE` | `business_routes` | Elimina un negocio. |
| `/api/pichangapp/v1/booking/businesses/{business_id}/campuses` | `GET` | `campus_routes` | Lista los campus de un negocio. |
| `/api/pichangapp/v1/booking/businesses/{business_id}/campuses/nearby?latitude=-12.05&longitude=-77.05` | `GET` | `campus_routes` | Lista campus cercanos al negocio usando coordenadas. |
| `/api/pichangapp/v1/booking/businesses/{business_id}/campuses` | `POST` | `campus_routes` | Crea un nuevo campus para el negocio. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}` | `GET` | `campus_routes` | Obtiene un campus por su identificador. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}` | `PUT` | `campus_routes` | Actualiza un campus existente. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}` | `DELETE` | `campus_routes` | Elimina un campus. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}/fields` | `GET` | `field_routes` | Lista las canchas de un campus. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}/fields` | `POST` | `field_routes` | Crea una cancha para el campus. |
| `/api/pichangapp/v1/booking/fields/{field_id}` | `GET` | `field_routes` | Obtiene una cancha por su identificador. |
| `/api/pichangapp/v1/booking/fields/{field_id}` | `PUT` | `field_routes` | Actualiza una cancha existente. |
| `/api/pichangapp/v1/booking/fields/{field_id}` | `DELETE` | `field_routes` | Elimina una cancha. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}/characteristic` | `GET` | `characteristic_routes` | Devuelve las características del campus. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}/characteristic` | `PATCH` | `characteristic_routes` | Actualiza las características del campus. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}/images` | `GET` | `image_routes` | Lista las imágenes asociadas a un campus. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}/images` | `POST` | `image_routes` | Crea una imagen para el campus. |
| `/api/pichangapp/v1/booking/fields/{field_id}/images` | `GET` | `image_routes` | Lista las imágenes asociadas a una cancha. |
| `/api/pichangapp/v1/booking/images/{image_id}` | `GET` | `image_routes` | Obtiene una imagen por su identificador. |
| `/api/pichangapp/v1/booking/images/{image_id}` | `PUT` | `image_routes` | Actualiza una imagen existente. |
| `/api/pichangapp/v1/booking/images/{image_id}` | `DELETE` | `image_routes` | Elimina una imagen. |

## Analytics Microservice Endpoints

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/analytics/revenue-summary` | `GET` | `analytics_routes` | Devuelve el resumen de ingresos agregados por fecha, semana y mes. |
| `/api/pichangapp/v1/analytics/campuses/{campus_id}/revenue-metrics` | `GET` | `analytics_routes` | Obtiene métricas detalladas de ingresos para un campus. |
| `/api/pichangapp/v1/analytics/campuses/{campus_id}/top-clients` | `GET` | `analytics_routes` | Lista los clientes más recurrentes del campus. |
| `/api/pichangapp/v1/analytics/campuses/{campus_id}/top-fields` | `GET` | `analytics_routes` | Lista las canchas más usadas del campus en el mes. |
| `/api/pichangapp/v1/analytics/feedback` | `POST` | `feedback_routes` | Registra feedback de un usuario autenticado. |
| `/api/pichangapp/v1/analytics/feedback/fields/{field_id}` | `GET` | `feedback_routes` | Lista todo el feedback asociado a una cancha. |
| `/api/pichangapp/v1/analytics/feedback/{feedback_id}` | `DELETE` | `feedback_routes` | Elimina feedback perteneciente al usuario autenticado. |

## Rasa (Chatbot) Microservice Endpoints

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/chatbot/messages` | `POST` | `chat_routes` | Envía un mensaje al chatbot y retorna la respuesta de Rasa. |
| `/api/pichangapp/v1/chatbot/users/{user_id}/history` | `GET` | `chat_routes` | Recupera el historial de conversaciones del usuario autorizado. |

## Notification Microservice Endpoints

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/notification/notifications/send-email` | `POST` | `notification_routes` | Envía correos de confirmación de renta a los destinatarios correspondientes. |

