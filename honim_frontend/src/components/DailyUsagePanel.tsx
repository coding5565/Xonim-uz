import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import {
  AlertTriangle, CalendarDays, CheckCircle2, ClipboardList, Save, Scale, TriangleAlert,
} from 'lucide-react'
import { api, money, today } from '../api'
import { useI18n } from '../i18n'
import { useSession } from '../session'
import type { DailyUsageLog, Ingredient, UsageComparison, UsageCompareRow } from '../types'

const STATUS: Record<UsageCompareRow['status'], { label: string; tone: string }> = {
  ok: { label: 'Mos', tone: 'paid' },
  alert: { label: 'Farq katta', tone: 'open' },
  missing: { label: 'Yozilmagan', tone: 'neutral' },
  extra: { label: 'Sotuvsiz', tone: 'neutral' },
}

function shiftDate(value: string, days: number) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10)
}

export default function DailyUsagePanel({ ingredients }: { ingredients: Ingredient[] }) {
  const { t, tn } = useI18n()
  const { user } = useSession()
  const [log, setLog] = useState<DailyUsageLog>()
  const [compare, setCompare] = useState<UsageComparison>()
  const [day, setDay] = useState(today())
  const [draft, setDraft] = useState<Record<number, string>>({})
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')

  const owner = user?.role === 'owner'

  const load = useCallback(async () => {
    setError('')
    try {
      const fetched = await api<DailyUsageLog>('daily-usage/')
      setLog(fetched)
      if (owner) setCompare(await api<UsageComparison>('daily-usage/compare/'))
    } catch (exception) {
      setError((exception as Error).message)
    }
  }, [owner])

  useEffect(() => {
    load()
  }, [load])

  // Tanlangan kunga allaqachon yozilgan qatorlar formaga tortiladi, shunda
  // admin o'zgartirish kiritayotganini ko'rib turadi.
  useEffect(() => {
    const existing = log?.days.find(row => row.date === day)
    setDraft(Object.fromEntries((existing?.lines || []).map(line => [line.ingredient, line.quantity])))
    setNote('')
  }, [log, day])

  const filled = Object.entries(draft).filter(([, value]) => value !== '' && Number(value) > 0)
  const draftValue = filled.reduce((total, [id, value]) => {
    const item = ingredients.find(row => row.id === Number(id))
    return total + Number(item?.unit_cost || 0) * Number(value)
  }, 0)

  async function save(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setSaved('')
    try {
      const lines = Object.entries(draft)
        .filter(([, value]) => value !== '')
        .map(([id, value]) => ({ ingredient: Number(id), quantity: value || '0', note }))
      if (!lines.length) throw new Error(t('Hech bo‘lmasa bitta mahsulot kiriting.'))
      const result = await api<{ saved: number; removed: number }>('daily-usage/', {
        method: 'POST',
        body: JSON.stringify({ date: day, lines }),
      })
      const removed = result.removed ? tn(', {count} tasi o‘chirildi', result.removed) : ''
      setSaved(`${tn('{day}: {count} ta qator saqlandi', result.saved, { day })}${removed}.`)
      await load()
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const back = log ? shiftDate(today(), -log.filters.backdate_days) : today()

  return (
    <>
      {error && <p className="alert error">{error}</p>}
      {saved && <p className="alert success">{saved}</p>}

      {owner && compare && (
        <section className={`panel ${compare.summary.alerts ? 'warn-panel' : ''}`}>
          <header className="panel-heading">
            <div>
              <h2>
                {compare.summary.alerts ? <TriangleAlert size={17} /> : <Scale size={17} />}
                {' '}{t('Tizim hisobi va haqiqiy sarf')}
              </h2>
              <p>
                {t('Tizim retsept bo‘yicha hisoblaydi, admin haqiqatda ketganini yozadi — farq {threshold}% dan oshsa belgilanadi', { threshold: compare.summary.alert_threshold })}
              </p>
            </div>
            <span className="pill subtle">{tn('{count} kun', compare.filters.days)}</span>
          </header>
          <div className="warn-grid">
            <div>
              <small>{t('Tizim hisoblagan')}</small>
              <strong>{money(compare.summary.system_value)}</strong>
              <em>{t('so‘m · retsept bo‘yicha')}</em>
            </div>
            <div>
              <small>{t('Admin yozgan')}</small>
              <strong>{money(compare.summary.actual_value)}</strong>
              <em>
                {tn('so‘m · {count} kun yozilgan', compare.summary.reported_days)}
                {compare.summary.missing_days > 0 && tn(', {count} kun yo‘q', compare.summary.missing_days)}
              </em>
            </div>
            <div>
              <small>{t('Farq')}</small>
              <strong className={Number(compare.summary.gap_value) > 0 ? 'owed' : undefined}>
                {Number(compare.summary.gap_value) > 0 ? '+' : ''}{money(compare.summary.gap_value)}
              </strong>
              <em>
                {compare.summary.gap_share ? `${compare.summary.gap_share}% · ` : ''}
                {compare.summary.alerts
                  ? tn("{count} ta mahsulotda e'tibor talab", compare.summary.alerts)
                  : t('jiddiy farq yo‘q')}
              </em>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t('MAHSULOT')}</th><th>{t('TIZIM HISOBI')}</th><th>{t('ADMIN YOZGAN')}</th>
                  <th>{t('FARQ')}</th><th>{t('FARQ SUMMASI')}</th><th>{t('HOLAT')}</th>
                </tr>
              </thead>
              <tbody>
                {compare.rows.map(row => (
                  <tr key={row.id}>
                    <td><strong>{row.name}</strong><small>{row.unit}</small></td>
                    <td className="number">{money(row.expected)} {row.unit}</td>
                    <td className="number">{money(row.counted)} {row.unit}</td>
                    <td className="number">
                      {Number(row.gap)
                        ? <span className={Number(row.gap) > 0 ? 'owed' : undefined}>
                          {Number(row.gap) > 0 ? '+' : ''}{money(row.gap)} {row.unit}
                          {row.share && <small>{row.share}%</small>}
                        </span>
                        : '—'}
                    </td>
                    <td className="number">
                      {Number(row.gap_value) ? `${money(row.gap_value)} ${t('so‘m')}` : '—'}
                    </td>
                    <td><span className={`status ${STATUS[row.status].tone}`}>{t(STATUS[row.status].label)}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!compare.rows.length && (
              <div className="empty-state compact">{t('Bu davrda na sotuv, na kunlik hisobot bor.')}</div>
            )}
          </div>
          <p className="data-note">
            {t('Farq musbat bo‘lsa — retseptdagidan ko‘proq ketyapti (ortiqcha solinyapti, isrof yoki yo‘qotish). Manfiy bo‘lsa — retseptda ko‘rsatilgan miqdor haqiqatdan yuqori.')}{' '}
            {t('Retseptni')} <Link to="/recipes" className="text-link">{t('shu yerdan')}</Link>{t(' tuzating.')}
          </p>
        </section>
      )}

      <section className="panel spaced">
        <header className="panel-heading">
          <div>
            <h2>{t('Kunlik hisobot kiritish')}</h2>
            <p>{t('Kechqurun qaysi mahsulotdan qancha ketganini yozing — ombordan ayirmaydi')}</p>
          </div>
          <label className="inline-date">
            <CalendarDays size={16} />
            <input value={day} onChange={event => setDay(event.target.value)} type="date" min={back} max={today()} />
          </label>
        </header>
        <form onSubmit={save}>
          <div className="usage-grid">
            {ingredients.map(item => (
              <label key={item.id} className="usage-field">
                <span>
                  {item.name}
                  <small>
                    {item.unit}
                    {Number(item.unit_cost) ? ` · ${money(item.unit_cost)} ${t('so‘m')}` : ` · ${t('narx yo‘q')}`}
                  </small>
                </span>
                <input
                  value={draft[item.id] ?? ''}
                  onChange={event => setDraft(previous => ({ ...previous, [item.id]: event.target.value }))}
                  type="number"
                  min="0"
                  step={item.unit === 'dona' ? '1' : '0.001'}
                  placeholder="0"
                />
              </label>
            ))}
          </div>
          {!ingredients.length && <div className="empty-state compact">{t('Avval ombor ro‘yxatiga mahsulot qo‘shing.')}</div>}
          <div className="usage-footer">
            <input
              value={note}
              onChange={event => setNote(event.target.value)}
              maxLength={250}
              placeholder={t('Izoh (ixtiyoriy) — masalan, banket bo‘ldi')}
            />
            <span>{tn('{count} ta mahsulot', filled.length)} · <strong>{money(draftValue)} {t('so‘m')}</strong></span>
            <button className="button primary" disabled={busy || !ingredients.length}>
              <Save size={16} />{busy ? t('Saqlanmoqda…') : t('Saqlash')}
            </button>
          </div>
          <p className="data-note">
            {t('Bo‘sh qoldirilgan mahsulot yozilmaydi. Noldan katta yozilsa saqlanadi, nol yozilsa o‘sha kungi yozuv o‘chiriladi.')}{' '}
            {tn('Oxirgi {count} kun uchun kiritish mumkin.', log?.filters.backdate_days ?? 7)}
          </p>
        </form>
      </section>

      <section className="panel spaced">
        <header className="panel-heading">
          <div>
            <h2>{t('Kiritilgan kunlar')}</h2>
            <p>{t('Oxirgi kunlar bo‘yicha nima yozilgani')}</p>
          </div>
          <ClipboardList size={18} />
        </header>
        <div className="usage-days">
          {(log?.days || []).map(row => (
            <button
              key={row.date}
              type="button"
              className={`usage-day${row.date === day ? ' selected' : ''}`}
              onClick={() => setDay(row.date)}
            >
              <div>
                <strong>{row.date}</strong>
                <small>{tn('{count} ta mahsulot', row.items)} · {row.actors.join(', ')}</small>
              </div>
              <b>{money(row.value)} <span>{t('so‘m')}</span></b>
              <p>{row.lines.map(line => `${line.name} ${money(line.quantity)} ${line.unit}`).join(' · ')}</p>
            </button>
          ))}
        </div>
        {!log?.days.length && (
          <div className="empty-state">
            <CheckCircle2 size={22} />
            <strong>{t('Hali kunlik hisobot kiritilmagan')}</strong>
            {t('Yuqoridagi formadan bugungi sarfni yozing.')}
          </div>
        )}
      </section>

      {!owner && (
        <p className="data-note">
          <AlertTriangle size={14} />
          {t('Siz kiritgan raqamlar tizim hisobi bilan solishtiriladi — bu farqni faqat superadmin ko‘radi.')}
        </p>
      )}
    </>
  )
}
