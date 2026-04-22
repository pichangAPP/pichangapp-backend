# Frontend: cierres semanales (admin) y efecto en reservas / horarios

Documento orientado a **equipo frontend** para el requerimiento de **reglas recurrentes de cierre** (`weekly_schedule_closure`): qué pantallas/flujos construir, **endpoints**, **cuerpos JSON** y **casos de uso**.

Contexto de negocio y DDL: [`manual-document.md`](./manual-document.md) § 10.

**Bases URL** (ajustar según gateway o entorno):

- Booking: `{API}/api/pichangapp/v1/booking`
- Reservation: `{API}/api/pichangapp/v1/reservation`

El router **booking v1** exige autenticación (`Depends(get_current_user)`) en todas las rutas incluidas las de cierres. El **reservation** según despliegue puede ser público o protegido; alinear con el gateway.

---

## 1. Qué debe construir el frontend

### 1.1 Panel admin (gestor / dueño de sede)

1. **Listado de reglas por campus**  
   - Entrada: `campus_id` (navegación desde campus o sede ya seleccionada).  
   - Tabla o cards: día de la semana, ámbito (todo el campus vs cancha), franja horaria o “día completo”, motivo (`reason`), activa (`is_active`), acciones editar / desactivar / borrar.

2. **Alta de regla**  
   - Selector **día de la semana** (`weekday` 0–6, ver tabla abajo).  
   - Selector de **ámbito**: “Todo el campus” (`id_field` omitido o `null`) o “Solo esta cancha” (`id_field` = id de la cancha; debe pertenecer al campus).  
   - **Tipo de cierre**:  
     - **Día completo**: no enviar horas o enviar ambas `null` (según contrato que acordéis con backend; hoy el schema acepta `null` en ambas).  
     - **Franja**: `local_start_time` y `local_end_time` en hora local (strings `HH:MM` o `HH:MM:SS` en JSON).  
   - **Cruce de medianoche / 24 h** (ayuda al usuario): si la franja es por ejemplo 22:00 → 06:00 del día siguiente, `local_end_time` puede ser **menor** que `local_start_time` en reloj del mismo calendario; si abre y cierra a la **misma hora** al día siguiente, representa **24 h**. El backend interpreta eso igual que el horario de apertura de cancha.  
   - Campo opcional **motivo** (`reason`).  
   - Toggle **activa** (`is_active`, default `true`).

3. **Edición** (`PUT`)  
   - Mismos campos en modo parcial (solo lo que cambie).  
   - Poder **desactivar** sin borrar (`is_active: false`).

4. **Borrado** (`DELETE`) con confirmación.

5. **Errores UX**  
   - **404**: campus inexistente al listar/crear; regla inexistente al editar/borrar.  
   - **400**: `id_field` que no pertenece al campus (crear/editar).  
   - **409** `WEEKLY_CLOSURE_CONFLICTS_RESERVED_RENT` al **crear o activar/editar** una regla de cierre cuya ventana recurrente intersecta una renta ya **`reserved`** (ver § 4.2).  
   - Mostrar mensaje amigable si **409** `SCHEDULE_WEEKLY_CLOSURE` al reservar o al gestionar horarios (ver § 4.1).

### 1.2 Flujos jugador / reserva (sin pantalla nueva obligatoria)

- Los listados de **horarios disponibles** y **slots por hora** ya **excluyen** visualmente lo bloqueado por reglas activas.  
- Si el usuario fuerza una acción que el backend rechaza (p. ej. reserva sobre franja cerrada), manejar **409** con código `SCHEDULE_WEEKLY_CLOSURE` (§ 4.1).

### 1.3 Convención `weekday` (obligatoria en UI y API)

| Valor | Día        |
|------:|------------|
| 0     | Lunes      |
| 1     | Martes     |
| 2     | Miércoles  |
| 3     | Jueves     |
| 4     | Viernes    |
| 5     | Sábado     |
| 6     | Domingo    |

Misma convención que **JavaScript** `Date.getDay()` **no**: en JS domingo es 0. Hay que **mapear** explícitamente a 0 = lunes … 6 = domingo (ISO / Python).

---

## 2. Endpoints booking — CRUD cierres semanales

Todas bajo: `GET|POST|PUT|DELETE {BASE_BOOKING}/…`

### 2.1 Listar reglas de un campus

`GET /campuses/{campus_id}/weekly-schedule-closures`

- **Body:** ninguno.  
- **200:** array de `WeeklyScheduleClosureResponse` (ver § 3).  
- **404:** campus no encontrado.

### 2.2 Crear regla

`POST /campuses/{campus_id}/weekly-schedule-closures`

**Body (JSON)** — `WeeklyScheduleClosureCreate`:

| Campo | Tipo | Requerido | Notas |
|--------|------|-------------|--------|
| `weekday` | number | Sí | 0–6 |
| `id_field` | number \| null | No | `null` = todo el campus |
| `local_start_time` | string (time) \| null | No | Ej. `"14:00:00"` |
| `local_end_time` | string (time) \| null | No | Ej. `"17:00:00"` |
| `reason` | string \| null | No | max 500 |
| `is_active` | boolean | No | default `true` |

