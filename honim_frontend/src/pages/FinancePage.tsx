import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle, ArrowRight, Banknote, ChefHat, Coins, Package, PiggyBank, Receipt, RefreshCw, Wallet,
} from 'lucide-react'
import { api, money, today } from '../api'
import { useI18n } from '../i18n'
import type { Finance } from '../types'

type Translate = (text: string, vars?: Record<string, string | number>) => string

const MONTHS = [
  'yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
  'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr',
]
const monthName = (key: string, t: Translate) => {
  const [year, month] = key.split('-')
  return t('{year}-yil {month}', { year, month: t(MONTHS[Number(month) - 1]) })
}

/** Xarajat kategoriyasi qaysi sahifada batafsil ko‘rinadi. */
function expenseLink(category: string, start: string, end: string, month: string | null) {
  if (category === 'Ish haqi') return `/payroll${month ? `?month=${month}` : ''}`
  return `/expenses?start=${start}&end=${end}&category=${encodeURIComponent(category)}`
}

export default function FinancePage() {
  const { t, tn } = useI18n()
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState<Finance>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const search = params.toString()

  const load = useCallback(async (query: string) => {
    setLoading(true)
    setError('')
    try {
      setData(await api<Finance>(`finance/?${query}`))
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load(search)
  }, [load, search])

  const pickMonth = (value: string) => setParams(value ? { month: value } : {}, { replace: true })

  if (!data) {
    return (
      <>
        <div className="page-heading">
          <div>
            <span className="eyebrow">{t('MOLIYA MARKAZI')}</span>
            <h1>{t('Umumiy moliya')}<span className="heading-dot">.</span></h1>
          </div>
        </div>
        {error ? <p className="alert error">{error}</p> : <div className="empty-state">{t('Hisoblanmoqda…')}</div>}
      </>
    )
  }

  const { profit, coverage, cash, stock, filters } = data
  const range = `start=${filters.start}&end=${filters.end}`
  const negative = Number(profit.net_profit) < 0
  const lowCoverage = Number(coverage.share) < 80
  const bigGap = !!Number(stock.consumed) && Math.abs(Number(stock.gap_share)) > 25
  const maxTrend = Math.max(1, ...data.trend.map(row => Math.abs(Number(row.revenue))))

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('MOLIYA MARKAZI')}</span>
          <h1>{t('Umumiy moliya')}<span className="heading-dot">.</span></h1>
          <p>{t('Butun biznesning pul manzarasi. Har bir raqamni bosing — u qayerdan kelganini ko‘rasiz.')}</p>
        </div>
        <div className="heading-actions">
          <select value={filters.month || ''} onChange={event => pickMonth(event.target.value)} aria-label={t('Oyni tanlash')}>
            <option value="">{t('Shu oy')}</option>
            {data.months.map(item => <option key={item} value={item}>{monthName(item, t)}</option>)}
          </select>
          <button className="button secondary" disabled={loading} onClick={() => load(search)}>
            <RefreshCw size={17} className={loading ? 'spin' : undefined} />{t('Yangilash')}
          </button>
        </div>
      </div>

      {error && <p className="alert error">{error}</p>}

      <p className="period-note">
        <strong>{filters.label}</strong> · {tn('{count} kun', Number(filters.days))}
        {' '}· {tn('{count} ta to‘langan chek', Number(profit.orders))}
      </p>

      <section className="panel chain-panel">
        <header className="panel-heading">
          <div><h2>{t('Foyda zanjiri')}</h2><p>{t('Yuqoridan pastga — pul qayerdan kelib, qayerga ketgani')}</p></div>
        </header>
        <div className="chain">
          <Link to={`/reports?${range}`} className="chain-row">
            <span className="chain-icon green"><Banknote size={18} /></span>
            <div>
              <strong>{t('Tushum')}</strong>
              <small>
                {tn('{count} ta chek', Number(profit.orders))}
                {' '}· {t('o‘rtacha {amount} so‘m', { amount: money(profit.average_check) })}
              </small>
            </div>
            <b>{money(profit.revenue)}</b>
            <ArrowRight size={15} />
          </Link>

          <Link to={`/inventory?view=usage&${range}`} className="chain-row minus">
            <span className="chain-icon orange"><ChefHat size={18} /></span>
            <div>
              <strong>{t('Tannarx')}</strong>
              <small>{t('Sotilgan taomlarning retsept bo‘yicha xomashyo qiymati')}</small>
            </div>
            <b>−{money(profit.cogs)}</b>
            <ArrowRight size={15} />
          </Link>

          <div className="chain-sum">
            <div>
              <strong>{t('Yalpi foyda')}</strong>
              <small>{t('{percent}% marja', { percent: profit.gross_margin })}</small>
            </div>
            <b>{money(profit.gross_profit)}</b>
          </div>

          <Link to={`/expenses?${range}`} className="chain-row minus">
            <span className="chain-icon violet"><Receipt size={18} /></span>
            <div>
              <strong>{t('Operatsion xarajatlar')}</strong>
              <small>{t('Ijara, kommunal, ish haqi va boshqalar — barchasi shu yerda')}</small>
            </div>
            <b>−{money(profit.expenses)}</b>
            <ArrowRight size={15} />
          </Link>

          {!!Number(profit.waste) && (
            <Link to={`/inventory?view=usage&${range}`} className="chain-row minus">
              <span className="chain-icon orange"><Package size={18} /></span>
              <div>
                <strong>{t('Ombor isrofi')}</strong>
                <small>{t('Qo‘lda yozilgan sarf — sotilmagan, lekin ombordan ketgan')}</small>
              </div>
              <b>−{money(profit.waste)}</b>
              <ArrowRight size={15} />
            </Link>
          )}

          <div className={`chain-total${negative ? ' negative' : ''}`}>
            <div>
              <strong>{t('Sof foyda')}</strong>
              <small>
                {negative
                  ? t('Bu davrda zarar')
                  : t('Tushumning {percent}% i', { percent: profit.net_margin })}
              </small>
            </div>
            <b>{money(profit.net_profit)} <em>{t('so‘m')}</em></b>
          </div>
        </div>
        <p className="data-note">{data.basis}</p>
      </section>

      {lowCoverage && (
        <section className="panel warn-panel">
          <header className="panel-heading">
            <div>
              <h2><AlertTriangle size={17} /> {t('Tannarx to‘liq emas')}</h2>
              <p>{t('Yuqoridagi marja haqiqatdan yuqori ko‘rinadi — pastdagi raqamga qarang')}</p>
            </div>
            <Link to="/recipes" className="button secondary">{t('Retseptlarni to‘ldirish')}</Link>
          </header>
          <div className="warn-grid">
            <div>
              <small>{t('Tannarx qamrab olgan tushum')}</small>
              <strong>{coverage.share}%</strong>
              <em>{money(coverage.covered_revenue)} {t('so‘m')}</em>
            </div>
            <div>
              <small>{t('Retsepti bor taomlar')}</small>
              <strong>{coverage.dishes_with_recipe} / {coverage.dishes_total}</strong>
              <em>
                {tn('menyuda {count} tasida retsept yo‘q', Number(coverage.menu_without_recipe))}
                {coverage.sold_uncovered > 0 &&
                  t(', shundan {count} tasi shu davrda sotilgan', { count: coverage.sold_uncovered })}
              </em>
            </div>
            <div>
              <small>{t('Haqiqiy marja (retsepti borlarda)')}</small>
              <strong>{coverage.covered_margin}%</strong>
              <em>{t('ko‘rsatilgan {percent}% o‘rniga', { percent: profit.gross_margin })}</em>
            </div>
          </div>
          {!!coverage.top_uncovered.length && (
            <div className="table-wrap">
              <table>
                <thead><tr><th>{t('RETSEPTSIZ SOTILGAN TAOM')}</th><th>{t('TUSHUM')}</th><th></th></tr></thead>
                <tbody>
                  {coverage.top_uncovered.map(row => (
                    <tr key={row.dish_id}>
                      <td><strong>{row.dish}</strong></td>
                      <td className="number">{money(row.revenue)} {t('so‘m')}</td>
                      <td><Link to="/recipes" className="text-link">{t('Retsept qo‘shish')} →</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      <div className="finance-grid">
        <section className="panel">
          <header className="panel-heading">
            <div><h2>{t('Pul oqimi')}</h2><p>{t('Foyda bilan pul bir xil emas — farqi shu yerda')}</p></div>
            <Wallet size={18} />
          </header>
          <div className="cash-rows">
            <Link to={`/sales?${range}`} className="cash-row">
              <span>{t('Pul tushdi')}</span><b>{money(cash.in)}</b><ArrowRight size={14} />
            </Link>
            <Link to={`/expenses?${range}`} className="cash-row">
              <span>{t('Xarajatlarga ketdi')}</span><b>−{money(cash.settled_expenses)}</b><ArrowRight size={14} />
            </Link>
            <Link to={`/inventory?view=usage&${range}`} className="cash-row">
              <span>{t('Ombor xaridiga ketdi')}</span><b>−{money(cash.stock_purchases)}</b><ArrowRight size={14} />
            </Link>
            <div className="cash-row total">
              <span>{t('Sof pul oqimi')}</span><b>{money(cash.net)} {t('so‘m')}</b>
            </div>
            {!!Number(cash.unpaid) && (
              <Link to={`/expenses?${range}`} className="cash-row hint">
                <span>{t('Hali to‘lanmagan qarz')}</span><b>{money(cash.unpaid)}</b><ArrowRight size={14} />
              </Link>
            )}
          </div>
          <p className="data-note">
            {t('Ombor xaridi foydadan ayirilmaydi — u tovarga aylanadi va sotilganda tannarx bo‘lib hisobga olinadi.')}
          </p>
        </section>

        <section className="panel">
          <header className="panel-heading">
            <div><h2>{t('Xarajat tarkibi')}</h2><p>{t('Pul aynan nimaga sarflandi')}</p></div>
            <Link to={`/expenses?${range}`} className="text-link">{t('Hammasi')} <ArrowRight size={14} /></Link>
          </header>
          {data.expenses.length ? (
            <div className="category-ranking">
              {data.expenses.map(row => (
                <Link key={row.category} to={expenseLink(row.category, filters.start, filters.end, filters.month)}>
                  <div>
                    <div>
                      <strong>{row.category}</strong>
                      <span>{tn('{count} ta yozuv', Number(row.count))} · {row.share}%</span>
                      <b>{money(row.amount)}</b>
                    </div>
                    <div className="progress-track"><span style={{ width: `${row.share}%` }} /></div>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <div className="empty-state compact">
              <strong>{t('Bu davrda xarajat kiritilmagan')}</strong>
              <Link to="/expenses" className="text-link">{t('Xarajat qo‘shish')} →</Link>
            </div>
          )}
        </section>
      </div>

      <div className="finance-grid">
        <section className="panel">
          <header className="panel-heading">
            <div><h2>{t('Pul qaysi yo‘l bilan tushdi')}</h2><p>{t('To‘lov turlari bo‘yicha')}</p></div>
            <Coins size={18} />
          </header>
          <div className="category-ranking">
            {data.methods.map(row => (
              <Link key={row.method} to={`/sales?${range}`}>
                <div>
                  <div>
                    <strong>{row.label}</strong>
                    <span>{tn('{count} ta chek', Number(row.orders))} · {row.share}%</span>
                    <b>{money(row.revenue)}</b>
                  </div>
                  <div className="progress-track"><span style={{ width: `${row.share}%` }} /></div>
                </div>
              </Link>
            ))}
            {!data.methods.length && <div className="empty-state compact">{t('Bu davrda savdo yo‘q.')}</div>}
          </div>
        </section>

        <section className="panel">
          <header className="panel-heading">
            <div><h2>{t('Ombor va ish haqi')}</h2><p>{t('Eng katta ikki xarajat manbasi')}</p></div>
            <Package size={18} />
          </header>
          <div className="cash-rows">
            <Link to="/inventory" className="cash-row">
              <span>{t('Omborda turgan pul')}</span><b>{money(stock.value)}</b><ArrowRight size={14} />
            </Link>
            <Link to={`/inventory?view=usage&${range}`} className="cash-row">
              <span>{t('Davrda sarflangan xomashyo')}</span><b>{money(stock.consumed)}</b><ArrowRight size={14} />
            </Link>
            <Link to={`/payroll${filters.month ? `?month=${filters.month}` : ''}`} className="cash-row">
              <span>{t('Ish haqiga to‘langan')}</span><b>{money(data.salary.total)}</b><ArrowRight size={14} />
            </Link>
          </div>
          {!!Number(data.salary.manual_total) && (
            <p className="alert">
              {tn(
                '«Ish haqi» deb qo‘lda kiritilgan {count} ta xarajat bor ({amount} so‘m) — ular oylik to‘loviga bog‘lanmagan, shuning uchun oyliklar hisobiga kirmaydi.',
                Number(data.salary.manual_count),
                { amount: money(data.salary.manual_total) },
              )}{' '}
              <Link to={`/expenses?${range}&category=Ish%20haqi`} className="text-link">{t('Tekshiring')}</Link>.
            </p>
          )}
          {bigGap && (
            <p className="alert">
              {t('Retsept tannarxi ({cost} so‘m) ombor narxidan ({stock} so‘m) {gap}% farq qilyapti. Retseptlardagi partiya narxi eskirgan bo‘lishi mumkin —', {
                cost: money(profit.cogs),
                stock: money(stock.consumed),
                gap: stock.gap_share,
              })}
              {' '}<Link to="/recipes" className="text-link">{t('tekshiring')}</Link>.
            </p>
          )}
        </section>
      </div>

      <section className="panel spaced">
        <header className="panel-heading">
          <div><h2>{t('Oyma-oy')}</h2><p>{t('Ustunni bosing — o‘sha oyning to‘liq moliyasi ochiladi')}</p></div>
          <PiggyBank size={18} />
        </header>
        <div className="report-chart" role="img" aria-label={t('Oylik moliya grafigi')}>
          {data.trend.map(point => (
            <button
              key={point.period}
              className="report-bar"
              title={t('{label}: tushum {revenue}, sof foyda {profit} so‘m', {
                label: point.label,
                revenue: money(point.revenue),
                profit: money(point.net_profit),
              })}
              onClick={() => pickMonth(point.period)}
            >
              <div><span style={{ height: `${(Number(point.revenue) / maxTrend) * 100}%` }} /></div>
              <small>{point.label}</small>
            </button>
          ))}
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t('OY')}</th><th>{t('TUSHUM')}</th><th>{t('TANNARX')}</th>
                <th>{t('XARAJAT')}</th><th>{t('SOF FOYDA')}</th>
              </tr>
            </thead>
            <tbody>
              {[...data.trend].reverse().filter(row => Number(row.revenue) || Number(row.expenses)).map(row => (
                <tr key={row.period}>
                  <td>
                    <button className="text-link" onClick={() => pickMonth(row.period)}>{monthName(row.period, t)}</button>
                  </td>
                  <td className="number">{money(row.revenue)}</td>
                  <td className="number">{money(row.cogs)}</td>
                  <td className="number">{money(row.expenses)}</td>
                  <td className="number">
                    <strong className={Number(row.net_profit) < 0 ? 'owed' : undefined}>{money(row.net_profit)}</strong>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
