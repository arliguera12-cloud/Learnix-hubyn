# Validación de Credenciales GROQ + VERTEX AI

**Estado:** PR #106 mergeado a `main`. Cambios activos:
- ✅ Hybrid escalation Flash→Pro (confianza < 75%)
- ✅ Thinking automático en validación de texto
- ✅ Etiquetado dinámico (reporta el modelo real que ejecutó)

---

## 1. Verificar Credenciales Localmente

Si quieres probar en tu máquina **antes de deployar a Streamlit Cloud**:

```bash
# Instala dependencias
pip install google-genai groq python-dotenv

# Crea .env en la raíz del proyecto con:
GROQ_API_KEY=gsk_...
VERTEX_API_KEY=AIzaSy...
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Corre el test script
python test_credentials.py
```

**Esperado:**
```
✅ TODAS LAS CREDENCIALES VALIDADAS

Próximos pasos:
1. Deployar a Streamlit Cloud con estas credenciales en Secrets
2. Subir un DTE (PDF) para probar extracción
3. Verificar en audit que:
   - motor_usado = 'vertex-ai/gemini-2.5-flash' (por defecto)
   - Si confianza < 75%, motor_usado = 'vertex-ai/gemini-2.5-pro (escalado)'
   - confianza_extraccion está presente (0-100)
```

---

## 2. Configurar en Streamlit Cloud

En **Settings > Secrets** del deployment de Streamlit Cloud, añade:

```toml
GROQ_API_KEY = "gsk_..."
VERTEX_API_KEY = "AIzaSy..."

# Google Service Account (toda la clave JSON de una línea)
GOOGLE_APPLICATION_CREDENTIALS = """{"type": "service_account", ...}"""

# Opcionales (si quieres override de modelos)
VERTEX_MODEL = "gemini-2.5-flash"
VERTEX_MODEL_PRO = "gemini-2.5-pro"

# Si quieres cambiar el umbral de escalada (default 75%)
# CONF_ESCALADO_PRO = 75
```

---

## 3. Probar con un DTE Real

**Después de deployar**, sube un PDF DTE a la app y:

1. Usa la función **2_Extractor_DTE_Compras** (o la que uses)
2. Sube un PDF
3. **Mira el audit JSON** para verificar:

```json
{
  "auditoria_ia": {
    "motor_usado": "vertex-ai/gemini-2.5-flash",           // Flash por defecto
    "confianza_extraccion": 85,                             // 0-100, si > 75 no escala
    "fecha_procesamiento": "2026-06-05T..."
  }
}
```

### Caso 1: Alta Confianza (≥ 75%)
- Solo **Flash** ejecuta
- `motor_usado = "vertex-ai/gemini-2.5-flash"`
- Rápido y económico ✅

### Caso 2: Baja Confianza (< 75%)
- Flash ejecuta primero
- Si confianza < 75%, **Pro escala automáticamente** (un reintento)
- `motor_usado = "vertex-ai/gemini-2.5-pro (escalado)"`
- Log: "Escalado a Pro por baja confianza (texto)." o "(visión)."
- Más preciso pero con costo adicional ⚠️

### Caso 3: Vertex AI No Disponible
- Fallback automático a **Groq** (llama-3.3-70b-versatile)
- `motor_usado = "groq/llama-3.3-70b-versatile"`
- Circuit breaker de Groq abierto = 5 errores, espera 60s

---

## 4. Dónde Ver Detalle de la Extracción

En la UI de Streamlit, después de subir un PDF:

1. **Tabla de resultados:** Campos extraídos (NIT, fecha, montos, etc.)
2. **JSON audit (expandible):** Detalles de qué IA corrió, timestamps, confianza
3. **Logs de la terminal:** Busca "Escalado a Pro" si ocurrió

---

## 5. Troubleshooting

### "VERTEX_API_KEY no está configurada"
- Verifica que en Streamlit Cloud Settings > Secrets esté la variable
- En local, verifica que `.env` tiene la clave
- Recarga la app después de cambiar secrets

### "Gemini 2.5 Pro no disponible"
- El proyecto GCP debe tener `gemini-2.5-pro` habilitado
- Verifica: https://console.cloud.google.com/gen-app-builder/engines?project=nomadic-sprite-440003-r7

### "thinking_config no soportado por el SDK"
- Es un warning esperado si usas `google-genai` vieja
- La app **degrada gracefully** a config estándar sin crash
- Actualiza: `pip install --upgrade google-genai`

### "Circuit breaker de Groq abierto"
- Groq alcanzó 5 errores en 60 segundos
- Espera 60s antes de reintentar
- Vertex debería estar disponible para evitar esto

---

## 6. Arquitectura Híbrida Resumida

```
┌─────────────────┐
│  DTE en PDF     │
└────────┬────────┘
         │
    ┌────v─────────────┐
    │ Extrae imagen    │
    │ (Visión primero) │
    └────┬─────────────┘
         │
    ┌────v──────────────────┐
    │ Intenta Vertex Flash   │
    │ (rápido, económico)    │
    └────┬──────────────────┘
         │
   ┌─────v──────────────────┐
   │ confianza >= 75%?       │
   │ ✅ SÍ → Usa Flash       │
   │ ❌ NO → Escala a Pro    │
   └─────┬──────────────────┘
         │
    ┌────v──────────────────┐
    │ Intenta Vertex Pro     │
    │ (preciso pero costoso) │
    │ (UN reintento máximo)  │
    └────┬──────────────────┘
         │
   ┌─────v──────────────────┐
   │ Vertex disponible?      │
   │ ✅ SÍ → Usa resultado   │
   │ ❌ NO → Fallback Groq   │
   └─────┬──────────────────┘
         │
    ┌────v──────────────────┐
    │ DTE validado + audit   │
    └────────────────────────┘
```

---

## 7. Preguntas Frecuentes

**P: ¿Cuándo escala a Pro?**
R: Cuando `confianza_extraccion < 75%` en la respuesta de Flash. Esto significa que el modelo mismo indicó baja certeza en los números extraídos (montos, IVA, etc.).

**P: ¿Thinking siempre está activado?**
R: Solo en la capa de texto (validación de montos/IVA). Vision no usa thinking (ya es multimodal).

**P: ¿Se puede deshabilitar el escalado?**
R: Sí, setea `VERTEX_MODEL_PRO = ""` en secrets → no escalará. O cambia `_CONF_ESCALADO_PRO` en código.

**P: ¿Groq es más barato que Vertex?**
R: Groq es **más económico** pero **menos preciso** que Pro. Flash es el balance ideal (rápido+preciso). Se usa Groq solo si Vertex falla.

---

**Siguiente paso:** Deployar a Streamlit Cloud y probar con los 5 PDFs de gasolineras + otros DTEs. ✅
