import { useState, type ReactNode } from 'react'
import type { ProductResults } from '../chat'
import { ChatCtx, type ViewedProduct } from './chatState'

export function ChatProvider({ children }: { children: ReactNode }) {
  const [isOpen, setOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const [results, setResults] = useState<ProductResults | null>(null)
  const [resultsVersion, setResultsVersion] = useState(0)
  const [shelfCollapsed, setShelfCollapsed] = useState(false)
  const showResults = (r: ProductResults) => {
    setResults(r)
    setResultsVersion((v) => v + 1)
    setShelfCollapsed(false)
  }
  const clearResults = () => setResults(null)
  const [viewing, setViewing] = useState<ViewedProduct | null>(null)
  const openChat = (text?: string) => {
    if (text !== undefined) setDraft(text)
    setOpen(true)
  }
  return (
    <ChatCtx.Provider
      value={{
        isOpen, draft, openChat, closeChat: () => setOpen(false), setDraft,
        results, resultsVersion, shelfCollapsed, showResults, setShelfCollapsed, clearResults,
        viewing, setViewing,
      }}
    >
      {children}
    </ChatCtx.Provider>
  )
}
