import { useCallback, useEffect, useRef, useState } from 'react'
import { MapPin, X } from 'lucide-react'
import { money } from '../api'
import { useI18n } from '../i18n'
import type { Dish } from '../types'
import DishArt from './DishArt'

interface Props {
  dish: Dish
  onClose: () => void
}

const CLOSE_MS = 220
/** Shu masofadan ko'proq pastga tortilsa oyna yopiladi. */
const DRAG_CLOSE_PX = 100

/**
 * Taom tafsiloti: telefonda pastdan chiqadigan oyna, katta ekranda o'rtada.
 * Pastga tortib, fonga yoki ✕ ga bosib, Esc bilan yopiladi.
 */
export default function DishSheet({ dish, onClose }: Props) {
  const { t } = useI18n()
  const [closing, setClosing] = useState(false)
  const sheet = useRef<HTMLDivElement>(null)
  const closeButton = useRef<HTMLButtonElement>(null)
  const drag = useRef<{ startY: number; offset: number } | null>(null)

  const closed = useRef(false)

  const close = useCallback(() => {
    if (closed.current) return
    closed.current = true
    setClosing(true)
    window.setTimeout(onClose, CLOSE_MS)
  }, [onClose])

  useEffect(() => {
    const opener = document.activeElement as HTMLElement | null
    const root = document.documentElement
    const previous = root.style.overflow
    root.style.overflow = 'hidden'
    closeButton.current?.focus({ preventScroll: true })
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') close() }
    window.addEventListener('keydown', onKey)
    return () => {
      root.style.overflow = previous
      window.removeEventListener('keydown', onKey)
      opener?.focus?.({ preventScroll: true })
    }
  }, [close])

  // Pastga tortish: tepadagi tutqich va rasm ustida. Transform to'g'ridan-to'g'ri
  // yoziladi, har harakatda React qayta chizilmaydi — barmoq ortidan silliq ketadi.
  const onPointerDown = (event: React.PointerEvent) => {
    drag.current = { startY: event.clientY, offset: 0 }
    event.currentTarget.setPointerCapture(event.pointerId)
    sheet.current?.classList.add('is-dragging')
  }
  const onPointerMove = (event: React.PointerEvent) => {
    if (!drag.current || !sheet.current) return
    drag.current.offset = Math.max(0, event.clientY - drag.current.startY)
    sheet.current.style.transform = `translateY(${drag.current.offset}px)`
  }
  const onPointerUp = () => {
    const state = drag.current
    drag.current = null
    const element = sheet.current
    if (!state || !element) return
    element.classList.remove('is-dragging')
    if (state.offset > DRAG_CLOSE_PX) {
      close()
    } else {
      element.style.transform = ''
    }
  }

  return (
    <div className={`ds-backdrop${closing ? ' is-closing' : ''}`} onClick={close}>
      <div
        ref={sheet}
        className="ds-sheet"
        role="dialog"
        aria-modal="true"
        aria-label={dish.name}
        onClick={event => event.stopPropagation()}
      >
        <div
          className="ds-drag"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        >
          <span className="ds-grab" />
        </div>
        <button ref={closeButton} className="ds-close" onClick={close} aria-label={t('Yopish')}>
          <X size={20} />
        </button>
        <div className="ds-media">
          <DishArt name={dish.name} category={dish.category_name} image={dish.image} />
        </div>
        <div className="ds-body">
          <span className="ds-eyebrow">{dish.category_name}</span>
          <h2>{dish.name}</h2>
          {dish.description && <p className="ds-desc">{dish.description}</p>}
          <div className="ds-price">
            <strong>{money(dish.price)} <small>{t('so‘m')}</small></strong>
            {dish.portion && <span>{dish.portion}</span>}
          </div>
          {!dish.available && <p className="ds-off">{t('Hozir mavjud emas')}</p>}
          <p className="ds-hint"><MapPin size={15} /> {t('Buyurtma berish uchun ofitsiantga murojaat qiling.')}</p>
        </div>
      </div>
    </div>
  )
}
