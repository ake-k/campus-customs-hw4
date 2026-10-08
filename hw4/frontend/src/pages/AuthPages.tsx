import { useState, type ChangeEvent, type FormEvent, type ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../components/authState'

// Account forms. The browser checks the basics for quick feedback; the backend
// re-checks everything and is the only place passwords are hashed and stored.

function AuthWindow(props: { title: string; children: ReactNode }) {
  return (
    <div className="page auth">
      <div className="auth-card">
        <p className="eyebrow">{props.title}</p>
        {props.children}
      </div>
    </div>
  )
}

function Notice({ tone, children }: { tone: 'info' | 'error'; children: ReactNode }) {
  return (
    <div className={`notice notice--${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      {children}
    </div>
  )
}

/** Shown on /login or /signup when someone is already signed in. */
function AlreadySignedIn({ title }: { title: string }) {
  const { user, logOut } = useAuth()
  const navigate = useNavigate()
  return (
    <AuthWindow title={title}>
      <h1 className="display display--sm">You're signed in, {user?.first_name}!</h1>
      <p className="muted">Logged in as <strong>{user?.email}</strong>.</p>
      <div className="auth-form">
        <Link to="/products" className="btn btn--primary btn--block">Keep shopping</Link>
        <button className="btn btn--ghost btn--block" onClick={() => void logOut().then(() => navigate('/login'))}>
          Log out
        </button>
      </div>
    </AuthWindow>
  )
}

// After login, send the shopper back where they came from (only same-site paths).
function useReturnPath(): string {
  const from = (useLocation().state as { from?: string } | null)?.from
  return from && from.startsWith('/') && !from.startsWith('//') && !['/login', '/signup'].includes(from) ? from : '/'
}

export function Login() {
  const { user, ready, logIn } = useAuth()
  const navigate = useNavigate()
  const returnTo = useReturnPath()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (ready && user) return <AlreadySignedIn title="Log in to Campus Customs" />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!email.trim() || !password) return setError('Please enter your email and password.')
    setBusy(true)
    setError('')
    try {
      await logIn(email, password)
      navigate(returnTo, { replace: true })
    } catch (err) {
      setError((err as Error).message)
      setPassword('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthWindow title="Log in to Campus Customs">
      <h1 className="display display--sm">Welcome back, Bulldog</h1>
      <p className="muted">Log in to pick up your chat and see items saved for you.</p>
      <form className="auth-form" onSubmit={onSubmit} noValidate>
        <label>
          <span className="label">Email</span>
          <input className="field" type="email" name="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@yale.edu" autoFocus />
        </label>
        <label>
          <span className="label">Password</span>
          <input className="field" type="password" name="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
        </label>
        {error && <Notice tone="error">{error}</Notice>}
        <button className="btn btn--primary btn--block" type="submit" disabled={busy}>
          {busy ? 'Logging in…' : 'Log in'}
        </button>
      </form>
      <p className="auth-switch">New here? <Link to="/signup">Create an account</Link></p>
    </AuthWindow>
  )
}

export function Signup() {
  const { user, ready, signUp } = useAuth()
  const navigate = useNavigate()
  const [justCreated, setJustCreated] = useState(false)
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '', password: '', confirm_password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const update = (k: keyof typeof form) => (e: ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value })

  const strength = Math.min(4, [/.{8,}/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter((r) => r.test(form.password)).length)

  if (ready && user && !justCreated) return <AlreadySignedIn title="Create your account" />

  if (justCreated && user) {
    return (
      <AuthWindow title="Create your account">
        <h1 className="display display--sm">Welcome to the family, {user.first_name}!</h1>
        <p className="muted">Your account is ready and you're signed in as <strong>{user.email}</strong>.</p>
        <div className="auth-form">
          <button className="btn btn--primary btn--block" onClick={() => navigate('/products')}>Start shopping</button>
        </div>
      </AuthWindow>
    )
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const message =
      !form.first_name.trim() || !form.last_name.trim() ? 'Please enter your first and last name.'
        : !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()) ? 'Please enter a valid email address.'
          : form.password.length < 8 ? 'Passwords need at least 8 characters.'
            : form.password !== form.confirm_password ? "Those passwords don't match."
              : ''
    if (message) return setError(message)
    setBusy(true)
    setError('')
    try {
      await signUp(form)
      setJustCreated(true)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthWindow title="Create your account">
      <h1 className="display display--sm">Join the Campus Customs family</h1>
      <p className="muted">An account lets our assistant remember you and your favorites.</p>
      <form className="auth-form" onSubmit={onSubmit} noValidate>
        <div className="auth-form__row">
          <label>
            <span className="label">First name</span>
            <input className="field" name="first_name" autoComplete="given-name" value={form.first_name} onChange={update('first_name')} autoFocus />
          </label>
          <label>
            <span className="label">Last name</span>
            <input className="field" name="last_name" autoComplete="family-name" value={form.last_name} onChange={update('last_name')} />
          </label>
        </div>
        <label>
          <span className="label">Email</span>
          <input className="field" type="email" name="email" autoComplete="email" value={form.email} onChange={update('email')} placeholder="you@yale.edu" />
        </label>
        <label>
          <span className="label">Password</span>
          <input className="field" type="password" name="password" autoComplete="new-password" value={form.password} onChange={update('password')} placeholder="At least 8 characters" />
          <div className="strength" aria-label={`Password strength ${strength} of 4`}>
            {[0, 1, 2, 3].map((i) => <span key={i} className={`strength__seg ${i < strength ? `is-on is-on--${strength}` : ''}`} />)}
          </div>
        </label>
        <label>
          <span className="label">Confirm password</span>
          <input className="field" type="password" name="confirm_password" autoComplete="new-password" value={form.confirm_password} onChange={update('confirm_password')} />
        </label>
        {error && <Notice tone="error">{error}</Notice>}
        <button className="btn btn--primary btn--block" type="submit" disabled={busy}>
          {busy ? 'Creating your account…' : 'Create account'}
        </button>
      </form>
      <p className="auth-switch">Already have an account? <Link to="/login">Log in</Link></p>
    </AuthWindow>
  )
}
