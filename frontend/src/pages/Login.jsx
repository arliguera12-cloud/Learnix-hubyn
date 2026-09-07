import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { signIn, useAuth } from '../services/auth'
import ThemeToggle from '../components/ThemeToggle'
import { IconSeccion, IconAlerta, IconOjo, IconOjoTachado } from '../components/Icons'

// Freno de cortesía, no un control de seguridad: vive en sessionStorage del
// navegador y se esquiva borrándolo, abriendo otra pestaña o llamando a la API
// de Supabase directo. Está para que quien se equivoca de contraseña deje de
// reintentar a ciegas. El límite real contra fuerza bruta lo aplica Supabase
// Auth del lado del servidor, que es el único que ve todos los intentos.
const MAX_INTENTOS = 5
const BLOQUEO_MS   = 5 * 60 * 1000 // 5 minutos

const WHATSAPP_SOLICITAR_ACCESO =
  'https://api.whatsapp.com/send/?phone=50377567894&text=' +
  encodeURIComponent('Hola, quiero contratar Learnix para mi empresa.') +
  '&type=phone_number&app_absent=0'

export default function Login() {
  const navigate = useNavigate()
  const { session, loading: authLoading } = useAuth()

  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [mostrarPassword, setMostrarPassword] = useState(false)
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
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center">
        <div className="animate-spin h-8 w-8 border-2 border-brand-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-paper flex flex-col">
      <div className="flex items-center justify-between px-6 py-5">
        <Link to="/" className="flex items-center gap-2.5">
          <IconSeccion className="w-8 h-8 text-base" />
          <span className="text-[15px] font-semibold text-fg hidden sm:inline">Learnix DTE Hub</span>
        </Link>
        <ThemeToggle className="text-fg-4 hover:text-fg" />
      </div>

      <div className="flex-1 flex items-center justify-center px-6 pb-16">
        <div className="w-full max-w-sm animate-rise">
          <p className="text-[0.65rem] uppercase tracking-[0.2em] text-fg-4 font-semibold mb-2">
            Acceso
          </p>
          <h1 className="text-2xl text-fg mb-1">Iniciar sesión</h1>
          <p className="text-sm text-fg-4 mb-8">Ingresá tus credenciales para continuar.</p>

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
              <div className="relative">
                <input
                  id="login-password"
                  className="input pr-16"
                  type={mostrarPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  disabled={bloqueado || loading}
                />
                <button
                  type="button"
                  onClick={() => setMostrarPassword(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1.5 text-xs text-fg-4 hover:text-accent transition-colors"
                  tabIndex={-1}
                >
                  {mostrarPassword ? <IconOjoTachado className="w-4 h-4" /> : <IconOjo className="w-4 h-4" />}
                  {mostrarPassword ? 'Ocultar' : 'Mostrar'}
                </button>
              </div>
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
              {loading ? 'Ingresando…' : bloqueado ? `Bloqueado (${restante}s)` : 'Entrar al sistema'}
            </button>
          </form>

          <p className="text-center text-sm text-fg-4 mt-6">
            ¿No tenés cuenta?{' '}
            <a
              href={WHATSAPP_SOLICITAR_ACCESO}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent font-semibold hover:underline"
            >
              Solicitar acceso
            </a>
          </p>
        </div>
      </div>

      <p className="text-center text-xs text-fg-4 pb-6">
        Learnix · El Salvador · {new Date().getFullYear()}
      </p>
    </div>
  )
}
