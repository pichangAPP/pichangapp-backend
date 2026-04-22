# Manual: solapes de horarios (`schedule`) y rentas (incl. combo)

Documentación de la lógica aplicada en el servicio **reservation** para evitar doble reserva en la misma cancha y ventana horaria, alineando **creación/actualización de schedules** y **creación y cambio de horario en rentas** (simple, admin y combo).

---

## Constantes relevantes

Definidas en `services/reservation/app/core/status_constants.py`:

| Constante | Uso |
|-----------|-----|
| **`SCHEDULE_EXCLUDED_CONFLICT_STATUS_CODES`** | Estados de **schedule** que **no** cuentan como solape al buscar **otra fila** en el mismo `id_field`. Hoy: **`expired`**, **`available`**. |
| **`RENT_FINAL_STATUS_CODES`** | Rentas en estos estados **no** son “activas” para conflictos (`cancelled`, `fullfilled`, rechazos, `expired_*`, etc.). |
| **`SCHEDULE_BLOCKING_STATUS_CODES`** | Referencia para UI/time-slots: `pending`, `hold_payment`, `blocked_admin`. |

Estados de schedule **bloqueantes** para solape (no están en la lista de exclusión): entre otros **`pending`**, **`hold_payment`**, **`blocked_admin`**, **`reserved`**, **`fullfilled`**.

---

## 1. Criterio de solape temporal

En SQL/Python se usa la condición habitual de intervalos **semiabiertos** en la práctica del código:

- `existing.start_time < requested.end_time`
- `existing.end_time > requested.start_time`

**Toque en el borde:** `[11:00, 12:00)` y `[12:00, 14:00)` **no** se consideran solapados (no hay minuto compartido estrictamente entre ambos intervalos con esta condición).

---

## 2. `ensure_field_not_reserved` (núcleo común)

**Archivo:** `services/reservation/app/domain/schedule/validations.py`

Se ejecuta en dos pasos **secuenciales** (el primero que falle dispara error):

1. **`field_has_schedule_in_range`** — ¿existe otra fila `reservation.schedule` en el mismo `id_field` con solape y estado **no** excluido?
2. **`field_has_active_rent_in_range`** — ¿existe renta **no final** cuyo `[start_time, end_time)` solape la ventana, en ese campo, vía `rent.id_schedule` **o** `rent_schedule`?

### Parámetros clave

| Parámetro | Efecto |
|-----------|--------|
| `excluded_schedule_statuses` | Normalmente `SCHEDULE_EXCLUDED_CONFLICT_STATUS_CODES`: filas `available` / `expired` **no** bloquean nuevos inserts solapados. |
| `excluded_rent_statuses` | Rentas finales no bloquean (`RENT_FINAL_STATUS_CODES` en callers). |
| `exclude_schedule_id` | Excluye esa fila `schedule` del chequeo de solape consigo misma; además, en rentas, las rentas ligadas **solo** a ese schedule por IDs se omiten en el paso 2 (vía `_rent_ids_tied_to_schedule`). |
| **`exclude_rent_id`** (opcional) | Omite esa **`id_rent`** en el paso 2. Sirve para **`PUT` renta** al cambiar `id_schedule`: la propia renta no debe bloquearse a sí misma. |

### Orden de errores HTTP

| Orden | Si falla | Código |
|-------|-----------|--------|
| 1 | Solape con schedule bloqueante | **`SCHEDULE_CONFLICT`** (409) |
| 2 | Solape con renta activa | **`RENT_ACTIVE_CONFLICT`** (409) |

Si hay **ambos** problemas, el cliente verá primero **`SCHEDULE_CONFLICT`**.

---

## 3. Schedules (`POST` / `PUT`)

**Servicio:** `ScheduleService` (`services/reservation/app/services/schedule_service.py`).

| Acción | Validación de solape |
|--------|----------------------|
| **POST** | Tras intento de **reuse** de `available` con ventana **idéntica** (timezone `settings.TIMEZONE`), si no aplica reuse → `ensure_field_not_reserved`. |
| **PUT** (cambio de ventana/campo) | `ensure_field_not_reserved` con `exclude_schedule_id` = schedule editado. |

### Tabla de casos (schedules)

| # | Caso | Resultado |
|---|------|-----------|
| S1 | `available` 13–15 + POST `pending` 12–14 mismo campo | **OK** (`available` ignorado en solape). |
| S2 | `pending`/`hold_payment` 12–16 + POST solapado | **409** `SCHEDULE_CONFLICT`. |
| S3 | `available` 13–15 + renta activa ajena 13–14 mismo campo + POST solapado | **409** `RENT_ACTIVE_CONFLICT` (el paso 2). |
| S4 | Solo `expired` solapado | **OK** (excluido). |
| S5 | Reuse: `available` misma ventana exacta, sin renta activa en ese `id_schedule` | **Reuse** (UPDATE fila, no INSERT). |
| S6 | Reuse: `available` misma ventana pero **sí** renta activa en ese `id_schedule` | Sigue buscando / cae en **INSERT** + `ensure_field_not_reserved` según contexto. |
| S7 | Borde: [11,12) vs [12,14) | **OK** (sin solape). |
| S8 | `id_field` null (si existiera en datos) | `ensure_field_not_reserved` no aplica en paths que exigen campo; validaciones previas pueden fallar. |

