# Mejora de seguridad: API Key para validar frontend legítimo
# Agregar en backend/app/config/settings.py

# API Key para validar requests del frontend legítimo
FRONTEND_API_KEY: str = os.getenv("FRONTEND_API_KEY", "cuenly-frontend-secure-2025")

# En backend/app/utils/security.py (nuevo archivo)
from fastapi import HTTPException, Depends, Request
from app.config.settings import settings

def validate_frontend_key(request: Request):
    """Valida que el request venga del frontend legítimo"""
    api_key = request.headers.get("X-Frontend-Key") 
    if not api_key or api_key != settings.FRONTEND_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid frontend key")
    return True

# Uso en endpoints críticos:
# @app.post("/process", dependencies=[Depends(validate_frontend_key)])