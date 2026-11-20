import os
import warnings

# Entorno de ejecución: "development" | "production"
VEKTOR_ENV = os.getenv("VEKTOR_ENV", "development").strip().lower()

# La SEC exige Nombre y un Email válido para no banear la IP
SEC_USER_AGENT = os.getenv(
    "SEC_USER_AGENT", "Martin Juan finanzas.juridicos@gmail.com"
)

# URL de base de datos: SQLite local por defecto; PostgreSQL en producción
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./financial_data.db")

# Seguridad y JWT
_DEFAULT_SECRET = "vektor-dev-secret-key-change-in-production-2026"
VEKTOR_SECRET_KEY = os.getenv("VEKTOR_SECRET_KEY", _DEFAULT_SECRET)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720")
)

if VEKTOR_ENV == "production" and VEKTOR_SECRET_KEY == _DEFAULT_SECRET:
    warnings.warn(
        "VEKTOR_SECRET_KEY está usando el valor por defecto en producción. "
        "Configurá una clave aleatoria fuerte en las variables de entorno.",
        RuntimeWarning,
    )

# Orígenes CORS permitidos (separados por coma en producción)
_RAW_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
)
ALLOWED_ORIGINS = [
    origin.strip() for origin in _RAW_ORIGINS.split(",") if origin.strip()
]

# Credenciales iniciales del Superadmin (bootstrap idempotente al arrancar)
VEKTOR_ADMIN_EMAIL = os.getenv(
    "VEKTOR_ADMIN_EMAIL", "admin@vektorterminal.local"
).strip().lower()
VEKTOR_ADMIN_PASSWORD = os.getenv("VEKTOR_ADMIN_PASSWORD", "Admin1234!")
VEKTOR_ADMIN_NAME = os.getenv("VEKTOR_ADMIN_NAME", "Administrador Vektor")