"""
supabase_admin.py — Cliente Supabase (service role) para uso interno del backend.

Hoy solo lo usa el healthcheck. Si en el futuro el backend necesita leer/escribir
en Supabase directamente (más allá del almacenamiento local en JSON), este es el
punto de entrada a reutilizar.
"""
from __future__ import annotations

import os
from functools import lru_cache

from supabase import Client, create_client


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ["SUPABASE_KEY"]
    return create_client(url, key)
