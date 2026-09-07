# Análisis de competencia — AIBX (aibexsv.com) vs Learnix DTE Hub

Fecha: 2026-09-07 · Fuente: página pública de planes de AIBX
(`/es/app/configuracion/membresia/planes`) contrastada contra el código de este repo
(commit `b1e4624`).

---

## 1. Qué vende AIBX

| | Prueba | LIGHT | PRO | ULTRA |
|---|---|---|---|---|
| Precio | $0 | **$17/mes** | **$25/mes** | **$50/mes** |
| Empresas | 1 | 10 | 25 | 50 |
| Facturas | 25 (total) | 500/mes | 1,400/mes | 3,000/mes |
| Libros IVA | prueba | Compras, Ventas consumidor, Ventas contribuyente, Retención 1% | igual | igual |
| Entrada | JSON | JSON, PDF, **imagen con OCR (beta)** | igual | igual |
| Centro de Correos | 25 descargas/mes + 1 buzón | 2,000/mes + 5 buzones | 3,000/mes + 10 buzones | 6,000/mes + 20 buzones |
| Soporte | email | email | prioritario | prioritario alto volumen |

Su empaque está construido sobre **dos ejes de medición**: número de empresas y
número de facturas/mes, más una tercera cuota (descargas de correo + buzones
conectados). Todo self-serve: el usuario entra, prueba con 25 facturas y elige plan
sin hablar con nadie.

---

## 2. Dónde estamos realmente

La lectura de "nos falta mucho" es correcta, pero **el hueco no está donde parece**.
En capacidad de extracción estamos a la par o por delante. Lo que no existe es la
capa comercial completa.

### 2.1 Motor fiscal — vamos ganando

| Capacidad | AIBX | Learnix | Evidencia |
|---|---|---|---|
| Ventas contribuyente (CCF/NC/ND, Anexo 1) | ✅ | ✅ | `backend/extractors/ventas.py` |
| Ventas consumidor final (Anexo 2) | ✅ | ✅ | idem |
| Compras (Anexo 3) | ✅ | ✅ | `backend/extractors/compras.py` |
| Retención 1% (DTE-07, Anexo 7) | ✅ | ✅ | `backend/extractors/retenciones.py` |
| **Sujetos Excluidos (DTE-14, Anexo 5)** | ❌ no listado | ✅ | `backend/extractors/sujetos_excluidos.py` |
| JSON firmado por Hacienda, parseado contra el schema oficial | ✅ | ✅ | `utils/dte_json.py`, `concurrent_processor.py` |
| PDF con capa de texto | ✅ | ✅ | `utils/pdf_utils.py` |
| PDF escaneado vía visión (Groq + Vertex, con circuit breaker) | ✅ "OCR beta" | ✅ | `utils/ai_utils.py:1244+` |
| Validación fiscal DGII + score de confianza por registro | no publicitado | ✅ | `utils/qa_utils.py` |
| Procesamiento por lotes con job persistido | no publicitado | ✅ | `db/07_procesamiento_jobs.sql` |
| Multi-tenant con RLS auditado | — | ✅ | `docs/SECURITY.md`, `db/01`, `db/08`, `db/09` |

**Empresas por cuenta: nosotros no tenemos límite.** Su plan de $50 tope a 50
empresas; nuestra tabla `clientes` acepta N declarantes por organización sin
restricción. Eso hoy es un regalo, no una ventaja: es capacidad que no cobramos.

### 2.2 Los huecos reales

**Bloqueantes de negocio — sin esto no hay ingreso, con o sin features:**

1. **No hay pasarela de pago.** Cero. `grep` de `stripe|wompi|paypal|checkout` en
   todo el repo devuelve solo la palabra "suscripción" en SQL y en el landing.
   AIBX cobra self-serve desde su propia app.
2. **No hay auto-registro.** `frontend/src/pages/Login.jsx` solo tiene email +
   contraseña; no existe `signUp` en ningún archivo de `frontend/src`. Las cuentas
   se crean a mano. Su embudo empieza con "$0 prueba, 25 facturas"; el nuestro
   empieza con un correo al fundador.
3. **Los límites existen en el schema pero no se aplican.** `organizaciones` tiene
   `limite_dtes_mes` y `dtes_procesados_mes`, y `db/01_schema_saas.sql:175` define
   `puede_procesar_dte()`. **Ningún archivo Python o JSX los invoca** (verificado
   por grep sobre `backend/`, `frontend/`, `scripts/`). Cualquier usuario procesa
   ilimitado, y no hay contador visible de consumo.
