import { createContext, useContext } from 'react'

export const SIZES = ['XS', 'S', 'M', 'L', 'XL', 'XXL'] as const
export type Size = (typeof SIZES)[number]
export type SizeMode = 'gray' | 'hide' // what to do with items not in stock in the shopper's size

export interface SizeControls {
  size: Size | null
  mode: SizeMode
  setSize: (size: Size | null) => void
  setMode: (mode: SizeMode) => void
}

export const SizeCtx = createContext<SizeControls | null>(null)

export function useSize(): SizeControls {
  const ctx = useContext(SizeCtx)
  if (!ctx) throw new Error('useSize must be used inside <SizeProvider>')
  return ctx
}

/** Is a product (catalogue or chat card) in stock in this size? */
export function inStockIn(p: { inventory?: { size: string; quantity: number }[]; sizes_in_stock?: string[] }, size: Size): boolean {
  if (p.inventory) return p.inventory.some((s) => s.size === size && s.quantity > 0)
  return (p.sizes_in_stock ?? []).includes(size)
}
