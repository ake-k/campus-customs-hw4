import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchProduct, fetchSimilar, formatPrice, swatchFor, type Product, type SimilarProduct } from '../api'
import { displayName } from '../catalog'
import { useBag } from '../components/bagState'
import { useChat } from '../components/chatState'
import Icon from '../components/Icon'
import ProductCard from '../components/ProductCard'
import { useSize } from '../components/sizeState'

const LOW_STOCK = 5

function listPhrase(items: string[]): string {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}

export default function ProductDetail() {
  const { productId = '' } = useParams()
  // key: remount with fresh state whenever the shopper opens a different product
  return <ProductView key={productId} productId={productId} />
}

function ProductView({ productId }: { productId: string }) {
  const [product, setProduct] = useState<Product | null>(null)
  const [similar, setSimilar] = useState<SimilarProduct[] | null>(null)
  const [error, setError] = useState('')
  const [size, setSize] = useState<string | null>(null)
  const [qty, setQty] = useState(1)
  const { openChat, setViewing } = useChat()
  const { size: mySize } = useSize()
  const { add } = useBag()

  // Tell the chat which product is on screen, so "do you have this in L?" refers to it.
  useEffect(() => {
    if (product) setViewing({ product_id: product.product_id, name: product.name })
    return () => setViewing(null)
  }, [product, setViewing])

  useEffect(() => {
    fetchProduct(productId)
      .then((p) => {
        setProduct(p)
        // Start on the shopper's own size if this item comes in it (even if sold out, so they see that).
        const offered = mySize && p.inventory.some((s) => s.size === mySize)
        setSize(offered ? mySize : (p.inventory.find((s) => s.quantity > 0)?.size ?? null))
      })
      .catch((e: Error) => setError(e.message))
    fetchSimilar(productId, mySize).then(setSimilar).catch(() => setSimilar([]))
    window.scrollTo({ top: 0 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productId])

  if (error) {
    return (
      <div className="page">
        <div className="empty">
          <h1 className="display display--sm">We couldn't find that item</h1>
          <p className="muted">{error}</p>
          <Link to="/products" className="btn btn--primary">Back to the shop</Link>
        </div>
      </div>
    )
  }

  if (!product) {
    return (
      <div className="page pdp">
        <div className="pdp__layout">
          <div className="skeleton pdp__skeleton-media" />
          <div className="skeleton pdp__skeleton-panel" />
        </div>
      </div>
    )
  }

  const name = displayName(product.name)
  const selected = product.inventory.find((s) => s.size === size)
  const inStock = product.inventory.filter((s) => s.quantity > 0).map((s) => s.size)
  const soldOut = product.inventory.filter((s) => s.quantity === 0).map((s) => s.size)
  const maxQty = selected?.quantity ?? 0

  const stockLine = !selected
    ? { tone: 'muted', text: 'Select a size to see availability.' }
    : selected.quantity === 0
      ? { tone: 'out', text: `Size ${selected.size} is sold out right now${inStock.length ? `. In stock in ${listPhrase(inStock)}.` : '.'}` }
      : selected.quantity <= LOW_STOCK
        ? { tone: 'low', text: `Only ${selected.quantity} left in ${selected.size}.` }
        : { tone: 'ok', text: `In stock in ${selected.size}.` }

  return (
    <div className="page pdp">
      <nav className="crumbs" aria-label="Breadcrumb">
        <Link to="/">Home</Link><span>/</span>
        <Link to={`/products?category=${encodeURIComponent(product.category)}`}>{product.category}</Link><span>/</span>
        <span aria-current="page">{name}</span>
      </nav>

      <div className="pdp__layout">
        <div className="pdp__media">
          <div className="pdp__photo"><img src={product.image_url} alt={name} /></div>

          <section className="pdp__details">
            <h2 className="h3">Details</h2>
            <dl className="specs">
              <div><dt>Style</dt><dd>{product.garment_type}</dd></div>
              {product.colors.length > 0 && <div><dt>Colors</dt><dd className="cap">{listPhrase(product.colors)}</dd></div>}
              <div><dt>Item</dt><dd><code>{product.product_id}</code></dd></div>
              <div>
                <dt>Stock by size</dt>
                <dd className="stock-grid">
                  {product.inventory.map((s) => (
                    <span key={s.size} className={s.quantity === 0 ? 'is-out' : s.quantity <= LOW_STOCK ? 'is-low' : ''}>
                      <b>{s.size}</b>{s.quantity === 0 ? 'Sold out' : `${s.quantity} left`}
                    </span>
                  ))}
                </dd>
              </div>
            </dl>
            {product.search_tags.length > 0 && (
              <p className="tags">Good for: {product.search_tags.slice(0, 8).join(' · ')}</p>
            )}
          </section>
        </div>

        <aside className="pdp__panel" aria-label="Purchase options">
          <p className="eyebrow">{product.category} · Officially licensed</p>
          <h1 className="pdp__name">{name}</h1>
          <p className="pdp__price">{formatPrice(product.price)}</p>

          <div className="pdp__desc">
            <p>{product.description}</p>
            <p className="muted">
              This {product.garment_type.toLowerCase()} is part of our {product.category.toLowerCase()} lineup.
              {product.colors.length > 0 && ` It comes in ${listPhrase(product.colors.map((c) => c.toLowerCase()))}.`}
              {soldOut.length > 0 && inStock.length > 0 && ` Sold out right now in ${listPhrase(soldOut)}.`}
            </p>
          </div>

          {product.colors.length > 0 && (
            <div className="swatches" aria-label="Colors">
              {product.colors.map((c) => (
                <span key={c} className="swatch" title={c}><span className="swatch__dot" style={{ background: swatchFor(c) }} />{c}</span>
              ))}
            </div>
          )}

          <div className="field-group">
            <div className="field-group__label">
              <span>Size</span>
              {mySize && <span className="muted">My size: {mySize}</span>}
            </div>
            <div className="sizes" role="radiogroup" aria-label="Size">
              {product.inventory.map((s) => (
                <button key={s.size} role="radio" aria-checked={size === s.size}
                  className={`size ${size === s.size ? 'is-active' : ''} ${s.quantity === 0 ? 'is-out' : ''}`}
                  onClick={() => { setSize(s.size); setQty(1) }}>
                  {s.size}
                </button>
              ))}
            </div>
            <p className={`stock-line stock-line--${stockLine.tone}`} role="status">{stockLine.text}</p>
          </div>

          <div className="buy">
            <div className="stepper" aria-label="Quantity">
              <button onClick={() => setQty((q) => Math.max(1, q - 1))} disabled={qty <= 1 || maxQty === 0} aria-label="Fewer"><Icon name="minus" size={16} /></button>
              <span>{maxQty === 0 ? 0 : qty}</span>
              <button onClick={() => setQty((q) => Math.min(maxQty, q + 1))} disabled={qty >= maxQty} aria-label="More"><Icon name="plus" size={16} /></button>
            </div>
            <button className="btn btn--primary btn--grow" disabled={!selected || maxQty === 0}
              onClick={() => selected && add({ product_id: product.product_id, name: product.name, price: product.price, image_url: product.image_url, size: selected.size, max: selected.quantity }, qty)}>
              {maxQty === 0 ? 'Sold out in this size' : `Add to bag · ${formatPrice(product.price * qty)}`}
            </button>
          </div>
          <button className="btn btn--ghost btn--block" onClick={() => openChat(`Is the ${name} a good fit for me? What sizes are in stock?`)}>
            <Icon name="chat" size={18} /> Ask about this item
          </button>

          <ul className="pdp__assure">
            <li>30-day returns on unworn items with tags</li>
            <li>Pick up at 57 Broadway, New Haven</li>
            <li>Questions? orderdept@campuscustoms.com</li>
          </ul>
        </aside>
      </div>

      <section className="collection" aria-labelledby="also-like">
        <header className="section-head">
          <div>
            <h2 id="also-like" className="h2">You might also like</h2>
            <p className="muted">{mySize ? `Similar styles, in stock in your size (${mySize}) first.` : 'Similar styles from the shop.'}</p>
          </div>
        </header>
        {similar === null ? (
          <div className="rail">{Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton tile-skeleton" />)}</div>
        ) : similar.length > 0 ? (
          <div className="rail rail--four">{similar.map((p) => <ProductCard key={p.product_id} product={p} compact />)}</div>
        ) : (
          <p className="muted">No similar styles right now.</p>
        )}
      </section>
    </div>
  )
}
