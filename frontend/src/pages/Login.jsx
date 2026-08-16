import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { signIn, useAuth } from '../services/auth'
import ThemeToggle from '../components/ThemeToggle'
import { SelloCircular, IconSeccion, IconAlerta } from '../components/Icons'

const MAX_INTENTOS = 5
const BLOQUEO_MS   = 5 * 60 * 1000 // 5 minutos

export default function Login() {
  const navigate = useNavigate()
  const { session, loading: authLoading } = useAuth()

  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState(null)
  const [loading,  setLoading]  = useState(false)
  const [intentos, setIntentos] = useState(() => Number(sessionStorage.getItem('login_intentos') || 0))
  const [bloqueadoHasta, setBloqueadoHasta] = useState(
    () => Number(sessionStorage.getItem('login_bloqueado') || 0)
  )

  useEffect(() => {
    if (!authLoading && session) navigate('/dashboard', { replace: true })
  }, [session, authLoading, navigate])

  const ahora     = Date.now()
  const bloqueado = bloqueadoHasta > ahora
  const restante  = bloqueado ? Math.ceil((bloqueadoHasta - ahora) / 1000) : 0

  // Contador regresivo del bloqueo
  useEffect(() => {
    if (!bloqueado) return
    const id = setInterval(() => {
      if (Date.now() >= bloqueadoHasta) {
        setBloqueadoHasta(0)
        setIntentos(0)
        sessionStorage.removeItem('login_bloqueado')
        sessionStorage.removeItem('login_intentos')
      }
    }, 1000)
    return () => clearInterval(id)
  }, [bloqueado, bloqueadoHasta])

  async function handleSubmit(e) {
    e.preventDefault()
    if (bloqueado) return

    setError(null)
    setLoading(true)
    try {
      await signIn(email, password)
      sessionStorage.removeItem('login_intentos')
      sessionStorage.removeItem('login_bloqueado')
      navigate('/dashboard')
    } catch (err) {
      const nuevos = intentos + 1
      setIntentos(nuevos)
      sessionStorage.setItem('login_intentos', nuevos)

      if (nuevos >= MAX_INTENTOS) {
        const hasta = Date.now() + BLOQUEO_MS
        setBloqueadoHasta(hasta)
        sessionStorage.setItem('login_bloqueado', hasta)
        setError('Demasiados intentos fallidos. Espera 5 minutos.')
      } else {
        setError(`Credenciales inválidas. Intento ${nuevos}/${MAX_INTENTOS}.`)
      }
    } finally {
      setLoading(false)
    }
  }

  if (authLoading) {
    return <div className="min-h-screen bg-paper flex items-center justify-center">
      <div className="animate-spin h-8 w-8 border-2 border-brand-500 border-t-transparent rounded-full"/>
    </div>
  }

  return (
    <div className="min-h-screen bg-paper flex flex-col paper-grain">
      {/* Masthead — mismo registro editorial que la portada */}
      <div className="border-b border-hairline bg-panel shrink-0">
        <div className="max-w-6xl mx-auto px-5 py-2 flex items-center justify-between text-[0.65rem]
                        uppercase tracking-[0.16em] text-fg-4 font-mono">
          <Link to="/" className="flex items-baseline gap-1.5 hover:text-accent transition-colors">
            <IconSeccion className="text-sm text-accent" />
            <span>Learnix DTE Hub</span>
          </Link>
          <span className="hidden sm:block">Acceso registrado</span>
          <ThemeToggle className="text-fg-4 -my-1" />
        </div>
      </div>

      <div className="flex-1 relative flex items-center justify-center p-4 overflow-hidden ledger-paper">
        {/* Marca de agua editorial de fondo */}
        <div className="pointer-events-none select-none absolute inset-0 flex items-center justify-center">
          <span className="font-display text-[26vw] leading-none text-fg/[0.045] whitespace-nowrap">
            Learnix
          </span>
        </div>

        <div className="w-full max-w-sm relative animate-rise py-10">
          <Link
            to="/"
            className="inline-flex items-center gap-1.5 text-xs text-fg-4 hover:text-accent
                       transition-colors duration-150 mb-6"
          >
            ← Volver al inicio
          </Link>

          {/* Logo / Header */}
          <div className="text-center mb-8">
            <div className="w-24 h-24 mx-auto mb-4 text-accent">
              <SelloCircular />
            </div>
            <h1 className="text-3xl text-fg leading-none">Learnix DTE Hub</h1>
            <div className="rule-double max-w-[160px] mx-auto" />
            <p className="text-sm text-fg-3 mt-1">Sistema de extracción de DTE — El Salvador</p>
          </div>

          <div className="card relative">
            <span className="absolute -top-3 left-5 bg-panel px-2 text-[0.65rem] uppercase
                              tracking-[0.14em] text-fg-4 font-semibold">
              Acceso registrado
            </span>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="form-label" htmlFor="login-email">Correo electrónico</label>
                <input
                  id="login-email"
                  className="input"
                  type="email"
                  autoComplete="email"
                  placeholder="usuario@empresa.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  disabled={bloqueado || loading}
                />
              </div>
              <div>
                <label className="form-label" htmlFor="login-password">Contraseña</label>
                <input
                  id="login-password"
                  className="input"
                  type="password"
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  disabled={bloqueado || loading}
                />
              </div>

              {error && (
                <div className="badge-err w-full justify-start px-3 py-2 rounded-lg text-xs" role="alert">
                  <IconAlerta className="w-3.5 h-3.5 shrink-0" />
                  <span>{error}</span>
                  {bloqueado && <span className="ml-auto font-mono">{restante}s</span>}
                </div>
              )}

              <button
                type="submit"
                disabled={bloqueado || loading}
                className="btn-primary w-full py-2.5"
              >
                {loading ? 'Ingresando…' : bloqueado ? `Bloqueado (${restante}s)` : 'Ingresar'}
              </button>
            </form>
          </div>

          <p className="text-center text-xs text-fg-4 mt-6 tracking-wide">
            Learnix · El Salvador · {new Date().getFullYear()}
          </p>
        </div>
      </div>
    </div>
  )
}
