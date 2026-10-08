// Shared catalogue data for the storefront: one cached fetch of /api/products,
// plus the curated collections and the "Shop" menu, all defined as filters over
// real catalogue fields (names, tags, categories) so every link has products.

import { useEffect, useState } from 'react'
import { fetchProducts, type Product } from './api'

let cache: Promise<Product[]> | null = null

export function loadCatalog(): Promise<Product[]> {
  if (!cache) cache = fetchProducts().catch((e) => { cache = null; throw e })
  return cache
}

export function useCatalog(): { products: Product[] | null; error: string } {
  const [products, setProducts] = useState<Product[] | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let live = true
    loadCatalog().then((p) => live && setProducts(p)).catch((e: Error) => live && setError(e.message))
    return () => { live = false }
  }, [])
  return { products, error }
}

const text = (p: Product) => [p.name, p.description, ...p.search_tags].join(' ').toLowerCase()

export const COLLEGES = [
  'Benjamin Franklin', 'Berkeley', 'Branford', 'Davenport', 'Ezra Stiles', 'Grace Hopper', 'Jonathan Edwards',
  'Morse', 'Pauli Murray', 'Pierson', 'Saybrook', 'Silliman', 'Timothy Dwight', 'Trumbull',
]
export const SPORTS = [
  'Baseball', 'Basketball', 'Diving', 'Fencing', 'Field Hockey', 'Football', 'Golf', 'Hockey', 'Lacrosse',
  'Sailing', 'Soccer', 'Squash', 'Swimming', 'Tennis', 'Track', 'Volleyball',
]
export const FAMILY = ['Mom', 'Dad', 'Grandma', 'Grandpa', 'Aunt', 'Uncle', 'Brother', 'Cousin']

const isCollege = (p: Product) => COLLEGES.some((c) => text(p).includes(c.toLowerCase()))
const isFamily = (p: Product) => FAMILY.some((f) => new RegExp(`\\b${f.toLowerCase()}\\b`).test(p.name.toLowerCase()))
const isGameDay = (p: Product) =>
  /the game|harvard|football/.test(text(p)) || /sports|left chest/i.test(p.name) && SPORTS.some((s) => p.name.toLowerCase().includes(s.toLowerCase()))

export interface Collection {
  slug: string
  title: string
  blurb: string
  match: (p: Product) => boolean
}

// "New This Season": the catalogue has no arrival dates, so this is a curated fall-layers edit.
export const COLLECTIONS: Collection[] = [
  { slug: 'game-day', title: 'Game Day', blurb: 'The Game, varsity teams, and stadium-ready tees.', match: isGameDay },
  { slug: 'residential-colleges', title: 'Residential Colleges', blurb: 'Crests and colors for the college you call home.', match: isCollege },
  { slug: 'gifts', title: 'Gifts', blurb: 'For the proud Yale mom, dad, grandparent, and more.', match: isFamily },
  {
    slug: 'new-this-season', title: 'New This Season', blurb: 'Fall layers for New Haven weather: quarter-zips, fleece, and jackets.',
    match: (p) => p.category === 'Quarter-Zips' || p.category === 'Jackets & Fleece',
  },
]

export const collectionBySlug = (slug: string | null) => COLLECTIONS.find((c) => c.slug === slug) ?? null

export const CATEGORIES = ['Hoodies', 'Crewnecks', 'T-Shirts', 'Quarter-Zips', 'Jackets & Fleece', 'Long Sleeves']

/** Groups for the "Shop" dropdown; only entries with at least one product are shown. */
export function shopMenu(products: Product[]) {
  const has = (q: string) => products.some((p) => text(p).includes(q.toLowerCase()))
  return {
    categories: CATEGORIES.map((c) => ({ label: c, to: `/products?category=${encodeURIComponent(c)}`, count: products.filter((p) => p.category === c).length })),
    collections: COLLECTIONS.map((c) => ({ label: c.title, to: `/products?collection=${c.slug}`, count: products.filter(c.match).length })),
    colleges: COLLEGES.filter(has).map((c) => ({ label: c, to: `/products?q=${encodeURIComponent(c)}` })),
    sports: SPORTS.filter((s) => products.some((p) => p.name.toLowerCase().includes(s.toLowerCase()))).map((s) => ({ label: s, to: `/products?q=${encodeURIComponent(s)}` })),
  }
}

/** Simple ranked search used by the live-suggest box and the Products page. */
export function searchProducts(products: Product[], query: string): Product[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean)
  if (!words.length) return products
  return products
    .map((p) => {
      const name = p.name.toLowerCase(), all = text(p) + ' ' + p.colors.join(' ').toLowerCase() + ' ' + p.category.toLowerCase()
      if (!words.every((w) => all.includes(w))) return null
      return { p, score: words.reduce((n, w) => n + (name.includes(w) ? 3 : 1), name.startsWith(words[0]) ? 2 : 0) }
    })
    .filter((x): x is { p: Product; score: number } => x !== null)
    .sort((a, b) => b.score - a.score || a.p.name.localeCompare(b.p.name))
    .map((x) => x.p)
}

/** Product names in the catalogue have odd spacing ("1 4 Zip"); show them cleanly. */
export function displayName(name: string): string {
  return name.replace(/\bVs\b/g, 'vs.').replace(/\b1 4 Zip\b/g, '1/4 Zip').replace(/\bT Shirt\b/g, 'T-Shirt').replace(/ \d$/, '').replace(/\bCreqneck\b/, 'Crewneck')
}
