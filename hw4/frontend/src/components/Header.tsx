import { useEffect, useRef, useState, type ReactNode } from 'react'
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { formatPrice } from '../api'
import { displayName, searchProducts, shopMenu, useCatalog } from '../catalog'
import { useAuth } from './authState'
import { useBag } from './bagState'
import { useChat } from './chatState'
import Icon from './Icon'
import SizePicker from './SizePicker'
import { useSize } from './sizeState'

/** Closes a popover on outside click or Escape. */
function useDismiss(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && close()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && close()
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open, close])
  return ref
}

function Popover({ open, children, className = '' }: { open: boolean; children: ReactNode; className?: string }) {
  return open ? <div className={`popover ${className}`} role="dialog">{children}</div> : null
}

function SearchBox() {
  const { products } = useCatalog()
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const close = () => setOpen(false)
  const ref = useDismiss(open, close)
  const hits = products && q.trim().length >= 2 ? searchProducts(products, q).slice(0, 6) : []
  const total = products && q.trim().length >= 2 ? searchProducts(products, q).length : 0

  function go(to: string) {
    setOpen(false)
    setQ('')
    setActive(-1)
    navigate(to)
  }
  function onKey(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive((a) => Math.min(hits.length - 1, a + 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(-1, a - 1)) }
    else if (e.key === 'Enter' && q.trim()) {
      e.preventDefault()
      go(active >= 0 && hits[active] ? `/products/${hits[active].product_id}` : `/products?q=${encodeURIComponent(q.trim())}`)
    }
  }

  return (
    <div className="search" ref={ref}>
      <Icon name="search" size={18} className="search__icon" />
      <input
        className="search__input"
        type="search"
        value={q}
        placeholder="Search hoodies, colleges, teams…"
        aria-label="Search products"
        aria-expanded={open && q.trim().length >= 2}
        onChange={(e) => { setQ(e.target.value); setOpen(true); setActive(-1) }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKey}
      />
      {open && q.trim().length >= 2 && (
        <div className="suggest" role="listbox">
          {hits.length === 0 ? (
            <div className="suggest__empty">No matches for “{q}”. Try a college, sport, or color.</div>
          ) : (
            hits.map((p, i) => (
              <button key={p.product_id} role="option" aria-selected={i === active}
                className={`suggest__item ${i === active ? 'is-active' : ''}`}
                onMouseEnter={() => setActive(i)} onClick={() => go(`/products/${p.product_id}`)}>
                <img src={p.image_url} alt="" />
                <span className="suggest__name">{displayName(p.name)}<small>{p.category}</small></span>
                <span className="suggest__price">{formatPrice(p.price)}</span>
              </button>
            ))
          )}
          {total > 0 && (
            <button className="suggest__all" onClick={() => go(`/products?q=${encodeURIComponent(q.trim())}`)}>
              See all {total} results <Icon name="arrow" size={16} />
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function ShopMenu() {
  const { products } = useCatalog()
  const [open, setOpen] = useState(false)
  const close = () => setOpen(false)
  const ref = useDismiss(open, close)
  const menu = products ? shopMenu(products) : null

  return (
    <div className="shopmenu" ref={ref} onMouseLeave={close}>
      <button className={`nav__link ${open ? 'is-open' : ''}`} aria-expanded={open} onClick={() => setOpen((o) => !o)} onMouseEnter={() => setOpen(true)}>
        Shop <Icon name="chevron" size={16} />
      </button>
      {open && menu && (
        <div className="mega" role="menu" onClick={(e) => (e.target as HTMLElement).closest('a') && close()}>
          <div className="mega__col">
            <h4>Clothing</h4>
            {menu.categories.map((l) => <Link key={l.label} to={l.to}>{l.label}</Link>)}
            <Link to="/products" className="mega__all">All products <Icon name="arrow" size={14} /></Link>
          </div>
          <div className="mega__col">
            <h4>Collections</h4>
            {menu.collections.map((l) => <Link key={l.label} to={l.to}>{l.label}</Link>)}
          </div>
          <div className="mega__col">
            <h4>Residential Colleges</h4>
            <div className="mega__grid">{menu.colleges.map((l) => <Link key={l.label} to={l.to}>{l.label}</Link>)}</div>
          </div>
          <div className="mega__col">
            <h4>Teams</h4>
            <div className="mega__grid">{menu.sports.map((l) => <Link key={l.label} to={l.to}>{l.label}</Link>)}</div>
          </div>
        </div>
      )}
    </div>
  )
}

function IconButton(props: { label: string; icon: Parameters<typeof Icon>[0]['name']; onClick: () => void; badge?: ReactNode; active?: boolean }) {
  return (
    <button className={`iconbtn ${props.active ? 'is-active' : ''}`} onClick={props.onClick} aria-label={props.label} title={props.label}>
      <Icon name={props.icon} size={21} />
      {props.badge !== undefined && <span className="iconbtn__badge">{props.badge}</span>}
    </button>
  )
}

export default function Header() {
  const { user, ready, logOut } = useAuth()
  const { size } = useSize()
  const { isOpen, openChat, closeChat } = useChat()
  const { count, lastAdded } = useBag()
  const navigate = useNavigate()
  const location = useLocation()
  const [menu, setMenu] = useState<'account' | 'size' | null>(null)
  const close = () => setMenu(null)
  const accountRef = useDismiss(menu === 'account', close)
  const sizeRef = useDismiss(menu === 'size', close)

  return (
    <header className="header">
      <div className="header__inner">
        <Link to="/" className="wordmark" aria-label="Campus Customs home">
          <span className="wordmark__name">Campus Customs</span>
          <span className="wordmark__sub">Yale Bulldog Blue · New Haven</span>
        </Link>

        <nav className="nav" aria-label="Main">
          <ShopMenu />
          <NavLink to="/products?collection=gifts" className={() => `nav__link ${location.search.includes('collection=gifts') ? 'active' : ''}`}>Gifts</NavLink>
          <NavLink to="/about" className="nav__link">About Us</NavLink>
        </nav>

        <SearchBox />

        <div className="header__icons">
          <div className="anchor" ref={accountRef}>
            <IconButton label={user ? `Account: ${user.first_name}` : 'Account'} icon="user" active={!!user} onClick={() => setMenu(menu === 'account' ? null : 'account')} />
            <Popover open={menu === 'account'} className="popover--account">
              {ready && user ? (
                <>
                  <p className="popover__title">Hi, {user.first_name}</p>
                  <p className="popover__muted">{user.email}</p>
                  <button className="btn btn--ghost btn--block" onClick={() => { close(); void logOut().then(() => navigate('/')) }}>Log out</button>
                </>
              ) : (
                <>
                  <p className="popover__title">Welcome</p>
                  <p className="popover__muted">Save your size and pick up your chats on any device.</p>
                  <Link to="/login" state={{ from: location.pathname }} className="btn btn--primary btn--block" onClick={close}>Log in</Link>
                  <Link to="/signup" className="btn btn--ghost btn--block" onClick={close}>Create account</Link>
                </>
              )}
            </Popover>
          </div>

          <div className="anchor" ref={sizeRef}>
            <button className={`sizebtn ${size ? 'is-set' : ''}`} onClick={() => setMenu(menu === 'size' ? null : 'size')} aria-label="My size" title="My size">
              <Icon name="size" size={21} />
              <span>{size ?? 'Size'}</span>
            </button>
            <Popover open={menu === 'size'} className="popover--size">
              <p className="popover__title">My size</p>
              <p className="popover__muted">We’ll show what’s in stock in your size everywhere you shop{user ? ' and save it to your account' : ''}.</p>
              <SizePicker />
            </Popover>
          </div>

          <button className={`askbtn ${isOpen ? 'is-active' : ''}`} onClick={() => (isOpen ? closeChat() : openChat())} aria-label="Ask the Bulldog, our shopping assistant">
            <Icon name="chat" size={20} /> <span>Ask</span>
          </button>

          <div className="anchor">
            <IconButton label={`Bag (${count} items)`} icon="bag" onClick={() => navigate('/bag')} badge={count > 0 ? count : undefined} />
            {lastAdded && (
              <div className="toast" role="status">
                <img src={lastAdded.image_url} alt="" />
                <div>
                  <strong>Added to bag</strong>
                  <span>{displayName(lastAdded.name)} · {lastAdded.size}</span>
                </div>
                <Link to="/bag" className="toast__link">View bag</Link>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