### Efectos colaterales (producto)

- Pueden coexistir **varias** filas `available` solapadas en el mismo campo (histórico + nuevos POST). Los **time slots** (`time_slots.py`) priorizan ocupación por rentas activas y estados bloqueantes; varias `available` pueden hacer el precio por rango menos obvio si se solapan en `price_by_range`.

---

## 4. Rentas: creación (`POST` simple, admin, combo)

**Servicio:** `RentService` — helper `_ensure_field_window_clear_for_new_rent`.

| Flujo | Qué se llama |
|-------|----------------|
| `create_rent` / `create_rent_admin` | `ensure_schedule_not_started` → `ensure_schedule_available` → `_ensure_field_window_clear_for_new_rent` (sin `exclude_rent_id`). |
| `create_rent_combo` | Por cada schedule: `ensure_schedule_not_started` → `ensure_schedule_available` → `_ensure_field_window_clear_for_new_rent`. Además `validate_combo_schedules` (miembros, ventana común, `schedule_has_active_rent` por id). |

### Tabla de casos (creación renta)

| # | Caso | Resultado |
|---|------|-----------|
| R1 | Renta activa otra 13–14 campo 9 + nueva renta schedule 12–16 campo 9 | **409** `RENT_ACTIVE_CONFLICT`. |
| R2 | Solo schedules `available` solapados + nueva renta | **OK** en paso campo (puede haber 409 solo si `ensure_schedule_available` falla en **ese** `id_schedule`). |
| R3 | Combo: campo 10 libre, campo 9 con conflicto | **409** al validar el schedule del **9** (falla todo el combo). |
| R4 | Renta `cancelled`/`fullfilled` solapada | **OK** (no cuenta como activa). |
| R5 | Mismo `id_schedule` ya con renta activa | **409** `ensure_schedule_available` (“Schedule already has an active rent”) antes del chequeo por campo. |
| R6 | `under_review`, `pending_payment`, `proof_submitted`, `reserved`, etc. | Cuentan como **activas** en `field_has_active_rent_in_range`. |

---

## 5. Rentas: actualización (`PUT` con cambio de `id_schedule`)

**Archivo:** `RentService.update_rent`, `update_rent_admin`.

Si el payload incluye **`id_schedule`**:

1. `ensure_schedule_available` (con `exclude_rent_id` = renta actual).
2. `_ensure_field_window_clear_for_new_rent` con **`exclude_rent_id`** = renta actual (no se auto-bloquea) y ventana del **nuevo** schedule.

**Combo:** no se permite enviar `id_schedule` en `update_rent` si hay más de un vínculo en `rent_schedule` (400).

### Tabla de casos (PUT renta)

| # | Caso | Resultado |
|---|------|-----------|
| U1 | Cambio de schedule a ventana que solapa renta **ajena** activa | **409** `RENT_ACTIVE_CONFLICT`. |
| U2 | Cambio a ventana que solo cruza `available` | **OK** (schedules `available` ignorados en paso 1 de `ensure_field_not_reserved`). |
| U3 | PUT solo pago / estado, **sin** `id_schedule` | **No** se ejecuta `ensure_field_not_reserved` (solo cambio de schedule dispara validación de campo). |
| U4 | Admin PUT sin `id_schedule` | Sigue `ensure_schedule_available` en el schedule **objetivo** actual (comportamiento previo). |

---

## 6. Comparativa: `ensure_schedule_available` vs `ensure_field_not_reserved`

| Validación | Alcance | Pregunta que responde |
|------------|---------|------------------------|
| **`schedule_has_active_rent`** vía `ensure_schedule_available` | Solo el **`id_schedule` concreto** | ¿Hay renta activa **ligada a esta fila** schedule? |
| **`field_has_active_rent_in_range`** vía `ensure_field_not_reserved` | Todo el **`id_field` + rango temporal** | ¿Hay renta activa en **cualquier** schedule de esa cancha que solape? |

Por eso hacen falta **ambas** en creación de renta: la fila puede estar “libre” pero el **campo** ocupado por otra ventana vía otro `id_schedule`.

---

## 7. Time slots (`build_time_slots_by_date`) — independiente de `SCHEDULE_EXCLUDED_CONFLICT_STATUS_CODES`

