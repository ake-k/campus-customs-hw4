import { useEffect, useState, type ReactNode } from 'react'
import { fetchMe, login, logout, signup, type SignupForm, type User } from '../api'
import { AuthCtx } from './authState'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    fetchMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setReady(true))
  }, [])

  const logIn = async (email: string, password: string) => {
    const u = await login(email, password)
    setUser(u)
    return u
  }
  const signUp = async (form: SignupForm) => {
    const u = await signup(form)
    setUser(u)
    return u
  }
  const logOut = async () => {
    await logout()
    setUser(null)
  }

  return <AuthCtx.Provider value={{ user, ready, logIn, signUp, logOut }}>{children}</AuthCtx.Provider>
}
