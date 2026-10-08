import { createContext, useContext } from 'react'
import type { SignupForm, User } from '../api'

export interface AuthControls {
  user: User | null
  ready: boolean // false until we've asked the backend who is logged in
  logIn: (email: string, password: string) => Promise<User>
  signUp: (form: SignupForm) => Promise<User>
  logOut: () => Promise<void>
}

export const AuthCtx = createContext<AuthControls | null>(null)

export function useAuth(): AuthControls {
  const ctx = useContext(AuthCtx)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
