import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle, ChevronRight, Clock, HandCoins, Handshake, PackageCheck, Plus, RefreshCw, Truck,
} from 'lucide-react'
import { api, money } from '../api'
import AppModal from '../components/AppModal'
import { useI18n } from '../i18n'
import { useSession } from '../session'
import { CardsSkeleton, TableSkeleton } from '../components/Skeleton'
import type { Partner, PartnerBoard } from '../types'

interface PartnerForm {
  name: string
  kind: Partner['kind']
  contact: string
  phone: string
  address: string
  note: string
}

const BLANK: PartnerForm = { name: '', kind: 'school', contact: '', phone: '', address: '', note: '' }

const KINDS: Partner['kind'][] = ['school', 'university', 'office', 'other']
const KIND_NAMES: Record<Partner['kind'], string> = {
  school: 'Maktab', university: 'Universitet', office: 'Ofis', other: 'Boshqa',
}

/**
 * Hamkorlar ro'yxati — kim qancha qarzdor va kimdan hisobot kutilmoqda.
 *
 * Har bir hamkorning ichki sahifasi bor: jo'natish, kechqurungi hisobot,
 * pul qabul qilish va shartnoma narxlari o'sha yerda. Bu sahifa faqat
 * «bugun kim bilan ishlash kerak» degan savolga javob beradi, shuning
 * uchun qatorlar qarz bo'yicha saralangan.
 */
