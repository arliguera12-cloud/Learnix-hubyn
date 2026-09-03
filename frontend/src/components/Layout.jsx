import Sidebar from './Sidebar'

export default function Layout({ children }) {
  return (
    <div className="min-h-screen" style={{ background: 'var(--bg)' }}>
      <Sidebar />
      <main className="ml-64 min-h-screen p-6 lg:p-8 xl:p-10">
        {children}
      </main>
    </div>
  )
}