**Ejemplos**

Cierre **todo el miércoles** en el campus `5`:

```json
{
  "weekday": 2,
  "reason": "Día de mantenimiento general",
  "is_active": true
}
```

Cierre **sábados 14:00–17:00** solo en cancha `12`:

```json
{
  "weekday": 5,
  "id_field": 12,
  "local_start_time": "14:00:00",
  "local_end_time": "17:00:00",
  "reason": "Liga juvenil",
  "is_active": true
}
```

Cierre **nocturno** miércoles 22:00 a jueves 06:00 (misma semana lógica anclada al miércoles):

```json
{
  "weekday": 2,
  "id_field": null,
  "local_start_time": "22:00:00",
  "local_end_time": "06:00:00",
  "reason": "Cierre nocturno"
}
```

- **201:** cuerpo = una `WeeklyScheduleClosureResponse` (incluye `id`, `id_campus`, `created_at`, …).  
- **400:** cancha no pertenece al campus.  
- **404:** campus no encontrado.  
- **409** `WEEKLY_CLOSURE_CONFLICTS_RESERVED_RENT`: la regla quedaría **activa** (`is_active` true) y solapa en el tiempo recurrente con al menos una renta **`reserved`** en alguna cancha afectada (campus completo o la cancha indicada).

### 2.3 Actualizar regla

`PUT /weekly-schedule-closures/{closure_id}`

**Body** — `WeeklyScheduleClosureUpdate` (todos opcionales; solo enviar lo que cambia):

| Campo | Tipo | Notas |
|--------|------|--------|
| `weekday` | number | 0–6 |
| `id_field` | number \| null | |
| `local_start_time` | string \| null | |
| `local_end_time` | string \| null | |
| `reason` | string \| null | |
| `is_active` | boolean | |

**Ejemplo** — desactivar sin borrar:

```json
{ "is_active": false }
```

- **200:** `WeeklyScheduleClosureResponse`.  
- **400:** cancha no pertenece al campus del cierre.  
- **404:** cierre no existe.  
- **409** `WEEKLY_CLOSURE_CONFLICTS_RESERVED_RENT`: el estado **efectivo** tras el `PUT` deja la regla **activa** y solapa con una renta **`reserved`** (no aplica si solo se envía `is_active: false` u otros cambios que dejen la regla inactiva).

### 2.4 Eliminar regla

`DELETE /weekly-schedule-closures/{closure_id}`

- **Body:** ninguno.  
- **204:** sin cuerpo.  
- **404:** cierre no existe.

### 2.5 Respuesta común (`WeeklyScheduleClosureResponse`)

Incluye todo lo de creación más:

- `id` (number)  
- `id_campus` (number)  
- `created_at` (datetime ISO)  
- `updated_at` (datetime ISO \| null)

---

## 3. Endpoints reservation — impacto en catálogo y reservas

Las reglas **no** tienen CRUD en reservation; solo **filtran / validan**. Útiles para el front de **jugador** y **admin de reservas**.

Prefijo: `{BASE_RESERVATION}`

### 3.1 Slots por día (1 h)

`GET /schedules/time-slots?field_id={id}&date=YYYY-MM-DD`

- **date** opcional; si falta, suele usarse hoy en servidor.  
- **200:** lista de `ScheduleTimeSlotResponse`: `start_time`, `end_time`, `status`, `price`.  
- Los intervalos que caen en cierre semanal **no** aparecen como libres (quedan fuera o ocupados según lógica de slots).

### 3.2 Horarios “disponibles” de un campo

`GET /schedules/available?field_id={id}&day_of_week=...&status=...`

- Query params opcionales según OpenAPI del servicio.  
- **200:** lista de `ScheduleResponse`; los que solapan un cierre activo **se omiten**.

### 3.3 Crear / actualizar schedule (gestor de franjas)

- `POST /schedules` — body `ScheduleCreate` (`day_of_week`, `start_time`, `end_time`, `status`, `price`, `id_field`, …).  
- `PUT /schedules/{schedule_id}` — body `ScheduleUpdate` (parcial).

Si la ventana cae en un cierre: **409** `SCHEDULE_WEEKLY_CLOSURE` (ver § 4.1).

### 3.4 Reservas que validan cierre

| Método | Ruta | Body principal | Cuándo aplica cierre |
|--------|------|----------------|----------------------|
| `POST` | `/rents` | `RentCreate` | Tras elegir `id_schedule`; status típ. `pending_payment`. |
| `POST` | `/rents/combo` | `RentCreateCombo` | Cada schedule del combo. |
| `POST` | `/rents/admin` | `RentAdminCreate` | `id_schedule` + datos cliente. |
| `PUT` | `/rents/{rent_id}` | `RentUpdate` | Si cambia `id_schedule`. |
| `PUT` | `/rents/admin/{rent_id}` | `RentAdminUpdate` | Si cambia `id_schedule`. |

**RentCreate** (ejemplo mínimo; el servicio exige `status` = `pending_payment`):

```json
{
  "id_schedule": 101,
  "status": "pending_payment"
}
```