**Archivo:** [`services/reservation/app/domain/schedule/time_slots.py`](services/reservation/app/domain/schedule/time_slots.py)

La API de solapes (`ensure_field_not_reserved`, constante `SCHEDULE_EXCLUDED_CONFLICT_STATUS_CODES`) **no** alimenta esta función. Los slots se construyen con reglas **propias**, a partir de:

1. **`list_schedules_by_date`** — todas las filas `schedule` del campo en la fecha civil del `start_time` (cualquier estado).
2. **`get_active_schedule_ids`** — `id_schedule` que tienen al menos una renta **no** en estado final (`RENT_FINAL_STATUS_CODES`).

### Clasificación por fila schedule

| Condición | Efecto en slots |
|-----------|-----------------|
| `status` ∈ `SCHEDULE_BLOCKING_STATUS_CODES` (`pending`, `hold_payment`, `blocked_admin`) | Ventana → **`reserved_ranges`** (horas ocupadas). |
| `status` ∉ (`available`, `expired`) (p. ej. `reserved`, `fullfilled`) | Misma rama: **`reserved_ranges`**. |
| `status` ∈ `available` / `expired` **y** `id_schedule` ∈ `get_active_schedule_ids(...)` | **`reserved_ranges`** (hay renta activa en esa fila). |
| `status` ∈ `available` / `expired` **y** **no** en `active_schedule_ids` | Solo **`price_by_range`** con clave exacta `(start_time, end_time)` del schedule; **no** marca ocupación por estado. |

### Implicaciones (alineadas con POST schedule que ignora solape con `available`)

- Varias filas **`available`** solapadas **sin** renta activa: **ninguna** añade a `reserved_ranges`; la lista de slots puede seguir mostrando esas horas como libres. Eso ya ocurría con una sola ventana `available` larga; permitir más inserts `available` solapados en API **no cambia** esta fórmula, solo puede aumentar filas en BD.
- **`price_by_range`**: la clave es la ventana **completa** del schedule; los slots son de **1 h**. Salvo coincidencia exacta con `(current_start, current_end)`, se usa `field.price_per_hour`. La ocupación visible depende sobre todo de **`reserved_ranges`**.

### Pruebas de caracterización

Ver `services/reservation/tests/test_time_slots.py` (pytest, mocks de repositorio) para fijar el comportamiento anterior sin tocar `time_slots.py` salvo requisito nuevo explícito.

---

## 8. Cancelación y jobs

| Tema | Comportamiento documentado |
|------|----------------------------|
| **Cancel rent** | Schedules vinculados pasan a **`available`** (no borrado por defecto). |
| **Nuevo POST schedule** | Puede solapar `available` existentes. |
| **Jobs SQL** en `database.py` | Lógica de expiración / fullfilled / cleanup en BD; **no** sustituyen `ensure_field_not_reserved` en API. Mantener coherencia operativa si se ejecutan fuera del servicio. |

---

## 9. Referencias de código

| Tema | Archivo |
|------|---------|
| Constantes | `services/reservation/app/core/status_constants.py` |
| Validación unificada | `services/reservation/app/domain/schedule/validations.py` |
| Queries solape | `services/reservation/app/repository/schedule_repository.py`, `rent_repository.py` |
| Schedules API | `services/reservation/app/services/schedule_service.py` |
| Rentas API | `services/reservation/app/services/rent_service.py` |
| Slots UI | `services/reservation/app/domain/schedule/time_slots.py` |
| Cierres semanales (reglas + DDL) | **§ 10** y rutas booking listadas allí. |
| Inventario de tests por microservicio | [`mapa-tests-microservicios.md`](./mapa-tests-microservicios.md) |
| Códigos error | `services/reservation/app/core/error_codes.py` |

---

## 10. Cierres semanales administrables (`booking.weekly_schedule_closure`)

Los administradores pueden definir **ventanas recurrentes por día de la semana** en las que **no se permiten reservas** (equivalente a “cerrado” o “bloqueado” en horario local). Aplica a:

- **Todo el campus:** reglas con `id_field` **NULL** (ej.: los miércoles no atienden).
- **Una cancha concreta:** reglas con `id_field` **NOT NULL** (ej.: los sábados de 14:00 a 17:00 solo en cancha 3).

La lógica se evalúa en **reservation** (crear/actualizar rentas y schedules, listados disponibles, slots por fecha) y en **booking** al listar schedules disponibles por campus; usa la variable de entorno **`TIMEZONE`** de cada servicio (deben coincidir en despliegue, p. ej. `America/Lima`).

### Convenciones

