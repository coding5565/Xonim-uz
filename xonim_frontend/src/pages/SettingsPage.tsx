import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import QRCode from 'qrcode'
import { ArrowRight, Bike, CheckCircle2, Clock3, DatabaseBackup, ExternalLink, KeyRound, QrCode, Server, ShieldCheck } from 'lucide-react'
import { api, dateLabel } from '../api'
import { useI18n } from '../i18n'
import type { ActivityLog, BackupState, ChannelFees } from '../types'
import { useSession } from '../session'

const ready = [
  'Sessiya, CSRF va rol bo‘yicha ruxsat',
  'Kategoriya, taom va rasm yuklash',
  'Buyurtma, to‘lov qaydi va brauzer cheki',
  'Xarajatlar va tushum grafigi',
  'Ombor kirimi va haqiqiy sarf',
  'Xodim profili, oylik va to‘lovlar tarixi',
]
const pending = ['Retsept, tannarx va smenalar', 'Printer/fiskal va bulut sinxronlash']

export default function SettingsPage() {
  const { t, tn } = useI18n()
  const { user } = useSession()
  const [qr, setQr] = useState('')
  const [error, setError] = useState('')
  const [audit, setAudit] = useState<ActivityLog>()
  const [fees, setFees] = useState<ChannelFees>()
  // Tahrirdagi qiymat alohida turadi: serverdan kelgan raqam yozayotganda
  // ostidan o'zgarib ketmasligi kerak.
  const [rates, setRates] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState('')
  const [saved, setSaved] = useState('')
  // Parol almashtirish: ilgari buning yo'li umuman yo'q edi.
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [repeat, setRepeat] = useState('')
  const [passwordBusy, setPasswordBusy] = useState(false)
  const [passwordError, setPasswordError] = useState('')
  const [passwordDone, setPasswordDone] = useState('')
  // Zaxira nusxa: jadval bo'yicha kuniga ikki marta olinadi, bu tugma esa
  // «hozir kerak» degan holat uchun.
  const [backup, setBackup] = useState<BackupState>()
  const [backupBusy, setBackupBusy] = useState(false)
  const [backupError, setBackupError] = useState('')
  const [backupDone, setBackupDone] = useState('')
  // Menyu manzili filialga bog'liq.
  const menuPath = user?.branch_slug ? `/menu/${user.branch_slug}` : '/menu'
  const url = `${window.location.origin}${menuPath}`

  useEffect(() => {
    async function load() {
      try {
        setQr(await QRCode.toDataURL(url, { width: 260, margin: 2, color: { dark: '#153d32', light: '#ffffff' } }))
        if (user?.role !== 'owner') return
        const [log, platform, saved] = await Promise.all([
          api<ActivityLog>('audit/'),
          api<ChannelFees>('channel-fees/'),
          api<BackupState>('backup/'),
        ])
        setAudit(log)
        setFees(platform)
        setBackup(saved)
        setRates(Object.fromEntries(platform.rows.map(row => [row.channel, row.commission])))
      } catch (exception) {
        setError((exception as Error).message)
      }
    }
    load()
  }, [url, user?.role])

  async function saveFee(channel: string) {
    setSaving(channel)
    setError('')
    setSaved('')
    try {
      const next = await api<ChannelFees>('channel-fees/', {
        method: 'PUT',
        body: JSON.stringify({ channel, commission: rates[channel] }),
      })
      setFees(next)
      setRates(Object.fromEntries(next.rows.map(row => [row.channel, row.commission])))
      setSaved(channel)
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setSaving('')
    }
  }

  async function makeBackup() {
    setBackupBusy(true)
    setBackupError('')
    setBackupDone('')
    try {
      const result = await api<BackupState & { sent_to_telegram: boolean; note: string }>(
        'backup/', { method: 'POST' })
      setBackup(result)
      setBackupDone(result.sent_to_telegram
        ? t('Nusxa olindi va Telegramga yuborildi.')
        : result.note || t('Nusxa olindi, lekin Telegramga yuborilmadi.'))
    } catch (exception) {
      setBackupError((exception as Error).message)
    } finally {
      setBackupBusy(false)
    }
  }

  async function changePassword(event: FormEvent) {
    event.preventDefault()
    setPasswordError('')
    setPasswordDone('')
    if (next !== repeat) return setPasswordError(t('Yangi parollar bir xil emas.'))
    setPasswordBusy(true)
    try {
      await api('auth/password/', {
        method: 'POST',
        body: JSON.stringify({ current_password: current, new_password: next }),
      })
      setCurrent('')
      setNext('')
      setRepeat('')
      setPasswordDone(t('Parol almashtirildi.'))
    } catch (exception) {
      setPasswordError((exception as Error).message)
    } finally {
      setPasswordBusy(false)
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('ISH MAYDONI')}</span>
          <h1>{t('Sozlamalar va QR')}<span className="heading-dot">.</span></h1>
          <p>{t('Mahalliy versiya, menyu havolasi va nazorat tarixi.')}</p>
        </div>
      </div>
      {error && <p className="alert error">{error}</p>}
      <div className="settings-grid">
        <section className="panel qr-panel">
          <QrCode size={26} />
          <h2>{t('Mijoz menyusi')}</h2>
          <p className="muted">{t('Faqat menyu ko‘rish uchun')}</p>
          {qr && <img src={qr} alt={t('Mijoz menyusi QR kodi')} width={230} height={230} />}
          <code>{url}</code>
          <Link to={menuPath} target="_blank" className="button primary">{t('Menyuni ochish')} <ExternalLink size={16} /></Link>
          <p className="data-note">
            {t('Bu QR localhost manziliga olib boradi. Telefonlardan foydalanish uchun LAN yoki ommaviy domen bilan sozlash kerak.')}
          </p>
        </section>
        <section className="panel version-panel">
          <span className="pill">{t('0.1 · Mahalliy ishlab chiqish')}</span>
          <h2>{t('Ishlaydigan asos')}</h2>
          <p className="muted">{t('Haqiqiy yozuvlar saqlanadi. To‘liq restoran tizimi bosqichma-bosqich quriladi.')}</p>
          <ul className="feature-list">
            {ready.map(item => <li key={item}><CheckCircle2 />{t(item)}</li>)}
            {pending.map(item => <li key={item} className="pending"><Clock3 />{t(item)}</li>)}
          </ul>
          <div className="inline-tip"><Server size={20} />{t('PostgreSQL 17 — mahalliy va production bir xil baza')}</div>
          <div className="inline-tip"><ShieldCheck size={20} />{t('Faqat localhost uchun ishga tushirilgan')}</div>
        </section>
      </div>

      {user?.role === 'owner' && (
        <section className="panel spaced">
          <header className="panel-heading">
            <div>
              <h2>{t('Zaxira nusxa')}</h2>
              <p>{t('Baza va taom rasmlari. Har kuni ikki marta o‘zi olinadi va Telegramga yuboriladi.')}</p>
            </div>
            <DatabaseBackup size={19} />
          </header>
          <div className="backup-panel">
            <p className={`alert ${backup?.telegram.configured ? '' : 'error'}`}>
              {backup?.telegram.configured
                ? t('Telegram ulangan ({chat}). Nusxalar shu chatga tushadi.', { chat: backup.telegram.chat })
                : t('Telegram ulanmagan — nusxa faqat serverda saqlanadi.')}
            </p>
            {backupError && <p className="alert error">{backupError}</p>}
            {backupDone && <p className="alert success">{backupDone}</p>}
            <button className="button primary" disabled={backupBusy} onClick={makeBackup}>
              <DatabaseBackup size={17} />
              {t(backupBusy ? 'Nusxa olinmoqda…' : 'Hozir nusxa olish va yuborish')}
            </button>
            {!!backup?.backups.length && (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>{t('FAYL')}</th><th>{t('HAJMI')}</th><th>{t('VAQT')}</th></tr>
                  </thead>
                  <tbody>
                    {backup.backups.map(row => (
                      <tr key={row.name}>
                        <td>
                          <strong>{t(row.kind === 'db' ? 'Baza' : 'Rasmlar')}</strong>
                          <small>{row.name}</small>
                        </td>
                        <td className="number">{row.size}</td>
                        <td>{dateLabel(row.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="data-note">
              {t('Serverda oxirgi {days} kunlik nusxalar saqlanadi, eskilari o‘chiriladi.',
                { days: backup?.keep_days ?? 14 })}
            </p>
          </div>
        </section>
      )}

      {/* Parolni almashtirish har bir xodimga ochiq: unutilgan parol
          yangi hisob ochishni talab qilmasligi kerak. */}
      <section className="panel spaced">
        <header className="panel-heading">
          <div>
            <h2>{t('Parolni almashtirish')}</h2>
            <p>{t('Kamida 12 belgi. Almashtirilgandan keyin boshqa qurilmalardagi sessiyalar uziladi.')}</p>
          </div>
          <KeyRound size={19} />
        </header>
        <form className="password-form" onSubmit={changePassword}>
          <div className="form-row">
            <label>
              {t('Joriy parol')}
              <input
                value={current}
                onChange={event => setCurrent(event.target.value)}
                type="password"
                autoComplete="current-password"
                required
              />
            </label>
            <label>
              {t('Yangi parol')}
              <input
                value={next}
                onChange={event => setNext(event.target.value)}
                type="password"
                autoComplete="new-password"
                minLength={12}
                required
              />
            </label>
            <label>
              {t('Yangi parolni takrorlang')}
              <input
                value={repeat}
                onChange={event => setRepeat(event.target.value)}
                type="password"
                autoComplete="new-password"
                minLength={12}
                required
              />
            </label>
          </div>
          {passwordError && <p className="alert error">{passwordError}</p>}
          {passwordDone && <p className="alert success">{passwordDone}</p>}
          <button className="button primary" disabled={passwordBusy}>
            {t(passwordBusy ? 'Saqlanmoqda…' : 'Parolni almashtirish')}
          </button>
        </form>
      </section>
      {user?.role === 'owner' && !!fees && (
        <section className="panel spaced">
          <header className="panel-heading">
            <div>
              <h2><Bike size={17} /> {t('Platforma ushlanmasi')}</h2>
              <p>{t('Uzum va Yandex savdo summasining qancha qismini o‘zida qoldiradi')}</p>
            </div>
            <span className="pill subtle">{t('Faqat superadmin')}</span>
          </header>
          <div className="fee-rows">
            {fees.rows.map(row => (
              <div key={row.channel} className="fee-row">
                <div className="fee-name">
                  <strong>{t(row.label)}</strong>
                  <small>
                    {row.configured && row.updated_at
                      ? t('o‘zgartirilgan: {date}', { date: dateLabel(row.updated_at) })
                      : t('shartnoma kiritilmagan — standart {percent}%', { percent: fees.default })}
                  </small>
                </div>
                <label className="fee-input">
                  {t('Ushlanma, %')}
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.01"
                    value={rates[row.channel] ?? row.commission}
                    onChange={event => setRates({ ...rates, [row.channel]: event.target.value })}
                  />
                </label>
                <div className="fee-net">
                  <small>{t('Bizga tushadi')}</small>
                  <strong>{(100 - Number(rates[row.channel] ?? row.commission)).toFixed(2)}%</strong>
                </div>
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => saveFee(row.channel)}
                  disabled={saving === row.channel || rates[row.channel] === row.commission}
                >
                  {saving === row.channel ? t('Saqlanmoqda…') : t('Saqlash')}
                </button>
                {saved === row.channel && <span className="pill good">{t('Saqlandi')}</span>}
              </div>
            ))}
          </div>
          <p className="data-note">
            {t('Yangi foiz faqat shu paytdan keyingi sotuvlarga qo‘llanadi. Har bir buyurtma o‘z foizini sotuv paytida muzlatib oladi, shuning uchun o‘tgan kunlarning hisobi o‘zgarmaydi.')}
          </p>
        </section>
      )}
      {user?.role === 'owner' && (
        <section className="panel spaced">
          <header className="panel-heading">
            <div>
              <h2>{t('So‘nggi amallar')}</h2>
              <p>{tn('Jami {count} ta qayd saqlangan · to‘liq ro‘yxat «Harakatlar» bo‘limida', audit?.count ?? 0)}</p>
            </div>
            <Link to="/activity" className="text-link">{t('Hammasini ochish')} <ArrowRight size={15} /></Link>
          </header>
          <div className="table-wrap">
            <table>
              <thead><tr><th>{t('VAQT')}</th><th>{t('XODIM')}</th><th>{t('AMAL')}</th><th>{t('TAFSILOT')}</th></tr></thead>
              <tbody>
                {(audit?.results || []).slice(0, 8).map(row => (
                  <tr key={row.id}>
                    <td>{dateLabel(row.created_at)}</td>
                    <td>{row.actor}</td>
                    <td><Link to={`/activity?action=${row.action}`} className="text-link">{t(row.label)}</Link></td>
                    <td>{row.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!audit?.results.length && <p className="empty-state compact">{t('Hali amallar qayd etilmagan.')}</p>}
          </div>
        </section>
      )}
    </>
  )
}
