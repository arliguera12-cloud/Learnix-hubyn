import { useEffect, useState } from 'react'
import { IconSol, IconLuna } from './Icons'

function leerPreferencia() {
  if (typeof document === 'undefined') return false
  return document.documentElement.classList.contains('dark')
}

export default function ThemeToggle({ className = '' }) {
  const [oscuro, setOscuro] = useState(leerPreferencia)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', oscuro)
    try {
      localStorage.setItem('learnix-theme', oscuro ? 'dark' : 'light')
    } catch {
      // Modo privado / almacenamiento bloqueado: el tema sigue aplicando en esta sesión.
    }
  }, [oscuro])

  return (
    <button
      type="button"
      onClick={() => setOscuro(v => !v)}
      aria-label={oscuro ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
      title={oscuro ? 'Modo claro' : 'Modo oscuro'}
      className={
        'inline-flex items-center justify-center w-8 h-8 rounded-lg border border-current/25 ' +
        'hover:opacity-70 transition-opacity duration-150 ' + className
      }
    >
      {oscuro ? <IconSol className="w-4 h-4" /> : <IconLuna className="w-4 h-4" />}
    </button>
  )
}
