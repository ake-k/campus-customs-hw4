import { Link } from 'react-router-dom'
import { formatPrice } from '../api'
import { CATEGORIES, COLLECTIONS, displayName, useCatalog } from '../catalog'
import { useChat } from '../components/chatState'
import Icon from '../components/Icon'
import ProductCard from '../components/ProductCard'
import { SIZES } from '../components/sizeState'

const FEATURED_ID = '2025-yale-vs-harvard-t-shirt'

export default function Home() {
  const { products, error } = useCatalog()
  const { openChat } = useChat()
  const featured = products?.find((p) => p.product_id === FEATURED_ID)

  return (
    <div className="page home">
      {/* Featured product */}
      <section className="feature">
        <Link to={featured ? `/products/${featured.product_id}` : '/products'} className="feature__media">
          {featured ? <img src={featured.image_url} alt={displayName(featured.name)} /> : <div className="skeleton feature__skeleton" />}
        </Link>
        <div className="feature__copy">
          <p className="eyebrow">Featured · The Game</p>
          <h1 className="display">Bulldogs vs. Crimson, 2025.</h1>
          {featured ? (
            <>
              <p className="lede">
                The {displayName(featured.name)}: heather gray, with Harvard and Yale helmets facing off for the 2025 Game.
                Printed for the stands and the tailgate.
              </p>
              <div className="feature__buy">
                <span className="feature__price">{formatPrice(featured.price)}</span>
                <span className="feature__sizes">
                  {SIZES.map((s) => {
                    const n = featured.inventory.find((x) => x.size === s)?.quantity ?? 0
                    return <span key={s} className={n > 0 ? '' : 'is-out'}>{s}</span>
                  })}
                </span>
              </div>
              <div className="feature__actions">
                <Link to={`/products/${featured.product_id}`} className="btn btn--primary">Shop the tee</Link>
                <Link to="/products?collection=game-day" className="btn btn--link">Explore Game Day <Icon name="arrow" size={16} /></Link>
              </div>
            </>
          ) : (
            <p className="lede">{error ? `Couldn't load the catalogue: ${error}` : 'Loading…'}</p>
          )}
        </div>
      </section>

      <ul className="assurances" aria-label="Why shop with us">
        <li><strong>Officially licensed</strong> Yale apparel</li>
        <li><strong>30-day returns</strong> on unworn items</li>
        <li><strong>57 Broadway</strong>, New Haven, since 1975</li>
      </ul>

      {/* Collection rows */}
      {products && COLLECTIONS.map((c) => {
        const items = products.filter(c.match)
        if (!items.length) return null
        return (
          <section key={c.slug} className="collection" aria-labelledby={`col-${c.slug}`}>
            <header className="section-head">
              <div>
                <h2 id={`col-${c.slug}`} className="h2">{c.title}</h2>
                <p className="muted">{c.blurb}</p>
              </div>
              <Link to={`/products?collection=${c.slug}`} className="btn btn--link">Shop all {items.length} <Icon name="arrow" size={16} /></Link>
            </header>
            <div className="rail">
              {items.slice(0, 8).map((p) => <ProductCard key={p.product_id} product={p} compact />)}
            </div>
          </section>
        )
      })}

      {/* Categories */}
      {products && (
        <section className="collection">
          <header className="section-head"><h2 className="h2">Shop by category</h2></header>
          <div className="categories">
            {CATEGORIES.map((c) => {
              const items = products.filter((p) => p.category === c)
              const cover = items.find((p) => !p.description_is_placeholder) ?? items[0]
              return (
                <Link key={c} to={`/products?category=${encodeURIComponent(c)}`} className="category">
                  {cover && <img src={cover.image_url} alt="" loading="lazy" />}
                  <span className="category__label">{c}<small>{items.length} styles</small></span>
                </Link>
              )
            })}
          </div>
        </section>
      )}

      <section className="concierge-cta">
        <div>
          <h2 className="h2">Not sure what to get?</h2>
          <p className="muted">Ask the Bulldog: it checks live stock in your size and finds gifts for every Yale fan.</p>
        </div>
        <button className="btn btn--primary" onClick={() => openChat('What would make a good gift for a Yale parent?')}>
          <Icon name="chat" size={18} /> Ask the Bulldog
        </button>
      </section>
    </div>
  )
}
