/**
 * Set de iconos propios — trazo técnico, geometría de plantilla de dibujo.
 *
 * Sustituyen a los emoji que se usaban antes (📤 📥 ✂️ 📋 …): los emoji se
 * renderizan distinto en cada sistema operativo, no heredan el color del
 * tema y rompen el registro editorial del resto de la interfaz.
 *
 * Convención: viewBox 24×24, trazo de 1.5 sobre `currentColor`, sin relleno.
 * El tamaño se controla con clases (`className="w-5 h-5"`), no con props.
 */

function Svg({ children, className = 'w-5 h-5', ...rest }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="square"
      strokeLinejoin="miter"
      className={className}
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  )
}

/** Hoja de documento — base compartida por los iconos de DTE. */
function Hoja() {
  return <path d="M6 2.75h7.5L18 7.25v14H6z" />
}

/** Ventas — documento que sale (flecha ascendente). */
export function IconVentas(props) {
  return (
    <Svg {...props}>
      <Hoja />
      <path d="M13.5 2.75v4.5H18" />
      <path d="M12 17.5v-6M9.5 14l2.5-2.5 2.5 2.5" />
    </Svg>
  )
}

/** Compras — documento que entra (flecha descendente). */
export function IconCompras(props) {
  return (
    <Svg {...props}>
      <Hoja />
      <path d="M13.5 2.75v4.5H18" />
      <path d="M12 11.5v6M9.5 15l2.5 2.5 2.5-2.5" />
    </Svg>
  )
}

/** Retenciones — documento con una porción retenida (banda sólida). */
export function IconRetenciones(props) {
  return (
    <Svg {...props}>
      <Hoja />
      <path d="M13.5 2.75v4.5H18" />
      <path d="M8.5 12.5h7" />
      <rect x="8.5" y="15" width="4" height="3.5" fill="currentColor" stroke="none" />
      <path d="M13.5 16.75h2" />
    </Svg>
  )
}

/** Sujetos excluidos — documento con figura de persona. */
export function IconSujetos(props) {
  return (
    <Svg {...props}>
      <Hoja />
      <path d="M13.5 2.75v4.5H18" />
      <circle cx="12" cy="13" r="1.75" />
      <path d="M8.75 18.5c0-1.8 1.45-3 3.25-3s3.25 1.2 3.25 3" />
    </Svg>
  )
}

/** Clientes — dos figuras (receptores). */
export function IconClientes(props) {
  return (
    <Svg {...props}>
      <circle cx="9" cy="8" r="2.75" />
      <path d="M3.5 19.25c0-3 2.45-5.25 5.5-5.25s5.5 2.25 5.5 5.25" />
      <path d="M16 5.5a2.75 2.75 0 010 5" />
      <path d="M17.25 14.5c1.9.6 3.25 2.4 3.25 4.75" />
    </Svg>
  )
}

/** Proveedores — edificio (emisores). */
export function IconProveedores(props) {
  return (
    <Svg {...props}>
      <path d="M3.75 21.25V6.5l7-3.25V21.25" />
      <path d="M10.75 10.5h9.5v10.75" />
      <path d="M2.5 21.25h19" />
      <path d="M14 14.25h3.25M14 17.75h3.25M6 9.75h1.5M6 13.25h1.5M6 16.75h1.5" />
    </Svg>
  )
}

/** Dashboard — libro mayor (renglones de registro). */
export function IconLibro(props) {
  return (
    <Svg {...props}>
      <path d="M3.75 4.25h16.5v15.5H3.75z" />
      <path d="M3.75 8.5h16.5" />
      <path d="M9 8.5v11.25" />
      <path d="M12 12h5.5M12 15.5h5.5" />
    </Svg>
  )
}

/** Exportar / descargar — bandeja con flecha. */
export function IconExportar(props) {
  return (
    <Svg {...props}>
      <path d="M12 3.5v10.5M8.5 10.5l3.5 3.5 3.5-3.5" />
      <path d="M4.25 15.5v5h15.5v-5" />
    </Svg>
  )
}

/** Subir — bandeja con flecha ascendente. */
export function IconSubir(props) {
  return (
    <Svg {...props}>
      <path d="M12 16.5V6M8.5 9.5L12 6l3.5 3.5" />
      <path d="M4.25 15.5v5h15.5v-5" />
    </Svg>
  )
}

/** Nube — importación desde Google Drive. */
export function IconNube(props) {
  return (
    <Svg {...props}>
      <path d="M7.5 17.5a4 4 0 01-.5-7.97 5 5 0 019.62-1.68A3.75 3.75 0 0116.25 17.5H7.5z" />
      <path d="M12 10.5v6M9.5 14l2.5-2.5 2.5 2.5" />
    </Svg>
  )
}

