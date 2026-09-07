# Análisis de competencia — AIBX (aibexsv.com) vs Learnix DTE Hub

Fecha: 2026-09-07 · Fuentes: página pública de planes de AIBX y recorrido de su app
(dashboard, selector de empresa, selector de libro, editor de libro e importación),
contrastados contra el código de este repo (commit `b1e4624`).

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

Su empaque se apoya en **dos ejes de medición** (empresas y facturas/mes) más una
tercera cuota (descargas de correo + buzones conectados), todo self-serve.

---

## 2. Dónde estamos realmente

En **capacidad de extracción** estamos a la par o por delante. Los dos huecos
reales son estructurales y ninguno es el motor: **el modelo de producto** y **la
capa comercial**.

### 2.1 Motor fiscal — vamos ganando

| Capacidad | AIBX | Learnix | Evidencia |
|---|---|---|---|
| Ventas contribuyente (CCF/NC/ND, Anexo 1) | ✅ | ✅ | `backend/extractors/ventas.py` |
| Ventas consumidor final (Anexo 2) | ✅ | ✅ | idem |
| Compras (Anexo 3) | ✅ | ✅ | `backend/extractors/compras.py` |
| Retención 1% (DTE-07, Anexo 7) | ✅ | ✅ | `backend/extractors/retenciones.py` |
| **Sujetos Excluidos (DTE-14, Anexo 5)** | ❌ no listado | ✅ | `backend/extractors/sujetos_excluidos.py` |
| JSON firmado, parseado contra el schema oficial | ✅ | ✅ | `utils/dte_json.py`, `concurrent_processor.py` |
| PDF con capa de texto | ✅ | ✅ | `utils/pdf_utils.py` |
| PDF escaneado vía visión (Groq + Vertex, circuit breaker) | ✅ "OCR beta" | ✅ | `utils/ai_utils.py:1244+` |
| Validación fiscal DGII + score de confianza | ✅ (lo muestran como "100% · Verificado") | ✅ (calculado, no mostrado antes de procesar) | `utils/qa_utils.py` |
| Procesamiento por lotes con job persistido | no visible | ✅ | `db/07_procesamiento_jobs.sql` |
| Multi-tenant con RLS auditado | — | ✅ | `docs/SECURITY.md`, `db/01`, `db/08`, `db/09` |
| Calendario de obligaciones | IVA | F-07, F-14, F-930 y Renta | `Dashboard.jsx:43` |
| Export con columnas exactas del anexo | "Anexo MH A1" | 5 anexos en xlsx (6 definidos) | `routers/exportar.py:338+` |
| Export en el formato subible al portal (CSV `;`) | ✅ | ❌ solo xlsx con encabezados | `anexos_schema/*.json` |
| Asiento contable para el sistema contable | ✅ "Asiento Diario" | ❌ no existe | — |

### 2.2 El modelo de producto — **la brecha estructural**

Esto es lo más importante del análisis y no se ve en la página de precios.

**Nuestro flujo:** entrás a la página del tipo de DTE → seleccionás declarante →
subís archivos → sale una tabla → exportás Excel. Se acabó.

**Su flujo:** `¿En qué empresa vas a trabajar?` (con "última usada") →
`¿Libro nuevo o existente?` (con período) → **editor del libro**, que es una hoja
de cálculo con buscar, deshacer/rehacer, zoom, "+ Añadir fila", "Guardar cambios",
"Importar JSON/PDF/Imagen" y **"Finalizar libro"**.

La diferencia de fondo:

| | Learnix | AIBX |
|---|---|---|
| Objeto central | el archivo que subís | **el libro del período, por empresa** |
| El trabajo persiste | no en la UI | sí — "Libro Agosto 2026 · 0 facturas · 07 sept" |
| Se puede corregir a mano | ❌ tabla de solo lectura | ✅ grid editable, fila por fila |
| Estado de cierre | no existe | "Finalizar libro" |
| Contexto de empresa | selector dentro del uploader | modal de sesión + "Crear empresa" |
| Seguimiento por período | calendario genérico | agenda automática por empresa con estado ("Sin iniciar", 0/1) |

Dos consecuencias concretas, verificables en el código:

