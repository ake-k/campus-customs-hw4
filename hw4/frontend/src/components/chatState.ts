import { createContext, useContext } from 'react'
import type { ProductResults } from '../chat'

// Lets any page open the floating chat, optionally with a question pre-filled.
export interface ChatControls {
  isOpen: boolean
  draft: string
  openChat: (draft?: string) => void
  closeChat: () => void
  setDraft: (text: string) => void
  // Product cards from the latest chat reply, shown on the page by <ResultsShelf>.
  results: ProductResults | null
  resultsVersion: number // bumps on every new set of results (used to animate and scroll into view)
  shelfCollapsed: boolean
  showResults: (results: ProductResults) => void
  setShelfCollapsed: (collapsed: boolean) => void
  clearResults: () => void
  // The product whose page is open (set by the product page), sent with chat messages as page context.
  viewing: ViewedProduct | null
  setViewing: (product: ViewedProduct | null) => void
}

export interface ViewedProduct {
  product_id: string
  name: string
}

export const ChatCtx = createContext<ChatControls | null>(null)

export function useChat(): ChatControls {
  const ctx = useContext(ChatCtx)
  if (!ctx) throw new Error('useChat must be used inside <ChatProvider>')
  return ctx
}
