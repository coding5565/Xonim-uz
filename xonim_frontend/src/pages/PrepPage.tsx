import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { AlertTriangle, ChefHat, CircleCheck, ClipboardList, CookingPot, Search, Soup, Trash2 } from 'lucide-react'
import { api, dateLabel } from '../api'
import { useI18n } from '../i18n'
import { useSession } from '../session'
import type { PrepHistory, PrepLeftovers, PrepStatus } from '../types'
import AppModal from '../components/AppModal'
import { CardsSkeleton, TableSkeleton } from '../components/Skeleton'

/** Bugun oshxona nechta porsiya tayyorlagani va nechtasi qolgani.
 *
 * Kassir ertalab kiritadi, kun davomida yana qo'shadi. Qoldiq sotuv bilan
 * kamayadi va Kassa ekranida ham ko'rinadi. Miqdori kiritilmagan taom
 * cheklanmaydi — unutilgan bo'lsa restoran to'xtab qolmasligi kerak.
 */
export default function PrepPage() {
  const { t, tn } = useI18n()
  const { user } = useSession()
  const owner = user?.role === 'owner'

  const [status, setStatus] = useState<PrepStatus>()
  const [history, setHistory] = useState<PrepHistory>()
  const [leftovers, setLeftovers] = useState<PrepLeftovers>()
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)
  const [query, setQuery] = useState('')
  const [note, setNote] = useState('')
  // Kiritilayotgan miqdorlar: taom id -> matn. Bo'sh qatorlar yuborilmaydi.
  const [draft, setDraft] = useState<Record<number, string>>({})
  // O'chirish tasdig'i kutayotgan yozuv.
  const [removing, setRemoving] = useState<PrepHistory['rows'][number]>()

  const load = useCallback(async () => {
    try {
      const [loadedStatus, loadedHistory] = await Promise.all([
        api<PrepStatus>('dish-prep/'),
        api<PrepHistory>('dish-prep/history/'),
      ])
      setStatus(loadedStatus)
      setHistory(loadedHistory)
      if (owner) setLeftovers(await api<PrepLeftovers>('dish-prep/leftovers/'))
    } catch (exception) {
      setError((exception as Error).message)
    }
  }, [owner])

  useEffect(() => {
    load()
  }, [load])

  // `status?.dishes || []` har renderda yangi massiv yaratardi va quyidagi
  // useMemo hech qachon keshni ishlatmasdi. Endi bo'sh ro'yxat ham
  // barqaror bo'ladi.
  const dishes = useMemo(() => status?.dishes || [], [status])
  const filtered = useMemo(
    () => dishes.filter(row => row.name.toLocaleLowerCase().includes(query.toLocaleLowerCase())),
    [dishes, query],
  )
  const tracked = dishes.filter(row => row.tracked)
  const warnings = tracked.filter(row => row.out || row.low)
  const lines = Object.entries(draft)
    .map(([dish, value]) => ({ dish: Number(dish), quantity: Number(value), note }))
    .filter(line => line.quantity > 0)

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!lines.length || busy) return
    setBusy(true)
    setFormError('')
    try {
      // Javob allaqachon yangi holat — qayta so'rash shart emas.
      setStatus(await api<PrepStatus>('dish-prep/', { method: 'POST', body: JSON.stringify({ lines }) }))
      setDraft({})
      setNote('')
      setHistory(await api<PrepHistory>('dish-prep/history/'))
      if (owner) setLeftovers(await api<PrepLeftovers>('dish-prep/leftovers/'))
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  /** Xato kiritilgan partiyani olib tashlaydi. Faqat bugungi yozuv. */
  async function removeRow() {
    if (!removing || busy) return
    setBusy(true)
    setFormError('')
    try {
      setStatus(await api<PrepStatus>(`dish-prep/${removing.id}/`, { method: 'DELETE' }))
      setRemoving(undefined)
      setHistory(await api<PrepHistory>('dish-prep/history/'))
      if (owner) setLeftovers(await api<PrepLeftovers>('dish-prep/leftovers/'))
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const summary = status?.summary

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('OSHXONA HISOBI')}</span>
          <h1>{t('Tayyor taomlar')}<span className="heading-dot">.</span></h1>
          <p>{t('Bugun nechta porsiya pishirildi va nechtasi qoldi.')}</p>
        </div>
        {!!status && <span className="pill">{status.date}</span>}
      </div>

      {error && <p className="alert error">{error}</p>}

      {!status ? <CardsSkeleton count={4} /> : (
        <div className="metric-grid">
          <article className="metric-card tone-in">
            <div className="metric-top">
              <span>{t('Tayyorlangan')}</span>
              <span className="metric-icon green"><CookingPot size={19} /></span>
            </div>
            <div className="metric-value">{summary!.prepared}<small>{tn('porsiya', summary!.prepared)}</small></div>
            <p>{tn('{count} ta taom hisobda', summary!.tracked)}</p>
          </article>
          <article className="metric-card tone-out">
            <div className="metric-top">
              <span>{t('Sotilgan')}</span>
              <span className="metric-icon violet"><Soup size={19} /></span>
            </div>
            <div className="metric-value">{summary!.sold}<small>{tn('porsiya', summary!.sold)}</small></div>
            <p>{t('Ochiq hisoblar ham shu yerda')}</p>
          </article>
          <article className={`metric-card ${summary!.remaining ? 'tone-hero' : 'tone-flat'}`}>
            <div className="metric-top">
              <span>{t('Qolgan')}</span>
              <span className="metric-icon blue"><ChefHat size={19} /></span>
            </div>
            <div className="metric-value">{summary!.remaining}<small>{tn('porsiya', summary!.remaining)}</small></div>
            <p>{t('Hozir sotishga tayyor')}</p>
          </article>
          <article className={`metric-card ${summary!.out || summary!.low ? 'tone-hero-down' : 'tone-flat'}`}>
            <div className="metric-top">
              <span>{t('Diqqat talab')}</span>
              <span className="metric-icon orange">
                {summary!.out || summary!.low ? <AlertTriangle size={19} /> : <CircleCheck size={19} />}
              </span>
            </div>
            <div className="metric-value">{summary!.out + summary!.low}<small>{t('ta taom')}</small></div>
            <p>{t('{out} ta tugadi · {low} ta kam qoldi', { out: summary!.out, low: summary!.low })}</p>
          </article>
        </div>
      )}

      {!!warnings.length && (
        <div className="alert error" role="alert">
          <AlertTriangle size={20} />
          <span>
            <strong>{t('Tugayotgan taomlar:')}</strong>{' '}
            {warnings.map(row => row.out
              ? t('{name} — tugadi', { name: row.name })
              : t('{name} — {count} ta qoldi', { name: row.name, count: row.remaining })).join(' · ')}
          </span>
        </div>
      )}

      <section className="panel">
        <header className="panel-heading">
          <div>
            <h2>{t('Bugun nima tayyorlandi?')}</h2>
            <p>{t('Miqdorni yozing. Qayta kiritilsa ustiga yozilmaydi — qo‘shiladi.')}</p>
          </div>
          <div className="search-field">
            <Search size={17} />
            <input
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder={t('Taom nomini yozing…')}
              aria-label={t('Taom qidirish')}
            />
          </div>
        </header>
        {!status ? <TableSkeleton rows={5} columns={3} /> : (
          <form className="prep-form" onSubmit={save}>
            <div className="prep-grid">
              {filtered.map(row => (
                <label
                  key={row.dish}
                  className={`prep-tile${row.out ? ' out' : row.low ? ' low' : ''}`}
                >
                  <span className="prep-name">{row.name}</span>
                  {/* Hisobi yuritilmayotgan taomda yozadigan narsa yo'q: har
                      qatorda takrorlangan izoh ko'zni charchatadi. */}
                  <span className="prep-state">
                    {row.tracked
                      ? t('{prepared} dan {remaining} qoldi', { prepared: row.prepared, remaining: row.remaining })
                      : row.sold ? tn('{count} ta sotilgan', row.sold) : ''}
                  </span>
                  <input
                    value={draft[row.dish] ?? ''}
                    onChange={event => setDraft(previous => ({ ...previous, [row.dish]: event.target.value }))}
                    type="number"
                    min="0"
                    max="9999"
                    step="1"
                    inputMode="numeric"
                    placeholder="0"
                    aria-label={t('{name} uchun tayyorlangan miqdor', { name: row.name })}
                  />
                </label>
              ))}
            </div>
            {!filtered.length && (
              <div className="empty-state compact">
                <strong>{t('Bunday taom topilmadi')}</strong>
                <p>{t('Menyuni «Menyu boshqaruvi» bo‘limidan to‘ldiring.')}</p>
              </div>
            )}
            <label className="prep-note">
              {t('Izoh (ixtiyoriy)')}
              <input
                value={note}
                onChange={event => setNote(event.target.value)}
                maxLength={200}
                placeholder={t('Masalan, ertalabki partiya')}
              />
            </label>
            {formError && <p className="alert error">{formError}</p>}
            <button className="button primary full" disabled={!lines.length || busy}>
              {busy
                ? t('Saqlanmoqda…')
                : lines.length
                  ? tn('{count} ta taomni saqlash', lines.length)
                  : t('Miqdorni kiriting')}
            </button>
          </form>
        )}
      </section>

      <section className="panel">
        <header className="panel-heading">
          <div>
            <h2>{t('Bugungi holat')}</h2>
            <p>{t('Tayyorlangan − sotilgan = qoldiq')}</p>
          </div>
          <ClipboardList size={18} />
        </header>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t('TAOM')}</th>
                <th>{t('TAYYORLANGAN')}</th>
                <th>{t('SOTILGAN')}</th>
                <th>{t('QOLDIQ')}</th>
                <th>{t('HOLAT')}</th>
              </tr>
            </thead>
            <tbody>
              {tracked.map(row => (
                <tr key={row.dish}>
                  <td><strong>{row.name}</strong></td>
                  <td className="number">{row.prepared}</td>
                  <td className="number">{row.sold}</td>
                  <td className="number"><strong>{row.remaining}</strong></td>
                  <td>
                    <span className={`status ${row.out ? 'alert' : row.low ? 'open' : 'paid'}`}>
                      {row.remaining < 0
                        ? t('Ortiqcha sotilgan')
                        : row.out ? t('Tugadi') : row.low ? t('Kam qoldi') : t('Yetarli')}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!tracked.length && (
            <div className="empty-state">
              <CookingPot size={38} strokeWidth={1.3} />
              <h3>{t('Bugun hali hech narsa kiritilmagan')}</h3>
              <p>{t('Miqdor kiritilmagan taomlar cheklanmaydi — sotuv odatdagidek davom etadi.')}</p>
            </div>
          )}
        </div>
      </section>

      {owner && !!leftovers?.leftovers.length && (
        <section className="panel">
          <header className="panel-heading">
            <div>
              <h2>{t('Sotilmay qolgani')}</h2>
              <p>{t('Kun oxirida shu taomlar ortib qoladi — ertaga kamroq tayyorlash mumkin')}</p>
            </div>
            <span className="pill">{tn('{count} ta taom', leftovers.leftovers.length)}</span>
          </header>
          <div className="category-ranking">
            {leftovers.leftovers.map(row => (
              <div key={row.dish}>
                <div>
                  <strong>{row.name}</strong>
                  <span>{t('{prepared} tayyorlandi · {sold} sotildi', { prepared: row.prepared, sold: row.sold })}</span>
                  <b>{tn('{count} ta qoldi', row.remaining)}</b>
                </div>
                <div className="progress-track">
                  <span style={{ width: `${Math.round((row.remaining / Math.max(row.prepared, 1)) * 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="panel">
        <header className="panel-heading">
          <div><h2>{t('Bugun kim nima kiritdi')}</h2><p>{t('Har bir partiya alohida yozuv bo‘lib qoladi')}</p></div>
          <span className="pill subtle">{tn('{count} ta yozuv', history?.rows.length || 0)}</span>
        </header>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t('TAOM')}</th><th>{t('MIQDOR')}</th><th>{t('IZOH')}</th>
                <th>{t('KIRITGAN')}</th><th>{t('VAQT')}</th>
                <th aria-label={t('Amallar')} />
              </tr>
            </thead>
            <tbody>
              {(history?.rows || []).map(row => (
                <tr key={row.id}>
                  <td><strong>{row.name}</strong></td>
                  <td className="number">+{row.quantity}</td>
                  <td>{row.note || <span className="muted">—</span>}</td>
                  <td>{row.actor}</td>
                  <td>{dateLabel(row.created_at)}</td>
                  <td className="row-actions">
                    {/* Yozuvlar qo'shilib boradi va manfiy miqdor kiritib
                        bo'lmaydi, shuning uchun «20 o'rniga 200» xatosini
                        tuzatishning yagona yo'li — yozuvni olib tashlash. */}
                    <button
                      className="icon-button"
                      aria-label={t('Yozuvni o‘chirish')}
                      title={t('Yozuvni o‘chirish')}
                      disabled={busy}
                      onClick={() => { setFormError(''); setRemoving(row) }}
                    >
                      <Trash2 size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!history?.rows.length && (
            <div className="empty-state compact">
              <strong>{t('Bugun hali yozuv yo‘q')}</strong>
            </div>
          )}
        </div>
      </section>

      <AppModal
        open={!!removing}
        title={t('Yozuvni o‘chirish')}
        onClose={() => { if (!busy) setRemoving(undefined) }}
      >
        {removing && (
          <>
            <p className="data-note">
              {t('«{name}» · +{count} porsiya — yozuv o‘chirilsinmi?', {
                name: removing.name, count: removing.quantity,
              })}
            </p>
            <p className="alert">{t('Bugungi qoldiq shu miqdorga kamayadi. Amal jurnalga yoziladi.')}</p>
            {formError && <p className="alert error">{formError}</p>}
            <button className="button danger full" disabled={busy} onClick={removeRow}>
              <Trash2 size={17} />{t(busy ? 'Saqlanmoqda…' : 'O‘chirish')}
            </button>
            <button className="button secondary full" disabled={busy} onClick={() => setRemoving(undefined)}>
              {t('Bekor qilish')}
            </button>
          </>
        )}
      </AppModal>

      <p className="data-note">
        {t('Bu bo‘lim ombordan masalliq ayirmaydi — masalliq sotuv paytida retsept bo‘yicha hisobdan chiqadi. Bu yerda faqat porsiyalar sanaladi.')}
      </p>
    </>
  )
}