1. **La tabla de resultados es de solo lectura.** `ResultadosTabla.jsx` no tiene un
   solo `<input>` ni `onChange` de edición. Ninguna extracción por IA es perfecta,
   así que el contador *tiene* que corregir — y hoy lo hace en Excel, fuera del
   producto. Ahí perdemos el registro y perdemos la razón para volver.
2. **Guardamos los datos y nunca los leemos.** `guardarResultados()`
   (`services/api.js:109`) escribe en las tablas con `periodo` calculado, pero
   **no existe ninguna consulta que los recupere**: grep de lecturas sobre esas
   tablas desde `ExtractorPage.jsx` no devuelve nada. Cerrás la pestaña y el
   trabajo desaparece de la interfaz aunque siga en la base.

Y la grilla no es una tabla genérica: **es el libro oficial**. Encabezados
anidados tal cual la DGII (`OPERACIONES DE VENTAS` → `PROPIAS` / `A CUENTA DE
TERCEROS`, cada una con `EXENTAS`, `INTERNAS GRAVADAS`, `DÉBITO FISCAL`), columna
`CORRELATIVO`, y una fila **`TOTALES DEL MES DE AGOSTO`** calculada sola. Arriba,
un indicador de autoguardado (`✓ Todo guardado`). El contador no ve "los campos que
la IA extrajo": ve su libro, con la forma que ya conoce.

Por eso pueden cobrar suscripción: no venden extracción, venden **el lugar donde
vive el libro**. Una herramienta de un solo uso no sostiene una mensualidad, por
buena que sea la extracción.

### 2.3 Las salidas — dónde termina el trabajo

Su menú de exportación tiene tres opciones: **Exportar Excel**, **Anexo MH A1** y
**Asiento Diario**.

Acá hay una ventaja nuestra que casi se me pasa y una carencia real:

- **Ventaja:** nuestro `routers/exportar.py` no exporta un Excel genérico — arma las
  **columnas exactas del F-07**, en hojas por anexo (`Ventas_Contribuyentes`,
  `Ventas_Consumidor`, `Compras_F07`, `Retenciones_Anexo7`,
  `SujetosExcluidos_Anexo5`), sobre las definiciones de
  `utils/anexos_schema/*.json`. Son **seis anexos definidos** (1, 2, 3, 5, 7 y el 8
  de percepción 1%, que ellos no listan) contra el único "A1" que ofrece su menú.
- **Carencia:** exportamos **XLSX con encabezados**, y los seis schemas declaran que
  el formato oficial es **CSV, separador `;`, sin encabezados, UTF-8, celdas como
  texto**. Es decir: tenemos las columnas correctas en el archivo equivocado, y el
  contador todavía tiene que convertirlo a mano antes de subirlo al portal. Su
  botón "Anexo MH A1" entrega el archivo subible. **Arreglo barato y de alto valor
  percibido: el CSV ya está descrito en los JSON que tenemos.**
- **Carencia real:** **Asiento Diario no existe en nuestro repo** (grep de
  `asiento|partida|cuenta contable` no devuelve nada). Ese es su puente a la
  contabilidad — lo que evita que el libro muera en el libro y lo vuelve parte del
  cierre mensual, no un trámite aparte.

### 2.4 La confianza, mostrada a tiempo

Su vista previa, antes de consumir cuota, muestra por archivo un porcentaje y **una
razón concreta**:

- `CCF DTE-252 ENVACASA.pdf` — 98% · Revisar — "La IA/OCR señaló información que debe compararse con el documento."
- `CCF DTE-259 PIPSA.pdf` — 96% · Revisar
- `CCF DTE-265 NAUFFAR.pdf` — **85% · Revisar — "La distribución de montos por concepto no coincide con el resumen extraído."**

Más un aviso agregado ("4 extracciones tienen confianza menor al 100%") y un modal
que calibra expectativas sin vender humo: *"considera una precisión operativa
aproximada de 80% a 90% hasta tener validación humana"*.

**Esto ya lo tenemos y lo enseñamos tarde.** `utils/qa_utils.py` produce razones del
mismo calibre — `clasificar_alerta_compra/venta` devuelve cosas como
`IVA $18.85 ≠ 145.00×13%=$18.85` o `Sello vacío`, y `validar_montos_*` acumula
alertas por registro. Es material de primera; el problema es que aparece después de
procesar, cuando la cuota ya se gastó y el contador ya no está decidiendo. Moverlo a
una vista previa es reordenar UI, no construir motor.

