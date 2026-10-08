import { useEffect, useRef, useState, type ReactNode } from 'react'
import { savePreferredSize } from '../api'
import { useAuth } from './authState'
import { SIZES, SizeCtx, type Size, type SizeMode } from './sizeState'

const SIZE_KEY = 'cc_size'
const MODE_KEY = 'cc_size_mode'

function stored<T extends string>(key: string, allowed: readonly T[]): T | null {
  const v = localStorage.getItem(key)
  return v && (allowed as readonly string[]).includes(v) ? (v as T) : null
}

// The shopper's size ("My size"). Guests: remembered in this browser (localStorage).
// Logged-in shoppers: saved to their account (users.preferred_size) so it follows them
// to any device; the agent also sees it.
export function SizeProvider({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth()
  const [size, setSizeState] = useState<Size | null>(() => stored(SIZE_KEY, SIZES))
  const [mode, setModeState] = useState<SizeMode>(() => stored(MODE_KEY, ['gray', 'hide'] as const) ?? 'gray')
  const syncedFor = useRef<number | null>(null)

  // On login: the account's saved size wins; if the account has none yet, save this browser's choice to it.
  useEffect(() => {
    if (!ready || !user || syncedFor.current === user.id) return
    syncedFor.current = user.id
    if (user.preferred_size) {
      // syncing with an external system (the account's saved size), which is what effects are for
      // eslint-disable-next-line react/set-state-in-effect
      setSizeState(user.preferred_size as Size)
      localStorage.setItem(SIZE_KEY, user.preferred_size)
    } else if (size) {
      void savePreferredSize(size).catch(() => {})
    }
  }, [ready, user, size])
  useEffect(() => {
    if (ready && !user) syncedFor.current = null
  }, [ready, user])

  const setSize = (next: Size | null) => {
    setSizeState(next)
    if (next) localStorage.setItem(SIZE_KEY, next)
    else localStorage.removeItem(SIZE_KEY)
    if (user) void savePreferredSize(next).catch(() => {})
  }
  const setMode = (next: SizeMode) => {
    setModeState(next)
    localStorage.setItem(MODE_KEY, next)
  }

  return <SizeCtx.Provider value={{ size, mode, setSize, setMode }}>{children}</SizeCtx.Provider>
}
