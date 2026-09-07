import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import ThemeToggle from '../components/ThemeToggle'
import {
  IconVentas, IconCompras, IconRetenciones, IconSujetos, IconSeccion, IconCheck,
} from '../components/Icons'

/** Índice de características — el "por qué Learnix" frente a hacerlo a mano. */
const CARACTERISTICAS = [
  {
    titulo: 'Lectura nativa del DTE',
    detalle: <>Lee el <b>JSON firmado</b> por Hacienda campo por campo — o el PDF si no lo tenés — sin regex frágil ni plantillas que se rompen con el próximo formato.</>,
  },
  {
    titulo: 'Verificación con IA',
    detalle: <>Vision y un segundo modelo revisan lo que el documento no dejó claro, con un <b>puntaje de confianza</b> por documento para saber qué mirar antes de declarar.</>,
  },
  {
    titulo: 'Multi-cliente real',
    detalle: <>Directorio de clientes con cambio instantáneo — cada extracción queda <b>separada</b>, sin mezclar el trabajo de dos empresas en la misma tabla.</>,
  },
  {
    titulo: 'Anexos listos para declarar',
    detalle: <>Exportá a Excel con los campos exactos del anexo — 1, 2 o 3 — en un clic, <b>sin reordenar columnas</b> a mano.</>,
  },
  {
    titulo: 'Importación desde Drive y Gmail',
    detalle: <>Traé los DTE directo desde tu Drive o tu correo, <b>sin descargar y volver a subir</b> cada archivo uno por uno.</>,
  },
  {
    titulo: 'Seguridad de tus datos',
    detalle: <>Autenticación con Supabase, <b>aislamiento por usuario</b> a nivel de base de datos y auditoría de acceso en cada sesión.</>,
  },
]

const STATS = [
  ['4', 'Anexos de Hacienda cubiertos: Ventas, Compras, Retenciones y Sujetos Excluidos.'],
  ['2', 'Motores de IA verificando cada documento — lectura Vision y verificación textual.'],
  ['100%', 'Campos leídos del documento firmado por Hacienda, no de una plantilla genérica.'],
  ['0', 'Captura manual. Todo desde el navegador, sin instalar nada.'],
]

const MODULOS = [
  {
    Icon: IconVentas,
    titulo: 'Ventas',
    detalle: 'CCF, notas de crédito/débito y facturas de consumidor final, leídas directo del DTE firmado.',
    ref: 'DTE-01 · 03 · 05 · 06 — Anexos 1 y 2',
  },
  {
    Icon: IconCompras,
    titulo: 'Compras',
    detalle: 'CCF recibidos de proveedores, con crédito fiscal calculado automáticamente.',
    ref: 'Anexo 3',
  },
  {
    Icon: IconRetenciones,
    titulo: 'Retenciones',
    detalle: 'Comprobantes de retención listos para la casilla exacta del formulario.',
    ref: 'DTE-07 — Casilla 162',
  },
  {
    Icon: IconSujetos,
    titulo: 'Sujetos Excluidos',
    detalle: 'Compras a sujetos excluidos de IVA, clasificadas sin revisión manual.',
    ref: 'DTE-14 — Casilla 66',
  },
]

const PASOS = [
  {
    titulo: 'Sube tus documentos',
    detalle: 'PDF o JSON firmado por Hacienda, uno o varios a la vez.',
  },
  {
    titulo: 'La IA extrae y verifica',
    detalle: 'Lectura nativa del DTE más verificación con IA y un puntaje de confianza por documento, así sabés qué revisar antes de declarar.',
  },
  {
    titulo: 'Exporta tus anexos',
    detalle: 'Anexos y formularios listos para tu declaración en un clic, sin abrir Excel ni tipear un solo número.',
  },
]

const WHATSAPP_SOLICITAR_ACCESO =
  'https://api.whatsapp.com/send/?phone=50377567894&text=' +
  encodeURIComponent('Hola, quiero contratar Learnix para mi empresa.') +
  '&type=phone_number&app_absent=0'

