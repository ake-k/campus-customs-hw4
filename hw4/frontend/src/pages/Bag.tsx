import { Link } from 'react-router-dom'
import { formatPrice } from '../api'
import { displayName } from '../catalog'
import { useBag } from '../components/bagState'
import Icon from '../components/Icon'

const STORE_EMAIL = 'orderdept@campuscustoms.com'

export default function Bag() {
  const { items, count, subtotal, setQty, remove } = useBag()

  // Online payment isn't connected yet, so checkout hands the order to the store by email.
  const orderEmail = `mailto:${STORE_EMAIL}?subject=${encodeURIComponent('Order request from campuscustoms website')}&body=${encodeURIComponent(
    `Hello Campus Customs,\n\nI'd like to order:\n${items
      .map((x) => `- ${displayName(x.name)}, size ${x.size}, qty ${x.qty} (${formatPrice(x.price)} each)`)
      .join('\n')}\n\nSubtotal: ${formatPrice(subtotal)}\n\nPlease let me know how to pay and whether to ship or hold for pickup at 57 Broadway.\n\nThank you!`,
  )}`

  return (
    <div className="page bag">
      <header className="listing__head">
        <h1 className="display display--sm">Your bag</h1>
        <p className="muted">{count === 0 ? 'Nothing here yet.' : `${count} ${count === 1 ? 'item' : 'items'}`}</p>
      </header>

      {items.length === 0 ? (
        <div className="empty">
          <p>Your bag is empty. Find something you love: hover over any product and tap your size to add it.</p>
          <Link to="/products" className="btn btn--primary">Start shopping</Link>
        </div>
      ) : (
        <div className="bag__layout">
          <ul className="bag__items">
            {items.map((x) => (
              <li key={`${x.product_id}-${x.size}`} className="bag__item">
                <Link to={`/products/${x.product_id}`} className="bag__thumb"><img src={x.image_url} alt="" /></Link>
                <div className="bag__info">
                  <Link to={`/products/${x.product_id}`} className="bag__name">{displayName(x.name)}</Link>
                  <span className="muted">Size {x.size} · {formatPrice(x.price)}</span>
                  {x.qty >= x.max && <span className="tile__note tile__note--low">That's all we have in {x.size}</span>}
                </div>
                <div className="stepper" aria-label={`Quantity of ${displayName(x.name)}`}>
                  <button onClick={() => setQty(x.product_id, x.size, x.qty - 1)} disabled={x.qty <= 1} aria-label="Fewer"><Icon name="minus" size={16} /></button>
                  <span>{x.qty}</span>
                  <button onClick={() => setQty(x.product_id, x.size, x.qty + 1)} disabled={x.qty >= x.max} aria-label="More"><Icon name="plus" size={16} /></button>
                </div>
                <span className="bag__line">{formatPrice(x.price * x.qty)}</span>
                <button className="bag__remove" onClick={() => remove(x.product_id, x.size)} aria-label={`Remove ${displayName(x.name)}`}>
                  <Icon name="close" size={18} />
                </button>
              </li>
            ))}
          </ul>

          <aside className="bag__summary">
            <div className="bag__row"><span>Subtotal</span><strong>{formatPrice(subtotal)}</strong></div>
            <p className="muted small">Shipping and tax are confirmed by the store.</p>
            <a href={orderEmail} className="btn btn--primary btn--block">Send order to the store</a>
            <p className="muted small">
              Online payment isn't available on this site yet. Sending your order opens an email to {STORE_EMAIL} with
              your items filled in, and the store will reply with payment and pickup or shipping details. You can also call (475) 301-4205
              or visit 57 Broadway.
            </p>
            <Link to="/products" className="btn btn--link">Keep shopping <Icon name="arrow" size={16} /></Link>
          </aside>
        </div>
      )}
    </div>
  )
}
