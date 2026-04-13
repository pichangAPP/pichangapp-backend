# Cuadra Backend

Documentación unificada de endpoints por microservicio. Para flujos complejos (time slots, reservas en canchas combinadas, integración con Rasa), ver el [manual de funcionalidades avanzadas](docs/manual-funcionalidades-avanzadas.md).

## Convenciones

- **Prefijo común:** `/api/pichangapp/v1/...`
- **JWT (Bearer):** requerido en **Booking** (router v1), **Analytics** (incluye feedback) y **Rasa (chatbot)**. Enviar cabecera `Authorization: Bearer <access_token>` salvo que el gateway inyecte otra política.
- **Auth — API interna:** rutas bajo `/api/pichangapp/v1/internal/...` usan la cabecera `X-Internal-Auth` (clave configurada en el servicio Auth). El **API Gateway** actual no las reexpone; llamar al host del servicio Auth en despliegues internos.

---

## Auth Microservice Endpoints

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/auth/register` | `POST` | `auth_routes` | Registra usuario o administrador. |
| `/api/pichangapp/v1/auth/login` | `POST` | `auth_routes` | Inicio de sesión con email y contraseña. |
| `/api/pichangapp/v1/auth/google` | `POST` | `auth_routes` | Inicio de sesión con `id_token` de Google. |
| `/api/pichangapp/v1/auth/refresh` | `POST` | `auth_routes` | Emite nuevos tokens a partir del `refresh_token`. |
| `/api/pichangapp/v1/users` | `GET` | `user_routes` | Lista todos los usuarios. |
| `/api/pichangapp/v1/users/{user_id}` | `GET` | `user_routes` | Obtiene un usuario por id. |
| `/api/pichangapp/v1/users/active` | `GET` | `user_routes` | Lista usuarios con estado `active`. |
| `/api/pichangapp/v1/users/roles/{role_id}` | `GET` | `user_routes` | Lista usuarios con el rol indicado. |
| `/api/pichangapp/v1/users/{user_id}` | `PUT` | `user_routes` | Actualiza datos modificables del usuario. |
| `/api/pichangapp/v1/internal/users/{user_id}` | `GET` | `internal_routes` | Consulta usuario por id (servicio a servicio). |
| `/api/pichangapp/v1/internal/users?ids=1&ids=2` | `GET` | `internal_routes` | Consulta usuarios por lista de ids (servicio a servicio). |

### Auth — ejemplos completos (JSON)

#### `POST /api/pichangapp/v1/auth/register` — Request

```json
{
  "name": "Ana",
  "lastname": "Pérez",
  "email": "ana.perez@example.com",
  "password": "Secreto123",
  "phone": "999888777",
  "id_role": 1,
  "imageurl": null,
  "birthdate": null,
  "gender": null,
  "city": "Lima",
  "district": "Miraflores"
}
```

#### `POST /api/pichangapp/v1/auth/register` — Response (`TokenResponse`)

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id_user": 12,
    "name": "Ana",
    "lastname": "Pérez",
    "email": "ana.perez@example.com",
    "phone": "999888777",
    "imageurl": null,
    "birthdate": null,
    "gender": null,
    "city": "Lima",
    "district": "Miraflores",
    "status": "active",
    "id_role": 1,
    "created_at": "2026-04-12T10:00:00",
    "updated_at": null
  }
}
```

#### `POST /api/pichangapp/v1/auth/login` — Request

```json
{
  "email": "ana.perez@example.com",
  "password": "Secreto123"
}
```

#### `POST /api/pichangapp/v1/auth/login` — Response

Misma forma que `TokenResponse` del registro (tokens + objeto `user`).

#### `POST /api/pichangapp/v1/auth/google` — Request

```json
{
  "id_token": "GOOGLE_OIDC_ID_TOKEN_JWT"
}
```

#### `POST /api/pichangapp/v1/auth/refresh` — Request

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

#### `PUT /api/pichangapp/v1/users/{user_id}` — Request

```json
{
  "name": "Ana",
  "lastname": "Pérez López",
  "phone": "999888777",
  "imageurl": null,
  "birthdate": null,
  "gender": "F",
  "city": "Lima",
  "district": "Surco",
  "status": "active",
  "id_role": 1
}
```

