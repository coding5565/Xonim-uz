import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, ShieldCheck, UtensilsCrossed } from 'lucide-react'
import { api, refreshCsrf } from '../api'
import { homeFor, session } from '../session'
import type { User } from '../types'

export default function LoginPage() {
  const navigate = useNavigate()
  const [username, setUsername] = useState('owner')
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
          <span className="brand-mark">h<span>•</span></span>
          <span className="brand-text">honim<span>RESTAURANT WORKSPACE</span></span>
        </div>
        <div className="login-headline">
          <span className="eyebrow">MEHMONDO‘STLIK. TARTIB. NAZORAT.</span>
          <h1>Restoraningiz.<br />Bir butun<br /><em>ish maydoni.</em></h1>
          <p>Buyurtmadan kun yakunigacha — har bir tafsilot o‘z o‘rnida.</p>
          <div className="login-orbit"><div><UtensilsCrossed size={60} strokeWidth={1} /></div></div>
        </div>
        <small>Honim · Restoran boshqaruv tizimi</small>
      </section>
      <section className="login-form">
        <span className="pill">Xush kelibsiz</span>
        <h2>Ish kunini boshlaymiz.</h2>
        <p className="muted">Hisobingizga kirib, restoranni boshqaring.</p>
        <form onSubmit={login}>
          <label>
            Login
            <input
              value={username}
              onChange={event => setUsername(event.target.value)}
              autoComplete="username"
              required
              placeholder="Loginingiz"
            />
          </label>
          <label>
            Parol
            <input
              value={password}
              onChange={event => setPassword(event.target.value)}
              type="password"
              autoComplete="current-password"
              required
              placeholder="Parolingizni kiriting"
            />
          </label>
          {error && <p className="alert error" role="alert">{error}</p>}
          <button className="button primary" disabled={busy}>
            {busy ? 'Tekshirilmoqda…' : 'Tizimga kirish'}<ArrowRight size={18} />
          </button>
        </form>
        <p className="security-note"><ShieldCheck size={18} />Himoyalangan sessiya orqali kirish</p>
        <div className="login-help">
          Mahalliy sinov hisobi uchun login va parol loyiha ichidagi <strong>.local-access.txt</strong> faylida.
        </div>
        <Link to="/menu" className="text-link">Mijoz menyusini ko‘rish →</Link>
      </section>
    </div>
  )
}
