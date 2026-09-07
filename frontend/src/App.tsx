import ChatView from './components/ChatView'

export default function App() {
  return (
    <div className="min-h-screen bg-ledger-50">
      <nav className="flex items-center justify-between border-b border-ledger-200 bg-white px-6 py-3">
        <span className="font-serif text-lg text-ledger-900">AGFinTax</span>
      </nav>
      <ChatView />
    </div>
  )
}
