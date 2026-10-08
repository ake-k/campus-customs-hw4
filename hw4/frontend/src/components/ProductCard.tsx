import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { formatPrice, type Product } from '../api'
import { displayName, useCatalog } from '../catalog'
import type { ProductCard as ChatProductCard } from '../chat'
import { useBag } from './bagState'
import { SIZES, inStockIn, useSize } from './sizeState'

// One product tile for both sources: catalogue products (/api/products) and the
// cards the chat agent returns (/api/chat results). Uniform photo, name, price,
// one-line description, a small stock note, and size buttons on hover that add
// straight to the bag. Clicking the tile opens /products/:id.
type CardSource = Product | ChatProductCard

const LOW = 5

function quantities(p: CardSource, catalog: Product[] | null): Record<string, number> | null {
  const full = 'inventory' in p ? p : catalog?.find((x) => x.product_id === p.product_id)
  return full ? Object.fromEntries(full.inventory.map((s) => [s.size, s.quantity])) : null
}

function stockNote(p: CardSource, qty: Record<string, number> | null, size: string | null): { text: string; tone: 'low' | 'out' } | null {
  if (qty) {
    if (size && size in qty) {
      if (qty[size] <= 0) return { text: `Sold out in ${size}`, tone: 'out' }
      if (qty[size] <= LOW) return { text: `Only ${qty[size]} left in ${size}`, tone: 'low' }
      return null
    }
    const total = Object.values(qty).reduce((a, b) => a + b, 0)
    if (total === 0) return { text: 'Sold out', tone: 'out' }
    const low = SIZES.find((s) => qty[s] > 0 && qty[s] <= LOW)
    return low ? { text: `Only ${qty[low]} left in ${low}`, tone: 'low' } : null
  }
  const n = 'sizes_in_stock' in p ? p.sizes_in_stock.length : SIZES.length
  return n === 0 ? { text: 'Sold out', tone: 'out' } : n < SIZES.length ? { text: 'Limited sizes', tone: 'low' } : null
}

interface Props {
  product: CardSource
  compact?: boolean
  onOpen?: () => void
  style?: CSSProperties
}

export default function ProductCard({ product, compact = false, onOpen, style }: Props) {
  const { size } = useSize()
  const { products: catalog } = useCatalog()
  const { add } = useBag()
  const qty = quantities(product, catalog)
  const fits = size ? inStockIn(product, size as (typeof SIZES)[number]) : null
  const note = stockNote(product, qty, size)
  const description = 'inventory' in product ? product.description : product.short_description
  const name = displayName(product.name)

  return (
    <article className={`tile ${compact ? 'tile--compact' : ''} ${fits === false ? 'tile--unavailable' : ''}`} style={style}>
      <div className="tile__frame">
      <Link to={`/products/${product.product_id}`} className="tile__media" onClick={onOpen}
        aria-label={fits === false ? `${name}, sold out in ${size}` : name}>
        <img src={product.image_url} alt={name} loading="lazy" />
        {size && <span className={`tile__flag ${fits ? 'is-ok' : 'is-out'}`}>{fits ? `${size} in stock` : `Sold out in ${size}`}</span>}
      </Link>
      {qty && (
        <div className="tile__sizes" aria-label={`Quick add ${name}`}>
          {SIZES.map((s) => {
            const n = qty[s] ?? 0
            return (
              <button key={s} disabled={n <= 0} className={s === size ? 'is-mine' : ''}
                title={n > 0 ? `Add size ${s} to bag` : `${s} sold out`}
                onClick={() => add({ product_id: product.product_id, name: product.name, price: product.price, image_url: product.image_url, size: s, max: n })}>
                {s}
              </button>
            )
          })}
        </div>
      )}
      </div>
      <Link to={`/products/${product.product_id}`} className="tile__info" onClick={onOpen}>
        <h3 className="tile__name">{name}</h3>
        {!compact && <p className="tile__desc">{description}</p>}
        <div className="tile__meta">
          <span className="tile__price">{formatPrice(product.price)}</span>
          {note && <span className={`tile__note tile__note--${note.tone}`}>{note.text}</span>}
        </div>
      </Link>
    </article>
  )
}