#### `PUT /api/pichangapp/v1/users/{user_id}` — Response

Objeto `UserResponse` (misma forma que `user` dentro de `TokenResponse`).

#### API interna — cabeceras

```http
GET /api/pichangapp/v1/internal/users/12 HTTP/1.1
X-Internal-Auth: <AUTH_INTERNAL_API_KEY>
```

#### `GET /api/pichangapp/v1/internal/users?ids=1&ids=12` — Response

```json
[
  {
    "id_user": 1,
    "name": "Admin",
    "lastname": "Sistema",
    "email": "admin@example.com",
    "phone": "900000001",
    "imageurl": null,
    "birthdate": null,
    "gender": null,
    "city": null,
    "district": null,
    "status": "active",
    "id_role": 2,
    "created_at": "2026-01-01T08:00:00",
    "updated_at": null
  }
]
```

---

## Reservation Microservice Endpoints

### Schedule

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/reservation/schedules` | `GET` | `schedule_routes` | Lista horarios; filtros opcionales `field_id`, `day_of_week`, `status`. |
| `/api/pichangapp/v1/reservation/schedules/time-slots?field_id=1&date=2026-04-12` | `GET` | `schedule_routes` | Slots de una hora para la fecha (query `date` opcional; por defecto hoy). |
| `/api/pichangapp/v1/reservation/schedules/available?field_id=7&day_of_week=Friday` | `GET` | `schedule_routes` | Horarios reservables con reglas de disponibilidad y rentas. |
| `/api/pichangapp/v1/reservation/schedules/{schedule_id}` | `GET` | `schedule_routes` | Un horario por id. |
| `/api/pichangapp/v1/reservation/schedules` | `POST` | `schedule_routes` | Crea un horario. |
| `/api/pichangapp/v1/reservation/schedules/{schedule_id}` | `PUT` | `schedule_routes` | Actualiza un horario. |
| `/api/pichangapp/v1/reservation/schedules/{schedule_id}` | `DELETE` | `schedule_routes` | Elimina un horario. |

> **Notas:** En `GET .../schedules`, `field_id` es opcional. En **time-slots**, `field_id` es obligatorio; `date` en formato `YYYY-MM-DD`. En **available**, `field_id` es obligatorio; `exclude_rent_statuses` se puede repetir en query (`&exclude_rent_statuses=cancelled&exclude_rent_statuses=refunded`).

#### `GET .../schedules` — Response (fragmento)

```json
[
  {
    "day_of_week": "Thursday",
    "start_time": "2026-04-10T08:00:00-05:00",
    "end_time": "2026-04-10T09:00:00-05:00",
    "status": "reserved",
    "price": "85.00",
    "id_status": 3,
    "id_field": 1,
    "id_user": null,
    "id_schedule": 2,
    "created_at": "2026-04-01T12:00:00-05:00",
    "updated_at": null,
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

#### `GET .../schedules/time-slots` — Response

```json
[
  {
    "start_time": "2026-04-12T10:00:00-05:00",
    "end_time": "2026-04-12T11:00:00-05:00",
    "status": "available",
    "price": "85.00"
  }
]
```

#### `GET .../schedules/available` — Response (fragmento)

```json
[
  {
    "id_schedule": 42,
    "day_of_week": "friday",
    "start_time": "2026-04-11T18:00:00Z",
    "end_time": "2026-04-11T19:00:00Z",
    "status": "available",
    "price": "120.00",
    "id_status": 1,
    "id_field": 7,
    "id_user": null,
    "created_at": "2026-03-15T10:00:00Z",
    "updated_at": null,
    "field": {
      "id_field": 7,
      "field_name": "Cancha Sintética A",
      "capacity": 10,
      "surface": "synthetic",
      "measurement": "20x40",
      "price_per_hour": "120.00",
      "status": "active",
      "open_time": "08:00:00",
      "close_time": "23:00:00",
      "minutes_wait": "15.00",
      "id_sport": 1,
      "id_campus": 3
    },
    "user": null
  }
]
```

#### `POST .../schedules` — Request

```json
{
  "day_of_week": "Friday",
  "start_time": "2026-04-12T20:00:00",
  "end_time": "2026-04-12T21:00:00",
  "status": "pending",
  "price": "90.00",
  "id_status": null,
  "id_field": 1,
  "id_user": 5
}
```

#### `POST .../schedules` — Response

```json
{
  "day_of_week": "Friday",
  "start_time": "2026-04-12T20:00:00-05:00",
  "end_time": "2026-04-12T21:00:00-05:00",
  "status": "pending",
  "price": "90.00",
  "id_status": 2,
  "id_field": 1,
  "id_user": 5,
  "id_schedule": 14,
  "created_at": "2026-04-12T09:15:00-05:00",
  "updated_at": null,
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

`PUT .../schedules/{schedule_id}` acepta el mismo tipo de campos que `ScheduleUpdate` (todos opcionales). `DELETE` responde `204 No Content`.

### Rents

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/reservation/rents` | `GET` | `rent_routes` | Lista rentas; query opcional `status`, `schedule_id`. |
| `/api/pichangapp/v1/reservation/rents/fields/{field_id}` | `GET` | `rent_routes` | Rentas de una cancha. |
| `/api/pichangapp/v1/reservation/rents/users/{user_id}` | `GET` | `rent_routes` | Rentas de un usuario. |
| `/api/pichangapp/v1/reservation/rents/campus/{campus_id}` | `GET` | `rent_routes` | Rentas de un campus. |
| `/api/pichangapp/v1/reservation/rents/users/{user_id}/history` | `GET` | `rent_routes` | Historial de rentas del usuario (más reciente primero). |
| `/api/pichangapp/v1/reservation/rents/{rent_id}` | `GET` | `rent_routes` | Una renta por id. |
| `/api/pichangapp/v1/reservation/rents` | `POST` | `rent_routes` | Crea renta simple (un horario); devuelve instrucciones de pago. |
| `/api/pichangapp/v1/reservation/rents/combo` | `POST` | `rent_routes` | Crea renta en canchas combinadas (varios horarios alineados). |
| `/api/pichangapp/v1/reservation/rents/admin` | `POST` | `rent_routes` | Crea renta desde administración. |
| `/api/pichangapp/v1/reservation/rents/{rent_id}/cancel` | `PUT` | `rent_routes` | Cancela renta y libera horario. |
| `/api/pichangapp/v1/reservation/rents/{rent_id}` | `PUT` | `rent_routes` | Actualiza renta. |
| `/api/pichangapp/v1/reservation/rents/admin/{rent_id}` | `PUT` | `rent_routes` | Actualiza renta (admin). |
| `/api/pichangapp/v1/reservation/rents/{rent_id}` | `DELETE` | `rent_routes` | Elimina renta. |

#### `POST .../rents` — Request (mínimo típico)

El servicio completa periodo, montos y fechas a partir del horario cuando `status` es `pending_payment`.

```json
{
  "id_schedule": 42,
  "status": "pending_payment"
}
```

#### `POST .../rents` — Response (`RentPaymentResponse`, ejemplo)

```json
{
  "rent": {
    "id_rent": 500,
    "period": "hour",
    "start_time": "2026-04-12T18:00:00-05:00",
    "end_time": "2026-04-12T19:00:00-05:00",
    "initialized": "2026-04-12T17:55:00-05:00",
    "finished": null,
    "status": "pending_payment",
    "id_status": 10,
    "minutes": "60.00",
    "mount": "120.00",
    "date_log": "2026-04-12T17:55:00-05:00",
    "date_create": "2026-04-12T17:55:00-05:00",
    "payment_deadline": "2026-04-12T18:00:00-05:00",
    "capacity": 10,
    "id_payment": null,
    "payment_code": "PAY-9F3A2C",
    "payment_proof_url": null,
    "payment_reviewed_at": null,
    "payment_reviewed_by": null,
    "customer_full_name": null,
    "customer_phone": null,
    "customer_email": null,
    "customer_document": null,
    "customer_notes": null,
    "id_schedule": 42,
    "schedules": [
      {
        "id_schedule": 42,
        "day_of_week": "saturday",
        "start_time": "2026-04-12T18:00:00-05:00",
        "end_time": "2026-04-12T19:00:00-05:00",
        "status": "hold_payment",
        "id_status": 4,
        "price": "120.00",
        "field": {
          "id_field": 7,
          "field_name": "Cancha Sintética A",
          "capacity": 10,
          "surface": "synthetic",
          "measurement": "20x40",
          "price_per_hour": "120.00",
          "status": "active",
          "open_time": "08:00:00",
          "close_time": "23:00:00",
          "minutes_wait": "15.00",
          "id_sport": 1,
          "id_campus": 3
        },
        "user": null
      }
    ],
    "schedule": {
      "id_schedule": 42,
      "day_of_week": "saturday",
      "start_time": "2026-04-12T18:00:00-05:00",
      "end_time": "2026-04-12T19:00:00-05:00",
      "status": "hold_payment",
      "id_status": 4,
      "price": "120.00",
      "field": {
        "id_field": 7,
        "field_name": "Cancha Sintética A",
        "capacity": 10,
        "surface": "synthetic",
        "measurement": "20x40",
        "price_per_hour": "120.00",
        "status": "active",
        "open_time": "08:00:00",
        "close_time": "23:00:00",
        "minutes_wait": "15.00",
        "id_sport": 1,
        "id_campus": 3
      },
      "user": null
    }
  },
  "payment_instructions": {
    "yape_phone": "999111222",
    "yape_qr_url": "https://example.com/qr/yape.png",
    "plin_phone": null,
    "plin_qr_url": null,
    "payment_code": "PAY-9F3A2C",
    "message": "Transfiere con el código indicado y sube tu comprobante.",
    "status": "active",
    "created_at": "2026-04-12T17:55:00-05:00",
    "updated_at": null
  }
}
```

#### `POST .../rents/combo` — Request

`status` debe ser exactamente `pending_payment`. `id_schedules` debe tener un id por cada cancha de la combinación, misma ventana horaria.

```json
{
  "id_combination": 3,
  "id_schedules": [101, 102],
  "status": "pending_payment",
  "customer_full_name": "Equipo Los Cóndores",
  "customer_phone": "987654321",
  "customer_email": "capitan@example.com"
}
```

#### `POST .../rents/combo` — Response

Misma forma que `RentPaymentResponse`; en rentas combo, `schedules` incluye un elemento por cada horario vinculado.

#### `POST .../rents/admin` — Request

```json
{
  "id_schedule": 42,
  "status": "confirmed",
  "customer_full_name": "Cliente VIP",
  "customer_phone": "900111222",
  "customer_email": "vip@example.com",
  "customer_document": "12345678",
  "customer_notes": "Llega 10 minutos antes"
}
```

#### `POST .../rents/admin` — Response

Objeto `RentResponse` (sin bloque `payment_instructions`).

#### `PUT .../rents/{rent_id}/cancel` — Request (opcional)

```json
{
  "schedule_id": 42
}
```

#### `PUT .../rents/{rent_id}/cancel` — Response

```json
{
  "rent_id": 500,
  "rent_status": "cancelled",
  "schedule_id": 42,
  "schedule_status": "available"
}
```

### Status catalog

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/reservation/status-catalog` | `GET` | `status_catalog_routes` | Lista estados; filtros opcionales `entity`, `is_active`. |
| `/api/pichangapp/v1/reservation/status-catalog/{status_id}` | `GET` | `status_catalog_routes` | Obtiene un estado del catálogo. |
| `/api/pichangapp/v1/reservation/status-catalog` | `POST` | `status_catalog_routes` | Crea entrada de catálogo. |
| `/api/pichangapp/v1/reservation/status-catalog/{status_id}` | `PUT` | `status_catalog_routes` | Actualiza entrada. |
| `/api/pichangapp/v1/reservation/status-catalog/{status_id}` | `DELETE` | `status_catalog_routes` | Elimina entrada (`204`). |

#### `POST .../status-catalog` — Request

```json
{
  "entity": "rent",
  "code": "pending_review",
  "name": "Pendiente de revisión",
  "description": "Pago reportado, pendiente de validación manual.",
  "is_final": false,
  "sort_order": 40,
  "is_active": true
}
```

#### `POST .../status-catalog` — Response

```json
{
  "id_status": 88,
  "entity": "rent",
  "code": "pending_review",
  "name": "Pendiente de revisión",
  "description": "Pago reportado, pendiente de validación manual.",
  "is_final": false,
  "sort_order": 40,
  "is_active": true,
  "created_at": "2026-04-12T11:00:00-05:00",
  "updated_at": "2026-04-12T11:00:00-05:00"
}
```

---

## Booking Microservice Endpoints

**Autenticación:** todas las rutas bajo `/api/pichangapp/v1/booking` del router v1 requieren **JWT** válido (`Authorization: Bearer ...`).

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/booking/businesses` | `GET` | `business_routes` | Lista negocios. |
| `/api/pichangapp/v1/booking/businesses` | `POST` | `business_routes` | Crea negocio (y campus opcionales anidados). |
| `/api/pichangapp/v1/booking/businesses/nearby?latitude=-12.05&longitude=-77.05` | `GET` | `business_routes` | Negocios cercanos. |
| `/api/pichangapp/v1/booking/businesses/managers/{manager_id}` | `GET` | `business_routes` | Negocio por id de manager. |
| `/api/pichangapp/v1/booking/businesses/{business_id}` | `GET` | `business_routes` | Detalle de negocio. |
| `/api/pichangapp/v1/booking/businesses/{business_id}` | `PUT` | `business_routes` | Actualiza negocio. |
| `/api/pichangapp/v1/booking/businesses/{business_id}` | `DELETE` | `business_routes` | Elimina negocio. |
| `/api/pichangapp/v1/booking/businesses/{business_id}/legal` | `GET` | `business_legal_routes` | Datos legales del negocio. |
| `/api/pichangapp/v1/booking/businesses/{business_id}/legal` | `POST` | `business_legal_routes` | Crea datos legales. |
| `/api/pichangapp/v1/booking/businesses/{business_id}/legal` | `PUT` | `business_legal_routes` | Actualiza datos legales. |
| `/api/pichangapp/v1/booking/businesses/{business_id}/legal` | `DELETE` | `business_legal_routes` | Elimina datos legales (`204`). |
| `/api/pichangapp/v1/booking/businesses/{business_id}/social-media` | `GET` | `business_social_media_routes` | Redes del negocio. |
| `/api/pichangapp/v1/booking/businesses/{business_id}/social-media` | `POST` | `business_social_media_routes` | Crea redes. |
| `/api/pichangapp/v1/booking/businesses/{business_id}/social-media` | `PUT` | `business_social_media_routes` | Actualiza redes. |
| `/api/pichangapp/v1/booking/businesses/{business_id}/social-media` | `DELETE` | `business_social_media_routes` | Elimina redes (`204`). |
| `/api/pichangapp/v1/booking/businesses/{business_id}/campuses` | `GET` | `campus_routes` | Lista campus del negocio. |
| `/api/pichangapp/v1/booking/businesses/{business_id}/campuses/nearby?latitude=-12.05&longitude=-77.05` | `GET` | `campus_routes` | Campus cercanos. |
| `/api/pichangapp/v1/booking/businesses/{business_id}/campuses` | `POST` | `campus_routes` | Crea campus. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}` | `GET` | `campus_routes` | Obtiene campus. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}` | `PUT` | `campus_routes` | Actualiza campus. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}` | `DELETE` | `campus_routes` | Elimina campus. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}/fields` | `GET` | `field_routes` | Lista canchas. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}/fields` | `POST` | `field_routes` | Crea cancha. |
| `/api/pichangapp/v1/booking/fields/{field_id}` | `GET` | `field_routes` | Obtiene cancha. |
| `/api/pichangapp/v1/booking/fields/{field_id}` | `PUT` | `field_routes` | Actualiza cancha. |
| `/api/pichangapp/v1/booking/fields/{field_id}` | `DELETE` | `field_routes` | Elimina cancha. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}/field-combinations` | `GET` | `field_combination_routes` | Lista combinaciones de canchas del campus. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}/field-combinations` | `POST` | `field_combination_routes` | Crea combinación (≥2 canchas). |
| `/api/pichangapp/v1/booking/fields/{field_id}/field-combinations` | `GET` | `field_combination_routes` | Combinaciones que incluyen la cancha. |
| `/api/pichangapp/v1/booking/field-combinations/{combination_id}` | `GET` | `field_combination_routes` | Detalle de combinación. |
| `/api/pichangapp/v1/booking/field-combinations/{combination_id}` | `PUT` | `field_combination_routes` | Actualiza combinación. |
| `/api/pichangapp/v1/booking/field-combinations/{combination_id}` | `DELETE` | `field_combination_routes` | Elimina combinación (`204`). |
| `/api/pichangapp/v1/booking/campuses/{campus_id}/characteristic` | `GET` | `characteristic_routes` | Características del campus. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}/characteristic` | `PATCH` | `characteristic_routes` | Actualiza características. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}/images` | `GET` | `image_routes` | Imágenes del campus. |
| `/api/pichangapp/v1/booking/campuses/{campus_id}/images` | `POST` | `image_routes` | Crea imagen del campus. |
| `/api/pichangapp/v1/booking/fields/{field_id}/images` | `GET` | `image_routes` | Imágenes de la cancha. |
| `/api/pichangapp/v1/booking/images/{image_id}` | `GET` | `image_routes` | Obtiene imagen. |
| `/api/pichangapp/v1/booking/images/{image_id}` | `PUT` | `image_routes` | Actualiza imagen. |
| `/api/pichangapp/v1/booking/images/{image_id}` | `DELETE` | `image_routes` | Elimina imagen. |
| `/api/pichangapp/v1/booking/kafka/test` | `POST` | `kafka_routes` | Publica evento de prueba en Kafka (diagnóstico). |

#### `POST .../campuses/{campus_id}/field-combinations` — Request

```json
{
  "name": "Full court A+B",
  "description": "Canchas 1 y 2 juntas para fútbol 11",
  "status": "active",
  "price_per_hour": "180.00",
  "members": [
    { "id_field": 10, "sort_order": 0 },
    { "id_field": 11, "sort_order": 1 }
  ]
}
```

#### `POST .../campuses/{campus_id}/field-combinations` — Response

```json
{
  "id_combination": 3,
  "id_campus": 5,
  "name": "Full court A+B",
  "description": "Canchas 1 y 2 juntas para fútbol 11",
  "status": "active",
  "price_per_hour": "180.00",
  "created_at": "2026-04-12T12:00:00-05:00",
  "updated_at": null,
  "members": [
    { "id_field": 10, "field_name": "Cancha A", "sort_order": 0 },
    { "id_field": 11, "field_name": "Cancha B", "sort_order": 1 }
  ]
}
```

#### `POST .../businesses/{business_id}/legal` — Request (ejemplo mínimo)

```json
{
  "terms_url": "https://mi-sede.com/terminos",
  "privacy_policy_url": "https://mi-sede.com/privacidad",
  "version": "2026-04",
  "effective_from": "2026-04-01"
}
```

#### `POST .../kafka/test` — Response

```json
{
  "status": "sent",
  "topic": "booking.events",
  "event": {
    "event_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "event_type": "booking.requested",
    "booking_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "occurred_at": "2026-04-12T18:00:00+00:00",
    "source": "booking",
    "payload": { "status": "requested" }
  }
}
```

Los cuerpos de `POST/PUT` para negocios, campus, canchas, imágenes y características siguen los esquemas `BusinessCreate`, `CampusCreate`, `FieldCreate`, `ImageCreate`, etc., en el código del servicio booking.

---

## Payment Microservice Endpoints

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/payment/payments` | `GET` | `payment_routes` | Lista pagos; query opcional `status_filter`. |
| `/api/pichangapp/v1/payment/payments/{payment_id}` | `GET` | `payment_routes` | Detalle de pago. |
| `/api/pichangapp/v1/payment/payments` | `POST` | `payment_routes` | Registra pago. |
| `/api/pichangapp/v1/payment/payments/{payment_id}` | `PATCH` | `payment_routes` | Actualiza pago. |
| `/api/pichangapp/v1/payment/payment-methods` | `GET` | `payment_methods_routes` | Lista métodos; filtros `id_business`, `id_campus`, `status_filter`. |
| `/api/pichangapp/v1/payment/payment-methods/{payment_methods_id}` | `GET` | `payment_methods_routes` | Detalle. |
| `/api/pichangapp/v1/payment/payment-methods` | `POST` | `payment_methods_routes` | Crea configuración de métodos. |
| `/api/pichangapp/v1/payment/payment-methods/{payment_methods_id}` | `PATCH` | `payment_methods_routes` | Actualiza configuración. |
| `/api/pichangapp/v1/payment/payment-methods/{payment_methods_id}` | `DELETE` | `payment_methods_routes` | Elimina (`204`). |

