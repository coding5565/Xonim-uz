import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, ShieldCheck, UtensilsCrossed } from 'lucide-react'
import { api, refreshCsrf } from '../api'
import { useI18n } from '../i18n'
import { homeFor, session } from '../session'
import type { User } from '../types'

export default function LoginPage() {
  const { t } = useI18n()
  const navigate = useNavigate()
  // Bo'sh boshlanadi: ilgari bu yerda «owner» yozib qo'yilgan edi va
  // kirish oynasi haqiqiy hisobning loginini o'zi aytib turardi.
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function login(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await refreshCsrf()
      const user = await api<User>('auth/login/', {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      })
      await refreshCsrf()
      session.set({ user, ready: true })
      navigate(homeFor(user.role))
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-page">
      <section className="login-story">
        <div className="brand light">
          <span className="brand-mark">x<span>•</span></span>
          <span className="brand-text">xonim<span>RESTAURANT WORKSPACE</span></span>
        </div>
        <div className="login-headline">
          <span className="eyebrow">{t('MEHMONDO‘STLIK. TARTIB. NAZORAT.')}</span>
          <h1>{t('Restoraningiz.')}<br />{t('Bir butun')}<br /><em>{t('ish maydoni.')}</em></h1>
          <p>{t('Buyurtmadan kun yakunigacha — har bir tafsilot o‘z o‘rnida.')}</p>
          <div className="login-orbit"><div><UtensilsCrossed size={60} strokeWidth={1} /></div></div>
        </div>
        <small>{t('Xonim · Restoran boshqaruv tizimi')}</small>
      </section>
      <section className="login-form">
        <span className="pill">{t('Xush kelibsiz')}</span>
        <h2>{t('Ish kunini boshlaymiz.')}</h2>
        <p className="muted">{t('Hisobingizga kirib, restoranni boshqaring.')}</p>
        <form onSubmit={login}>
          <label>
            {t('Login')}
            <input
              value={username}
              onChange={event => setUsername(event.target.value)}
              autoComplete="username"
              required
              placeholder={t('Loginingiz')}
            />
          </label>
          <label>
            {t('Parol')}
            <input
              value={password}
              onChange={event => setPassword(event.target.value)}
              type="password"
              autoComplete="current-password"
              required
              placeholder={t('Parolingizni kiriting')}
            />
          </label>
          {error && <p className="alert error" role="alert">{error}</p>}
          <button className="button primary" disabled={busy}>
            {busy ? t('Tekshirilmoqda…') : t('Tizimga kirish')}<ArrowRight size={18} />
          </button>
        </form>
        <p className="security-note"><ShieldCheck size={18} />{t('Himoyalangan sessiya orqali kirish')}</p>
        <div className="login-help">
          {t('Mahalliy sinov hisobi uchun login va parol loyiha ichidagi')} <strong>.local-access.txt</strong> {t('faylida.')}
        </div>
        <Link to="/menu" className="text-link">{t('Mijoz menyusini ko‘rish')} →</Link>
      </section>
    </div>
  )
}
