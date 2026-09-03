import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import ThemeToggle from '../components/ThemeToggle'
import {
  IconVentas, IconCompras, IconRetenciones, IconSujetos, IconSeccion, SelloCircular,
} from '../components/Icons'

/** Cinta de tasas vigentes — el equivalente al pie de cotizaciones de un diario. */
const TASAS = [
  ['IVA', '13%'],
  ['RET·IVA', '1%'],
  ['PERCEP·IVA', '1%'],
  ['RET·RENTA·SERV', '10%'],
  ['SUJ·EXCLUIDO', '10%'],
  ['MONEDA', 'USD'],
  ['DTE-01·03·05·06', 'VENTAS'],
  ['DTE-07', 'RETENCIÓN'],
  ['DTE-14', 'EXCLUIDOS'],
  ['ANEXOS', '1 · 2 · 3'],
]

/** Índice de características — el "por qué Learnix" frente a hacerlo a mano. */
const CARACTERISTICAS = [
  {
    num: 'i',
    titulo: 'Lectura nativa del DTE',
    detalle: <>Lee el <b>JSON firmado</b> por Hacienda campo por campo — o el PDF si no lo tenés — sin regex frágil ni plantillas que se rompen con el próximo formato.</>,
  },
  {
    num: 'ii',
    titulo: 'Verificación con IA',
    detalle: <>Vision y un segundo modelo revisan lo que el documento no dejó claro, con un <b>puntaje de confianza</b> por documento para saber qué mirar antes de declarar.</>,
  },
  {
    num: 'iii',
    titulo: 'Multi-cliente real',
    detalle: <>Directorio de clientes con cambio instantáneo — cada extracción queda <b>separada</b>, sin mezclar el trabajo de dos empresas en la misma tabla.</>,
  },
  {
    num: 'iv',
    titulo: 'Anexos listos para declarar',
    detalle: <>Exportá a Excel con los campos exactos del anexo — 1, 2 o 3 — en un clic, <b>sin reordenar columnas</b> a mano.</>,
  },
  {
    num: 'v',
    titulo: 'Importación desde Drive y Gmail',
    detalle: <>Traé los DTE directo desde tu Drive o tu correo, <b>sin descargar y volver a subir</b> cada archivo uno por uno.</>,
  },
  {
    num: 'vi',
    titulo: 'Seguridad de tus datos',
    detalle: <>Autenticación con Supabase, <b>aislamiento por usuario</b> a nivel de base de datos y auditoría de acceso en cada sesión.</>,
  },
]

const STATS = [
  ['4', 'Anexos de Hacienda cubiertos: Ventas, Compras, Retenciones y Sujetos Excluidos.', true],
  ['2', 'Motores de IA verificando cada documento — lectura Vision y verificación textual.', false],
  ['100%', 'Campos leídos del documento firmado por Hacienda, no de una plantilla genérica.', false],
  ['0', 'Captura manual. Todo desde el navegador, sin instalar nada.', true],
]

const MODULOS = [
  {
    num: '01',
    Icon: IconVentas,
    titulo: 'Ventas',
    detalle: 'CCF, notas de crédito/débito y facturas de consumidor final, leídas directo del DTE firmado.',
    ref: 'DTE-01 · 03 · 05 · 06 — Anexos 1 y 2',
  },
  {
    num: '02',
    Icon: IconCompras,
    titulo: 'Compras',
    detalle: 'CCF recibidos de proveedores, con crédito fiscal calculado automáticamente.',
    ref: 'Anexo 3',
  },
  {
    num: '03',
    Icon: IconRetenciones,
    titulo: 'Retenciones',
    detalle: 'Comprobantes de retención listos para la casilla exacta del formulario.',
    ref: 'DTE-07 — Casilla 162',
  },
  {
    num: '04',
    Icon: IconSujetos,
    titulo: 'Sujetos Excluidos',
    detalle: 'Compras a sujetos excluidos de IVA, clasificadas sin revisión manual.',
    ref: 'DTE-14 — Casilla 66',
  },
]