#### `POST .../payments` — Request

```json
{
  "amount": "120.00",
  "currency": "PEN",
  "method": "yape",
  "status": "completed",
  "type": "rent",
  "rent_id": 500,
  "payer_phone": "999888777",
  "approval_code": "ABC123",
  "paid_at": "2026-04-12T18:30:00-05:00",
  "memberships_id_membership": null,
  "reference": null,
  "additional_data": null
}
```

#### `POST .../payments` — Response

```json
{
  "id_payment": 77,
  "transaction_id": 9001,
  "amount": "120.00",
  "currency": "PEN",
  "method": "yape",
  "status": "completed",
  "type": "rent",
  "paid_at": "2026-04-12T18:30:00-05:00",
  "memberships_id_membership": null,
  "reference": null,
  "additional_data": null
}
```

#### `POST .../payment-methods` — Request (solo efectivo)

```json
{
  "id_business": 1,
  "id_campus": 5,
  "uses_cash": true,
  "uses_yape": false,
  "uses_plin": false,
  "uses_bank_transfer": false,
  "uses_card": false,
  "uses_pos": false,
  "uses_apple_pay": false,
  "uses_google_pay": false,
  "uses_invoice": false,
  "status": "active"
}
```

#### `POST .../payment-methods` — Response (fragmento)

