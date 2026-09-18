import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  Banknote, CalendarCheck, Download, Pencil, Plus, Search, ShieldCheck, UserRoundCog, Users,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, download, money, today } from '../api'
import AppModal from '../components/AppModal'

interface Staff {
  id: number
  name: string
  username: string
  role: 'owner' | 'admin' | 'cashier' | 'kitchen'
  active: boolean
  phone: string
  salary: string
  hired_at: string | null
  notes: string
  last_login: string | null
  last_salary_period: string | null
  last_salary_paid_on: string | null
}

interface SalaryPayment {
  id: number
  period: string
  amount: string
  payment_method: 'cash' | 'card'
  paid_on: string
  note: string
  actor_name: string
}

interface CreateForm {
  name: string
  username: string
  role: string
  password: string
  phone: string
  salary: string
  hired_at: string
  notes: string
}

interface EditForm {
  name: string
  role: string
  phone: string
  salary: string
  hired_at: string
  notes: string
  active: boolean
}

interface PayForm {
  period: string
  amount: string
  payment_method: string
  paid_on: string
  note: string
}

const roleName = (role: string) =>
  role === 'owner' ? 'Superadmin' : role === 'admin' ? 'Admin' : role === 'kitchen' ? 'Oshxona' : 'Kassir'

export default function StaffPage() {
  const currentMonth = today().slice(0, 7)
  const [staff, setStaff] = useState<Staff[]>([])
  const [payments, setPayments] = useState<SalaryPayment[]>([])
  const [selected, setSelected] = useState<Staff>()
  const [query, setQuery] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [payOpen, setPayOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [createForm, setCreateForm] = useState<CreateForm>({
    name: '', username: '', role: 'admin', password: '', phone: '', salary: '', hired_at: today(), notes: '',
  })
  const [editForm, setEditForm] = useState<EditForm>({
    name: '', role: 'admin', phone: '', salary: '', hired_at: '', notes: '', active: true,
  })
  const [payForm, setPayForm] = useState<PayForm>({
    period: currentMonth, amount: '', payment_method: 'cash', paid_on: today(), note: '',
  })

  const updateCreate = (patch: Partial<CreateForm>) => setCreateForm(previous => ({ ...previous, ...patch }))
  const updateEdit = (patch: Partial<EditForm>) => setEditForm(previous => ({ ...previous, ...patch }))
  const updatePay = (patch: Partial<PayForm>) => setPayForm(previous => ({ ...previous, ...patch }))

  const load = useCallback(async () => {
    try {
      setStaff(await api<Staff[]>('staff/'))
    } catch (exception) {
      setError((exception as Error).message)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const filtered = staff.filter(item =>
    `${item.name} ${item.username} ${item.phone} ${item.role}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
  )
  const employees = staff.filter(item => item.role !== 'owner')
  const activeCount = employees.filter(item => item.active).length
  const monthlyPayroll = employees.filter(item => item.active).reduce((sum, item) => sum + Number(item.salary), 0)
  const paidThisMonth = employees.filter(item => item.last_salary_period === currentMonth).length

  function startCreate() {
    setCreateForm({
      name: '', username: '', role: 'admin', password: '', phone: '', salary: '', hired_at: today(), notes: '',
    })
    setFormError('')
    setCreateOpen(true)
  }

  async function createStaff(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setFormError('')
    try {
      await api('staff/', {
        method: 'POST',
        body: JSON.stringify({
          ...createForm,
          salary: createForm.salary || '0',
          hired_at: createForm.hired_at || null,
        }),
      })
      setCreateOpen(false)
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function startEdit(item: Staff) {
    setSelected(item)
    setEditForm({
      name: item.name,
      role: item.role,
      phone: item.phone,
      salary: item.salary,
      hired_at: item.hired_at || '',
      notes: item.notes,
      active: item.active,
    })
    setFormError('')
    setEditOpen(true)
  }

  async function updateStaff(event: FormEvent) {
    event.preventDefault()
    if (!selected) return
    setBusy(true)
    setFormError('')
    try {
      await api(`staff/${selected.id}/`, {
        method: 'PATCH',
        body: JSON.stringify({ ...editForm, hired_at: editForm.hired_at || null }),
      })
      setEditOpen(false)
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function loadPayments(item: Staff) {
    setPayments(await api<SalaryPayment[]>(`staff/${item.id}/salary-payments/`))
  }

  async function startPay(item: Staff) {
    setSelected(item)
    setPayForm({
      period: currentMonth, amount: item.salary, payment_method: 'cash', paid_on: today(), note: '',
    })
    setFormError('')
    try {
      await loadPayments(item)
      setPayOpen(true)
    } catch (exception) {
      setError((exception as Error).message)
    }
  }

  async function paySalary(event: FormEvent) {
    event.preventDefault()
    if (!selected) return
    setBusy(true)
    setFormError('')
    try {
      await api(`staff/${selected.id}/salary-payments/`, { method: 'POST', body: JSON.stringify(payForm) })
      setPayOpen(false)
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function showHistory(item: Staff) {
    setSelected(item)
    setError('')
    try {
      await loadPayments(item)
      setHistoryOpen(true)
    } catch (exception) {
      setError((exception as Error).message)
    }
  }

  async function exportPayroll() {
    try {
      await download('staff/salary-payments/export/', 'honim-umumiy-oyliklar.xlsx')
    } catch (exception) {
      setError((exception as Error).message)
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">JAMOA VA ISH HAQI</span>
          <h1>Xodimlar<span className="heading-dot">.</span></h1>
          <p>Hisoblar, lavozimlar va oylik to‘lovlari bir joyda.</p>
        </div>
        <div className="heading-actions">
          <Link to="/payroll" className="button secondary"><Banknote size={17} />Oyliklar tahlili</Link>
          <button className="button secondary" onClick={exportPayroll}><Download size={17} />Oyliklar Excel</button>
          <button className="button primary" onClick={startCreate}><Plus size={18} />Xodim yaratish</button>
        </div>
      </div>
      {error && <p className="alert error">{error}</p>}
      <div className="staff-summary-grid">
        <article>
          <Users /><span>Faol xodimlar</span><strong>{activeCount}</strong>
          <small>{employees.length} ta xodim hisobidan</small>
        </article>
        <article>
          <Banknote /><span>Oylik ish haqi fondi</span><strong>{money(monthlyPayroll)}</strong><small>so‘m / oy</small>
        </article>
        <article>
          <CalendarCheck /><span>{currentMonth} da to‘langan</span>
          <strong>{paidThisMonth} / {activeCount}</strong><small>har xodimga oyiga bir marta</small>
        </article>
      </div>
      <section className="panel">
        <header className="panel-heading">
          <div><h2>Xodimlar ro‘yxati</h2><p>Rol, oylik va hisob holatini boshqaring</p></div>
          <div className="search-field">
            <Search size={17} />
            <input
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder="Ism, login yoki telefon…"
              aria-label="Xodim qidirish"
            />
          </div>
        </header>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>XODIM</th><th>ROL</th><th>OYLIK</th><th>SO‘NGGI TO‘LOV</th><th>HOLAT</th><th>AMALLAR</th></tr>
            </thead>
            <tbody>
              {filtered.map(item => (
                <tr key={item.id}>
                  <td>
                    <strong>{item.name}</strong>
                    <small>@{item.username}{item.phone ? ` · ${item.phone}` : ''}</small>
                  </td>
                  <td><span className="pill subtle">{roleName(item.role)}</span></td>
                  <td className="number">{item.role === 'owner' ? '—' : `${money(item.salary)} so‘m`}</td>
                  <td>
                    {item.role === 'owner' ? <span>—</span>
                      : item.last_salary_period ? (
                        <>
                          <strong>{item.last_salary_period}</strong>
                          <small>{item.last_salary_paid_on}</small>
                        </>
                      ) : <span>To‘lov yo‘q</span>}
                  </td>
                  <td>
                    <span className={`status ${item.active ? 'paid' : 'open'}`}>
                      {item.active ? 'Faol' : 'Bloklangan'}
                    </span>
                  </td>
                  <td>
                    {item.role !== 'owner' ? (
                      <div className="staff-actions">
                        <button className="table-action" title="Tahrirlash" onClick={() => startEdit(item)}>
                          <Pencil size={15} />
                        </button>
                        <button className="table-action pay" onClick={() => startPay(item)}>
                          <Banknote size={15} />Oylik
                        </button>
                        <button className="text-link" onClick={() => showHistory(item)}>Tarix</button>
                      </div>
                    ) : <small>Bosh hisob</small>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!filtered.length && (
            <div className="empty-state"><UserRoundCog size={38} strokeWidth={1.3} /><h3>Xodim topilmadi</h3></div>
          )}
        </div>
      </section>
      <div className="inline-tip">
        <ShieldCheck size={20} />
        <span>
          Oylik to‘lovi saqlanganda “Ish haqi” kategoriyasida xarajat yaratiladi va superadmin dashboardida darhol hisoblanadi.
        </span>
      </div>

      <AppModal open={createOpen} title="Yangi xodim hisobi" onClose={() => { if (!busy) setCreateOpen(false) }}>
        <form onSubmit={createStaff}>
          <div className="form-row">
            <label>
              Xodim ismi
              <input
                value={createForm.name}
                onChange={event => updateCreate({ name: event.target.value })}
                required
                maxLength={150}
                placeholder="Masalan, Azizbek"
              />
            </label>
            <label>
              Telefon
              <input
                value={createForm.phone}
                onChange={event => updateCreate({ phone: event.target.value })}
                maxLength={30}
                placeholder="+998 90 123 45 67"
              />
            </label>
          </div>
          <div className="form-row">
            <label>
              Login
              <input
                value={createForm.username}
                onChange={event => updateCreate({ username: event.target.value })}
                required
                minLength={3}
                maxLength={150}
                pattern="[A-Za-z0-9_@.+-]+"
                autoComplete="off"
                placeholder="aziz_admin"
              />
            </label>
            <label>
              Rol
              <select value={createForm.role} onChange={event => updateCreate({ role: event.target.value })}>
                <option value="admin">Admin</option>
                <option value="cashier">Kassir</option>
                <option value="kitchen">Oshxona</option>
              </select>
            </label>
          </div>
          <div className="form-row">
            <label>
              Oylik, so‘m
              <input
                value={createForm.salary}
                onChange={event => updateCreate({ salary: event.target.value })}
                type="number"
                min="0"
                step="1000"
                placeholder="3500000"
              />
            </label>
            <label>
              Ishga kirgan sana
              <input
                value={createForm.hired_at}
                onChange={event => updateCreate({ hired_at: event.target.value })}
                type="date"
                max={today()}
              />
            </label>
          </div>
          <label>
            Vaqtinchalik parol
            <input
              value={createForm.password}
              onChange={event => updateCreate({ password: event.target.value })}
              type="password"
              required
              minLength={12}
              maxLength={128}
              autoComplete="new-password"
              placeholder="Kamida 12 belgi"
            />
          </label>
          <label>
            Izoh
            <textarea
              value={createForm.notes}
              onChange={event => updateCreate({ notes: event.target.value })}
              maxLength={300}
              rows={2}
              placeholder="Lavozim yoki qo‘shimcha ma’lumot"
            />
          </label>
          <p className="alert">Login va parolni xodimga xavfsiz yetkazing. Tizim parolni keyin qayta ko‘rsatmaydi.</p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? 'Yaratilmoqda…' : 'Hisobni yaratish'}
          </button>
        </form>
      </AppModal>

      <AppModal open={editOpen} title="Xodim ma’lumotlari" onClose={() => { if (!busy) setEditOpen(false) }}>
        <form onSubmit={updateStaff}>
          <div className="form-row">
            <label>
              Ism
              <input value={editForm.name} onChange={event => updateEdit({ name: event.target.value })} required maxLength={150} />
            </label>
            <label>
              Telefon
              <input value={editForm.phone} onChange={event => updateEdit({ phone: event.target.value })} maxLength={30} />
            </label>
          </div>
          <div className="form-row">
            <label>
              Rol
              <select value={editForm.role} onChange={event => updateEdit({ role: event.target.value })}>
                <option value="admin">Admin</option>
                <option value="cashier">Kassir</option>
                <option value="kitchen">Oshxona</option>
              </select>
            </label>
            <label>
              Oylik, so‘m
              <input
                value={editForm.salary}
                onChange={event => updateEdit({ salary: event.target.value })}
                type="number"
                min="0"
                step="1000"
                required
              />
            </label>
          </div>
          <label>
            Ishga kirgan sana
            <input
              value={editForm.hired_at}
              onChange={event => updateEdit({ hired_at: event.target.value })}
              type="date"
              max={today()}
            />
          </label>
          <label>
            Izoh
            <textarea
              value={editForm.notes}
              onChange={event => updateEdit({ notes: event.target.value })}
              maxLength={300}
              rows={2}
            />
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={editForm.active} onChange={event => updateEdit({ active: event.target.checked })} />
            Hisob faol, tizimga kira oladi
          </label>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? 'Saqlanmoqda…' : 'O‘zgarishlarni saqlash'}
          </button>
        </form>
      </AppModal>

      <AppModal
        open={payOpen}
        title={`${selected?.name || ''} · oylik to‘lovi`}
        onClose={() => { if (!busy) setPayOpen(false) }}
      >
        <form onSubmit={paySalary}>
          <div className="salary-amount">{money(payForm.amount || 0)} <small>so‘m</small></div>
          <div className="form-row">
            <label>
              Qaysi oy uchun?
              <input
                value={payForm.period}
                onChange={event => updatePay({ period: event.target.value })}
                type="month"
                max={currentMonth}
                required
              />
            </label>
            <label>
              To‘lov sanasi
              <input
                value={payForm.paid_on}
                onChange={event => updatePay({ paid_on: event.target.value })}
                type="date"
                max={today()}
                required
              />
            </label>
          </div>
          <div className="form-row">
            <label>
              Summa
              <input
                value={payForm.amount}
                onChange={event => updatePay({ amount: event.target.value })}
                type="number"
                min="1"
                step="1000"
                required
              />
            </label>
            <label>
              To‘lov usuli
              <select value={payForm.payment_method} onChange={event => updatePay({ payment_method: event.target.value })}>
                <option value="cash">Naqd</option>
                <option value="card">Karta</option>
              </select>
            </label>
          </div>
          <label>
            Izoh
            <textarea
              value={payForm.note}
              onChange={event => updatePay({ note: event.target.value })}
              maxLength={250}
              rows={2}
              placeholder="Avans, bonus yoki boshqa izoh"
            />
          </label>
          <p className="alert">
            Bir xodimga bir oy uchun faqat bitta oylik to‘lovi yoziladi. To‘lov xarajatlarda ham aks etadi.
          </p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? 'Saqlanmoqda…' : 'Oylikni to‘langan deb belgilash'}
          </button>
        </form>
      </AppModal>

      <AppModal
        open={historyOpen}
        title={`${selected?.name || ''} · to‘lovlar tarixi`}
        onClose={() => setHistoryOpen(false)}
      >
        <div className="salary-history">
          {payments.map(item => (
            <div key={item.id}>
              <span>
                <strong>{item.period}</strong>
                <small>{item.paid_on} · {item.payment_method === 'cash' ? 'Naqd' : 'Karta'} · {item.actor_name}</small>
              </span>
              <strong>{money(item.amount)} so‘m</strong>
              {item.note && <p>{item.note}</p>}
            </div>
          ))}
          {!payments.length && (
            <div className="empty-state compact"><Banknote size={32} /><p>Hali oylik to‘lovi kiritilmagan.</p></div>
          )}
        </div>
      </AppModal>
    </>
  )
}
