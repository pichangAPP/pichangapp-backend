# pichangapp-backend

## Auth Microservice Endpoints

| Endpoint                           | Método | api          | Función                                                   |
|------------------------------------|--------|-----------------------|--------------------------------------------------|
| `/api/pichangapp/v1/auth/register`| `POST`  | `auth_routes`   | Registra tanto a un usuario como un administrador.     |
| `/api/pichangapp/v1/auth/login`   | `POST`  | `auth_routes`   | Loguea a players y a admins                            |
| `/api/pichangapp/v1/users` | `GET`  | `user_routes`   | Obtiene toda la lista de usuarios   |
| `/api/pichangapp/v1/users/{user_id}` | `GET`  | `user_routes`   | Obtiene al usuario del id correspondiente"   |
| `/api/pichangapp/v1/users/active` | `GET`  | `user_routes`   | Obtiene toda la lista de usuarios de estado "active"   |
| `/api/pichangapp/v1/users/roles/{role_id}` | `GET`  | `user_routes`   | Obtiene toda la lista de usuarios pertenecientes a ese "role_id" |
| `/api/pichangapp/v1/users/{user_id}` | `PUT`  | `user_routes`   | Actualizar los datos MODIFICABLES de un usuario"   |