4. **No hay eje de "empresas" en el plan.** No existe `limite_empresas` ni conteo de
   declarantes activos. Sin eso no se puede escalonar precio como ellos.
5. **`plan_suscripcion` es decorativo.** Sus valores (`starter`/`profesional`/
   `enterprise`) no corresponden a ningún precio publicado ni a ninguna diferencia
   de comportamiento en el producto.
6. **El landing vende un plan único de $15/mes.** Contra su matriz de 4 planes eso
   nos deja en el peor de los dos mundos: caro para el contador con 1 empresa
   (que ellos captan gratis) y regalado para la firma con 40 empresas (que a ellos
   les paga $50).

**Paridad de producto — visibles en su página de precios, ausentes acá:**

7. **Imagen como formato de entrada.** `_read_upload_bytes()`
   (`backend/routers/procesamiento.py:36`) rechaza todo lo que no sea `.pdf` o
   `.json`. El motor de visión ya existe y funciona; lo que falta es aceptar
   `.jpg/.png/.heic` y renderizarlos al mismo pipeline. **Es el gap más barato de
   toda la lista** — horas, no semanas.
8. **Centro de Correos vs nuestro Centro de importación.** Tenemos Drive + Gmail
   funcionando (`routers/importar.py`), pero:
   - Gmail es IMAP con **App Password que el usuario reescribe en cada sesión**
     (`ImportCenter.jsx:283`) — no hay buzones guardados.
   - **No hay Outlook / Microsoft 365.** Ellos sí.
   - No hay sincronización automática ni contador de descargas: ellos venden
     exactamente eso ("6,000 descargas/mes + 20 buzones").
9. **Soporte escalonado por plan.** Puro empaquetado, costo casi nulo, y es una de
   las cuatro filas que ellos muestran en cada tarjeta.

**Deuda que frena la velocidad:**

10. Sin tests ni CI en el repo (ya anotado en el README). Cada release es manual.
11. `Dashboard.jsx` muestra `count(*)` de tablas; no hay consumo del mes, ni libro
    consolidado por período, ni cierre mensual.

---

## 3. Plan propuesto

### Fase 1 — Poder cobrar (prioridad absoluta)

Nada de esto es investigación; todo es trabajo conocido sobre schema que ya existe.

1. `db/10_planes.sql`: tabla `planes` (código, precio, `limite_empresas`,
   `limite_dtes_mes`, `limite_descargas_correo`, `limite_buzones`) + FK desde
   `organizaciones`, reemplazando el CHECK de `plan_suscripcion`.
2. Enforcement real: llamar `puede_procesar_dte()` en la dependencia de auth de
   `routers/procesamiento.py`, e incrementar el contador al cerrar cada extracción
   (incluido cada archivo de un lote). Devolver `402` con el plan sugerido.
3. Auto-registro + trial: `signUp` de Supabase en `Login.jsx`, organización creada
   con plan `trial` (1 empresa, 25 DTEs), verificación por correo.
4. Página `/configuracion/planes` con las tarjetas y el consumo del mes.
5. Checkout. Para El Salvador la vía práctica es **Wompi SV** (tarjeta local) con
   Stripe como salida para clientes fuera del país; webhook → actualiza
   `organizaciones.plan_id` y `estado_suscripcion`.
6. Reprecificar el landing a la matriz de planes real.

**Salida de la fase 1: se puede vender sin intervención humana.** Hoy no se puede.

### Fase 2 — Paridad visible

7. Aceptar imagen (`.jpg/.png/.heic`) en `_read_upload_bytes` → visión. Barato.
8. Buzones persistentes: tabla `buzones`, OAuth de Google en vez de App Password, y
   **Microsoft Graph para Outlook/365**. Contador de descargas por plan.

### Fase 3 — Ventaja propia

9. Empujar lo que ellos no muestran: Sujetos Excluidos, score de confianza por
   campo, cierre mensual con libro consolidado listo para la DGII.
10. Tests + CI sobre los extractors (ahí es donde duelen las regresiones: los
    commits `#182`, `#183` fueron correcciones de extracción en producción).

---

## 4. Lectura corta

No estamos atrás en lo difícil. El motor de extracción es comparable y en un par de
puntos superior, y la base multi-tenant con RLS ya está auditada. Estamos atrás en
lo que se vende: ellos tienen trial, planes, medidor y cobro automático; nosotros
tenemos un producto que funciona y ninguna forma de que un cliente nuevo llegue,
pruebe y pague solo. Los puntos 1–6 son el trabajo que cierra esa distancia; el
resto es alcanzable después.
