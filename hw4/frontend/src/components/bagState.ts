import { createContext, useContext } from 'react'

export interface BagItem {
  product_id: string
  name: string
  price: number
  image_url: string
  size: string
  qty: number
  max: number // units in stock in that size when added (can't add more than the shelf holds)
}

export interface BagControls {
  items: BagItem[]
  count: number
  subtotal: number
  add: (item: Omit<BagItem, 'qty'>, qty?: number) => void
  setQty: (product_id: string, size: string, qty: number) => void
  remove: (product_id: string, size: string) => void
  clear: () => void
  lastAdded: BagItem | null // drives the "Added to bag" confirmation
}

export const BagCtx = createContext<BagControls | null>(null)

export function useBag(): BagControls {
  const ctx = useContext(BagCtx)
  if (!ctx) throw new Error('useBag must be used inside <BagProvider>')
  return ctx
}
