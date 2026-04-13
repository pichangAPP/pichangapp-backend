FROM postgres:17

# Instalar pg_cron
RUN apt-get update \
 && apt-get install -y postgresql-17-cron \
 && rm -rf /var/lib/apt/lists/*

# Habilitar pg_cron por defecto
RUN echo "shared_preload_libraries = 'pg_cron'" >> /usr/share/postgresql/postgresql.conf.sample