/** Correo — importación desde Gmail. */
export function IconCorreo(props) {
  return (
    <Svg {...props}>
      <path d="M3.75 5.75h16.5v12.5H3.75z" />
      <path d="M3.75 6.5L12 13l8.25-6.5" />
    </Svg>
  )
}

/** Cerrar / quitar — equis. */
export function IconCerrar(props) {
  return (
    <Svg {...props}>
      <path d="M6 6l12 12M18 6L6 18" />
    </Svg>
  )
}

/** Documento — archivo genérico (PDF/JSON) en una lista. */
export function IconArchivo(props) {
  return (
    <Svg {...props}>
      <path d="M6 2.75h7.5L18 7.25v14H6z" />
      <path d="M13.5 2.75v4.5H18" />
    </Svg>
  )
}

/** Buscar — lupa. */
export function IconBuscar(props) {
  return (
    <Svg {...props}>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="M20 20l-4.5-4.5" />
    </Svg>
  )
}

/** Ojo — mostrar contraseña. */
export function IconOjo(props) {
  return (
    <Svg {...props}>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
      <circle cx="12" cy="12" r="3" />
    </Svg>
  )
}

/** Ojo tachado — ocultar contraseña. */
export function IconOjoTachado(props) {
  return (
    <Svg {...props}>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
      <circle cx="12" cy="12" r="3" />
      <path d="M3.5 3.5l17 17" />
    </Svg>
  )
}

/** Cerrar sesión — salida. */
export function IconSalir(props) {
  return (
    <Svg {...props}>
      <path d="M14.5 3.75H4.75v16.5h9.75" />
      <path d="M10 12h10.5M17 8.5l3.5 3.5-3.5 3.5" />
    </Svg>
  )
}

/** Modo claro. */
export function IconSol(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.2 5.2l1.8 1.8M17 17l1.8 1.8M18.8 5.2L17 7M7 17l-1.8 1.8" />
    </Svg>
  )
}

/** Modo oscuro. */
export function IconLuna(props) {
  return (
    <Svg {...props}>
      <path d="M20 14.5A8.5 8.5 0 019.5 4a8.5 8.5 0 1010.5 10.5z" />
    </Svg>
  )
}

/** Verificado / conforme. */
export function IconCheck(props) {
  return (
    <Svg {...props}>
      <path d="M4.5 12.5l5 5 10-11" />
    </Svg>
  )
}

/** Observación / alerta. */
export function IconAlerta(props) {
  return (
    <Svg {...props}>
      <path d="M12 3.5l9.25 16.75H2.75z" />
      <path d="M12 9.5v5" />
      <path d="M12 17.25h.01" strokeWidth="2" />
    </Svg>
  )
}

/**
 * Sello circular de registro — texto sobre trayectoria, gira lentamente.
 * Toma el color de `currentColor`, así que el contenedor decide el tono.
 */
export function SelloCircular({ className = 'w-full h-full' }) {
  return (
    <svg viewBox="0 0 200 200" className={className} aria-hidden="true">
      <defs>
        <path id="circulo-sello" d="M 100,100 m -78,0 a 78,78 0 1,1 156,0 a 78,78 0 1,1 -156,0" />
      </defs>
      <circle cx="100" cy="100" r="94" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.55" />
      <circle cx="100" cy="100" r="88" fill="none" stroke="currentColor" strokeWidth="0.75" opacity="0.4" />
      <circle cx="100" cy="100" r="60" fill="none" stroke="currentColor" strokeWidth="0.75" opacity="0.4" />
      <g className="seal-spin">
        <text fill="currentColor" fontSize="11.5" letterSpacing="3.5" fontFamily="var(--font-ui)">
          <textPath href="#circulo-sello" startOffset="0%">
            · LEARNIX DTE HUB · REGISTRO DIGITAL · EL SALVADOR
          </textPath>
        </text>
      </g>
      <text
        x="100" y="94" textAnchor="middle"
        fontFamily="var(--font-display)" fontStyle="italic" fontWeight="500"
        fontSize="34" fill="currentColor"
      >
        L
      </text>
      <text
        x="100" y="118" textAnchor="middle"
        fontFamily="var(--font-mono)" fontSize="9" letterSpacing="2" fill="currentColor" opacity="0.75"
      >
        № 001
      </text>
    </svg>
  )
}

/** Marca de sección — el calderón editorial usado como logotipo. */
export function IconSeccion({ className = 'w-5 h-5' }) {
  return (
    <span
      className={`inline-flex items-center justify-center font-display italic leading-none ${className}`}
      aria-hidden="true"
    >
      §
    </span>
  )
}
