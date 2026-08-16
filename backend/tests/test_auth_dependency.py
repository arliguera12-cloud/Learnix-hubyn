"""
Prueba de la verificación de JWT contra un JWKS simulado.

Levanta un servidor local que sirve un JWKS con una clave ES256 real, apunta
SUPABASE_URL a él y comprueba que get_current_user acepta lo que debe y
rechaza lo que debe.
"""
import http.server
import json
import os
import sys
import threading
import time
from pathlib import Path

import jwt
from cryptography.hazmat.primitives.asymmetric import ec

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# ── Clave ES256 de prueba y su JWKS ────────────────────────────────────────
clave_priv = ec.generate_private_key(ec.SECP256R1())
KID = "kid-de-prueba"
jwk_pub = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(clave_priv.public_key()))
jwk_pub.update({"kid": KID, "use": "sig", "alg": "ES256"})
JWKS = {"keys": [jwk_pub]}

peticiones_jwks = {"n": 0}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.endswith("/.well-known/jwks.json"):
            peticiones_jwks["n"] += 1
            cuerpo = json.dumps(JWKS).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *a):
        pass


servidor = http.server.HTTPServer(("127.0.0.1", 0), Handler)
PUERTO = servidor.server_address[1]
threading.Thread(target=servidor.serve_forever, daemon=True).start()

BASE = f"http://127.0.0.1:{PUERTO}"
ISS = f"{BASE}/auth/v1"
os.environ["SUPABASE_URL"] = BASE
os.environ["SUPABASE_JWT_SECRET"] = "secreto-legacy-de-prueba"

from fastapi import HTTPException                      # noqa: E402
from fastapi.security import HTTPAuthorizationCredentials  # noqa: E402
from utils.auth_dependency import get_current_user     # noqa: E402


def llamar(token):
    return get_current_user(
        HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    )


def base(**extra):
    ahora = int(time.time())
    d = {
        "sub": "usuario-123",
        "email": "nahum.mpc@gmail.com",
        "aud": "authenticated",
        "iss": ISS,
        "iat": ahora,
        "exp": ahora + 3600,
    }
    d.update(extra)
    return d


fallos = []


def caso(nombre, fn, espera_ok, detalle_esperado=None):
    try:
        r = fn()
        ok = espera_ok
        obtenido = f"aceptado ({r['email']})"
    except HTTPException as e:
        ok = (not espera_ok) and (detalle_esperado is None or detalle_esperado in e.detail)
        obtenido = f"HTTP {e.status_code}: {e.detail}"
    except Exception as e:
        ok = False
        obtenido = f"{type(e).__name__}: {e}"
    print(f"{'PASA ' if ok else 'FALLA'}  {nombre:<46} → {obtenido}")
    if not ok:
        fallos.append(nombre)


# 1. Token ES256 válido (el formato que emite Supabase hoy)
caso(
    "ES256 válido (Supabase actual)",
    lambda: llamar(jwt.encode(base(), clave_priv, algorithm="ES256",
                              headers={"kid": KID})),
    True,
)

# 2. Token HS256 legacy con el secreto compartido
caso(
    "HS256 legacy con secreto correcto",
    lambda: llamar(jwt.encode(base(), "secreto-legacy-de-prueba", algorithm="HS256")),
    True,
)

# 3. HS256 firmado con otro secreto
caso(
    "HS256 con secreto equivocado",
    lambda: llamar(jwt.encode(base(), "otro-secreto", algorithm="HS256")),
    False, "Token inválido",
)

# 4. ES256 firmado por una clave que no está en el JWKS
otra = ec.generate_private_key(ec.SECP256R1())
caso(
    "ES256 firmado por clave ajena",
    lambda: llamar(jwt.encode(base(), otra, algorithm="ES256",
                              headers={"kid": KID})),
    False, "Token inválido",
)

# 5. Expirado
caso(
    "ES256 expirado",
    lambda: llamar(jwt.encode(base(exp=int(time.time()) - 10), clave_priv,
                              algorithm="ES256", headers={"kid": KID})),
    False, "Token expirado",
)

# 6. Audiencia incorrecta
caso(
    "ES256 con audience equivocada",
    lambda: llamar(jwt.encode(base(aud="otra-cosa"), clave_priv,
                              algorithm="ES256", headers={"kid": KID})),
    False, "Token inválido",
)

# 7. Emisor incorrecto (token de OTRO proyecto Supabase)
caso(
    "ES256 de otro proyecto (iss ajeno)",
    lambda: llamar(jwt.encode(base(iss="https://malicioso.supabase.co/auth/v1"),
                              clave_priv, algorithm="ES256",
                              headers={"kid": KID})),
    False, "otro proyecto de Supabase",
)

# 8. alg: none — intento clásico de saltarse la firma
caso(
    "alg 'none' (intento de evasión de firma)",
    lambda: llamar(jwt.encode(base(), key="", algorithm="none")),
    False, "Algoritmo de firma no admitido",
)

# 9. Basura
caso("token malformado", lambda: llamar("esto-no-es-un-jwt"), False, "malformado")

# 10. El JWKS se cachea (no se pide en cada request)
n_antes = peticiones_jwks["n"]
for _ in range(5):
    llamar(jwt.encode(base(), clave_priv, algorithm="ES256", headers={"kid": KID}))
n_nuevas = peticiones_jwks["n"] - n_antes
ok_cache = n_nuevas == 0
print(f"{'PASA ' if ok_cache else 'FALLA'}  {'JWKS cacheado (5 peticiones)':<46} "
      f"→ {n_nuevas} descargas extra del JWKS")
if not ok_cache:
    fallos.append("cache JWKS")

print()
print(f"JWKS descargado {peticiones_jwks['n']} vez/veces en total")
print("TODOS LOS CASOS PASAN" if not fallos else f"FALLOS: {fallos}")
sys.exit(1 if fallos else 0)