```json
{
  "id_payment_methods": 4,
  "id_business": 1,
  "id_campus": 5,
  "uses_cash": true,
  "uses_yape": false,
  "status": "active",
  "created_at": "2026-04-12T13:00:00-05:00",
  "updated_at": "2026-04-12T13:00:00-05:00"
}
```

Si activas Yape/Plin/transferencia u otros flags, deben enviarse los campos obligatorios asociados (ver validaciones en `PaymentMethodsCreate`).

---

## Analytics Microservice Endpoints

**Autenticación:** **JWT** obligatorio en todas las rutas del servicio.

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/analytics/revenue-summary` | `GET` | `analytics_routes` | Ingresos agregados; queries opcionales `start_date`, `end_date`, `status` (default `paid`). |
| `/api/pichangapp/v1/analytics/campuses/{campus_id}/revenue-metrics` | `GET` | `analytics_routes` | Métricas de ingresos del campus. |
| `/api/pichangapp/v1/analytics/campuses/{campus_id}/top-clients` | `GET` | `analytics_routes` | Clientes más recurrentes. |
| `/api/pichangapp/v1/analytics/campuses/{campus_id}/top-fields` | `GET` | `analytics_routes` | Canchas más usadas en el mes. |
| `/api/pichangapp/v1/analytics/feedback` | `POST` | `feedback_routes` | Crea feedback del usuario autenticado. |
| `/api/pichangapp/v1/analytics/feedback/fields/{field_id}` | `GET` | `feedback_routes` | Lista feedback de una cancha. |
| `/api/pichangapp/v1/analytics/feedback/{feedback_id}` | `DELETE` | `feedback_routes` | Elimina feedback del usuario autenticado. |

#### `POST .../analytics/feedback` — Request

```json
{
  "id_rent": 500,
  "rating": 9.5,
  "comment": "Excelente iluminación y vestuarios limpios."
}
```

#### `POST .../analytics/feedback` — Response

```json
{
  "id_feedback": 33,
  "id_rent": 500,
  "id_user": 12,
  "rating": 9.5,
  "comment": "Excelente iluminación y vestuarios limpios.",
  "created_at": "2026-04-12T20:00:00-05:00"
}
```

---

## Rasa (Chatbot) Microservice Endpoints

Las rutas del chatbot viven en el servicio FastAPI de Rasa bajo el prefijo `/api/pichangapp/v1/chatbot`. Instalación, entrenamiento del modelo, variables de entorno y seguridad de acciones admin se documentan en [services/rasa/README.md](services/rasa/README.md).

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/chatbot/messages` | `POST` | `chat_routes` | Envía mensaje al bot; reenvía a Rasa con metadata enriquecida. |
| `/api/pichangapp/v1/chatbot/users/{user_id}/history` | `GET` | `chat_routes` | Historial de sesiones y mensajes (solo el propio usuario o admin). |

