# Mapa de tests automatizados por microservicio

Inventario de **tests automatizados presentes en el repositorio** (principalmente **pytest** en Python). No incluye pruebas manuales, Postman u otros que no estén versionados aquí.

Para la lógica de negocio de solapes y cierres semanales, ver también [`manual-document.md`](./manual-document.md).

---

## Cómo ejecutar lo que hoy existe

Solo el servicio **reservation** define carpeta `tests/` con pytest.

Desde el directorio del servicio (Windows PowerShell):

```powershell
cd services\reservation
$env:PYTHONPATH = "app"
python -m pytest tests/ -v
```

---

## Resumen por microservicio

| Microservicio | Carpeta | Tests pytest en repo | Notas |
|---------------|---------|----------------------|--------|
| **reservation** | `services/reservation/` | Sí (`tests/`) | Ver detalle abajo. |
| **auth** | `services/auth/` | No | Sin `tests/` versionados; validar vía API manual o añadir suite. |
| **booking** | `services/booking/` | No | Sin `tests/` versionados. |
| **notification** | `services/notification/` | No | Sin `tests/` versionados. |
| **analytics** | `services/analytics/` | No | Sin `tests/` versionados. |
| **payment** | `services/payment/` | No | Sin `tests/` versionados. |
| **gateway** | `services/gateway/` | No | Sin `tests/` versionados. |
| **rasa** | `services/rasa/` | No (en este mapa) | Tiene `pyproject.toml` propio; tests de NLU/dialog suelen ir aparte del patrón pytest de FastAPI de los demás. |

---

## Reservation — detalle por archivo y qué cubre

Ámbito del código bajo prueba: **dominio / integración ligera**, sin levantar HTTP real (mocks de repositorio donde aplica).

### `services/reservation/tests/test_time_slots.py`

| Test | Qué valida (servicio / API relacionada) |
|------|-------------------------------------------|
| `test_hold_payment_blocks_hour_slots` | `build_time_slots_by_date` — horario `hold_payment` marca horas ocupadas en slots de 1 h. Expuesto vía **`ScheduleService.list_time_slots_by_date`** → rutas bajo prefijo reservation de time slots. |
| `test_available_without_active_rent_does_not_block` | Misma función: `available` sin renta activa no ocupa slots. |
| `test_available_with_active_rent_blocks` | `available` + `id_schedule` en rentas activas → slot ocupado. |
| `test_two_overlapping_available_no_rents_do_not_block` | Dos `available` solapadas sin rentas → no bloquean (comportamiento documentado en manual § 7). |
| `test_non_available_non_expired_status_blocks` (`reserved`, `fullfilled`) | Estados no disponibles / no expired bloquean la hora afectada. |

**Código principal:** `app/domain/schedule/time_slots.py` (`build_time_slots_by_date`).

### `services/reservation/tests/test_weekly_closure_overlap.py`

| Test | Qué valida (servicio / API relacionada) |
|------|-------------------------------------------|
| `test_full_day_closure_blocks_same_weekday` | `utc_interval_overlaps_weekly_closures` — día completo por `weekday`. Afecta **`RentService`** (crear/actualizar renta), **`ScheduleService`** (crear/actualizar schedule, listar disponibles), filtros en **booking** `reservation_reader`, y **time slots** vía reglas semanales. |
| `test_full_day_closure_does_not_block_other_weekday` | No bloquea otro día de la semana. |
| `test_partial_window_overlap` / `test_partial_window_outside` | Franja misma día (`fin > inicio`). |
| `test_overnight_closure_covers_next_morning` | Cierre que cruza medianoche (`fin < inicio`). |
| `test_equal_times_means_24h_block` | Misma hora inicio/fin = ventana 24 h. |

**Código principal:** `app/domain/schedule/weekly_closure.py` (booking: `app/core/weekly_schedule_closure_overlap.py` — utilidad pura en **core**, no en `domain`).

---

## Qué faltaría para “cerrar” el requerimiento

1. **Cobertura por microservicio:** añadir `tests/` (o equivalente) en **auth**, **booking**, **gateway**, **notification**, **payment**, **analytics** y documentar aquí cada archivo → API/servicio (mismo formato que reservation).
2. **Tests HTTP / integración:** los actuales son **unitarios de dominio**; no hay suite que llame a `TestClient` FastAPI por ruta (`GET/POST …`) en CI.
3. **Rasa:** si hay tests de modelo/pipeline, conviene enlazarlos en este mapa o en un subdocumento `docs/mapa-tests-rasa.md`.
4. **Mantenimiento:** al agregar un módulo de tests nuevo, actualizar esta tabla en la misma PR.

Este documento cumple el inventario **según el estado actual del repo**; el trabajo pendiente es ampliar tests y reflejarlo en nuevas filas o secciones.