Nota de arquitectura: su modal dice que convierten PDF/imagen a **"JSON interno"** y
que el "motor IVA" siempre trabaja sobre ese JSON. Es una decisión limpia y conviene
copiarla cuando aceptemos imagen: normalizar todo a la misma forma que ya produce
nuestro parser de JSON firmado, en vez de abrir un tercer camino de datos.

### 2.5 La capa comercial — no se puede cobrar

1. **No hay pasarela de pago.** Cero, en todo el repo.
2. **No hay auto-registro.** `signUp` no aparece en ningún archivo de
   `frontend/src`; las cuentas se crean a mano. Su embudo empieza con "$0 prueba,
   25 documentos".
3. **Los límites existen en el schema pero no se aplican.** `organizaciones` tiene
   `limite_dtes_mes` y `dtes_procesados_mes`, y `db/01_schema_saas.sql:175` define
   `puede_procesar_dte()`. **Ningún `.py` ni `.jsx` los invoca** (verificado por
   grep sobre `backend/`, `frontend/`, `scripts/`).
4. **La cuota es invisible.** Ellos la muestran en el header del editor ("Facturas
   disponibles: 23") y otra vez en la vista previa de importación ("Cuota
   disponible: 23 facturas") **antes** de consumirla. Nosotros no mostramos nada.
5. **No hay eje de "empresas por plan"** (`limite_empresas`), que es como escalonan
   de $17 a $50. Nuestra tabla `clientes` acepta N declarantes sin límite: hoy es
   capacidad regalada, no ventaja.
6. **`plan_suscripcion` es decorativo** — sus valores no corresponden a ningún
   precio publicado ni cambian comportamiento.
7. **El landing vende un plan único de $15/mes**: caro para el contador de una
   empresa (que ellos captan gratis) y regalado para la firma de cuarenta (que a
   ellos les paga $50).

### 2.6 Paridad de features pendiente

8. **Imagen como formato de entrada.** `_read_upload_bytes()`
   (`routers/procesamiento.py:36`) rechaza todo lo que no sea `.pdf` o `.json`. El
   motor de visión ya existe y funciona. **El gap más barato de la lista** — horas.
9. **Vista previa antes de procesar.** Ellos muestran archivo, verificación (100%)
   y monto ($163.85) y dejan cancelar sin gastar cuota. Nosotros ya calculamos
   confianza en `qa_utils.py`, pero solo después de procesar.
10. **Centro de Correos.** Tenemos Drive + Gmail (`routers/importar.py`), pero el
    Gmail es IMAP con App Password que el usuario reescribe cada sesión
    (`ImportCenter.jsx:283`), **sin Outlook/Microsoft 365**, sin buzones guardados,
    sin sincronización automática y sin contador de descargas.
11. **Soporte escalonado por plan** — empaquetado puro, costo casi nulo.

### 2.7 Deuda que frena la velocidad

12. Sin tests ni CI (ya anotado en el README). Los commits `#182` y `#183` fueron
    correcciones de extracción encontradas en producción.
13. `Dashboard.jsx` muestra `count(*)` de tablas; no hay consumo del mes ni estado
    de avance por empresa/período.

---

## 3. Plan propuesto

El orden importa. Cobrar por un producto al que nadie vuelve produce churn, no
ingreso; y un producto al que sí se vuelve pero que no puede cobrar tampoco sirve.
La secuencia es: **hacer que el trabajo persista → medir → cobrar**.

### Fase 0 — Tres arreglos de horas, no de semanas

Ninguno necesita diseño ni decisiones; el material ya está en el repo.

- **Exportar el CSV subible** (`;`, sin encabezados, UTF-8) junto al xlsx actual.
  El formato está descrito en los seis `anexos_schema/*.json` y las columnas ya se
  arman en `exportar.py`. Cierra el último paso manual del contador.
- **Aceptar imagen** (`.jpg/.png/.heic`) en `_read_upload_bytes`
  (`routers/procesamiento.py:36`) → el motor de visión que ya existe.
- **Mostrar las alertas de `qa_utils` antes de procesar**, no después: la razón
  concreta por archivo ya se calcula, solo aparece tarde.

### Fase 1 — El libro persistente (lo que justifica la suscripción)

1. `db/10_libros.sql`: tabla `libros` (`organizacion_id`, `cliente_id`, `tipo`,
   `periodo`, `estado` ∈ borrador/finalizado, timestamps) y FK `libro_id` en las
   tablas de registros existentes, con RLS al mismo nivel que el resto.
2. Selector de empresa y de libro al entrar al extractor (nuevo vs. existente por
   período), con "última usada" recordada.
3. **Grid editable con forma de libro oficial** en `ResultadosTabla.jsx`: editar
   celda, añadir y borrar fila, encabezados anidados del anexo, **fila de totales
   del mes** calculada, y autoguardado con indicador de estado. Es el punto que más
   pesa: sin esto el contador se va a Excel.
4. Recargar el libro guardado al abrirlo — hoy los datos se escriben y nunca se
   leen.
5. "Finalizar libro" + exportación desde el libro cerrado.

### Fase 2 — Medir y cobrar

6. `db/11_planes.sql`: tabla `planes` (código, precio, `limite_empresas`,
   `limite_dtes_mes`, `limite_descargas_correo`, `limite_buzones`) + FK desde
   `organizaciones`, reemplazando el CHECK de `plan_suscripcion`.
7. Enforcement real: invocar `puede_procesar_dte()` en la dependencia de auth de
   `routers/procesamiento.py` e incrementar el contador al cerrar cada extracción
   (incluido cada archivo de un lote); `402` con el plan sugerido.
8. Cuota visible en el header del extractor y en una vista previa de importación
   que muestre confianza y monto **antes** de consumir.
9. Auto-registro con trial: `signUp` de Supabase, organización en plan `trial`
   (1 empresa, 25 DTEs), verificación por correo.
10. Página `/configuracion/planes` + checkout. Para El Salvador la vía práctica es
    **Wompi SV**, con Stripe para clientes fuera del país; webhook → actualiza
    `plan_id` y `estado_suscripcion`.
11. Reprecificar el landing a la matriz real.

### Fase 3 — Paridad y ventaja

12. Aceptar imagen (`.jpg/.png/.heic`) en `_read_upload_bytes` → visión. Barato,
    se puede adelantar a cualquier fase.
13. Buzones persistentes: tabla `buzones`, OAuth de Google y **Microsoft Graph**
    para Outlook/365, con contador de descargas por plan.
14. Agenda de cumplimiento por empresa y período (estado, avance), apoyada en el
    calendario de obligaciones que ya existe — el nuestro cubre F-07, F-14, F-930
    y Renta, más de lo que ellos muestran.
15. **Asiento Diario**: exportar la partida contable del período. Es lo que conecta
    el libro con la contabilidad y con el cierre mensual — hoy no existe de nuestro
    lado y es de las pocas cosas que ellos tienen y nosotros no, de raíz.
16. Conectar el anexo 8 (percepción 1%): el schema existe, el extractor no.
17. Tests + CI sobre los extractors, que es donde duelen las regresiones.

---

## 4. Lectura corta

No estamos atrás en lo difícil: el motor de extracción es comparable y en varios
puntos superior, y la base multi-tenant con RLS ya está auditada. Estamos atrás en
dos cosas que no son extracción.

La primera, y la que casi no se ve: **ellos construyeron un sistema de registro y
nosotros una herramienta de un solo uso.** Su usuario abre una empresa, abre el
libro de agosto, corrige filas a mano, guarda y vuelve mañana. El nuestro sube
archivos, baja un Excel y se va — y lo que corrija, lo corrige fuera del producto.
Eso, y no el precio, es lo que hace que una mensualidad tenga sentido.

La segunda: no hay forma de que un cliente nuevo llegue, pruebe y pague solo.

Y hay una tercera, más chica pero vergonzosa por lo fácil que es: tenemos las
columnas exactas de seis anexos y las entregamos en el archivo equivocado. El
formato que el portal acepta está escrito en nuestros propios JSON de schema.

La fase 0 son horas. La fase 1 arregla la razón para volver. La fase 2 cobra por
ella.