**Autenticación:** `Authorization: Bearer <access_token>` obligatorio.

#### `POST .../chatbot/messages` — Request

```json
{
  "message": "Quiero una cancha de fútbol 7 en Surco para el sábado en la tarde",
  "conversation_id": "user-12-session-1",
  "metadata": {
    "locale": "es-PE"
  }
}
```

Si omites `conversation_id`, el servicio usa `user-{id}` derivado del JWT. El servidor fusiona en metadata: `user_id`, `id_user`, `user_role`, `id_role`, `token`, y `model` por defecto desde configuración.

#### `POST .../chatbot/messages` — Response

```json
{
  "conversation_id": "user-12-session-1",
  "messages": [
    {
      "recipient_id": "user-12-session-1",
      "text": "Tengo estas canchas en Surco para el sábado por la tarde...",
      "image": null,
      "custom": null
    }
  ]
}
```

#### `GET .../chatbot/users/{user_id}/history` — Response (fragmento)

```json
{
  "user_id": 12,
  "sessions": [
    {
      "session_id": 55,
      "theme": "general",
      "status": "open",
      "started_at": "2026-04-12T15:00:00-05:00",
      "ended_at": null,
      "messages": [
        {
          "message": "Hola",
          "bot_response": "¡Hola! Soy Chato, ¿en qué te ayudo?",
          "response_type": "session_started",
          "sender_type": "bot",
          "timestamp": "2026-04-12T15:00:05-05:00",
          "intent_confidence": null,
          "metadata": null
        }
      ]
    }
  ]
}
```

