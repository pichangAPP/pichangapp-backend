# Payment Domain

Este directorio contiene la lógica de dominio para el microservicio `payment`.

## payment/
- `payment/payments.py`: validaciones y utilidades de pago (status, metadata Yape/Plin).
- `payment/methods.py`: reglas de validación para métodos de pago.

Las clases de `services/` orquestan repositorios e integraciones usando estas reglas.
