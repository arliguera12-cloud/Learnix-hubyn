/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#eff6ff',
          100: '#dbeafe',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
        },
        surface: {
          900: '#0e1117',
          800: '#161b27',
          700: '#1c2333',
          600: '#243044',
          500: '#2d3b52',
        },
      },
    },
  },
  plugins: [],
}
