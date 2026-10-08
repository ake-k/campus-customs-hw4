import { Fragment, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { formatPrice } from '../api'
import { ChatError, fetchChatHistory, streamChatMessage, type ChatLimits, type ChatMessage } from '../chat'
import { useAuth } from './authState'
import { useChat } from './chatState'
import { useSize } from './sizeState'
import Icon from './Icon'
import { displayName } from '../catalog'

function welcome(firstName?: string): ChatMessage {
  return {
    role: 'assistant',
    content: `Hi${firstName ? ` ${firstName}` : ' there'}, and welcome to Campus Customs! I'm your shopping assistant. Ask me about hoodies, sizes, prices, or what's in stock.`,
  }
}

// Tiny, safe formatter for replies: **bold** and "- " bullet lines. Builds React
// elements (never raw HTML), so model text can't inject markup.
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : <Fragment key={i}>{part}</Fragment>,
  )
}

function FormattedText({ text }: { text: string }) {
  const blocks: ReactNode[] = []
  let bullets: string[] = []
  const flush = () => {
    if (bullets.length) blocks.push(<ul key={blocks.length}>{bullets.map((b, i) => <li key={i}>{inline(b)}</li>)}</ul>)
    bullets = []
  }
  for (const line of text.split('\n')) {
    const m = line.match(/^\s*[-•*]\s+(.*)/)
    if (m) bullets.push(m[1])
    else {
      flush()
      if (line.trim()) blocks.push(<p key={blocks.length}>{inline(line)}</p>)
    }
  }
  flush()
  return <>{blocks}</>
}

const COMPOSING = 'Putting your answer together' // matches the backend's step text

/** Suggested questions that fit the page the shopper is on. */
function suggestionsFor(path: string, search: string, product: string | null, size: string | null): string[] {
  if (product) return [size ? `Is this in stock in ${size}?` : 'What sizes is this in stock in?', 'What else goes with this?', 'Do you have this in another color?']
  const category = path === '/products' ? new URLSearchParams(search).get('category') : null
  if (category) return [`Which ${category.toLowerCase()} are in stock in ${size ?? 'M'}?`, `Any ${category.toLowerCase()} under $60?`, 'What would make a good gift?']
  return ['What hoodies do you have?', size ? `What's in stock in ${size}?` : 'Gifts for a Yale parent', 'Anything for Davenport College?']
}

/** Reveals a just-arrived reply a few words at a time, then hands over to the normal formatter. */
function RevealText({ text, onDone }: { text: string; onDone: () => void }) {
  const words = text.split(/(\s+)/)
  const [count, setCount] = useState(0)
  useEffect(() => {
    if (count >= words.length) {
      onDone()
      return
    }
    const t = setTimeout(() => setCount((c) => Math.min(words.length, c + 2)), 28)
    return () => clearTimeout(t)
  }, [count, words.length, onDone])
  return <FormattedText text={words.slice(0, count).join('')} />
}

/** Live progress while the agent works: each step appears as the backend reports it. */
function ProgressSteps({ steps, live }: { steps: string[]; live: boolean }) {
  return (
    <ol className={`progress-steps ${live ? 'progress-steps--live' : ''}`}>
      {steps.map((s, i) => {
        const current = live && i === steps.length - 1
        return (
          <li key={i} className={current ? 'is-current' : 'is-done'}>
            <span className="progress-steps__icon">{current ? <span className="mini-spinner" /> : '✓'}</span>
            {s}
          </li>
        )
      })}
    </ol>
  )
}