export default function PartnersPage() {
  const { t, tn } = useI18n()
  const { user } = useSession()
  const owner = user?.role === 'owner'

  const [board, setBoard] = useState<PartnerBoard>()
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)
  const [addOpen, setAddOpen] = useState(false)
  const [form, setForm] = useState<PartnerForm>(BLANK)

  const load = useCallback(async () => {
    setError('')
    try {
      setBoard(await api<PartnerBoard>('partner-board/'))
    } catch (exception) {
      setError((exception as Error).message)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  async function create(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setFormError('')
    try {
      await api('partners/', { method: 'POST', body: JSON.stringify(form) })
      setAddOpen(false)
      setForm(BLANK)
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const rows = board?.partners || []
  // Ro'yxatdan olingan hamkor qarzi to'langunicha ko'rinib turadi: aks
  // holda pul unutilib ketardi.
  const visible = rows.filter(row => row.active || Number(row.debt) !== 0)
  const waiting = rows.filter(row => row.pending_count > 0)

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('HAMKORLAR BILAN SAVDO')}</span>
          <h1>{t('Hamkorlar')}<span className="heading-dot">.</span></h1>
          <p>{t('Maktab va universitetlarga jo‘natilgan taom, kechqurungi hisobot va pul.')}</p>
        </div>
        <div className="heading-actions">
          <button className="button secondary" disabled={!board} onClick={() => load()}>
            <RefreshCw size={17} className={board ? undefined : 'spin'} />{t('Yangilash')}
          </button>
          {owner && (
            <button className="button primary" onClick={() => { setForm(BLANK); setFormError(''); setAddOpen(true) }}>
              <Plus size={17} />{t('Hamkor qo‘shish')}
            </button>
          )}
        </div>
      </div>

      {error && <p className="alert error">{error}</p>}

      {!board && (
        <>
          <CardsSkeleton />
          <section className="panel"><TableSkeleton rows={4} columns={6} /></section>
        </>
      )}

      {board && (
        <>
          <div className="report-metrics">
            <article>
              <span className="metric-icon blue"><Truck /></span>
              <div>
                <small>{t('Bugun jo‘natildi')}</small>
                <strong>{money(board.summary.sent_value)} <em>{t('so‘m')}</em></strong>
                <em>{tn('{count} porsiya', board.summary.sent_portions)}</em>
              </div>
            </article>
            <article>
              <span className="metric-icon green"><HandCoins /></span>
              <div>
                <small>{t('Hamkorlardan tushgan pul')}</small>
                <strong>{money(board.summary.received)} <em>{t('so‘m')}</em></strong>
                <em>{tn('{count} ta to‘lov', board.summary.settlements)}</em>
              </div>
            </article>
            <article>
              <span className={`metric-icon ${Number(board.summary.debt) > 0 ? 'orange' : 'green'}`}>
                <AlertTriangle />
              </span>
              <div>
                <small>{t('Qarzdorlik')}</small>
                <strong>{money(board.summary.debt)} <em>{t('so‘m')}</em></strong>
                <em>{t('butun vaqt bo‘yicha')}</em>
              </div>
            </article>
            <article>
              <span className="metric-icon violet"><Clock /></span>
              <div>
                <small>{t('Hisobot kutilmoqda')}</small>
                <strong>{board.summary.pending_count} <em>{t('ta jo‘natma')}</em></strong>
                <em>{money(board.summary.pending_value)} {t('so‘m')}</em>
              </div>
            </article>
          </div>

          {!!waiting.length && (
            <p className="alert">
              {tn('{count} ta hamkor bugungi ovqat uchun hali hisob bermadi.', waiting.length)}
              {' '}{waiting.map(row => row.name).join(', ')}
            </p>
          )}

          <section className="panel">
            <header className="panel-heading">
              <div>
                <h2><Handshake size={17} /> {t('Hamkorlar ro‘yxati')}</h2>
                <p>{t('Qatorni oching — jo‘natish, hisobot va to‘lov o‘sha hamkorning ichida.')}</p>
              </div>
              <span className="muted">{tn('{count} ta hamkor', visible.length)}</span>
            </header>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t('NOMI')}</th>
                    <th className="number">{t('JO‘NATILDI')}</th>
                    <th className="number">{t('HISOBOT KUTILMOQDA')}</th>
                    <th className="number">{t('QARZ')}</th>
                    <th>{t('QARZ KUNLARI')}</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {visible.map(row => (
                    <tr key={row.id} className={row.active ? undefined : 'row-muted'}>
                      <td>
                        <strong>{row.name}</strong>
                        <small>
                          {t(KIND_NAMES[row.kind] || row.kind_label)}
                          {row.phone ? ` · ${row.phone}` : ''}
                          {row.active ? '' : ` · ${t('faolsizlantirilgan')}`}
                        </small>
                      </td>
                      <td className="number">
                        <strong>{money(row.sent_value)}</strong>
                        <small>{tn('{count} porsiya', row.sent_portions)}</small>
                      </td>
                      <td className="number">
                        {row.pending_count ? (
                          <>
                            <strong>{money(row.pending_value)}</strong>
                            <small>{tn('{count} ta jo‘natma', row.pending_count)}</small>
                          </>
                        ) : <small>—</small>}
                      </td>
                      <td className="number">
                        <strong className={Number(row.debt) > 0 ? 'owed' : undefined}>{money(row.debt)}</strong>
                      </td>
                      <td>
                        <small>{row.oldest_days > 0 ? tn('{count} kundan beri', row.oldest_days) : '—'}</small>
                      </td>
                      <td>
                        <Link className="button secondary small" to={`/hamkorlar/${row.id}`}>
                          {t('Ochish')}<ChevronRight size={15} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!visible.length && (
                <div className="empty-state">
                  <PackageCheck size={34} strokeWidth={1.4} />
                  <strong>{t('Hali hamkor yo‘q')}</strong>
                  <p>{t('Shartnoma tuzilgan maktab yoki universitetni qo‘shing — narxlari ham o‘sha yerda belgilanadi.')}</p>
                </div>
              )}
            </div>
            <p className="data-note">
              {t('Hamkorga jo‘natilgan porsiyalar «Tayyor taomlar» hisobiga ham, zal savdosiga ham qo‘shilmaydi — ular alohida pishiriladi va alohida hisoblanadi.')}
            </p>
          </section>
        </>
      )}

      <AppModal open={addOpen} title={t('Yangi hamkor')} onClose={() => { if (!busy) setAddOpen(false) }}>
        <form onSubmit={create}>
          <label>
            {t('Nomi')}
            <input
              value={form.name}
              onChange={event => setForm({ ...form, name: event.target.value })}
              maxLength={120}
              required
              autoFocus
              placeholder={t('Masalan, 25-maktab')}
            />
          </label>
          <div className="form-row">
            <label>
              {t('Turi')}
              <select
                value={form.kind}
                onChange={event => setForm({ ...form, kind: event.target.value as Partner['kind'] })}
              >
                {KINDS.map(kind => <option key={kind} value={kind}>{t(KIND_NAMES[kind])}</option>)}
              </select>
            </label>
            <label>
              {t('Telefon')}
              <input
                value={form.phone}
                onChange={event => setForm({ ...form, phone: event.target.value })}
                maxLength={30}
                placeholder="+998"
              />
            </label>
          </div>
          <div className="form-row">
            <label>
              {t('Mas’ul shaxs')}
              <input
                value={form.contact}
                onChange={event => setForm({ ...form, contact: event.target.value })}
                maxLength={80}
              />
            </label>
            <label>
              {t('Manzil')}
              <input
                value={form.address}
                onChange={event => setForm({ ...form, address: event.target.value })}
                maxLength={200}
              />
            </label>
          </div>
          <label>
            {t('Izoh')}
            <textarea
              value={form.note}
              onChange={event => setForm({ ...form, note: event.target.value })}
              maxLength={300}
              rows={2}
            />
          </label>
          <p className="data-note">
            {t('Qo‘shgandan keyin shartnoma narxlarini belgilang — narxsiz taomni hamkorga jo‘natib bo‘lmaydi.')}
          </p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? t('Saqlanmoqda…') : t('Hamkorni qo‘shish')}
          </button>
        </form>
      </AppModal>
    </>
  )
}
