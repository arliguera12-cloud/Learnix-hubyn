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
    detalle: 'CCF recibidos de proveedores.',
    ref: 'Anexo 3',
  },
  {
    num: '03',
    Icon: IconRetenciones,
    titulo: 'Retenciones',
    detalle: 'Comprobantes de retención.',
    ref: 'DTE-07 — Casilla 162',
  },
  {
    num: '04',
    Icon: IconSujetos,
    titulo: 'Sujetos Excluidos',
    detalle: 'Compras a sujetos excluidos de IVA.',
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
    detalle: 'Lectura nativa del DTE más verificación con IA y un puntaje de confianza por documento.',
  },
  {
    num: 'III',
    titulo: 'Exporta tus anexos',
    detalle: 'Anexos y formularios listos para tu declaración, sin captura manual.',
  },
]

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-paper text-fg-3 paper-grain">
      {/* ═══ Masthead ═══ */}
      <div className="border-b border-hairline bg-panel">
        <div className="max-w-6xl mx-auto px-5 py-2 flex items-center justify-between text-[0.65rem]
                        uppercase tracking-[0.16em] text-fg-4 font-mono">
          <span className="shrink-0">№ 001 · Edición del sistema</span>
          <span className="hidden sm:block shrink-0">Publicado en El Salvador</span>
          <span className="shrink-0">DTE · IVA 13% · USD</span>
        </div>
      </div>

      {/* ═══ Nav ═══ */}
      <header className="sticky top-0 z-30 border-b border-hairline bg-paper/95 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-5 py-3.5 flex items-center justify-between gap-4">
          <div className="flex items-baseline gap-2 shrink-0">
            <IconSeccion className="text-2xl text-accent" />
            <span className="font-display text-xl text-fg leading-none">Learnix</span>
            <span className="hidden sm:inline text-[9px] text-fg-4 uppercase tracking-[0.2em] leading-none">
              DTE Hub
            </span>
          </div>
          <nav className="hidden md:flex items-center gap-7 text-sm text-fg-3">
            <a href="#modulos" className="hover:text-accent transition-colors">Módulos</a>
            <a href="#procedimiento" className="hover:text-accent transition-colors">Cómo funciona</a>
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
      <section className="max-w-6xl mx-auto px-5 pt-16 pb-16 md:pt-24 md:pb-24">
        <div className="grid md:grid-cols-[1.15fr_1fr] gap-12 md:gap-16 items-center">
          {/* Titular */}
          <h1 className="animate-rise text-[3rem] leading-[0.98] sm:text-[4.25rem] sm:leading-[0.94]
                         md:text-[5.5rem] md:leading-[0.92] text-fg tracking-[-0.02em]">
            Tus DTE,
            <span className="block font-display italic font-medium text-accent2">
              por fin,
            </span>
            <span className="marker">en orden.</span>
          </h1>

          {/* Manifiesto */}
          <div className="animate-fade md:border-l md:border-hairline md:pl-10 relative">
            <div className="hidden md:block absolute -top-24 -right-4 w-44 h-44 text-accent/45">
              <SelloCircular />
            </div>

            <p className="text-[0.65rem] uppercase tracking-[0.2em] text-fg-4 font-semibold mb-4 md:mt-24">
              Manifiesto
            </p>
            <p className="text-lg md:text-xl text-fg-3 leading-relaxed font-display">
              Un extractor de DTE pensado desde{' '}
              <strong className="text-accent2 font-semibold">El Salvador</strong> — lee el
              documento firmado por Hacienda, no una plantilla genérica. Ventas, compras,
              retenciones y sujetos excluidos, con{' '}
              <strong className="text-accent2 font-semibold">anexos listos</strong> para
              declarar. Nada de captura manual.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link to="/login" className="btn-primary py-2.5 px-6">
                Ingresar al sistema →
              </Link>
              <a href="#modulos" className="btn-ghost py-2.5 px-6 border border-hairline">
                Ver módulos
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
              className="flex items-baseline gap-2.5 shrink-0 px-7 text-[0.7rem] font-mono
                         uppercase tracking-[0.12em]"
            >
              <span className="ticker-label">{label}</span>
              <span className="ticker-value">{valor}</span>
            </span>
          ))}
        </div>
      </section>

      {/* ═══ Módulos ═══ */}
      <section id="modulos" className="max-w-6xl mx-auto px-5 py-20 md:py-24 scroll-mt-16">
        <div className="mb-10 animate-fade grid md:grid-cols-[auto_1fr] md:items-end gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.16em] text-accent font-semibold mb-2">
              Índice · Extractores
            </p>
            <h2 className="text-3xl md:text-[2.75rem] leading-[1.05] text-fg">
              Cuatro registros,<br className="hidden md:block" /> un mismo libro
            </h2>
          </div>
          <p className="text-sm text-fg-4 max-w-xs md:justify-self-end md:text-right">
            Cada módulo aplica las reglas de Hacienda de su propio anexo, sin mezclarlas.
          </p>
        </div>

        <div
          className="grid md:grid-cols-[1.4fr_1fr] gap-px bg-hairline border border-hairline
                     rounded-xl overflow-hidden"
        >
          {/* Ficha destacada */}
          <div
            className="bg-panel p-8 animate-fade flex flex-col justify-between gap-8
                       border-l-2 border-accent md:row-span-3"
          >
            <div>
              <div className="flex items-start justify-between mb-7">
                <IconVentas className="w-12 h-12 text-accent" />
                <span className="font-mono text-xs text-fg-4">№ {MODULOS[0].num}</span>
              </div>
              <h3 className="text-4xl text-fg mb-3 leading-none">{MODULOS[0].titulo}</h3>
              <p className="text-base text-fg-3 max-w-sm leading-relaxed">{MODULOS[0].detalle}</p>
            </div>

            <div>
              <div className="rule-hair !mt-0" />
              <p className="text-[0.7rem] uppercase tracking-wider text-fg-4 font-mono">
                {MODULOS[0].ref}
              </p>
            </div>
          </div>

          {/* Fichas secundarias */}
          {MODULOS.slice(1).map(({ num, Icon, titulo, detalle, ref }, i) => (
            <div
              key={num}
              className="bg-panel p-6 animate-fade flex flex-col justify-center"
              style={{ animationDelay: `${(i + 1) * 90}ms` }}
            >
              <div className="flex items-start justify-between mb-4">
                <Icon className="w-6 h-6 text-fg-3" />
                <span className="font-mono text-xs text-fg-4">№ {num}</span>
              </div>
              <h3 className="text-xl text-fg mb-1.5">{titulo}</h3>
              <p className="text-sm text-fg-3 mb-3">{detalle}</p>
              <div className="rule-hair" />
              <p className="text-[0.7rem] uppercase tracking-wider text-fg-4 font-mono mt-3">
                {ref}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ═══ Cómo funciona ═══ */}
      <section id="procedimiento" className="border-t border-hairline scroll-mt-16">
        <div className="max-w-6xl mx-auto px-5 py-20 md:py-24">
          <div className="mb-14 animate-fade">
            <p className="text-xs uppercase tracking-[0.16em] text-accent font-semibold mb-2">
              Procedimiento
            </p>
            <h2 className="text-3xl md:text-[2.75rem] text-fg">Tres pasos, sin captura manual</h2>
          </div>

          <div className="grid md:grid-cols-3 gap-10 md:gap-6 relative">
            <div className="hidden md:block absolute top-[1.4rem] left-0 right-0 h-px bg-hairline" />
            {PASOS.map((p, i) => (
              <div
                key={p.num}
                className="animate-fade relative"
                style={{ animationDelay: `${i * 120}ms` }}
              >
                <span className="font-display italic text-5xl text-accent block mb-2 bg-paper pr-5 w-fit leading-none">
                  {p.num}
                </span>
                <h3 className="text-lg text-fg mt-4 mb-1.5">{p.titulo}</h3>
                <p className="text-sm text-fg-3 leading-relaxed max-w-xs">{p.detalle}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══ CTA final ═══ */}
      <section className="border-t border-hairline bg-panel2/50">
        <div className="max-w-6xl mx-auto px-5 py-20 text-center animate-fade">
          <div className="w-24 h-24 mx-auto mb-6 text-accent">
            <SelloCircular />
          </div>
          <h2 className="text-3xl md:text-4xl text-fg mb-2">Abre tu registro</h2>
          <p className="text-sm text-fg-3 mb-8 max-w-md mx-auto">
            Ingresa con tu cuenta para empezar a extraer y declarar tus DTE.
          </p>
          <Link to="/login" className="btn-primary py-2.5 px-7 inline-block">
            Ingresar al sistema →
          </Link>
        </div>
      </section>

      {/* ═══ Footer ═══ */}
      <footer className="border-t border-hairline">
        <div className="max-w-6xl mx-auto px-5 py-6 flex flex-wrap items-center justify-between gap-2
                        text-xs text-fg-4">
          <span>Learnix DTE Hub · El Salvador · {new Date().getFullYear()}</span>
          <span className="font-mono uppercase tracking-[0.12em]">Sistema de extracción de DTE</span>
        </div>
      </footer>
    </div>
  )
}
