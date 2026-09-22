import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CalendarDays, RefreshCw, Search, Soup, Trash2, UtensilsCrossed, Wallet } from 'lucide-react'
import { api, list, money, today } from '../api'
import AppModal from '../components/AppModal'
import { useI18n } from '../i18n'
import { useSession } from '../session'
import { CardsSkeleton, TableSkeleton } from '../components/Skeleton'
import type { Dish, StaffMeal, StaffMealBoard } from '../types'

/**
 * Hodimlar ovqati: o'z oshxonamizdan yegan taom.
 *
 * Pul olinmaydi va bu hech kimning oyligiga ta'sir qilmaydi — yozuvning
 * butun maqsadi «oyiga qancha ketyapti» degan savolga javob berish.
 *
 * Kim yegani ro'yxatdan tanlanmaydi, izohda yoziladi: mehmon ham kelishi
 * mumkin, bir kishi boshqasi uchun olishi ham mumkin, va ro'yxat bu
 * ikkalasini ham ushlay olmasdi.
 */
export default function StaffMealsPage() {
  const { t, tn } = useI18n()
  const { user } = useSession()
  const owner = user?.role === 'owner'
  const [params, setParams] = useSearchParams()

  const [board, setBoard] = useState<StaffMealBoard>()
  const [dishes, setDishes] = useState<Dish[]>([])
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)
  const [query, setQuery] = useState('')
  const [chosen, setChosen] = useState<Dish>()
  const [quantity, setQuantity] = useState('1')
  const [note, setNote] = useState('')
  const [key, setKey] = useState('')
  const [removing, setRemoving] = useState<StaffMeal>()

  const start = params.get('start') || `${today().slice(0, 8)}01`
  const end = params.get('end') || today()

  const load = useCallback(async () => {
    setError('')
    try {
      setBoard(await api<StaffMealBoard>(`staff-meals/?${new URLSearchParams({ start, end })}`))
    } catch (exception) {
      setError((exception as Error).message)
    }
  }, [start, end])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    list<Dish>('dishes/').then(setDishes).catch(() => setDishes([]))
  }, [])

  const menu = useMemo(
    () => dishes
      .filter(dish => !dish.archived)
      .filter(dish => dish.name.toLocaleLowerCase().includes(query.toLocaleLowerCase())),
    [dishes, query],
  )

  function choose(dish: Dish) {
    setChosen(dish)
    // Kalit oyna ochilganda tug'iladi: ikki marta bosilsa ham bitta yozuv.
    setKey(crypto.randomUUID())
    setQuantity('1')
    setNote('')
    setFormError('')
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!chosen || busy) return
    setBusy(true)
    setFormError('')
    try {
      await api('staff-meals/', {
        method: 'POST',
        body: JSON.stringify({ key, dish: chosen.id, quantity: Number(quantity), note }),
      })
      setChosen(undefined)
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!removing || busy) return
    setBusy(true)
    setFormError('')
    try {
      await api(`staff-meals/${removing.id}/`, { method: 'DELETE' })
      setRemoving(undefined)
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('O‘Z OSHXONAMIZDAN')}</span>
          <h1>{t('Hodimlar ovqati')}<span className="heading-dot">.</span></h1>
          <p>{t('Kim nima yegani va u bizga nechchiga tushgani. Oyliklarga ta’sir qilmaydi.')}</p>
        </div>
        <div className="heading-actions">
          <button className="button secondary" disabled={!board} onClick={() => load()}>
            <RefreshCw size={17} className={board ? undefined : 'spin'} />{t('Yangilash')}
          </button>
        </div>
      </div>

      {error && <p className="alert error">{error}</p>}

      <section className="panel report-filters">
        <header>
          <CalendarDays size={19} />
          <div>
            <h2>{t('Davr')}</h2>
            <p>{t('Sanani o‘zgartiring — pastdagi raqamlar o‘sha davr uchun qayta hisoblanadi')}</p>
          </div>
        </header>
        <div className="report-filter-grid">
          <label>
            {t('Boshlanish')}
            <input
              value={start}
              onChange={event => setParams({ start: event.target.value, end }, { replace: true })}
              type="date"
              max={end}
              required
            />
          </label>
          <label>
            {t('Tugash')}
            <input
              value={end}
              onChange={event => setParams({ start, end: event.target.value }, { replace: true })}
              type="date"
              max={today()}
              required
            />
          </label>
        </div>
      </section>

      {!board && (
        <>
          <CardsSkeleton count={3} />
          <section className="panel"><TableSkeleton rows={4} columns={5} /></section>
        </>
      )}

      {board && (
        <div className="report-metrics">
          <article>
            <span className="metric-icon blue"><Soup /></span>
            <div>
              <small>{t('Yeyilgan porsiya')}</small>
              <strong>{board.summary.portions}</strong>
              <em>{tn('{count} ta yozuv', board.summary.records)}</em>
            </div>
          </article>
          <article>
            <span className="metric-icon orange"><Wallet /></span>
            <div>
              <small>{t('Bizga tushgan tannarx')}</small>
              <strong>{money(board.summary.cost)} <em>{t('so‘m')}</em></strong>
              <em>{t('foydadan aynan shu chiqadi')}</em>
            </div>
          </article>
          <article>
            <span className="metric-icon violet"><UtensilsCrossed /></span>
            <div>
              <small>{t('Menyu bo‘yicha qiymati')}</small>
              <strong>{money(board.summary.value)} <em>{t('so‘m')}</em></strong>
              <em>{t('sotilganda shuncha bo‘lardi')}</em>
            </div>
          </article>
        </div>
      )}

      {/* ── Taom tanlash: ro'yxat emas, bosiladigan kataklar ── */}
      <section className="panel spaced">
        <header className="panel-heading">
          <div>
            <h2><UtensilsCrossed size={17} /> {t('Taomni tanlang')}</h2>
            <p>{t('Taomni bosing, so‘ng nechta va kim yeganini yozing.')}</p>
          </div>
          <label className="search-field">
            <Search size={16} />
            <input
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder={t('Taom nomi')}
              aria-label={t('Taom qidirish')}
            />
          </label>
        </header>
        <div className="prep-grid meal-grid">
          {menu.map(dish => (
            <button key={dish.id} type="button" className="prep-tile meal-tile" onClick={() => choose(dish)}>
              <span className="prep-name">{dish.name}</span>
              <span className="prep-state">{money(dish.price)} {t('so‘m')}</span>
            </button>
          ))}
        </div>
        {!menu.length && (
          <div className="empty-state compact">
            <strong>{t('Bunday taom topilmadi')}</strong>
          </div>
        )}
      </section>

      {board && (
        <>
          <section className="panel spaced">
            <header className="panel-heading">
              <div>
                <h2>{t('Taomlar kesimi')}</h2>
                <p>{t('Qaysi taomdan qancha yeyilgan')}</p>
              </div>
            </header>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t('TAOM')}</th>
                    <th className="number">{t('PORSIYA')}</th>
                    <th className="number">{t('TANNARXI')}</th>
                  </tr>
                </thead>
                <tbody>
                  {board.dishes.map(row => (
                    <tr key={row.dish}>
                      <td><strong>{row.name}</strong></td>
                      <td className="number"><strong>{row.portions}</strong></td>
                      <td className="number">{money(row.cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!board.dishes.length && (
                <div className="empty-state compact">{t('Bu davrda yozuv yo‘q.')}</div>
              )}
            </div>
          </section>

          <section className="panel spaced">
            <header className="panel-heading">
              <div>
                <h2>{t('Yozuvlar')}</h2>
                <p>{t('Kim yegani izohda turadi — ro‘yxatdan tanlanmaydi.')}</p>
              </div>
              <span className="muted">{tn('{count} ta yozuv', board.rows.length)}</span>
            </header>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t('SANA')}</th>
                    <th>{t('TAOM')}</th>
                    <th className="number">{t('SONI')}</th>
                    <th>{t('KIM YEDI')}</th>
                    <th className="number">{t('TANNARXI')}</th>
                    <th>{t('KIRITDI')}</th>
                    {owner && <th />}
                  </tr>
                </thead>
                <tbody>
                  {board.rows.map(row => (
                    <tr key={row.id}>
                      <td>{row.date}</td>
                      <td>
                        <strong>{row.name}</strong>
                        <small>{money(row.menu_price)} {t('so‘m')}</small>
                      </td>
                      <td className="number">{row.quantity}</td>
                      <td>{row.note}</td>
                      <td className="number">
                        <strong>{money(row.cost_total)}</strong>
                        <small>{t('menyuda {amount}', { amount: money(row.value) })}</small>
                      </td>
                      <td><small>{row.actor_name}</small></td>
                      {owner && (
                        <td>
                          {row.date === today() && (
                            <button
                              className="table-action"
                              title={t('Yozuvni o‘chirish')}
                              onClick={() => { setFormError(''); setRemoving(row) }}
                            >
                              <Trash2 size={14} />
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
              {!board.rows.length && (
                <div className="empty-state">
                  <Soup size={34} strokeWidth={1.4} />
                  <strong>{t('Bu davrda yozuv yo‘q')}</strong>
                  <p>{t('Yuqoridan taomni tanlang va kim yeganini yozing.')}</p>
                </div>
              )}
            </div>
            <p className="data-note">
              {t('Yeyilgan ovqatning masallig‘i ombordan ayriladi va tannarxi foydadan chiqadi — lekin bu hech kimning oyligiga ta’sir qilmaydi.')}
            </p>
          </section>
        </>
      )}

      <AppModal
        open={!!chosen}
        title={t('{name} · hodimlar ovqati', { name: chosen?.name || '' })}
        onClose={() => { if (!busy) setChosen(undefined) }}
      >
        <form onSubmit={save}>
          <label>
            {t('Nechta porsiya')}
            <input
              value={quantity}
              onChange={event => setQuantity(event.target.value)}
              type="number"
              min="1"
              max="99"
              step="1"
              inputMode="numeric"
              required
              autoFocus
            />
          </label>
          <label>
            {t('Kim yedi')}
            <input
              value={note}
              onChange={event => setNote(event.target.value)}
              maxLength={200}
              minLength={2}
              required
              placeholder={t('Masalan, oshpaz Aziz · Dilnoza uchun')}
            />
            <small className="field-hint">
              {t('Ro‘yxatdan tanlanmaydi: mehmon ham bo‘lishi mumkin, bir kishi boshqasi uchun ham olishi mumkin.')}
            </small>
          </label>
          <div className="salary-amount">
            {money(Number(chosen?.price || 0) * Number(quantity || 0))} <small>{t('so‘m menyu bo‘yicha')}</small>
          </div>
          <p className="data-note">
            {t('Pul olinmaydi va oylikka ta’sir qilmaydi. Lekin masalliq ombordan ayriladi, chunki ovqat haqiqatda chiqadi.')}
          </p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? t('Saqlanmoqda…') : t('Yozib qo‘yish')}
          </button>
        </form>
      </AppModal>

      <AppModal
        open={!!removing}
        title={t('Yozuvni o‘chirish')}
        onClose={() => { if (!busy) setRemoving(undefined) }}
      >
        <p className="alert">
          {t('«{name}» · {count} porsiya · {note} — o‘chiriladi va masalliq omborga qaytariladi.', {
            name: removing?.name || '', count: removing?.quantity || 0, note: removing?.note || '',
          })}
        </p>
        {formError && <p className="alert error">{formError}</p>}
        <button className="button danger full" disabled={busy} onClick={remove}>
          {busy ? t('Saqlanmoqda…') : t('O‘chirish')}
        </button>
      </AppModal>
    </>
  )
}
