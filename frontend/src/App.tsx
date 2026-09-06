import { useState } from 'react'
import ChatView from './components/ChatView'
import AdminKB from './components/AdminKB'

export default function App() {
  const [tab, setTab] = useState<'chat' | 'admin'>('chat')

  return (
    <div className="min-h-screen bg-ledger-50">
      <nav className="flex items-center justify-between border-b border-ledger-200 bg-white px-6 py-3">
        <span className="font-serif text-lg text-ledger-900">AGFinTax</span>
        <div className="flex gap-1 rounded-full bg-ledger-100 p-1 text-sm">
          <button
            onClick={() => setTab('chat')}
            className={`rounded-full px-4 py-1.5 font-medium transition-colors ${
              tab === 'chat' ? 'bg-white text-ledger-900 shadow-sm' : 'text-ledger-600'
            }`}
          >
            Chat
          </button>
          <button
            onClick={() => setTab('admin')}
            className={`rounded-full px-4 py-1.5 font-medium transition-colors ${
              tab === 'admin' ? 'bg-white text-ledger-900 shadow-sm' : 'text-ledger-600'
            }`}
          >
            Admin
          </button>
        </div>
      </nav>
      {tab === 'chat' ? <ChatView /> : <AdminKB />}
    </div>
  )
}
