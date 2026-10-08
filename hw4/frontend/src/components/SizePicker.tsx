import { SIZES, useSize, type Size } from './sizeState'

// "My size" picker: a glossy segmented control plus a switch that chooses whether items
// not in stock in that size are grayed out or hidden. Used on the Products page and
// on the chat results shelf; the choice is shared site-wide.
export default function SizePicker({ compact = false }: { compact?: boolean }) {
  const { size, mode, setSize, setMode } = useSize()
  return (
    <div className={`size-pref ${compact ? 'size-pref--compact' : ''}`}>
      <span className="size-pref__label">My size</span>
      <div className="segmented segmented--sizes" role="radiogroup" aria-label="My size">
        <button role="radio" aria-checked={size === null} className={`segmented__btn ${size === null ? 'is-active' : ''}`} onClick={() => setSize(null)}>
          Any
        </button>
        {SIZES.map((s: Size) => (
          <button key={s} role="radio" aria-checked={size === s} className={`segmented__btn ${size === s ? 'is-active' : ''}`} onClick={() => setSize(s)}>
            {s}
          </button>
        ))}
      </div>
      {size && (
        <label className="toggle" title="Items not in stock in your size">
          <input type="checkbox" checked={mode === 'hide'} onChange={(e) => setMode(e.target.checked ? 'hide' : 'gray')} />
          <span className="toggle__track"><span className="toggle__knob" /></span>
          <span className="toggle__label">{mode === 'hide' ? `Hiding items without ${size}` : `Graying out items without ${size}`}</span>
        </label>
      )}
    </div>
  )
}