| Campo | Significado |
|--------|-------------|
| **`weekday`** | Igual que **Python `date.weekday()`**: **0 = lunes** … **6 = domingo**. |
| **`local_start_time` / `local_end_time`** | Hora local del cierre. **Ambas NULL** = **todo el día** de ese `weekday`. Con las dos informadas: si `fin > inicio`, franja el mismo día; si `fin < inicio` o `fin == inicio`, la franja **cruza medianoche** hasta el día siguiente (misma idea que `open_time` / `close_time` de cancha: cierre en la mañana del día siguiente o 24h si abre y cierra a la misma hora). No hay `CHECK` en BD sobre estas horas. |
| **`is_active`** | `false` desactiva la regla sin borrarla. |

### API (booking, requiere auth como el resto del router v1)

**Especificación para frontend** (pantallas, bodies JSON, casos de uso, errores): [`frontend-cierres-semanales.md`](./frontend-cierres-semanales.md).

Prefijo: `/api/pichangapp/v1/booking`

| Método | Ruta |
|--------|------|
| `GET` | `/campuses/{campus_id}/weekly-schedule-closures` |
| `POST` | `/campuses/{campus_id}/weekly-schedule-closures` |
| `PUT` | `/weekly-schedule-closures/{closure_id}` |
| `DELETE` | `/weekly-schedule-closures/{closure_id}` |

### Errores en booking (alta o edición de cierres)

Si el resultado efectivo del **POST** o **PUT** deja la regla **activa** (`is_active` true) y su ventana recurrente intersecta en el tiempo con al menos una renta en estado **`reserved`** en alguna cancha alcanzada por la regla (toda la sede o una cancha concreta), booking responde **409** con código **`WEEKLY_CLOSURE_CONFLICTS_RESERVED_RENT`**. La comprobación usa lectura directa del esquema **`reservation`** desde el servicio booking (`reservation_reader`). No aplica al **solo** desactivar (`is_active` false).

### Errores en reservation

Si un usuario o admin intenta reservar o publicar un schedule en una ventana cubierta por una regla activa, la API responde **409** con código **`SCHEDULE_WEEKLY_CLOSURE`**.

### DDL: crear la tabla en base de datos (manual)

**No** se crea esta tabla al arrancar el servicio booking. Debes ejecutar el siguiente SQL **una vez** (o equivalente vía migración propia) en la base compartida:

```sql
CREATE TABLE IF NOT EXISTS booking.weekly_schedule_closure (
    id BIGSERIAL PRIMARY KEY,
    id_campus BIGINT NOT NULL
        REFERENCES booking.campus (id_campus) ON DELETE CASCADE,
    id_field BIGINT NULL
        REFERENCES booking.field (id_field) ON DELETE CASCADE,
    weekday SMALLINT NOT NULL,
    local_start_time TIME NULL,
    local_end_time TIME NULL,
    reason VARCHAR(500),
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ,
    CONSTRAINT chk_weekly_closure_weekday
        CHECK (weekday >= 0 AND weekday <= 6)
);

CREATE INDEX IF NOT EXISTS ix_weekly_schedule_closure_campus
    ON booking.weekly_schedule_closure (id_campus);

CREATE INDEX IF NOT EXISTS ix_weekly_schedule_closure_field
    ON booking.weekly_schedule_closure (id_field)
    WHERE id_field IS NOT NULL;
```

Si la tabla ya existía con el `CHECK` antiguo, quítalo en base de datos:

```sql
ALTER TABLE booking.weekly_schedule_closure
    DROP CONSTRAINT IF EXISTS chk_weekly_closure_times;
```

### Referencias de código

| Tema | Ubicación |
|------|-----------|
| Modelo / CRUD booking | `services/booking/app/models/weekly_schedule_closure.py`, `weekly_schedule_closure_repository.py`, `weekly_schedule_closure_service.py`, `api/v1/weekly_schedule_closure_routes.py` |
| Lectura de reglas desde reservation | `services/reservation/app/integrations/booking_reader.py` (`list_weekly_closure_rules_for_field`) |
| Solape UTC ↔ reglas locales (incl. cierre que cruza medianoche / 24h) | `services/reservation/app/domain/schedule/weekly_closure.py` (`naive_weekly_closure_block`) |
| Solape en booking (listados campus + conflicto cierre ↔ rentas `reserved`) | `services/booking/app/core/weekly_schedule_closure_overlap.py`, `integrations/reservation_reader.py` (`list_reserved_rent_time_windows_for_fields`, `find_reserved_rent_id_conflicting_with_weekly_rule`) |
| Slots por fecha | `services/reservation/app/domain/schedule/time_slots.py` |
| Horario de cancha que cruza medianoche (`open_time` / `close_time`) | `services/reservation/app/domain/schedule/validations.py` — `validate_schedule_window` (alineado con slots en `time_slots.py` § 7). |

---

## 11. Manual extendido

Diagramas, flujos reserva y tabla de errores: `docs/manual-funcionalidades-avanzadas.md` (§ **6.8** y enlaces).
