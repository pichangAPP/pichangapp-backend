from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,            # Máx. conexiones en el pool
    max_overflow=20,         # Conexiones extra si el pool está lleno
    pool_timeout=30,         # Espera máx. para obtener una conexión
    pool_recycle=1800,       # Recicla conexiones cada 30 min (evita timeouts del servidor)
    pool_pre_ping=True       # Testea conexión antes de usarla (evita "server closed connection")
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()
