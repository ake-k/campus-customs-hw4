import { useEffect, useState, type ReactNode } from 'react'
import { BagCtx, type BagItem } from './bagState'

const KEY = 'cc_bag'

function load(): BagItem[] {
  try {
    const items = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    return Array.isArray(items) ? items : []
  } catch {
    return []
  }
}

// Shopping bag kept in this browser (localStorage). Quantities are capped at the
// stock on hand for that size when the item was added.
export function BagProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<BagItem[]>(load)
  const [lastAdded, setLastAdded] = useState<BagItem | null>(null)

  useEffect(() => {
    localStorage.setItem(KEY, JSON.stringify(items))
  }, [items])
  useEffect(() => {
    if (!lastAdded) return
    const t = setTimeout(() => setLastAdded(null), 3200)
    return () => clearTimeout(t)
  }, [lastAdded])

  const same = (x: BagItem, item: Omit<BagItem, 'qty'>) => x.product_id === item.product_id && x.size === item.size
  const add = (item: Omit<BagItem, 'qty'>, qty = 1) => {
    const existing = items.find((x) => same(x, item))
    const next: BagItem = { ...item, qty: Math.min(item.max, (existing?.qty ?? 0) + qty) }
    setItems((list) => (existing ? list.map((x) => (same(x, item) ? next : x)) : [...list, next]))
    setLastAdded(next)
  }
  const setQty = (product_id: string, size: string, qty: number) =>
    setItems((list) => list.map((x) => (x.product_id === product_id && x.size === size ? { ...x, qty: Math.max(1, Math.min(x.max, qty)) } : x)))
  const remove = (product_id: string, size: string) => setItems((list) => list.filter((x) => !(x.product_id === product_id && x.size === size)))

  const count = items.reduce((n, x) => n + x.qty, 0)
  const subtotal = items.reduce((n, x) => n + x.qty * x.price, 0)
  return (
    <BagCtx.Provider value={{ items, count, subtotal, add, setQty, remove, clear: () => setItems([]), lastAdded }}>
      {children}
    </BagCtx.Provider>
  )
}
