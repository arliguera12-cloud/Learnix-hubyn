/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Superficies — reapuntadas a los tokens de tema.
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
        // Primario — acento índigo único de marca/interacción. Pestañas
        // activas, barras de progreso, foco de inputs, CTA.
        brand: {
          50:  'rgb(var(--gold-rgb) / <alpha-value>)',
          100: 'rgb(var(--gold-rgb) / <alpha-value>)',
          400: 'rgb(var(--gold-rgb) / <alpha-value>)',
          500: 'rgb(var(--gold-rgb) / <alpha-value>)',
          600: 'rgb(var(--gold-rgb) / <alpha-value>)',
        },
        // Éxito / ganancia
        ledger: {
          DEFAULT: 'rgb(var(--cinnabar-rgb))',
          tint: 'rgb(var(--cinnabar-rgb) / 0.1)',
        },
        // Sidebar — siempre oscuro
        sb: {
          bg: '#0d0e12',
          'bg-2': '#171922',
          hair: 'rgba(246,244,238,0.08)',
          txt: '#c7cbd6',
          'txt-mute': '#767c8c',
          'txt-hi': '#f4f5f8',
        },
        // Escalas nativas de Tailwind reapuntadas a los tokens de tema. Las
        // páginas de extractores (Ventas, Compras, …) ya usan `text-slate-400`,
        // `bg-surface-700`, etc. en cientos de sitios; remapearlas aquí hace
        // que toda esa UI siga el tema claro/oscuro sin reescribir su marcado.
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
        // Semánticos: error real → rojo (independiente del acento de marca),
        // ganancia/conforme → verde, observación → ámbar. Los tonos 700–900
        // se usan casi siempre con modificador de opacidad (bg-red-900/20),
        // así que apuntan al mismo color base y el tinte lo da la opacidad.
        red: {
          300: 'rgb(var(--danger-rgb) / <alpha-value>)',
          400: 'rgb(var(--danger-rgb) / <alpha-value>)',
          500: 'rgb(var(--danger-rgb) / <alpha-value>)',
          700: 'rgb(var(--danger-rgb) / <alpha-value>)',
          800: 'rgb(var(--danger-rgb) / <alpha-value>)',
          900: 'rgb(var(--danger-rgb) / <alpha-value>)',
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
        // reconducen al acento único de marca (ahora índigo, así que ya
        // no hace falta "disfrazarlos" — son, literalmente, el acento).
        blue:   { 400: 'rgb(var(--gold-rgb) / <alpha-value>)', 500: 'rgb(var(--gold-rgb) / <alpha-value>)' },
        sky:    { 400: 'rgb(var(--gold-rgb) / <alpha-value>)', 500: 'rgb(var(--gold-rgb) / <alpha-value>)' },
        green:  { 400: 'rgb(var(--cinnabar-rgb) / <alpha-value>)' },
        // Tokens de tema (claro por defecto / oscuro vía .dark) — con soporte
        // de modificador de opacidad (bg-paper/80, text-fg-3/60, etc.) porque
        // apuntan a variables RGB, no hex.
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
        danger:   'rgb(var(--danger-rgb) / <alpha-value>)',
        warn:     'rgb(var(--warn-rgb) / <alpha-value>)',
      },
      fontFamily: {
        sans: ["'Instrument Sans'", '-apple-system', 'BlinkMacSystemFont', "'Segoe UI'", 'sans-serif'],
        display: ["'Instrument Sans'", '-apple-system', 'BlinkMacSystemFont', "'Segoe UI'", 'sans-serif'],
        ui: ["'Instrument Sans'", '-apple-system', 'BlinkMacSystemFont', "'Segoe UI'", 'sans-serif'],
        mono: ["'JetBrains Mono'", "'Menlo'", "'Consolas'", 'monospace'],
      },
      borderRadius: {
        // Escala moderna generosa — reemplaza el radio casi recto (2px,
        // "boleto impreso") del sistema editorial anterior.
        DEFAULT: '0.625rem',
        sm: '0.5rem',
        md: '0.75rem',
        lg: '0.875rem',
        xl: '1rem',
        '2xl': '1.25rem',
      },
      boxShadow: {
        card: 'var(--shadow-card)',
        'card-lg': 'var(--shadow-card-lg)',
      },
    },
  },
  plugins: [],
}