**RentAdminCreate** (ejemplo mínimo):

```json
{
  "id_schedule": 101,
  "status": "reserved",
  "customer_full_name": "María Pérez"
}
```

**RentCreateCombo** (ejemplo mínimo):

```json
{
  "id_combination": 3,
  "id_schedules": [201, 202],
  "status": "pending_payment"
}
```

---

## 4. Errores 409 relacionados con cierres

### 4.1 `SCHEDULE_WEEKLY_CLOSURE` (reservation)

Cuando la ventana del schedule/renta solapa una regla activa, el servicio responde **409**. El **handler global** de reservation normaliza el cuerpo a JSON **plano** (no anidado bajo otra clave `detail`):

```json
{
  "code": "SCHEDULE_WEEKLY_CLOSURE",
  "message": "Este horario no está disponible por un cierre recurrente del campus o cancha.",
  "detail": "Este horario cae en un cierre recurrente configurado por el administrador."
}
```

El front debe usar el campo **`code`** del JSON (`"SCHEDULE_WEEKLY_CLOSURE"`) o el **`message`** para no confundir con otros **409** (`SCHEDULE_CONFLICT`, `RENT_ACTIVE_CONFLICT`, etc.).

### 4.2 `WEEKLY_CLOSURE_CONFLICTS_RESERVED_RENT` (booking, CRUD cierres)

Al **POST** o **PUT** una regla con **`is_active` true** (efectivo tras merge en actualización parcial), booking consulta en base de datos (esquema **`reservation`**, vía `reservation_reader`) las rentas en estado **`reserved`** cuyo intervalo intersecta el bloque recurrente (día completo o franja, incluido cruce de medianoche). Si existe conflicto, responde **409** con cuerpo normalizado por el handler de booking, por ejemplo:

```json
{
  "code": "WEEKLY_CLOSURE_CONFLICTS_RESERVED_RENT",
  "message": "No se puede definir el cierre: existe una reserva en estado reservada que intersecta este bloqueo recurrente.",
  "detail": "id_rent=12345"
}
```

Desactivar una regla (`is_active: false`) **no** dispara esta validación.

**Nota:** Si el cliente llama **a través de un gateway** que transforme errores, validar la forma final del JSON en integración.

---

## 5. Casos de uso (resumen)

| ID | Actor | Caso | Backend / UI |
|----|--------|------|----------------|
| CU1 | Admin sede | Configurar “los miércoles cerrado todo el día” en todo el campus | POST sin horas; `weekday=2`, `id_field` null. |
| CU2 | Admin sede | “Sábados 14–17 solo cancha A” | POST con `weekday`, `id_field`, horas. |
| CU3 | Admin sede | Cierre que cruza medianoche (22:00–06:00) | POST con `local_start_time` > `local_end_time` en sentido reloj mismo día calendario. |
| CU4 | Admin sede | Desactivar regla temporalmente | PUT `{ "is_active": false }`. |
| CU5 | Admin sede | Quitar regla | DELETE por `closure_id`. |
| CU6 | Jugador | Ver día en calendario de cancha | GET time-slots: no ve huecos en horas cerradas. |
| CU7 | Jugador | Reservar slot que visualmente parece libre pero regla nueva lo bloquea | POST rent → 409 `SCHEDULE_WEEKLY_CLOSURE`; refrescar slots/listas. |
| CU8 | Admin reservas | Crear renta admin en franja cerrada | POST `/rents/admin` → 409; mensaje claro. |
| CU9 | Admin reservas | Cambiar renta a otro schedule en franja cerrada | PUT con `id_schedule` → 409. |
| CU10 | Admin sede | Definir cierre recurrente que taparía una renta ya **reservada** | POST/PUT booking cierres → 409 `WEEKLY_CLOSURE_CONFLICTS_RESERVED_RENT`; ajustar horario o cancelar/reubicar la renta antes. |

---

## 6. Booking — listados campus (opcional para front)

Si la app lista sedes con horarios desde **booking** (`get_available_schedules` interno), esas filas **también** se filtran por cierres. Cualquier UI que consuma ese agregado verá menos schedules; no requiere llamar al CRUD de cierres si no es pantalla de administración.

---

## 7. Checklist frontend

- [ ] Pantalla listado + alta + edición + baja de cierres por `campus_id`.  
- [ ] Mapeo UI día de la semana ↔ `weekday` 0–6 (lunes primero).  
- [ ] Opción campus completo vs cancha (`id_field`).  
- [ ] Formulario franja con ayuda texto para cruce medianoche / 24 h.  
- [ ] Manejo 409 `SCHEDULE_WEEKLY_CLOSURE` en flujos de reserva y de creación/edición de schedule.  
- [ ] Manejo 409 `WEEKLY_CLOSURE_CONFLICTS_RESERVED_RENT` al crear/editar cierres semanales (admin booking).  
- [ ] Tras crear/editar/borrar regla, **refrescar** time-slots y listas de disponibles si están abiertas.

Documentación de negocio adicional: [`manual-document.md`](./manual-document.md), [`manual-funcionalidades-avanzadas.md`](./manual-funcionalidades-avanzadas.md).
