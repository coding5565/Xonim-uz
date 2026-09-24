import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  Banknote, CalendarCheck, Download, Pencil, Plus, Search, ShieldCheck, UserRoundCog, Users,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, download, money, today } from '../api'
import AppModal from '../components/AppModal'
import { useI18n } from '../i18n'

interface Staff {
  id: number
  name: string
  /** Erkin matn: «Oshpaz», «Farrosh» — ro'yxat emas. */
  position: string
  /** Tizimga kirmaydigan xodimda bo'sh. */
  username: string
  role: 'owner' | 'cashier' | 'kitchen' | ''
  active: boolean
  phone: string
  daily_wage: string
  week_wage: string
  hired_at: string | null
  notes: string
  last_login: string | null
  /** Davomatdan yig'ilgan haq − berilgan pul. */
  days_worked: number
  earned: string
  paid: string
  balance: string
  last_salary_amount: string | null
  last_salary_paid_on: string | null
}

interface SalaryPayment {
  id: number
  amount: string
  payment_method: 'cash' | 'card'
  payment_label: string
  paid_on: string
  note: string
  actor_name: string
}

interface CreateForm {
  name: string
  position: string
  phone: string
  daily_wage: string
  hired_at: string
  notes: string
  /** Tizimga kirish kerak bo'lsagina to'ldiriladi. */
  username: string
  role: string
  password: string
}

interface EditForm {
  name: string
  position: string
  role: string
  phone: string
  daily_wage: string
  hired_at: string
  notes: string
  active: boolean
}

interface PayForm {
  key: string
  amount: string
  payment_method: string
  paid_on: string
  note: string
}

const roleName = (role: string) =>
  role === 'owner' ? 'Superadmin' : role === 'kitchen' ? 'Oshxona' : role ? 'Kassir' : ''

