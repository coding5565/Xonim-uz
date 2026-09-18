import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { LayoutGrid, Pencil, Plus, Trash2 } from 'lucide-react'
import { api, list, money } from '../api'
import type { Table, TableZone } from '../types'
import AppModal from '../components/AppModal'

interface TableForm {
  number: string
  name: string
  seats: string
  zone: TableZone
  seating: 'divan' | 'chair'
  active: boolean
}

const ZONE_LABELS: Record<TableZone, string> = {
  hall_left: 'Ichkari — chap tomon',
  hall_right: 'Ichkari — o‘ng tomon',
  outside: 'Tashqari',
}

const emptyForm: TableForm = {
  number: '', name: '', seats: '4', zone: 'hall_right', seating: 'chair', active: true,
}

export default function TablesAdminPage() {
  const [tables, setTables] = useState<Table[]>([])
  const [modal, setModal] = useState(false)
  const [editId, setEditId] = useState<number>()
  const [form, setForm] = useState<TableForm>(emptyForm)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')

  const update = (patch: Partial<TableForm>) => setForm(previous => ({ ...previous, ...patch }))

  const load = useCallback(async () => {
    try {
      setTables(await list<Table>('tables/'))
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  function open(table?: Table) {
    setFormError('')
    setEditId(table?.id)
    setForm(table
      ? {
        number: String(table.number), name: table.name, seats: String(table.seats),
        zone: table.zone, seating: table.seating, active: table.active,
      }
      : { ...emptyForm, number: String(Math.max(0, ...tables.map(item => item.number)) + 1) })
    setModal(true)
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setFormError('')
    try {
      await api(`tables/${editId ? `${editId}/` : ''}`, {
        method: editId ? 'PATCH' : 'POST',
        body: JSON.stringify({
          number: Number(form.number),
          name: form.name,
          seats: Number(form.seats),
          zone: form.zone,
          seating: form.seating,
          active: form.active,
        }),
      })
      setModal(false)
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(table: Table) {
    if (!confirm(`${table.label} olib tashlansinmi? Savdo tarixi saqlanadi.`)) return
    setError('')
    try {
      await api(`tables/${table.id}/`, { method: 'DELETE' })
      await load()
    } catch (exception) {
      setError((exception as Error).message)
    }
  }

  const busyTables = tables.filter(item => item.open_order).length

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ZAL TUZILISHI</span>
          <h1>Stollar<span className="heading-dot">.</span></h1>
          <p>Kassir ekranidagi stollar xaritasi shu ro‘yxatdan tuziladi.</p>
        </div>
        <button className="button primary" onClick={() => open()}><Plus size={18} />Stol qo‘shish</button>
      </div>

      {error && <p className="alert error">{error}</p>}

      <div className="inventory-summary">
        <div><LayoutGrid size={21} /><span><strong>{tables.filter(t => t.active).length}</strong> faol stol</span></div>
        <div><span className="warning-dot" /><span><strong>{busyTables}</strong> tasida ochiq hisob</span></div>
        <p>Ochiq hisobi bor stolni olib tashlab bo‘lmaydi — avval to‘lovni yakunlang.</p>
      </div>

      <section className="panel">
        <header className="panel-heading">
          <div><h2>Stollar ro‘yxati</h2><p>Zona kassir ekranidagi joylashuvni belgilaydi</p></div>
        </header>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>STOL</th><th>ZONA</th><th>TUR</th><th>O‘RIN</th><th>HOLAT</th><th>AMALLAR</th></tr>
            </thead>
            <tbody>
              {tables.map(item => (
                <tr key={item.id}>
                  <td><strong>{item.label}</strong><small>#{item.number}</small></td>
                  <td><span className="pill subtle">{ZONE_LABELS[item.zone]}</span></td>
                  <td>{item.seating === 'divan' ? 'Divan' : 'Stulli'}</td>
                  <td>{item.seats}</td>
                  <td>
                    {item.open_order
                      ? <span className="status open">{money(item.open_order.total)} so‘m</span>
                      : <span className={`status ${item.active ? 'paid' : 'open'}`}>{item.active ? 'Bo‘sh' : 'Olib tashlangan'}</span>}
                  </td>
                  <td>
                    <div className="staff-actions">
                      <button className="table-action" title="Tahrirlash" onClick={() => open(item)}>
                        <Pencil size={15} />
                      </button>
                      {item.active && (
                        <button className="table-action" title="Olib tashlash" onClick={() => remove(item)}>
                          <Trash2 size={15} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && !tables.length && <div className="empty-state">Hali stol qo‘shilmagan.</div>}
        </div>
      </section>

      <AppModal
        open={modal}
        title={editId ? 'Stolni tahrirlash' : 'Yangi stol'}
        onClose={() => { if (!busy) setModal(false) }}
      >
        <form onSubmit={save}>
          <div className="form-row">
            <label>
              Stol raqami
              <input
                value={form.number}
                onChange={event => update({ number: event.target.value })}
                type="number"
                min="1"
                required
              />
            </label>
            <label>
              O‘rinlar soni
              <input
                value={form.seats}
                onChange={event => update({ seats: event.target.value })}
                type="number"
                min="1"
                max="50"
                required
              />
            </label>
          </div>
          <label>
            Nomi (ixtiyoriy)
            <input
              value={form.name}
              onChange={event => update({ name: event.target.value })}
              maxLength={40}
              placeholder="Masalan, VIP xona — bo‘sh qoldirilsa «5-stol» bo‘ladi"
            />
          </label>
          <div className="form-row">
            <label>
              Zona
              <select value={form.zone} onChange={event => update({ zone: event.target.value as TableZone })}>
                <option value="hall_left">Ichkari — chap tomon</option>
                <option value="hall_right">Ichkari — o‘ng tomon</option>
                <option value="outside">Tashqari</option>
              </select>
            </label>
            <label>
              O‘rindiq turi
              <select
                value={form.seating}
                onChange={event => update({ seating: event.target.value as 'divan' | 'chair' })}
              >
                <option value="chair">Stulli</option>
                <option value="divan">Divan</option>
              </select>
            </label>
          </div>
          <label className="checkbox">
            <input type="checkbox" checked={form.active} onChange={event => update({ active: event.target.checked })} />
            Faol — kassir ekranida ko‘rinadi
          </label>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? 'Saqlanmoqda…' : 'Saqlash'}
          </button>
        </form>
      </AppModal>
    </>
  )
}
