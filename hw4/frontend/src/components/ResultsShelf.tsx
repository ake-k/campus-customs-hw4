import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { useChat } from './chatState'
import Icon from './Icon'
import ProductCard from './ProductCard'
import SizePicker from './SizePicker'
import { inStockIn, useSize } from './sizeState'

// Shows the products from the latest chat reply on the page itself, above
// whatever page the shopper is on. Each tile links to /products/:id, the same
// single-item page as the catalogue grid. Opening one collapses the shelf to a
// slim bar so the product page is front and center.
export default function ResultsShelf() {
  const { results, resultsVersion, shelfCollapsed, setShelfCollapsed, clearResults } = useChat()
  const ref = useRef<HTMLElement>(null)
  const { size, mode } = useSize()

  // New results: bring the shelf into view (below the sticky header).
  useEffect(() => {
    if (!results || !ref.current) return
    const headerHeight = document.querySelector('.header')?.getBoundingClientRect().height ?? 64
    const top = ref.current.getBoundingClientRect().top + window.scrollY - headerHeight - 16
    window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
    // only when a new set arrives, not on every render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resultsVersion])

  if (!results) return null
  const shown = results.products.length
  const fits = size ? results.products.filter((p) => inStockIn(p, size)) : results.products
  const cards = !size ? results.products : mode === 'hide' ? fits : [...fits, ...results.products.filter((p) => !inStockIn(p, size))]

  if (shelfCollapsed) {
    return (
      <section ref={ref} className="shelf shelf--collapsed" aria-label="Chat results">
        <span className="shelf__mini-title">From your conversation: <strong>{results.heading}</strong> · {shown}</span>
        <button className="btn btn--link" onClick={() => setShelfCollapsed(false)}>Show results</button>
        <button className="iconbtn" onClick={clearResults} aria-label="Dismiss chat results"><Icon name="close" size={18} /></button>
      </section>
    )
  }

  return (
    <section ref={ref} key={resultsVersion} className="shelf" aria-live="polite" aria-label="Products from your conversation">
      <header className="shelf__head">
        <div>
          <p className="eyebrow">From your conversation</p>
          <h2 className="h2">{results.heading}</h2>
          <p className="muted">You asked: “{results.query}”</p>
        </div>
        <div className="shelf__actions">
          <span className="shelf__count">
            {results.category_total && results.category_total > shown ? `${shown} of ${results.category_total}` : `${shown} ${shown === 1 ? 'item' : 'items'}`}
          </span>
          {results.see_all_url && (
            <Link to={results.see_all_url} className="btn btn--ghost btn--sm" onClick={() => setShelfCollapsed(true)}>
              See all {results.category?.toLowerCase()}
            </Link>
          )}
          <button className="btn btn--link" onClick={() => setShelfCollapsed(true)}>Hide</button>
          <button className="iconbtn" onClick={clearResults} aria-label="Dismiss chat results"><Icon name="close" size={18} /></button>
        </div>
      </header>
      <div className="shelf__sizes">
        <SizePicker compact />
        {size && (
          <span className="muted small">
            {fits.length} of {shown} in stock in {size}
            {mode === 'hide' && shown - fits.length > 0 ? ` · ${shown - fits.length} hidden` : ''}
          </span>
        )}
      </div>
      {cards.length === 0 && (
        <p className="notice">None of these are in stock in {size}. Switch to “gray out” to see them anyway, or ask the Bulldog for alternatives in your size.</p>
      )}
      <div className="grid">
        {cards.map((p, i) => (
          <ProductCard key={p.product_id} product={p} onOpen={() => setShelfCollapsed(true)} style={{ animationDelay: `${i * 30}ms` }} />
        ))}
      </div>
    </section>
  )
}