---

## Notification Microservice Endpoints

| Endpoint | Método | API | Función |
| --- | --- | --- | --- |
| `/api/pichangapp/v1/notification/notifications/send-email` | `POST` | `notification_routes` | Encola envío de correos de confirmación de renta (`202 Accepted`). |
| `/api/pichangapp/v1/notification/notifications/rent-approved` | `POST` | `notification_routes` | Encola correo de aprobación al jugador (`202`). |
| `/api/pichangapp/v1/notification/notifications/reservation-pass?token=...` | `GET` | `notification_routes` | Devuelve PNG de boleta; `token` en query. |

#### `POST .../notifications/send-email` — Request

```json
{
  "rent": {
    "rent_id": 500,
    "schedule_day": "Saturday",
    "start_time": "2026-04-12T18:00:00-05:00",
    "end_time": "2026-04-12T19:00:00-05:00",
    "status": "confirmed",
    "period": "hour",
    "mount": "120.00",
    "payment_deadline": "2026-04-12T18:00:00-05:00",
    "field_name": "Cancha Sintética A",
    "campus": {
      "id_campus": 3,
      "name": "Sede Surco",
      "address": "Av. Principal 123",
      "district": "Surco",
      "contact_email": "contacto@sede.com",
      "contact_phone": "011222333"
    }
  },
  "user": {
    "name": "Ana",
    "lastname": "Pérez",
    "email": "ana.perez@example.com"
  },
  "manager": {
    "name": "Luis",
    "lastname": "Gestor",
    "email": "manager@sede.com"
  }
}
```

#### `POST .../notifications/send-email` — Response

```json
{
  "detail": "Emails sent"
}
```

#### `GET .../notifications/reservation-pass?token=...`

Respuesta binaria `image/png` (no JSON).
