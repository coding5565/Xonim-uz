import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react'
import { useI18n } from '../i18n'
import './MenuIntro.css'

interface Props {
  /** Taom rasmlari. Menyu kelishi bilan shu yerga tushadi — kirish animatsiyasi uni kutmaydi. */
  images: string[]
  /** Parda ochila boshlaganda: menyu o'z kirish animatsiyasini shu paytda boshlaydi. */
  onExit: () => void
  /** Parda to'liq ochildi, qatlam olib tashlanadi. */
  onDone: () => void
}

/** Logotip o'rnashib bo'lmaguncha likopchalar chiqmaydi. */
const PLATES_NOT_BEFORE = 650
/** Rasmlar shu vaqtgacha tayyor bo'lmasa, likopchasiz davom etamiz (sekin internet). */
const PLATES_GIVE_UP = 1800
/** Likopchalar uchib kirgach, parda ochilguncha ushlab turish. */
const HOLD_WITH_PLATES = 1250
/** Likopchasiz bo'lsa: rasm kutishdan voz kechgandan keyin qancha turish. */
const HOLD_WITHOUT_PLATES = 350
const CURTAIN_MS = 1150
const MIN_PLATES = 3

const LETTERS = ['X', 'O', 'N', 'I', 'M']

/**
 * Chang zarralari: joyi va tezligi qo'lda yozilgan, har chizilganda tasodifiy
 * son olinmaydi — shuning uchun qayta chizilsa ham sakramaydi.
 */
const DUST = Array.from({ length: 16 }, (_, i) => ({
  x: ((i * 37 + 11) % 100),
  size: 2 + ((i * 5) % 4),
  rise: 40 + ((i * 13) % 45),
  drift: ((i * 29) % 40) - 20,
  delay: ((i * 0.37) % 3.2).toFixed(2),
  duration: (3.6 + ((i * 7) % 28) / 10).toFixed(1),
}))

function preload(urls: string[]): Promise<string[]> {
  return Promise.all(urls.map(url => new Promise<string | null>(resolve => {
    const image = new Image()
    const timer = window.setTimeout(() => resolve(null), 2000)
    const finish = (ok: boolean) => { window.clearTimeout(timer); resolve(ok ? url : null) }
    image.src = url
    // decode() — rasmni oldindan ochib qo'yadi, aks holda likopcha uchib
    // kirayotgan paytda telefon uni shu zahoti ochib, animatsiya uzilib qoladi.
    image.decode().then(() => finish(true), () => finish(false))
  }))).then(list => list.filter((url): url is string => url !== null))
}

export default function MenuIntro({ images, onExit, onDone }: Props) {
  const { t } = useI18n()
  const [leaving, setLeaving] = useState(false)
  const [plates, setPlates] = useState<string[]>([])
  const [gaveUp, setGaveUp] = useState(false)
  const hasPlates = plates.length > 0

  const left = useRef(false)

  const leave = useCallback(() => {
    if (left.current) return
    left.current = true
    setLeaving(true)
    onExit()
  }, [onExit])

  // Animatsiya paytida sahifa suriladigan bo'lmasin.
  useEffect(() => {
    const root = document.documentElement
    const previous = root.style.overflow
    root.style.overflow = 'hidden'
    const timer = window.setTimeout(() => setGaveUp(true), PLATES_GIVE_UP)
    return () => {
      root.style.overflow = previous
      window.clearTimeout(timer)
    }
  }, [])

  useEffect(() => {
    if (images.length < MIN_PLATES) return
    const startedAt = performance.now()
    let alive = true
    let timer = 0
    preload(images).then(ready => {
      if (!alive || ready.length < MIN_PLATES) return
      const elapsed = performance.now() - startedAt
      timer = window.setTimeout(() => alive && setPlates(ready), Math.max(0, PLATES_NOT_BEFORE - elapsed))
    })
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [images])

  useEffect(() => {
    if (!hasPlates || leaving) return
    const timer = window.setTimeout(leave, HOLD_WITH_PLATES)
    return () => window.clearTimeout(timer)
  }, [hasPlates, leaving, leave])

  useEffect(() => {
    if (hasPlates || !gaveUp || leaving) return
    const timer = window.setTimeout(leave, HOLD_WITHOUT_PLATES)
    return () => window.clearTimeout(timer)
  }, [hasPlates, gaveUp, leaving, leave])

  useEffect(() => {
    if (!leaving) return
    const timer = window.setTimeout(onDone, CURTAIN_MS)
    return () => window.clearTimeout(timer)
  }, [leaving, onDone])

  return (
    // Istalgan joyga bosilsa o'tkazib yuboriladi.
    <div className={`mi-root${leaving ? ' is-leaving' : ''}`} onPointerDown={leave} aria-hidden="true">
      <div className="mi-curtain mi-top" />
      <div className="mi-curtain mi-bottom" />
      <div className="mi-stage">
        <div className="mi-glow" />
        <div className="mi-steam"><i /><i /><i /></div>
        <div className="mi-dust">
          {DUST.map((dust, index) => (
            <i
              key={index}
              style={{
                left: `${dust.x}%`,
                width: dust.size,
                height: dust.size,
                '--rise': `${dust.rise}dvh`,
                '--drift': `${dust.drift}px`,
                animationDelay: `${dust.delay}s`,
                animationDuration: `${dust.duration}s`,
              } as CSSProperties}
            />
          ))}
        </div>
        <div className="mi-board">
          <span className="mi-ring mi-ring-outer" />
          <span className="mi-ring mi-ring-inner" />
          <div className="mi-center">
            <div className="mi-mark">
              <span className="mi-x">x</span>
              <span className="mi-dot">
                <i /><i /><i />
              </span>
            </div>
            <div className="mi-name">
              {LETTERS.map((letter, index) => (
                <span key={letter + index} style={{ '--i': index } as CSSProperties}>{letter}</span>
              ))}
            </div>
            <span className="mi-sub">RESTAURANT</span>
          </div>
          {hasPlates && (
            <div className="mi-orbit">
              {plates.map((src, index) => {
                const angle = ((-90 + (360 / plates.length) * index) * Math.PI) / 180
                return (
                  <div
                    key={src}
                    className="mi-fly"
                    style={{
                      '--cx': Math.cos(angle).toFixed(4),
                      '--cy': Math.sin(angle).toFixed(4),
                      '--i': index,
                    } as CSSProperties}
                  >
                    <div className="mi-counter">
                      <div className="mi-plate"><img src={src} alt="" draggable={false} /></div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
        <p className="mi-tagline">{t('Ta’mlar')} {t('bir dasturxonda.')}</p>
      </div>
    </div>
  )
}
