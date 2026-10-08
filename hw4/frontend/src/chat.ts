// Chat client for the shop assistant (PydanticAI agent behind FastAPI).
// The browser sends only the new message; the backend keeps the conversation
// (saved to the database for logged-in shoppers, in memory for guests).

import type { User } from './api'

/** Mirrors models.ProductCard on the backend. Prices and stock come from the database. */
export interface ProductCard {
  product_id: string
  name: string
  category: string
  price: number
  image_url: string
  short_description: string
  colors: string[]
  sizes_in_stock: string[]
  total_stock: number
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  products?: ProductCard[]
  steps?: string[] // what the assistant did for this reply (live progress, kept under the reply)
  kind?: 'screened' | 'limit' | 'error' // special notices, styled differently
  animate?: boolean // reveal this reply word by word (only for replies that just arrived)
}

/** Mirrors models.ChatLimits */
export interface ChatLimits {
  remaining_this_minute: number
  remaining_today: number
  per_minute: number
  per_day: number
}

/** Mirrors models.ProductResults: the cards the website shows on the page for a chat reply. */
export interface ProductResults {
  heading: string
  query: string
  products: ProductCard[]
  category: string | null
  category_total: number | null
  see_all_url: string | null
}

export interface ChatReply {
  reply: string
  screened: boolean // true = blocked by the input check before reaching the model
  limits: ChatLimits | null
  products: ProductCard[]
  results: ProductResults | null // null = nothing to show on the page; keep the current shelf
  user: User | null
}

/** Mirrors models.PageContext: where the shopper is, so "this" / "it" can be resolved. */
export interface PageContext {
  path: string
  product_id: string | null
  category: string | null
}

export class ChatError extends Error {
  status: number
  retryAfter: number | null
  constructor(message: string, status: number, retryAfter: number | null = null) {
    super(message)
    this.status = status
    this.retryAfter = retryAfter
  }
}

type StreamEvent =
  | { type: 'status'; text: string }
  | { type: 'done'; response: ChatReply }
  | { type: 'error'; status: number; detail: string; retry_after: number | null }

/**
 * POST /api/chat/stream: the backend sends one JSON line per agent step ("Checking stock: … in L"),
 * then the full reply. onStatus is called for each step so the widget can show live progress.
 */
export async function streamChatMessage(
  message: string,
  page: PageContext,
  preferredSize: string | null,
  onStatus: (text: string) => void,
): Promise<ChatReply> {
  const res = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, page, preferred_size: preferredSize }),
  })
  if (!res.ok || !res.body) {
    const data = await res.json().catch(() => null)
    throw new ChatError(data?.detail ?? "Sorry, I couldn't reach the shop just now. Please try again in a moment.", res.status)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done })
    let nl: number
    while ((nl = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, nl).trim()
      buffer = buffer.slice(nl + 1)
      if (!line) continue
      const event = JSON.parse(line) as StreamEvent
      if (event.type === 'status') onStatus(event.text)
      else if (event.type === 'done') return event.response
      else throw new ChatError(event.detail, event.status, event.retry_after)
    }
    if (done) break
  }
  throw new ChatError("Sorry, the connection dropped before I finished. Please try again.", 0)
}

/** Non-streaming version (POST /api/chat); kept for simple clients and tests. */
export async function sendChatMessage(message: string, page: PageContext): Promise<ChatReply> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, page }),
  })
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new Error(data?.detail ?? "Sorry, I couldn't reach the shop just now. Please try again in a moment.")
  return data as ChatReply
}

export async function fetchChatHistory(): Promise<ChatMessage[]> {
  const res = await fetch('/api/chat/history')
  if (!res.ok) return []
  const data = (await res.json()) as { messages: ChatMessage[] }
  return data.messages
}
