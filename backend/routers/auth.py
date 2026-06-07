from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from utils.supabase_client import login, logout

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class LogoutRequest(BaseModel):
    access_token: str


@router.post("/login")
def auth_login(body: LoginRequest):
    """Autentica un usuario vía Supabase Auth."""
    result = login(body.email, body.password)
    if not result.get("success"):
        raise HTTPException(status_code=401, detail=result.get("error", "Credenciales inválidas"))
    return result


@router.post("/logout")
def auth_logout(body: LogoutRequest):
    """Cierra la sesión del usuario."""
    result = logout(body.access_token)
    return result