export default function ChatWidget() {
  const { isOpen, draft, closeChat, setDraft, showResults, viewing } = useChat()
  const location = useLocation()
  // Only treat the viewed product as context while its page is actually open.
  const onProductPage = viewing && location.pathname === `/products/${viewing.product_id}` ? viewing : null
  const { user, ready } = useAuth()
  const [messages, setMessages] = useState<ChatMessage[]>([welcome()])
  const [sending, setSending] = useState(false)
  const [steps, setSteps] = useState<string[]>([]) // live progress for the message being answered
  const [limits, setLimits] = useState<ChatLimits | null>(null)
  const [blockedUntil, setBlockedUntil] = useState(0) // after a 429: no sending until this time (ms)
  const [now, setNow] = useState(() => Date.now())
  const { size } = useSize()

  useEffect(() => {
    if (blockedUntil <= now) return
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [blockedUntil, now])
  const waitSeconds = Math.max(0, Math.ceil((blockedUntil - now) / 1000))

  // Load this shopper's earlier conversation; reload when they log in or out.
  useEffect(() => {
    if (!ready) return
    let cancelled = false
    fetchChatHistory().then((history) => {
      if (!cancelled) setMessages([welcome(user?.first_name), ...history])
    })
    return () => {
      cancelled = true
    }
  }, [ready, user?.id, user?.first_name])
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, sending, steps])

  useEffect(() => {
    if (isOpen) inputRef.current?.focus()
  }, [isOpen])

  async function send(text: string) {
    const content = text.trim()
    if (!content || sending || waitSeconds > 0) return
    setMessages((m) => [...m, { role: 'user', content }])
    setDraft('')
    setSending(true)
    setSteps([])
    const taken: string[] = []
    try {
      const page = {
        path: location.pathname + location.search,
        product_id: onProductPage?.product_id ?? null,
        category: location.pathname === '/products' ? new URLSearchParams(location.search).get('category') : null,
      }
      const reply = await streamChatMessage(content, page, size, (step) => {
        // "Putting your answer together" is followed by more lookups when the agent needs another round;
        // keep the list tidy by replacing it instead of repeating it.
        if (taken[taken.length - 1] === COMPOSING) taken.pop()
        taken.push(step)
        setSteps([...taken])
      })
      setLimits(reply.limits)
      setMessages((m) => [
        ...m,
        {
          role: 'assistant', content: reply.reply, products: reply.products, animate: true,
          steps: reply.screened ? undefined : taken, kind: reply.screened ? 'screened' : undefined,
        },
      ])
      if (reply.results) showResults(reply.results) // put the matching products on the page
    } catch (err) {
      const e = err as ChatError
      if (e.status === 429 && e.retryAfter) {
        // (inside an event handler, not render; the linter can't tell)
        // eslint-disable-next-line react/purity
        setBlockedUntil(Date.now() + e.retryAfter * 1000)
        // eslint-disable-next-line react/purity
        setNow(Date.now())
      }
      setMessages((m) => [...m, { role: 'assistant', content: e.message, kind: e.status === 429 ? 'limit' : 'error' }])
    } finally {
      setSending(false)
      setSteps([])
    }
  }

  const finishReveal = (index: number) =>
    setMessages((m) => (m[index]?.animate ? m.map((x, i) => (i === index ? { ...x, animate: false } : x)) : m))

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void send(draft)
  }

  const suggestions = suggestionsFor(location.pathname, location.search, onProductPage?.name ?? null, size)

  return (
    <>
      {isOpen && <div className="scrim" onClick={closeChat} aria-hidden="true" />}
      <aside className={`concierge ${isOpen ? 'is-open' : ''}`} aria-label="Ask the Bulldog, shopping assistant" aria-hidden={!isOpen} inert={!isOpen}>
        <header className="concierge__head">
          <div>
            <h2 className="concierge__title">Ask the Bulldog</h2>
            <p className="concierge__sub"><span className="dot" /> Shopping concierge · checks live stock{size ? ` in ${size}` : ''}</p>
          </div>
          <button className="iconbtn" onClick={closeChat} aria-label="Close assistant"><Icon name="close" size={20} /></button>
        </header>

        <div className="concierge__messages" ref={scrollRef}>
          {messages.map((m, i) => (
            <div key={i} className={`msg msg--${m.role} ${m.kind ? `msg--${m.kind}` : ''}`}>
              {m.kind === 'screened' && <p className="msg__flag">Safety check</p>}
              {m.kind === 'limit' && <p className="msg__flag">Message limit</p>}
              <div className="msg__body">
                {m.role === 'assistant' ? (
                  m.animate ? <RevealText text={m.content} onDone={() => finishReveal(i)} /> : <FormattedText text={m.content} />
                ) : (
                  <p>{m.content}</p>
                )}
              </div>
              {m.products && m.products.length > 0 && (
                <ul className="rows">
                  {m.products.map((p) => (
                    <li key={p.product_id}>
                      <Link to={`/products/${p.product_id}`} className="row">
                        <img src={p.image_url} alt="" />
                        <span className="row__text">
                          <span className="row__name">{displayName(p.name)}</span>
                          <span className="row__sizes">{p.sizes_in_stock.length ? `In stock: ${p.sizes_in_stock.join(' ')}` : 'Sold out'}</span>
                        </span>
                        <span className="row__price">{formatPrice(p.price)}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
              {m.steps && m.steps.length > 0 && (
                <details className="msg__steps">
                  <summary>How I found this · {m.steps.length} steps</summary>
                  <ProgressSteps steps={m.steps} live={false} />
                </details>
              )}
            </div>
          ))}
          {sending && (
            <div className="msg msg--assistant msg--working" aria-live="polite" aria-label="Assistant is working">
              <p className="working">Working on it<span className="working__dots"><span /><span /><span /></span></p>
              {steps.length > 0 && <ProgressSteps steps={steps} live />}
            </div>
          )}
        </div>

        <footer className="concierge__foot">
          {!sending && (
            <div className="suggestions" aria-label="Suggested questions">
              {suggestions.map((q) => (
                <button key={q} className="suggestion" onClick={() => void send(q)}>{q}</button>
              ))}
            </div>
          )}
          {onProductPage && (
            <p className="concierge__context">Asking about <strong>{displayName(onProductPage.name)}</strong></p>
          )}
          {(waitSeconds > 0 || (limits && (limits.remaining_today <= 10 || limits.remaining_this_minute <= 1))) && (
            <p className={`concierge__limit ${waitSeconds > 0 ? 'is-blocked' : ''}`} role="status">
              {waitSeconds > 0
                ? waitSeconds > 3600
                  ? "You've reached today's message limit. Please come back tomorrow."
                  : `Message limit reached. You can send again in ${waitSeconds}s.`
                : limits && limits.remaining_today <= 10
                  ? `${limits.remaining_today} messages left today`
                  : 'Slow down a little: 1 more message this minute'}
            </p>
          )}
          <form className="composer" onSubmit={onSubmit}>
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder={waitSeconds > 0 ? `Please wait ${waitSeconds}s…` : onProductPage ? 'Ask about this item…' : 'Ask about sizes, stock, or gifts…'}
              aria-label="Message"
              disabled={waitSeconds > 0}
            />
            <button type="submit" className="composer__send" disabled={sending || !draft.trim() || waitSeconds > 0} aria-label="Send">
              <Icon name="arrow" size={18} />
            </button>
          </form>
        </footer>
      </aside>
    </>
  )
}