const PASOS = [
  {
    num: 'I',
    titulo: 'Sube tus documentos',
    detalle: 'PDF o JSON firmado por Hacienda, uno o varios a la vez.',
  },
  {
    num: 'II',
    titulo: 'La IA extrae y verifica',
    detalle: 'Lectura nativa del DTE más verificación con IA y un puntaje de confianza por documento, así sabés qué revisar antes de declarar.',
  },
  {
    num: 'III',
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
    <div ref={ref} className="landing-page min-h-screen bg-paper text-fg-3 paper-grain">
      {/* ═══ Masthead ═══ */}
      <div className="border-b border-hairline bg-panel">
        <div className="max-w-[87.5rem] mx-auto px-8 py-2 flex items-center justify-between text-[11px]
                        uppercase tracking-[0.16em] text-fg-4 font-mono">
          <span className="shrink-0">№ 001 · Edición del sistema</span>
          <span className="hidden sm:block shrink-0">Publicado en El Salvador</span>
          <span className="shrink-0">DTE · IVA 13% · USD</span>
        </div>
      </div>

      {/* ═══ Nav ═══ */}
      <header className="sticky top-0 z-30 border-b border-hairline bg-paper/95 backdrop-blur-sm">
        <div className="max-w-[87.5rem] mx-auto px-8 py-4 flex items-center justify-between gap-4">
          <div className="flex items-baseline gap-2 shrink-0">
            <IconSeccion className="text-[30px] text-accent" />
            <span className="font-display italic font-black text-[30px] text-fg leading-none">Learnix</span>
            <span className="hidden sm:inline text-[10px] text-fg-4 uppercase tracking-[0.2em] leading-none">
              DTE Hub
            </span>
          </div>
          <nav className="hidden md:flex items-center gap-8 text-[15px] text-fg-3">
            <a href="#producto" className="hover:text-accent transition-colors">Producto</a>
            <a href="#procedimiento" className="hover:text-accent transition-colors">Cómo funciona</a>
            <a href="#precio" className="hover:text-accent transition-colors">Precio</a>
            <Link to="/login" className="hover:text-accent transition-colors">Iniciar sesión</Link>
          </nav>
          <div className="flex items-center gap-3 shrink-0">
            <ThemeToggle className="text-fg-3" />
            <Link to="/login" className="btn-primary text-[15px] py-2 px-4">
              Ingresar
            </Link>
          </div>
        </div>
      </header>

      {/* ═══ Hero ═══ */}
      <section className="relative max-w-[87.5rem] mx-auto px-8 pt-16 pb-16 md:pt-24 md:pb-24">
        <div
          className="hidden md:block absolute text-accent/45"
          style={{ top: '60px', right: '40px', width: '180px', height: '180px', transform: 'rotate(-8deg)' }}
        >
          <SelloCircular />
        </div>

        <div className="grid md:grid-cols-[1.4fr_1fr] gap-10 md:gap-[60px] items-start">
          {/* Titular */}
          <h1 className="animate-rise text-fg tracking-[-0.045em] leading-[0.92]"
              style={{ fontSize: 'clamp(56px, 9vw, 140px)', fontWeight: 300 }}>
            Tus DTE,
            <span className="block font-display italic font-black text-accent2">
              por fin,
            </span>
            <span className="marker">en orden.</span>
          </h1>

          {/* Manifiesto */}
          <div className="animate-fade md:border-l md:border-hairline md:pl-10 md:pr-[220px]">
            <p className="text-[11px] uppercase tracking-[0.2em] text-fg-4 font-semibold mb-4">
              Manifiesto
            </p>
            <p className="text-[22px] text-fg-3 leading-relaxed font-display">
              Un extractor de DTE pensado desde{' '}
              <strong className="text-accent2 font-semibold">El Salvador</strong>: lee el
              documento firmado por Hacienda campo por campo, no adivina con una plantilla
              genérica. Subís el PDF o el JSON y en segundos tenés{' '}
              <strong className="text-accent2 font-semibold">tus anexos de IVA listos</strong>{' '}
              para declarar — ventas, compras, retenciones y sujetos excluidos, sin tipear un
              solo número.
            </p>

            <div className="mt-6 grid grid-cols-3 gap-4 max-w-sm">
              {[
                ['4', 'Anexos cubiertos'],
                ['0', 'Captura manual'],
                ['seg.', 'Por documento'],
              ].map(([valor, label]) => (
                <div key={label}>
                  <p className="font-display text-[28px] text-fg leading-none">{valor}</p>
                  <p className="text-[11px] uppercase tracking-[0.1em] text-fg-4 mt-1 leading-tight">
                    {label}
                  </p>
                </div>
              ))}
            </div>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link to="/login" className="btn-primary py-2.5 px-6 text-[16px]">
                Ingresar al sistema →
              </Link>
              <a href="#producto" className="btn-ghost py-2.5 px-6 border border-hairline text-[16px]">
                Ver características
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ Cinta de tasas ═══ */}
      <section className="ticker-bar overflow-hidden">
        <div className="ticker-track py-3">
          {[...TASAS, ...TASAS].map(([label, valor], i) => (
            <span
              key={i}
              className="flex items-baseline gap-2.5 shrink-0 px-7 text-[12px] font-mono
                         uppercase tracking-[0.12em]"
            >
              <span className="ticker-label">{label}</span>
              <span className="ticker-value">{valor}</span>
            </span>
          ))}
        </div>
      </section>

      {/* ═══ Producto — índice de características ═══ */}
      <section id="producto" className="max-w-[87.5rem] mx-auto px-8 py-20 md:py-24 scroll-mt-16">
        <div className="reveal grid md:grid-cols-[220px_1fr] gap-6 md:gap-[60px] items-end pb-10 border-b border-hairline">
          <span className="font-display italic text-[42px] md:text-[56px] text-accent leading-none">§ 01</span>
          <div>
            <p className="text-[13px] uppercase tracking-[0.16em] text-accent font-semibold mb-2">
              Índice de características
            </p>
            <h2 className="text-[30px] md:text-[44px] leading-[1.05] text-fg">
              Lo que le falta<br className="hidden md:block" />{' '}
              <span className="font-display italic text-accent2">a la hoja de cálculo.</span>
            </h2>
            <p className="text-[16px] text-fg-4 mt-3 max-w-xl">
              No es una plantilla con fórmulas. Es un sistema que lee el documento oficial y
              hace el trabajo de captura por vos.
            </p>
          </div>
        </div>

        <div className="grid md:grid-cols-3 border border-hairline divide-x-0 md:divide-x divide-y divide-hairline">
          {CARACTERISTICAS.map(({ num, titulo, detalle }) => (
            <div
              key={num}
              className="reveal p-7 hover:bg-panel2/40 transition-colors duration-150 border-t border-hairline md:border-t-0 first:border-t-0"
            >
              <div className="flex items-center justify-center w-10 h-10 rounded-full border border-hairline
                              font-display italic text-[16px] text-accent mb-5">
                {num}
              </div>
              <h3 className="font-display text-[24px] text-fg mb-2 leading-tight">{titulo}</h3>
              <p className="text-[15px] text-fg-3 leading-relaxed">{detalle}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ═══ Cifras destacadas ═══ */}
      <section className="forest-block">
        <div className="max-w-[87.5rem] mx-auto px-8 py-20 grid grid-cols-2 md:grid-cols-4 gap-10">
          {STATS.map(([valor, detalle, enfasis]) => (
            <div key={detalle} className="reveal pt-4 border-t border-sb-hair">
              <p className={`font-display text-[64px] md:text-[72px] leading-none mb-3 ${enfasis ? 'italic font-black text-accent' : 'text-sb-txt-hi'}`}>
                {valor}
              </p>
              <p className="text-[15px] leading-relaxed text-sb-txt max-w-[22ch]">{detalle}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ═══ Módulos ═══ */}
      <section id="modulos" className="max-w-[87.5rem] mx-auto px-8 py-20 md:py-24 scroll-mt-16">
        <div className="mb-10 reveal grid md:grid-cols-[auto_1fr] md:items-end gap-4">
          <div>
            <p className="text-[13px] uppercase tracking-[0.16em] text-accent font-semibold mb-2">
              Índice · Extractores
            </p>
            <h2 className="text-[30px] md:text-[44px] leading-[1.05] text-fg">
              Cuatro registros,<br className="hidden md:block" /> un mismo libro
            </h2>
          </div>
          <p className="text-[15px] text-fg-4 max-w-xs md:justify-self-end md:text-right">
            Cada módulo aplica las reglas de Hacienda de su propio anexo, sin mezclarlas.
          </p>
        </div>

        <div
          className="reveal grid md:grid-cols-[1.4fr_1fr] gap-px bg-hairline border border-hairline
                     rounded-xl overflow-hidden"
        >
          {/* Ficha destacada */}
          <div
            className="bg-panel p-8 flex flex-col justify-between gap-8
                       border-l-2 border-accent md:row-span-3"
          >
            <div>
              <div className="flex items-start justify-between mb-7">
                <IconVentas className="w-12 h-12 text-accent" />
                <span className="font-mono text-[12px] text-fg-4">№ {MODULOS[0].num}</span>
              </div>
              <h3 className="text-[40px] text-fg mb-3 leading-none">{MODULOS[0].titulo}</h3>
              <p className="text-[17px] text-fg-3 max-w-sm leading-relaxed">{MODULOS[0].detalle}</p>
            </div>

            <div>
              <div className="rule-hair !mt-0" />
              <p className="text-[12px] uppercase tracking-wider text-fg-4 font-mono">
                {MODULOS[0].ref}
              </p>
            </div>
          </div>

          {/* Fichas secundarias */}
          {MODULOS.slice(1).map(({ num, Icon, titulo, detalle, ref }) => (
            <div
              key={num}
              className="bg-panel p-6 flex flex-col justify-center"
            >
              <div className="flex items-start justify-between mb-4">
                <Icon className="w-6 h-6 text-fg-3" />
                <span className="font-mono text-[12px] text-fg-4">№ {num}</span>
              </div>
              <h3 className="text-[22px] text-fg mb-1.5">{titulo}</h3>
              <p className="text-[15px] text-fg-3 mb-3">{detalle}</p>
              <div className="rule-hair" />
              <p className="text-[12px] uppercase tracking-wider text-fg-4 font-mono mt-3">
                {ref}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ═══ Cómo funciona ═══ */}
      <section id="procedimiento" className="border-t border-hairline scroll-mt-16">
        <div className="max-w-[87.5rem] mx-auto px-8 py-20 md:py-24">
          <div className="mb-14 reveal grid md:grid-cols-[220px_1fr] gap-6 md:gap-[60px] items-end">
            <span className="font-display italic text-[42px] md:text-[56px] text-accent leading-none">§ 02</span>
            <div>
              <p className="text-[13px] uppercase tracking-[0.16em] text-accent font-semibold mb-2">
                Procedimiento
              </p>
              <h2 className="text-[30px] md:text-[44px] text-fg">Tres pasos, sin captura manual</h2>
            </div>
          </div>

          <div className="grid md:grid-cols-3 md:divide-x divide-hairline">
            {PASOS.map((p) => (
              <div key={p.num} className="reveal px-0 md:px-8 first:pl-0 py-2">
                <span className="font-display italic text-[36px] text-accent block mb-3 leading-none">
                  {p.num}
                </span>
                <h3 className="font-display italic text-[28px] text-fg mb-2">{p.titulo}</h3>
                <p className="text-[15px] text-fg-3 leading-relaxed">{p.detalle}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ Precio ═══ */}
      <section id="precio" className="border-t border-hairline scroll-mt-16">
        <div className="max-w-[87.5rem] mx-auto px-8 py-20 md:py-24">
          <div className="mb-14 reveal grid md:grid-cols-[220px_1fr] gap-6 md:gap-[60px] items-end">
            <span className="font-display italic text-[42px] md:text-[56px] text-accent leading-none">§ 03</span>
            <div>
              <p className="text-[13px] uppercase tracking-[0.16em] text-accent font-semibold mb-2">
                Precio
              </p>
              <h2 className="text-[30px] md:text-[44px] text-fg">Un plan, sin letra chica</h2>
            </div>
          </div>

          <div className="reveal relative max-w-[1000px] border border-hairline bg-panel2/40 p-8 md:p-10">
            <span className="price-badge border border-hairline text-[11px] uppercase tracking-[0.18em] text-accent font-semibold">
              Plan único
            </span>
            <div className="grid md:grid-cols-[1.2fr_1fr] gap-10 md:gap-[60px]">
              <div>
                <h3 className="font-display text-[26px] text-fg mb-5">Suscripción Learnix</h3>
                <ul className="space-y-0">
                  {PRECIO_ITEMS.map(item => (
                    <li
                      key={item}
                      className="flex items-start gap-2.5 py-2.5 border-b border-dashed border-hairline text-[15px] text-fg-3"
                    >
                      <IconSeccion className="text-accent text-[17px] shrink-0 leading-none mt-0.5" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="md:text-right flex flex-col md:items-end justify-center">
                <p className="font-display text-[64px] md:text-[96px] text-accent2 leading-none">
                  $<strong className="font-black italic">15</strong>
                </p>
                <p className="text-[13px] text-fg-4 mt-2 mb-6">por mes · USD</p>
                <a
                  href={WHATSAPP_SOLICITAR_ACCESO}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-primary py-2.5 px-6 w-full md:w-auto text-center text-[16px]"
                >
                  Solicitar acceso →
                </a>
                <Link to="/login" className="block mt-3 text-[13px] text-fg-4 hover:text-accent transition-colors">
                  Ya tenés cuenta — iniciar sesión
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══ CTA final ═══ */}
      <section className="forest-block">
        <div className="max-w-[87.5rem] mx-auto px-8 py-24 md:py-32 text-center reveal">
          <div className="w-24 h-24 mx-auto mb-6 text-sb-txt-mute">
            <SelloCircular />
          </div>
          <h2 className="font-display text-[34px] md:text-[54px] text-sb-txt-hi mb-4 leading-tight max-w-2xl mx-auto">
            Deja de tipear DTE <span className="italic text-accent">a mano.</span>
          </h2>
          <p className="text-[16px] md:text-[18px] text-sb-txt mb-9 max-w-md mx-auto">
            Subí tus documentos, dejá que la IA los lea y exportá los anexos de Hacienda con
            tranquilidad.
          </p>
          <Link
            to="/login"
            className="inline-block py-2.5 px-7 bg-paper text-fg font-medium text-[16px] rounded-lg
                       transition-all duration-150 hover:-translate-y-px hover:bg-accent hover:text-sb-txt-hi"
          >
            Ingresar al sistema →
          </Link>
        </div>
      </section>

      {/* ═══ Footer ═══ */}
      <footer className="forest-block-deep">
        <div className="max-w-[87.5rem] mx-auto px-8 py-6 flex flex-wrap items-center justify-between gap-2 text-[13px]">
          <span className="font-display italic text-[18px]">§ Learnix</span>
          <span className="uppercase tracking-[0.12em] opacity-80">
            El Salvador · {new Date().getFullYear()} · Todos los derechos reservados
          </span>
          <Link to="/login" className="hover:opacity-70 transition-opacity">Iniciar sesión</Link>
        </div>
      </footer>
    </div>
  )
}
