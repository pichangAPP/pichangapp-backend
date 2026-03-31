# Auth Domain

Este directorio contiene la logica de dominio para el microservicio de `auth`.

## Auth
- `auth/passwords.py`: hash y verificacion de contrasenas.
- `auth/tokens.py`: construccion de claims y generacion de tokens JWT.
- `auth/sessions.py`: manejo de sesiones de usuario (refresh/access).
- `auth/google.py`: validacion de `id_token` de Google.

## User
- `user/validations.py`: obtencion de usuario/rol con errores controlados.

## Audit
- `audit.py`: registro de eventos de auditoria y errores.
