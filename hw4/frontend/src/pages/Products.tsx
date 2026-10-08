import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import type { Product } from '../api'
import { CATEGORIES, collectionBySlug, searchProducts, useCatalog } from '../catalog'
import ProductCard from '../components/ProductCard'
import SizePicker from '../components/SizePicker'
import { inStockIn, useSize } from '../components/sizeState'

type Sort = 'featured' | 'price-asc' | 'price-desc' | 'name'

export default function Products() {
  const [params, setParams] = useSearchParams()
  const { products, error } = useCatalog()
  const [sort, setSort] = useState<Sort>('featured')
  const { size, mode } = useSize()
  const category = params.get('category')
  const collection = collectionBySlug(params.get('collection'))
  const q = params.get('q') ?? ''

  const title = q ? `Results for “${q}”` : collection ? collection.title : category ?? 'All products'
  const subtitle = q ? 'Matching names, descriptions, colleges, and teams.' : collection ? collection.blurb : 'Officially licensed Yale apparel, printed and stitched in New Haven.'

  const { list, hidden, base } = useMemo(() => {
    if (!products) return { list: [] as Product[], hidden: 0, base: 0 }
    let items = q ? searchProducts(products, q) : products
    if (collection) items = items.filter(collection.match)
    if (category) items = items.filter((p) => p.category === category)
    const sorters: Record<Sort, ((a: Product, b: Product) => number) | null> = {
      featured: q ? null : (a, b) => b.total_stock - a.total_stock,
      'price-asc': (a, b) => a.price - b.price || a.name.localeCompare(b.name),
      'price-desc': (a, b) => b.price - a.price || a.name.localeCompare(b.name),
      name: (a, b) => a.name.localeCompare(b.name),
    }
    const sorter = sorters[sort]
    const sorted = sorter ? [...items].sort(sorter) : items
    if (!size) return { list: sorted, hidden: 0, base: sorted.length }
    const fits = sorted.filter((p) => inStockIn(p, size))
    return mode === 'hide'
      ? { list: fits, hidden: sorted.length - fits.length, base: sorted.length }
      : { list: [...fits, ...sorted.filter((p) => !inStockIn(p, size))], hidden: 0, base: sorted.length }
  }, [products, q, collection, category, sort, size, mode])

  const setCategory = (c: string | null) => {
    const next = new URLSearchParams(params)
    if (c) next.set('category', c)
    else next.delete('category')
    setParams(next)
  }

  return (
    <div className="page listing">
      <header className="listing__head">
        <nav className="crumbs" aria-label="Breadcrumb"><Link to="/">Home</Link><span>/</span>{q || collection || category ? <Link to="/products">Shop</Link> : <span>Shop</span>}</nav>
        <h1 className="display display--sm">{title}</h1>
        <p className="muted">{subtitle}</p>
      </header>

      <div className="toolbar">
        <div className="tabs" role="tablist" aria-label="Category">
          <button role="tab" aria-selected={!category} className={`tab ${!category ? 'is-active' : ''}`} onClick={() => setCategory(null)}>All</button>
          {CATEGORIES.map((c) => (
            <button key={c} role="tab" aria-selected={category === c} className={`tab ${category === c ? 'is-active' : ''}`} onClick={() => setCategory(c)}>{c}</button>
          ))}
        </div>
        <div className="toolbar__right">
          <SizePicker compact />
          <label className="select-wrap">
            <span className="sr-only">Sort</span>
            <select className="select" value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
              <option value="featured">{q ? 'Best match' : 'Featured'}</option>
              <option value="price-asc">Price: low to high</option>
              <option value="price-desc">Price: high to low</option>
              <option value="name">Name A–Z</option>
            </select>
          </label>
        </div>
      </div>

      {error && <p className="notice notice--error">Couldn't load products: {error}</p>}
      {!products && !error && <div className="grid">{Array.from({ length: 8 }, (_, i) => <div key={i} className="skeleton tile-skeleton" />)}</div>}

      {products && (
        <>
          <p className="result-count" role="status">
            {list.length} {list.length === 1 ? 'style' : 'styles'}
            {size && mode === 'hide' && hidden > 0 && <> · {hidden} hidden (not in stock in {size})</>}
            {size && mode === 'gray' && base > 0 && <> · in stock in {size} first</>}
          </p>
          {list.length === 0 ? (
            <div className="empty">
              <p>No styles match. Try another search, clear the size filter, or <Link to="/products">browse everything</Link>.</p>
            </div>
          ) : (
            <div className="grid">{list.map((p) => <ProductCard key={p.product_id} product={p} />)}</div>
          )}
        </>
      )}
    </div>
  )
}
