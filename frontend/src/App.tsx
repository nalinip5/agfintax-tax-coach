import { useState } from 'react'
import ChatView from './components/ChatView'
import Dashboard from './components/Dashboard'

export default function App() {
  const [tab, setTab] = useState<'dashboard' | 'chat'>('dashboard')
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null)

  function askCoach(question: string) {
    setPendingQuestion(question)
    setTab('chat')
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <nav className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
        <div className="flex items-baseline gap-1">
          <span className="text-lg font-bold text-orange-500">AG</span>
          <span className="text-lg font-semibold text-slate-900">FinTax</span>
        </div>
        <div className="flex gap-1 rounded-full bg-slate-100 p-1 text-sm">
          <button
            onClick={() => setTab('dashboard')}
            className={`rounded-full px-4 py-1.5 font-medium transition-colors ${
              tab === 'dashboard' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'
            }`}
          >
            Dashboard
          </button>
          <button
            onClick={() => setTab('chat')}
            className={`rounded-full px-4 py-1.5 font-medium transition-colors ${
              tab === 'chat' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'
            }`}
          >
            Tax Coach
          </button>
        </div>
      </nav>
      {tab === 'dashboard' ? <Dashboard onAskCoach={askCoach} /> : <ChatView pendingQuestion={pendingQuestion} />}
    </div>
  )
}
