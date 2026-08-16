/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Superficies — reapuntadas a los tokens de tema (ver `slate` abajo).
        surface: {
          50:  'rgb(var(--panel-rgb) / <alpha-value>)',
          100: 'rgb(var(--panel-rgb) / <alpha-value>)',
          200: 'rgb(var(--panel2-rgb) / <alpha-value>)',
          300: 'rgb(var(--border-rgb) / <alpha-value>)',
          400: 'rgb(var(--ink5-rgb) / <alpha-value>)',
          500: 'rgb(var(--border-rgb) / <alpha-value>)',
          600: 'rgb(var(--border-rgb) / <alpha-value>)',
          700: 'rgb(var(--panel2-rgb) / <alpha-value>)',
          800: 'rgb(var(--panel-rgb) / <alpha-value>)',
          900: 'rgb(var(--bg-rgb) / <alpha-value>)',
        },
        // Primario — el bermellón de imprenta. Antes era un celeste que no
        // pertenecía a la paleta editorial; se usa en pestañas activas,
        // barras de progreso y foco de inputs.
        brand: {
          50:  'rgb(var(--gold-rgb) / <alpha-value>)',
          100: 'rgb(var(--gold-rgb) / <alpha-value>)',
          400: 'rgb(var(--gold-rgb) / <alpha-value>)',
          500: 'rgb(var(--gold-rgb) / <alpha-value>)',
          600: 'rgb(var(--gold-rgb) / <alpha-value>)',
        },
        // Acento editorial — dorado
        gold: {
          DEFAULT: '#d4b45c',
          tint: '#2a2110',
        },
        // Tokens explícitos --ink/--cream (modo oscuro) para componentes
        // que replican el patrón exacto de Certia (btn-primary, form-label, etc.)
        ink: {
          DEFAULT: '#f2ede1',
          3: '#a89f8b',
          5: '#4d4638',
        },
        cream: {
          DEFAULT: '#0b0a08',
          hi: '#131110',
        },
        // Éxito / ganancia — ledger
        ledger: {
          DEFAULT: '#5fd7be',
          tint: '#0b2620',
        },
        // Error / pérdida — cinnabar
        cinnabar: {
          DEFAULT: '#ed8b73',
          tint: '#2b1310',
        },
        // Sidebar — siempre oscuro
        sb: {
          bg: '#0d0c0a',
          'bg-2': '#171512',
          hair: 'rgba(246,244,238,0.08)',
          txt: '#d3ccbc',
          'txt-mute': '#7a7365',
          'txt-hi': '#f6f4ee',
        },
        // Escalas nativas de Tailwind reapuntadas a los tokens de tema. Las
        // páginas de extractores (Ventas, Compras, …) ya usan `text-slate-400`,
        // `bg-surface-700`, `text-emerald-400`, etc. en cientos de sitios;
        // remapearlas aquí hace que toda esa UI siga el tema claro/oscuro sin
        // reescribir su marcado. Los números conservan su sentido relativo
        // (más alto = más apagado en texto, más profundo en superficie).
        slate: {
          50:  'rgb(var(--panel-rgb) / <alpha-value>)',
          100: 'rgb(var(--ink-rgb) / <alpha-value>)',
          200: 'rgb(var(--ink-rgb) / <alpha-value>)',
          300: 'rgb(var(--ink3-rgb) / <alpha-value>)',
          400: 'rgb(var(--ink3-rgb) / <alpha-value>)',
          500: 'rgb(var(--ink4-rgb) / <alpha-value>)',
          600: 'rgb(var(--ink5-rgb) / <alpha-value>)',
          700: 'rgb(var(--border-rgb) / <alpha-value>)',
          800: 'rgb(var(--panel2-rgb) / <alpha-value>)',
          900: 'rgb(var(--panel-rgb) / <alpha-value>)',
        },
        // Semánticos: pérdida/error → bermellón, ganancia/conforme → verde,
        // observación → ocre. Los tonos 700–900 se usan casi siempre con
        // modificador de opacidad (bg-red-900/20), así que apuntan al mismo
        // color base y el tinte lo da la opacidad.
        red: {
          300: 'rgb(var(--gold-rgb) / <alpha-value>)',
          400: 'rgb(var(--gold-rgb) / <alpha-value>)',
          500: 'rgb(var(--gold-rgb) / <alpha-value>)',
          700: 'rgb(var(--gold-rgb) / <alpha-value>)',
          800: 'rgb(var(--gold-rgb) / <alpha-value>)',
          900: 'rgb(var(--gold-rgb) / <alpha-value>)',
        },
        emerald: {
          400: 'rgb(var(--cinnabar-rgb) / <alpha-value>)',
          500: 'rgb(var(--cinnabar-rgb) / <alpha-value>)',
          800: 'rgb(var(--cinnabar-rgb) / <alpha-value>)',
          900: 'rgb(var(--cinnabar-rgb) / <alpha-value>)',
        },
        amber: {
          300: 'rgb(var(--warn-rgb) / <alpha-value>)',
          400: 'rgb(var(--warn-rgb) / <alpha-value>)',
          500: 'rgb(var(--warn-rgb) / <alpha-value>)',
          700: 'rgb(var(--warn-rgb) / <alpha-value>)',
          800: 'rgb(var(--warn-rgb) / <alpha-value>)',
          900: 'rgb(var(--warn-rgb) / <alpha-value>)',
        },
        // Azules/rosas sueltos que quedaron de la plantilla original: se
        // reconducen al acento editorial para que no reaparezca el arcoíris.
        blue:   { 400: 'rgb(var(--gold-rgb) / <alpha-value>)', 500: 'rgb(var(--gold-rgb) / <alpha-value>)' },
        sky:    { 400: 'rgb(var(--gold-rgb) / <alpha-value>)', 500: 'rgb(var(--gold-rgb) / <alpha-value>)' },
        green:  { 400: 'rgb(var(--cinnabar-rgb) / <alpha-value>)' },
        // Tokens de tema (claro por defecto / oscuro vía .dark) — con soporte
        // de modificador de opacidad (bg-paper/80, text-fg-3/60, etc.) porque
        // apuntan a variables RGB, no hex. Usados en landing, login y layout.
        paper:    'rgb(var(--bg-rgb) / <alpha-value>)',
        panel:    'rgb(var(--panel-rgb) / <alpha-value>)',
        panel2:   'rgb(var(--panel2-rgb) / <alpha-value>)',
        hairline: 'rgb(var(--border-rgb) / <alpha-value>)',
        fg:       'rgb(var(--ink-rgb) / <alpha-value>)',
        'fg-3':   'rgb(var(--ink3-rgb) / <alpha-value>)',
        'fg-4':   'rgb(var(--ink4-rgb) / <alpha-value>)',
        'fg-5':   'rgb(var(--ink5-rgb) / <alpha-value>)',
        accent:   'rgb(var(--gold-rgb) / <alpha-value>)',
        accent2:  'rgb(var(--cinnabar-rgb) / <alpha-value>)',
        warn:     'rgb(var(--warn-rgb) / <alpha-value>)',
      },
      fontFamily: {
        sans: ["'Instrument Sans'", '-apple-system', 'BlinkMacSystemFont', "'Segoe UI'", 'sans-serif'],
        display: ["'Fraunces'", "'Times New Roman'", 'Georgia', 'serif'],
        ui: ["'Instrument Sans'", '-apple-system', 'BlinkMacSystemFont', "'Segoe UI'", 'sans-serif'],
        mono: ["'JetBrains Mono'", "'Menlo'", "'Consolas'", 'monospace'],
      },
      borderRadius: {
        lg: '2px',
        xl: '3px',
      },
    },
  },
  plugins: [],
}
