// Typed helpers for the Campus Customs FastAPI backend (backend/main.py).

export interface SizeStock {
  size: string
  quantity: number
}

export interface Product {
  product_id: string
  name: string
  garment_type: string
  category: string
  description: string
  description_is_placeholder: boolean
  colors: string[]
  search_tags: string[]
  image_file_path: string
  image_url: string
  price: number
  inventory: SizeStock[]
  total_stock: number
}

export interface Category {
  name: string
  count: number
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail ?? `Request failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

export const fetchProducts = () => getJson<Product[]>('/api/products')
export const fetchProduct = (id: string) => getJson<Product>(`/api/products/${encodeURIComponent(id)}`)
export const fetchCategories = () => getJson<Category[]>('/api/categories')

export const formatPrice = (price: number) =>
  price.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

export type StockLevel = 'in' | 'low' | 'out'

export function stockLevel(quantity: number): StockLevel {
  if (quantity <= 0) return 'out'
  if (quantity <= 5) return 'low'
  return 'in'
}

/** Short one-line summary of per-size stock for product cards. */
export function stockSummary(p: Product): { level: StockLevel; label: string } {
  const available = p.inventory.filter((s) => s.quantity > 0)
  if (available.length === 0) return { level: 'out', label: 'Sold out' }
  if (available.length === p.inventory.length) return { level: 'in', label: 'All sizes in stock' }
  return { level: 'low', label: `${available.map((s) => s.size).join(' · ')} available` }
}

// Rough swatch colors for the color names used in the catalogue.
const SWATCHES: [string, string][] = [
  ['navy', '#1b2f63'],
  ['charcoal', '#3f4449'],
  ['dark heather', '#5a5f66'],
  ['heather', '#a4a9ae'],
  ['gray', '#9aa0a6'],
  ['grey', '#9aa0a6'],
  ['silver', '#c9ced3'],
  ['black', '#16181b'],
  ['white', '#ffffff'],
  ['cream', '#f3ead3'],
  ['ivory', '#f6f1e1'],
  ['oatmeal', '#e2d6bf'],
  ['royal', '#2451c7'],
  ['light blue', '#8cc4ff'],
  ['sky', '#8cc4ff'],
  ['blue', '#2266cc'],
  ['maroon', '#6d1f2f'],
  ['crimson', '#b3122e'],
  ['red', '#d42b2b'],
  ['pink', '#f59ac0'],
  ['coral', '#e8857a'],
  ['multicolor', 'conic-gradient(#e33, #fc3, #3c6, #39f, #93f, #e33)'],
  ['orange', '#f28a1e'],
  ['yellow', '#f5d23a'],
  ['gold', '#d9a92b'],
  ['green', '#2f9e44'],
  ['forest', '#24633a'],
  ['teal', '#1aa5a5'],
  ['purple', '#7a44c2'],
  ['brown', '#7a5230'],
  ['tan', '#c9a878'],
  ['khaki', '#bfae80'],
]

export function swatchFor(color: string): string {
  const c = color.toLowerCase()
  return SWATCHES.find(([k]) => c.includes(k))?.[1] ?? '#b8c2cc'
}

// ---------- Accounts ----------
// The session lives in an HttpOnly cookie set by the backend, so the browser
// sends it automatically and page scripts can never read it.

export interface User {
  id: number
  first_name: string
  last_name: string
  name: string
  email: string
  created_at: string
  preferred_size?: string | null
}

export interface SignupForm {
  first_name: string
  last_name: string
  email: string
  password: string
  confirm_password: string
}

async function sendJson<T>(url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new Error(data?.detail ?? `Request failed (${res.status})`)
  return data as T
}

export const fetchMe = () => getJson<{ user: User | null }>('/api/auth/me').then((d) => d.user)
export const login = (email: string, password: string) =>
  sendJson<{ user: User }>('/api/auth/login', { email, password }).then((d) => d.user)
export const signup = (form: SignupForm) => sendJson<{ user: User }>('/api/auth/signup', form).then((d) => d.user)
export const logout = () => sendJson<{ user: null }>('/api/auth/logout')

/** Save the size-picker choice to the logged-in shopper's account (PUT /api/me/preferences). */
export async function savePreferredSize(size: string | null): Promise<void> {
  const res = await fetch('/api/me/preferences', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ preferred_size: size }),
  })
  if (!res.ok) throw new Error('Could not save your size')
}

export type SimilarProduct = Product & { why_similar: string }

/** "You might also like": similar products, preferring ones in stock in `size`. */
export const fetchSimilar = (id: string, size: string | null, limit = 4) =>
  getJson<SimilarProduct[]>(`/api/products/${encodeURIComponent(id)}/similar?limit=${limit}${size ? `&size=${size}` : ''}`)
