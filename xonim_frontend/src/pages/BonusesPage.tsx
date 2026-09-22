import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { CalendarDays, Gift, Percent, Plus, RefreshCw, Trash2, Wallet } from 'lucide-react'
import { api, dateLabel, list, money, today } from '../api'
import AppModal from '../components/AppModal'
import { useI18n } from '../i18n'
import { useSession } from '../session'
import { CardsSkeleton, TableSkeleton } from '../components/Skeleton'
import type { BonusReport, BonusRule, Dish, SaleChannel } from '../types'

const CHANNELS: { channel: SaleChannel; name: string }[] = [
  { channel: 'uzum', name: 'Uzum' },
  { channel: 'yandex', name: 'Yandex' },
  { channel: 'hall', name: 'Zal' },
  { channel: 'takeaway', name: 'Olib ketish' },
]

interface RuleForm {
  channel: SaleChannel
  dish: number
  free_quantity: string
  active: boolean
}

/**
 * Bonuslar: aksiya bo'yicha tekin ketgan porsiyalar.
 *
 * Qoida oddiy — buyurtmada belgilangan taom bo'lsa, mijoz nechta olganidan
 * qat'i nazar ustiga shuncha tekin qo'shiladi. Bu sahifa ikki savolga
 * javob beradi: nechta porsiya tekin ketdi va u bizga nechchiga tushdi.
 *
 * Ikki xil raqam ataylab yonma-yon turadi. «Qiymat» — menyu narxi, ya'ni
 * mijozga qancha pullik sovg'a qilingani. «Tannarx» esa bizga aslida
 * nechchiga tushgani va aynan u foydadan chiqib ketgan.
 */
