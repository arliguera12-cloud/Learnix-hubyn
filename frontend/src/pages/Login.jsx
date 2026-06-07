import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { signIn, useAuth } from '../services/auth'

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
    if (!authLoading && session) navigate('/', { replace: true })
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
      navigate('/')
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
    return <div className="min-h-screen bg-surface-900 flex items-center justify-center">
      <div className="animate-spin h-8 w-8 border-2 border-brand-500 border-t-transparent rounded-full"/>
    </div>
  }

  return (
    <div className="min-h-screen bg-surface-900 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo / Header */}
        <div className="text-center mb-8">
          <p className="text-4xl mb-3">🏛️</p>
          <h1 className="text-2xl font-bold text-white">Learnix DTE Hub</h1>
          <p className="text-sm text-slate-400 mt-1">Sistema de extracción de DTEs — El Salvador</p>
        </div>

        <div className="card">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Correo electrónico</label>
              <input
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
              <label className="block text-xs text-slate-400 mb-1">Contraseña</label>
              <input
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
              <div className="badge-err w-full justify-start px-3 py-2 rounded-lg text-xs">
                ⚠️ {error}
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

        <p className="text-center text-xs text-slate-600 mt-6">
          Learnix · El Salvador · {new Date().getFullYear()}
        </p>
      </div>
    </div>
  )
}
