import { Link } from 'react-router-dom'

export default function Footer() {
  return (
    <footer className="footer">
      <div className="footer__inner">
        <div className="footer__brand">
          <span className="wordmark__name">Campus Customs</span>
          <p className="muted">Officially licensed Yale apparel. Family-run in New Haven since 1975.</p>
        </div>
        <nav className="footer__col" aria-label="Shop">
          <h4>Shop</h4>
          <Link to="/products">All products</Link>
          <Link to="/products?collection=game-day">Game Day</Link>
          <Link to="/products?collection=residential-colleges">Residential Colleges</Link>
          <Link to="/products?collection=gifts">Gifts</Link>
        </nav>
        <nav className="footer__col" aria-label="Help">
          <h4>Help</h4>
          <Link to="/about">About us</Link>
          <Link to="/about#returns">Returns</Link>
          <Link to="/login">Log in</Link>
          <Link to="/signup">Create account</Link>
        </nav>
        <div className="footer__col">
          <h4>Visit</h4>
          <span>57 Broadway, New Haven, CT 06511</span>
          <a href="mailto:orderdept@campuscustoms.com">orderdept@campuscustoms.com</a>
          <span>(475) 301-4205</span>
        </div>
      </div>
    </footer>
  )
}