export default function BonusesPage() {
  const { t, tn } = useI18n()
  const { user } = useSession()
  const owner = user?.role === 'owner'
  const [params, setParams] = useSearchParams()

  const [board, setBoard] = useState<BonusReport>()
  const [dishes, setDishes] = useState<Dish[]>([])
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)
  const [ruleOpen, setRuleOpen] = useState(false)
  const [removing, setRemoving] = useState<BonusRule>()
  const [form, setForm] = useState<RuleForm>({
    channel: 'uzum', dish: 0, free_quantity: '1', active: true,
  })

  const start = params.get('start') || `${today().slice(0, 8)}01`
  const end = params.get('end') || today()

  const load = useCallback(async () => {
    setError('')
    try {
      setBoard(await api<BonusReport>(`bonuses/?${new URLSearchParams({ start, end })}`))
    } catch (exception) {
      setError((exception as Error).message)
    }
  }, [start, end])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    if (owner) list<Dish>('dishes/').then(setDishes).catch(() => setDishes([]))
  }, [owner])

  function startRule(rule?: BonusRule) {
    setForm(rule
      ? {
        channel: rule.channel, dish: rule.dish,
        free_quantity: String(rule.free_quantity), active: rule.active,
      }
      : { channel: 'uzum', dish: dishes[0]?.id || 0, free_quantity: '1', active: true })
    setFormError('')
    setRuleOpen(true)
  }

  async function saveRule(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setFormError('')
    try {
      await api('bonus-rules/', {
        method: 'PUT',
        body: JSON.stringify({ ...form, free_quantity: Number(form.free_quantity) }),
      })
      setRuleOpen(false)
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function removeRule() {
    if (!removing || busy) return
    setBusy(true)
    setFormError('')
    try {
      await api(`bonus-rules/?id=${removing.id}`, { method: 'DELETE' })
      setRemoving(undefined)
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const rules = board?.rules || []
  const live = rules.filter(rule => rule.active)

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('AKSIYA VA SOVG‘ALAR')}</span>
          <h1>{t('Bonuslar')}<span className="heading-dot">.</span></h1>
          <p>{t('Buyurtmaga qo‘shib berilgan tekin porsiyalar va ularning tannarxi.')}</p>
        </div>
        <div className="heading-actions">
          <button className="button secondary" disabled={!board} onClick={() => load()}>
            <RefreshCw size={17} className={board ? undefined : 'spin'} />{t('Yangilash')}
          </button>
          {owner && (
            <button className="button primary" disabled={!dishes.length} onClick={() => startRule()}>
              <Plus size={17} />{t('Aksiya qo‘shish')}
            </button>
          )}
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
        <>
          <div className="report-metrics">
            <article>
              <span className="metric-icon violet"><Gift /></span>
              <div>
                <small>{t('Tekin ketgan porsiya')}</small>
                <strong>{board.summary.portions}</strong>
                <em>{tn('{count} ta chekda', board.summary.orders)}</em>
              </div>
            </article>
            <article>
              <span className="metric-icon blue"><Percent /></span>
              <div>
                <small>{t('Menyu bo‘yicha qiymati')}</small>
                <strong>{money(board.summary.value)} <em>{t('so‘m')}</em></strong>
                <em>{t('mijozga shuncha pullik sovg‘a')}</em>
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
          </div>

          {owner && (
            <section className="panel spaced">
              <header className="panel-heading">
                <div>
                  <h2><Gift size={17} /> {t('Aksiya qoidalari')}</h2>
                  <p>{t('Buyurtmada shu taom bo‘lsa — mijoz nechta olganidan qat’i nazar — ustiga belgilangan miqdor tekin qo‘shiladi.')}</p>
                </div>
                <span className="muted">{tn('{count} ta yoqilgan', live.length)}</span>
              </header>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>{t('TAOM')}</th>
                      <th>{t('KANAL')}</th>
                      <th className="number">{t('TEKIN QO‘SHILADI')}</th>
                      <th>{t('HOLAT')}</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {rules.map(rule => (
                      <tr key={rule.id} className={rule.active ? undefined : 'row-muted'}>
                        <td>
                          <strong>{rule.dish_name}</strong>
                          <small>{money(rule.menu_price)} {t('so‘m')}{rule.archived ? ` · ${t('arxivlangan')}` : ''}</small>
                        </td>
                        <td>{t(rule.channel_label)}</td>
                        <td className="number"><strong>+{rule.free_quantity}</strong></td>
                        <td>
                          <span className={`status ${rule.active ? 'paid' : 'open'}`}>
                            {rule.active ? t('Yoqilgan') : t('O‘chirilgan')}
                          </span>
                        </td>
                        <td>
                          <div className="row-buttons">
                            <button className="table-action" onClick={() => startRule(rule)}>
                              {t('O‘zgartirish')}
                            </button>
                            <button
                              className="table-action"
                              title={t('Qoidani o‘chirish')}
                              onClick={() => { setFormError(''); setRemoving(rule) }}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!rules.length && (
                  <div className="empty-state compact">
                    <strong>{t('Hali aksiya yo‘q')}</strong>
                    <p>{t('Masalan: Uzumda «Bozor honim» buyurtma qilinsa, ustiga bittasi tekin.')}</p>
                  </div>
                )}
              </div>
              <p className="data-note">
                {t('Qoida o‘zgarsa faqat keyingi buyurtmalarga ta’sir qiladi — sotilgan chekdagi bonus o‘zgarmaydi.')}
              </p>
            </section>
          )}

          <section className="panel spaced">
            <header className="panel-heading">
              <div>
                <h2>{t('Taomlar kesimi')}</h2>
                <p>{t('Qaysi taomdan qancha tekin ketdi')}</p>
              </div>
            </header>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t('TAOM')}</th>
                    <th className="number">{t('PORSIYA')}</th>
                    <th className="number">{t('CHEK')}</th>
                    <th className="number">{t('QIYMATI')}</th>
                    <th className="number">{t('TANNARXI')}</th>
                  </tr>
                </thead>
                <tbody>
                  {board.dishes.map(row => (
                    <tr key={row.dish}>
                      <td><strong>{row.name}</strong></td>
                      <td className="number"><strong>{row.portions}</strong></td>
                      <td className="number">{row.orders}</td>
                      <td className="number">{money(row.value)}</td>
                      <td className="number">{money(row.cost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!board.dishes.length && (
                <div className="empty-state compact">
                  <strong>{t('Bu davrda bonus berilmagan')}</strong>
                </div>
              )}
            </div>
          </section>

          <section className="panel spaced">
            <header className="panel-heading">
              <div>
                <h2>{t('Oxirgi bonuslar')}</h2>
                <p>{t('Qaysi chekka qaysi tekin porsiya qo‘shilgan')}</p>
              </div>
            </header>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t('CHEK')}</th>
                    <th>{t('TAOM')}</th>
                    <th className="number">{t('SONI')}</th>
                    <th>{t('KANAL')}</th>
                    <th className="number">{t('QIYMATI')}</th>
                    <th>{t('VAQT')}</th>
                  </tr>
                </thead>
                <tbody>
                  {board.rows.map(row => (
                    <tr key={row.id}>
                      <td>#{row.order}</td>
                      <td><strong>{row.name}</strong></td>
                      <td className="number">{row.quantity}</td>
                      <td>{t(row.channel_label)}</td>
                      <td className="number">{money(row.value)}</td>
                      <td>{row.paid_at ? dateLabel(row.paid_at) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!board.rows.length && (
                <div className="empty-state compact">{t('Yozuv yo‘q.')}</div>
              )}
            </div>
          </section>
        </>
      )}

      <AppModal
        open={ruleOpen}
        title={t('Aksiya qoidasi')}
        onClose={() => { if (!busy) setRuleOpen(false) }}
      >
        <form onSubmit={saveRule}>
          <label>
            {t('Taom')}
            <select
              value={form.dish}
              onChange={event => setForm({ ...form, dish: Number(event.target.value) })}
              required
            >
              {dishes.filter(dish => !dish.archived).map(dish => (
                <option key={dish.id} value={dish.id}>{dish.name}</option>
              ))}
            </select>
          </label>
          <div className="form-row">
            <label>
              {t('Kanal')}
              <select
                value={form.channel}
                onChange={event => setForm({ ...form, channel: event.target.value as SaleChannel })}
              >
                {CHANNELS.map(item => (
                  <option key={item.channel} value={item.channel}>{t(item.name)}</option>
                ))}
              </select>
            </label>
            <label>
              {t('Nechta tekin qo‘shiladi')}
              <input
                value={form.free_quantity}
                onChange={event => setForm({ ...form, free_quantity: event.target.value })}
                type="number"
                min="1"
                max="99"
                step="1"
                required
              />
            </label>
          </div>
          <label className="checkbox">
            <input
              checked={form.active}
              onChange={event => setForm({ ...form, active: event.target.checked })}
              type="checkbox"
            />
            <span>{t('Aksiya yoqilgan')}</span>
          </label>
          <p className="data-note">
            {t('Mijoz bu taomdan nechta olsa ham ustiga aynan shuncha tekin ketadi. Buyurtmada bu taom bo‘lmasa bonus ham berilmaydi.')}
          </p>
          <p className="data-note">
            {t('Tekin porsiya ham oshxonadan chiqadi: masallig‘i ombordan ayriladi va tayyor porsiyalar hisobiga kiradi.')}
          </p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy || !form.dish}>
            {busy ? t('Saqlanmoqda…') : t('Saqlash')}
          </button>
        </form>
      </AppModal>

      <AppModal
        open={!!removing}
        title={t('Qoidani o‘chirish')}
        onClose={() => { if (!busy) setRemoving(undefined) }}
      >
        <p className="alert">
          {t('«{name}» uchun aksiya qoidasi o‘chiriladi. Berilgan bonuslar tarixda qoladi.', {
            name: removing?.dish_name || '',
          })}
        </p>
        {formError && <p className="alert error">{formError}</p>}
        <button className="button danger full" disabled={busy} onClick={removeRule}>
          {busy ? t('Saqlanmoqda…') : t('O‘chirish')}
        </button>
      </AppModal>
    </>
  )
}
