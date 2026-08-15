/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Superficies (paleta "Ledger Editorial" de Certia, modo oscuro)
        surface: {
          50:  '#fbfaf7',
          100: '#f2ede1',
          200: '#d8d2c3',
          300: '#c2bbaa',
          400: '#746c5c',
          500: '#4d4638',
          600: '#2d2822',
          700: '#1c1917',
          800: '#131110',
          900: '#0b0a08',
        },
        // Primario / "notarial" — cobalt
        brand: {
          50:  '#e4ebf3',
          100: '#cfe0ee',
          400: '#a8caea',
          500: '#7bb3e8',
          600: '#cfe0ee',
        },
        // Acento editorial — dorado
        gold: {
          DEFAULT: '#d4b45c',
          tint: '#2a2110',
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
        // Reemplaza las escalas nativas de Tailwind que ya se usan en el código
        // por tonos derivados de la paleta Certia, para que toda la UI herede
        // el mismo lenguaje visual sin reescribir cada página.
        slate: {
          50:  '#fbfaf7',
          100: '#f2ede1',
          200: '#d8d2c3',
          300: '#c2bbaa',
          400: '#a89f8b',
          500: '#8b8271',
          600: '#746c5c',
          700: '#4d4638',
          800: '#2d2822',
          900: '#1c1917',
        },
        red: {
          300: '#f3ab98',
          400: '#ed8b73',
          500: '#e2724f',
          700: '#4a221c',
          800: '#3a1a16',
          900: '#2b1310',
        },
        emerald: {
          400: '#5fd7be',
          500: '#3fc7ab',
          800: '#123832',
          900: '#0b2620',
        },
        amber: {
          300: '#f0c785',
          400: '#e8b45c',
          500: '#d99f3e',
          700: '#7a531c',
          800: '#4a3313',
          900: '#2b1e0a',
        },
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