export default function StaffPage() {
  const { t, tn } = useI18n()
  const [staff, setStaff] = useState<Staff[]>([])
  const [payments, setPayments] = useState<SalaryPayment[]>([])
  const [selected, setSelected] = useState<Staff>()
  const [query, setQuery] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [editOpen, setEditOpen] = useState(false)
  const [payOpen, setPayOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  // Login bo'limi ataylab ochiladi: ko'pchilik xodim tizimga kirmaydi.
  const [wantsLogin, setWantsLogin] = useState(false)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [createForm, setCreateForm] = useState<CreateForm>({
    name: '', position: '', phone: '', daily_wage: '', hired_at: today(), notes: '',
    username: '', role: 'cashier', password: '',
  })
  const [editForm, setEditForm] = useState<EditForm>({
    name: '', position: '', role: 'cashier', phone: '', daily_wage: '', hired_at: '', notes: '', active: true,
  })
  const [payForm, setPayForm] = useState<PayForm>({
    key: '', amount: '', payment_method: 'cash', paid_on: today(), note: '',
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
    `${item.name} ${item.position} ${item.username} ${item.phone}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
  )
  const employees = staff.filter(item => item.role !== 'owner')
  const activeCount = employees.filter(item => item.active).length
  // Hafta olti kun: to'liq ishlangan haftaning narxi.
  const weeklyPayroll = employees.filter(item => item.active).reduce((sum, item) => sum + Number(item.week_wage), 0)
  const owed = employees.reduce((sum, item) => sum + Number(item.balance), 0)

  function startCreate() {
    setCreateForm({
      name: '', position: '', phone: '', daily_wage: '', hired_at: today(), notes: '',
      username: '', role: 'cashier', password: '',
    })
    setWantsLogin(false)
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
          daily_wage: createForm.daily_wage || '0',
          hired_at: createForm.hired_at || null,
          // Login bo'sh bo'lsa hisob ochilmaydi — maydonlar ham
          // yuborilmaydi, aks holda server ularni to'ldirilgan deb o'qiydi.
          username: createForm.username || undefined,
          role: createForm.username ? createForm.role : undefined,
          password: createForm.username ? createForm.password : undefined,
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
      position: item.position,
      role: item.role || 'cashier',
      phone: item.phone,
      daily_wage: item.daily_wage,
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
        body: JSON.stringify({
          ...editForm,
          hired_at: editForm.hired_at || null,
          // Rol hisobga tegishli: logini yo'q xodimga yuborilsa server
          // uni xato deb qaytaradi.
          role: selected.username ? editForm.role : undefined,
        }),
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
      // Kalit shu yerda tug'iladi: ikki marta bosilgan tugma ikki marta
      // pul bermaydi.
      key: crypto.randomUUID(),
      // Odatda qarzning hammasi beriladi; boshqa summa qo'lda yoziladi.
      amount: Number(item.balance) > 0 ? item.balance : '',
      payment_method: 'cash',
      paid_on: today(),
      note: '',
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
      await download('staff/salary-payments/export/', 'xonim-umumiy-oyliklar.xlsx')
    } catch (exception) {
      setError((exception as Error).message)
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('JAMOA VA ISH HAQI')}</span>
          <h1>{t('Xodimlar')}<span className="heading-dot">.</span></h1>
          <p>{t('Hisoblar, lavozimlar va kunlik ish haqi bir joyda.')}</p>
        </div>
        <div className="heading-actions">
          <Link to="/payroll" className="button secondary"><Banknote size={17} />{t('Davomat va ish haqi')}</Link>
          <button className="button secondary" onClick={exportPayroll}><Download size={17} />{t('To‘lovlar Excel')}</button>
          <button className="button primary" onClick={startCreate}><Plus size={18} />{t('Xodim yaratish')}</button>
        </div>
      </div>
      {error && <p className="alert error">{error}</p>}
      <div className="staff-summary-grid">
        <article>
          <Users /><span>{t('Faol xodimlar')}</span><strong>{activeCount}</strong>
          <small>{tn('{count} ta xodim hisobidan', employees.length)}</small>
        </article>
        <article>
          <Banknote /><span>{t('Haftalik ish haqi fondi')}</span><strong>{money(weeklyPayroll)}</strong>
          <small>{t('so‘m · olti kunlik hafta')}</small>
        </article>
        <article>
          <CalendarCheck /><span>{t('Hozirgi qarzimiz')}</span>
          <strong className={owed > 0 ? 'owed' : undefined}>{money(owed)}</strong>
          <small>{t('yig‘ilgan haq − berilgan pul')}</small>
        </article>
      </div>
      <section className="panel">
        <header className="panel-heading">
          <div><h2>{t('Xodimlar ro‘yxati')}</h2><p>{t('Rol, kunlik haq va hisob holatini boshqaring')}</p></div>
          <div className="search-field">
            <Search size={17} />
            <input
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder={t('Ism, login yoki telefon…')}
              aria-label={t('Xodim qidirish')}
            />
          </div>
        </header>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t('XODIM')}</th><th>{t('LAVOZIM')}</th><th>{t('KUNLIK HAQ')}</th>
                <th>{t('BALANS')}</th><th>{t('SO‘NGGI TO‘LOV')}</th><th>{t('HOLAT')}</th><th>{t('AMALLAR')}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(item => (
                <tr key={item.id}>
                  <td>
                    <strong>{item.name}</strong>
                    <small>
                      {item.username ? `@${item.username}` : t('tizimga kirmaydi')}
                      {item.phone ? ` · ${item.phone}` : ''}
                    </small>
                  </td>
                  <td>
                    <span className="pill subtle">{item.position || t('Lavozimsiz')}</span>
                    {!!item.role && <small>{t(roleName(item.role))}</small>}
                  </td>
                  <td className="number">
                    {item.role === 'owner' ? '—' : (
                      <>
                        {money(item.daily_wage)} {t('so‘m')}
                        <small>{t('haftasiga {amount}', { amount: money(item.week_wage) })}</small>
                      </>
                    )}
                  </td>
                  <td className="number">
                    {item.role === 'owner' ? '—' : (
                      <>
                        <strong className={Number(item.balance) > 0 ? 'owed' : undefined}>
                          {money(item.balance)}
                        </strong>
                        <small>
                          {tn('{count} ish kuni', item.days_worked)}
                          {Number(item.balance) < 0 ? ` · ${t('avans')}` : ''}
                        </small>
                      </>
                    )}
                  </td>
                  <td>
                    {item.role === 'owner' ? <span>—</span>
                      : item.last_salary_paid_on ? (
                        <>
                          <strong>{money(item.last_salary_amount || 0)}</strong>
                          <small>{item.last_salary_paid_on}</small>
                        </>
                      ) : <span>{t('To‘lov yo‘q')}</span>}
                  </td>
                  <td>
                    <span className={`status ${item.active ? 'paid' : 'open'}`}>
                      {item.active ? t('Faol') : t('Bloklangan')}
                    </span>
                  </td>
                  <td>
                    {item.role !== 'owner' ? (
                      <div className="staff-actions">
                        <button className="table-action" title={t('Tahrirlash')} onClick={() => startEdit(item)}>
                          <Pencil size={15} />
                        </button>
                        <button className="table-action pay" onClick={() => startPay(item)}>
                          <Banknote size={15} />{t('Pul berish')}
                        </button>
                        <button className="text-link" onClick={() => showHistory(item)}>{t('Tarix')}</button>
                      </div>
                    ) : <small>{t('Bosh hisob')}</small>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!filtered.length && (
            <div className="empty-state"><UserRoundCog size={38} strokeWidth={1.3} /><h3>{t('Xodim topilmadi')}</h3></div>
          )}
        </div>
      </section>
      <div className="inline-tip">
        <ShieldCheck size={20} />
        <span>
          {t('Har bir to‘lov “Ish haqi” kategoriyasida xarajat yaratadi va xodimning balansidan ayriladi. Haq esa davomatdan yig‘iladi — “Davomat va ish haqi” bo‘limida.')}
        </span>
      </div>

      <AppModal open={createOpen} title={t('Yangi xodim hisobi')} onClose={() => { if (!busy) setCreateOpen(false) }}>
        <form onSubmit={createStaff}>
          <div className="form-row">
            <label>
              {t('Xodim ismi')}
              <input
                value={createForm.name}
                onChange={event => updateCreate({ name: event.target.value })}
                required
                maxLength={150}
                placeholder={t('Masalan, Azizbek')}
              />
            </label>
            <label>
              {t('Telefon')}
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
              {t('Lavozim')}
              <small className="field-hint">{t('O‘zingiz yozasiz: oshpaz, farrosh, ofitsiant…')}</small>
              <input
                value={createForm.position}
                onChange={event => updateCreate({ position: event.target.value })}
                maxLength={60}
                placeholder={t('Masalan, Oshpaz')}
              />
            </label>
          </div>
          <div className="form-row">
            <label>
              {t('Kunlik haq, so‘m')}
              <small className="field-hint">{t('Bir ish kuni uchun. Hafta olti kun.')}</small>
              <input
                value={createForm.daily_wage}
                onChange={event => updateCreate({ daily_wage: event.target.value })}
                type="number"
                min="0"
                step="any"
                placeholder="150000"
              />
            </label>
            <label>
              {t('Ishga kirgan sana')}
              <input
                value={createForm.hired_at}
                onChange={event => updateCreate({ hired_at: event.target.value })}
                type="date"
                max={today()}
              />
            </label>
          </div>
          {/* Ko'pchilik xodim tizimga umuman kirmaydi, shuning uchun login
              bo'limi yopiq turadi va ataylab ochiladi. */}
          <label className="checkbox">
            <input
              type="checkbox"
              checked={!!createForm.username || wantsLogin}
              onChange={event => {
                setWantsLogin(event.target.checked)
                if (!event.target.checked) updateCreate({ username: '', password: '' })
              }}
            />
            {t('Bu xodim tizimga kiradi')}
          </label>
          {(wantsLogin || !!createForm.username) && (
            <>
              <div className="form-row">
                <label>
                  {t('Login')}
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
                  {t('Rol')}
                  <select value={createForm.role} onChange={event => updateCreate({ role: event.target.value })}>
                    <option value="cashier">{t('Kassir')}</option>
                    <option value="kitchen">{t('Oshxona')}</option>
                  </select>
                </label>
              </div>
              <label>
                {t('Vaqtinchalik parol')}
                <input
                  value={createForm.password}
                  onChange={event => updateCreate({ password: event.target.value })}
                  type="password"
                  required
                  minLength={12}
                  maxLength={128}
                  autoComplete="new-password"
                  placeholder={t('Kamida 12 belgi')}
                />
              </label>
            </>
          )}
          <label>
            {t('Izoh')}
            <textarea
              value={createForm.notes}
              onChange={event => updateCreate({ notes: event.target.value })}
              maxLength={300}
              rows={2}
              placeholder={t('Lavozim yoki qo‘shimcha ma’lumot')}
            />
          </label>
          <p className="alert">{t('Login va parolni xodimga xavfsiz yetkazing. Tizim parolni keyin qayta ko‘rsatmaydi.')}</p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? t('Yaratilmoqda…') : t('Hisobni yaratish')}
          </button>
        </form>
      </AppModal>

      <AppModal open={editOpen} title={t('Xodim ma’lumotlari')} onClose={() => { if (!busy) setEditOpen(false) }}>
        <form onSubmit={updateStaff}>
          <div className="form-row">
            <label>
              {t('Ism')}
              <input value={editForm.name} onChange={event => updateEdit({ name: event.target.value })} required maxLength={150} />
            </label>
            <label>
              {t('Telefon')}
              <input value={editForm.phone} onChange={event => updateEdit({ phone: event.target.value })} maxLength={30} />
            </label>
          </div>
          <div className="form-row">
            <label>
              {t('Lavozim')}
              <input
                value={editForm.position}
                onChange={event => updateEdit({ position: event.target.value })}
                maxLength={60}
                placeholder={t('Masalan, Oshpaz')}
              />
            </label>
            {!!selected?.username && (
              <label>
                {t('Rol')}
                <select value={editForm.role} onChange={event => updateEdit({ role: event.target.value })}>
                  <option value="cashier">{t('Kassir')}</option>
                  <option value="kitchen">{t('Oshxona')}</option>
                </select>
              </label>
            )}
            <label>
              {t('Kunlik haq, so‘m')}
              <small className="field-hint">{t('O‘zgarish faqat keyingi kunlarga ta’sir qiladi')}</small>
              <input
                value={editForm.daily_wage}
                onChange={event => updateEdit({ daily_wage: event.target.value })}
                type="number"
                min="0"
                step="any"
                required
              />
            </label>
          </div>
          <label>
            {t('Ishga kirgan sana')}
            <input
              value={editForm.hired_at}
              onChange={event => updateEdit({ hired_at: event.target.value })}
              type="date"
              max={today()}
            />
          </label>
          <label>
            {t('Izoh')}
            <textarea
              value={editForm.notes}
              onChange={event => updateEdit({ notes: event.target.value })}
              maxLength={300}
              rows={2}
            />
          </label>
          <label className="checkbox">
            <input type="checkbox" checked={editForm.active} onChange={event => updateEdit({ active: event.target.checked })} />
            {t('Hisob faol, tizimga kira oladi')}
          </label>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? t('Saqlanmoqda…') : t('O‘zgarishlarni saqlash')}
          </button>
        </form>
      </AppModal>

      <AppModal
        open={payOpen}
        title={t('{name} · pul berish', { name: selected?.name || '' })}
        onClose={() => { if (!busy) setPayOpen(false) }}
      >
        <form onSubmit={paySalary}>
          <div className="salary-amount">{money(payForm.amount || 0)} <small>{t('so‘m')}</small></div>
          {!!selected && (
            <p className="alert">
              {Number(selected.balance) >= 0
                ? t('Hozirgi qarz: {amount} so‘m · {days} ish kuni yig‘ilgan', {
                  amount: money(selected.balance), days: selected.days_worked,
                })
                : t('Bu xodimga {amount} so‘m avans berilgan — yangi to‘lov uning ustiga qo‘shiladi', {
                  amount: money(Math.abs(Number(selected.balance))),
                })}
            </p>
          )}
          <div className="form-row">
            <label>
              {t('To‘lov sanasi')}
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
              {t('Summa')}
              <input
                value={payForm.amount}
                onChange={event => updatePay({ amount: event.target.value })}
                type="number"
                min="1"
                step="any"
                required
              />
            </label>
            <label>
              {t('To‘lov usuli')}
              <select value={payForm.payment_method} onChange={event => updatePay({ payment_method: event.target.value })}>
                <option value="cash">{t('Naqd')}</option>
                <option value="card">{t('Karta')}</option>
              </select>
            </label>
          </div>
          <label>
            {t('Izoh')}
            <textarea
              value={payForm.note}
              onChange={event => updatePay({ note: event.target.value })}
              maxLength={250}
              rows={2}
              placeholder={t('Avans, bonus yoki boshqa izoh')}
            />
          </label>
          <p className="data-note">
            {t('Istalgan summa, istalgan kuni: to‘lov balansdan ayriladi. Balansdan ko‘p berilsa qolgani avans bo‘lib turadi va keyingi ish kunlari bilan yopiladi.')}
          </p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? t('Saqlanmoqda…') : t('Pulni berildi deb yozish')}
          </button>
        </form>
      </AppModal>

      <AppModal
        open={historyOpen}
        title={t('{name} · to‘lovlar tarixi', { name: selected?.name || '' })}
        onClose={() => setHistoryOpen(false)}
      >
        <div className="salary-history">
          {payments.map(item => (
            <div key={item.id}>
              <span>
                <strong>{item.paid_on}</strong>
                <small>
                  {item.payment_method === 'cash' ? t('Naqd') : t('Karta')} · {item.actor_name}
                </small>
              </span>
              <strong>{money(item.amount)} {t('so‘m')}</strong>
              {item.note && <p>{item.note}</p>}
            </div>
          ))}
          {!payments.length && (
            <div className="empty-state compact"><Banknote size={32} /><p>{t('Hali oylik to‘lovi kiritilmagan.')}</p></div>
          )}
        </div>
      </AppModal>
    </>
  )
}