const PRECIO_ITEMS = [
  'Extracción ilimitada de DTE — PDF y JSON firmado',
  'Los 4 anexos: Ventas, Compras, Retenciones, Sujetos Excluidos',
  'Verificación con IA y puntaje de confianza por documento',
  'Directorio de clientes ilimitado, con historial separado',
  'Importación directa desde Google Drive y Gmail',
  'Exportación a Excel sin límite de documentos',
  'Soporte por correo',
]

/**
 * Revela en cascada los elementos `.reveal` de un contenedor al entrar en viewport.
 */
function useReveal() {
  const ref = useRef(null)
  useEffect(() => {
    const nodos = ref.current?.querySelectorAll('.reveal') ?? []
    const obs = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          if (!entry.isIntersecting) return
          const i = Number(entry.target.dataset.revealIndex || 0)
          entry.target.style.transitionDelay = `${(i % 6) * 60}ms`
          entry.target.classList.add('on')
          obs.unobserve(entry.target)
        })
      },
      { threshold: 0.12 }
    )
    nodos.forEach((el, i) => {
      el.dataset.revealIndex = i
      obs.observe(el)
    })
    return () => obs.disconnect()
  }, [])
  return ref
}

export default function LandingPage() {
  const ref = useReveal()

  return (
    <div ref={ref} className="min-h-screen bg-paper text-fg-3">
      {/* ═══ Nav ═══ */}
      <header className="sticky top-0 z-30 border-b border-hairline bg-paper/90 backdrop-blur-sm">
        <div className="max-w-[75rem] mx-auto px-6 py-4 flex items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2.5 shrink-0">
            <IconSeccion className="w-8 h-8 text-base" />
            <span className="font-semibold text-fg text-[15px]">Learnix</span>
            <span className="hidden sm:inline text-[10px] text-fg-4 uppercase tracking-[0.2em]">
              DTE Hub
            </span>
          </Link>
          <nav className="hidden md:flex items-center gap-8 text-[15px] text-fg-3">
            <a href="#producto" className="hover:text-accent transition-colors">Producto</a>
            <a href="#procedimiento" className="hover:text-accent transition-colors">Cómo funciona</a>
            <a href="#precio" className="hover:text-accent transition-colors">Precio</a>
            <Link to="/login" className="hover:text-accent transition-colors">Iniciar sesión</Link>
          </nav>
          <div className="flex items-center gap-3 shrink-0">
            <ThemeToggle className="text-fg-3" />
            <Link to="/login" className="btn-primary text-sm py-2 px-4">
              Ingresar
            </Link>
          </div>
        </div>
      </header>

      {/* ═══ Hero ═══ */}
      <section className="max-w-[75rem] mx-auto px-6 pt-16 pb-16 md:pt-24 md:pb-24">
        <div className="max-w-3xl">
          <p className="reveal text-[13px] uppercase tracking-[0.18em] text-accent font-semibold mb-4">
            Extracción automática de DTE · El Salvador
          </p>
          <h1
            className="reveal text-fg font-bold tracking-tight leading-[1.05]"
            style={{ fontSize: 'clamp(40px, 6vw, 72px)' }}
          >
            Tus DTE, por fin, en orden.
          </h1>
          <p className="reveal text-lg text-fg-3 leading-relaxed mt-6 max-w-2xl">
            Learnix lee el documento firmado por Hacienda campo por campo — PDF o JSON — y en
            segundos tenés tus anexos de IVA listos para declarar: ventas, compras, retenciones y
            sujetos excluidos, sin tipear un solo número.
          </p>
          <div className="reveal mt-8 flex flex-wrap items-center gap-3">
            <Link to="/login" className="btn-primary py-3 px-6 text-[15px]">
              Ingresar al sistema
            </Link>
            <a href="#producto" className="btn-ghost py-3 px-6 border border-hairline text-[15px]">
              Ver características
            </a>
          </div>

          <div className="reveal mt-12 grid grid-cols-3 gap-6 max-w-md">
            {[
              ['4', 'Anexos cubiertos'],
              ['0', 'Captura manual'],
              ['seg.', 'Por documento'],
            ].map(([valor, label]) => (
              <div key={label}>
                <p className="text-3xl font-bold text-fg leading-none">{valor}</p>
                <p className="text-xs text-fg-4 mt-1.5">{label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ Producto — índice de características ═══ */}
      <section id="producto" className="max-w-[75rem] mx-auto px-6 py-20 md:py-24 scroll-mt-16 border-t border-hairline">
        <div className="reveal max-w-2xl mb-12">
          <p className="text-[13px] uppercase tracking-[0.18em] text-accent font-semibold mb-2">
            Producto
          </p>
          <h2 className="text-3xl md:text-4xl text-fg">Lo que le falta a la hoja de cálculo</h2>
          <p className="text-fg-4 mt-3">
            No es una plantilla con fórmulas. Es un sistema que lee el documento oficial y hace
            el trabajo de captura por vos.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          {CARACTERISTICAS.map(({ titulo, detalle }) => (
            <div key={titulo} className="reveal tile p-6">
              <h3 className="text-lg font-semibold text-fg mb-2">{titulo}</h3>
              <p className="text-sm text-fg-3 leading-relaxed">{detalle}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ═══ Cifras destacadas ═══ */}
      <section className="border-t border-hairline bg-panel2/40">
        <div className="max-w-[75rem] mx-auto px-6 py-16 grid grid-cols-2 md:grid-cols-4 gap-10">
          {STATS.map(([valor, detalle]) => (
            <div key={detalle} className="reveal">
              <p className="text-4xl md:text-5xl font-bold text-fg leading-none mb-2">{valor}</p>
              <p className="text-sm text-fg-4 leading-relaxed max-w-[22ch]">{detalle}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ═══ Módulos ═══ */}
      <section id="modulos" className="max-w-[75rem] mx-auto px-6 py-20 md:py-24 scroll-mt-16">
        <div className="mb-12 reveal grid md:grid-cols-[auto_1fr] md:items-end gap-4">
          <div>
            <p className="text-[13px] uppercase tracking-[0.18em] text-accent font-semibold mb-2">
              Extractores
            </p>
            <h2 className="text-3xl md:text-4xl text-fg">Cuatro registros, un mismo libro</h2>
          </div>
          <p className="text-sm text-fg-4 max-w-xs md:justify-self-end md:text-right">
            Cada módulo aplica las reglas de Hacienda de su propio anexo, sin mezclarlas.
          </p>
        </div>

        <div className="reveal tile p-8 mb-4 flex flex-col md:flex-row md:items-center gap-8">
          <span className="inline-flex h-14 w-14 items-center justify-center rounded-xl bg-accent/10 shrink-0">
            <IconVentas className="w-7 h-7 text-accent" />
          </span>
          <div className="flex-1">
            <h3 className="text-2xl font-semibold text-fg mb-1.5">{MODULOS[0].titulo}</h3>
            <p className="text-fg-3 leading-relaxed max-w-lg">{MODULOS[0].detalle}</p>
          </div>
          <p className="text-xs uppercase tracking-wider text-fg-4 font-mono shrink-0 md:text-right">
            {MODULOS[0].ref}
          </p>
        </div>

        <div className="grid sm:grid-cols-3 gap-4">
          {MODULOS.slice(1).map(({ Icon, titulo, detalle, ref }) => (
            <div key={titulo} className="reveal tile p-6 flex flex-col">
              <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-panel2 mb-4">
                <Icon className="w-5 h-5 text-fg-3" />
              </span>
              <h3 className="text-base font-semibold text-fg mb-1">{titulo}</h3>
              <p className="text-sm text-fg-3 mb-4 flex-1">{detalle}</p>
              <p className="text-[11px] uppercase tracking-wider text-fg-4 font-mono">{ref}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ═══ Cómo funciona ═══ */}
      <section id="procedimiento" className="border-t border-hairline scroll-mt-16">
        <div className="max-w-[75rem] mx-auto px-6 py-20 md:py-24">
          <div className="reveal max-w-2xl mb-12">
            <p className="text-[13px] uppercase tracking-[0.18em] text-accent font-semibold mb-2">
              Procedimiento
            </p>
            <h2 className="text-3xl md:text-4xl text-fg">Tres pasos, sin captura manual</h2>
          </div>

          <div className="grid md:grid-cols-3 gap-8">
            {PASOS.map((p, i) => (
              <div key={p.titulo} className="reveal">
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-accent text-white text-sm font-semibold mb-4">
                  {i + 1}
                </span>
                <h3 className="text-lg font-semibold text-fg mb-2">{p.titulo}</h3>
                <p className="text-sm text-fg-3 leading-relaxed">{p.detalle}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ Precio ═══ */}
      <section id="precio" className="border-t border-hairline scroll-mt-16">
        <div className="max-w-[75rem] mx-auto px-6 py-20 md:py-24">
          <div className="reveal max-w-2xl mx-auto mb-12 text-center">
            <p className="text-[13px] uppercase tracking-[0.18em] text-accent font-semibold mb-2">
              Precio
            </p>
            <h2 className="text-3xl md:text-4xl text-fg">Un plan, sin letra chica</h2>
          </div>

          <div className="reveal max-w-xl mx-auto tile p-8 md:p-10">
            <div className="text-center mb-1">
              <span className="text-5xl md:text-6xl font-bold text-fg">$15</span>
              <span className="text-fg-4 ml-1">/ mes · USD</span>
            </div>
            <p className="text-center text-sm text-fg-4 mb-8">Suscripción Learnix — todo incluido</p>
            <ul className="space-y-3 mb-8">
              {PRECIO_ITEMS.map(item => (
                <li key={item} className="flex items-start gap-2.5 text-sm text-fg-3">
                  <IconCheck className="w-4 h-4 text-accent2 shrink-0 mt-0.5" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <a
              href={WHATSAPP_SOLICITAR_ACCESO}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-primary w-full py-3 text-center block"
            >
              Solicitar acceso
            </a>
            <Link to="/login" className="block mt-3 text-center text-sm text-fg-4 hover:text-accent transition-colors">
              Ya tenés cuenta — iniciar sesión
            </Link>
          </div>
        </div>
      </section>

      {/* ═══ CTA final ═══ */}
      <section className="bg-accent">
        <div className="max-w-[75rem] mx-auto px-6 py-20 md:py-28 text-center reveal">
          <h2 className="text-3xl md:text-5xl text-white font-bold mb-4 leading-tight max-w-2xl mx-auto">
            Dejá de tipear DTE a mano.
          </h2>
          <p className="text-white/80 mb-9 max-w-md mx-auto">
            Subí tus documentos, dejá que la IA los lea y exportá los anexos de Hacienda con
            tranquilidad.
          </p>
          <Link
            to="/login"
            className="inline-block py-3 px-7 bg-white text-accent font-semibold text-[16px] rounded-xl
                       transition-all duration-150 hover:-translate-y-px"
          >
            Ingresar al sistema
          </Link>
        </div>
      </section>

      {/* ═══ Footer ═══ */}
      <footer className="border-t border-hairline">
        <div className="max-w-[75rem] mx-auto px-6 py-6 flex flex-wrap items-center justify-between gap-3 text-sm text-fg-4">
          <div className="flex items-center gap-2">
            <IconSeccion className="w-6 h-6 text-sm" />
            <span className="font-semibold text-fg">Learnix</span>
          </div>
          <span>El Salvador · {new Date().getFullYear()} · Todos los derechos reservados</span>
          <Link to="/login" className="hover:text-accent transition-colors">Iniciar sesión</Link>
        </div>
      </footer>
    </div>
  )
}
