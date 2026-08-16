import Sidebar from './Sidebar'

export default function Layout({ children }) {
  return (
    <div className="min-h-screen" style={{ background: 'var(--bg)' }}>
      <Sidebar />
      <main className="ml-56 min-h-screen p-6">
        {children}
      </main>
    </div>
  )
}
