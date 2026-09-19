import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import QRCode from 'qrcode'
import { ArrowRight, CheckCircle2, Clock3, ExternalLink, QrCode, Server, ShieldCheck } from 'lucide-react'
import { api, dateLabel } from '../api'
import { useI18n } from '../i18n'
import type { ActivityLog } from '../types'
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
  const url = `${window.location.origin}/menu`

  useEffect(() => {
    async function load() {
      try {
        setQr(await QRCode.toDataURL(url, { width: 260, margin: 2, color: { dark: '#153d32', light: '#ffffff' } }))
        if (user?.role === 'owner') setAudit(await api<ActivityLog>('audit/'))
      } catch (exception) {
        setError((exception as Error).message)
      }
    }
    load()
  }, [url, user?.role])

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
          <Link to="/menu" target="_blank" className="button primary">{t('Menyuni ochish')} <ExternalLink size={16} /></Link>
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
          <div className="inline-tip"><Server size={20} />{t('Mahalliy SQLite · production uchun PostgreSQL')}</div>
          <div className="inline-tip"><ShieldCheck size={20} />{t('Faqat localhost uchun ishga tushirilgan')}</div>
        </section>
      </div>
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
