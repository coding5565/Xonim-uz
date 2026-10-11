import { useRef } from 'react'
import { Building2, Database, Download, Languages, RotateCcw, Trash2, Upload } from 'lucide-react'
import { Card, Field, NumberInput, Select, SectionTitle, TextInput } from '@/components/ui'
import { StatRow } from '@/components/Kpi'
import { PERIODS } from '@/core/period'
import { money, num } from '@/core/format'
import type { Period } from '@/core/types'
import { parseModel } from '@/core/validate'
import { PERIOD_LABEL_KEY } from '@/i18n/keys'
import { LOCALES, LOCALE_NAMES } from '@/i18n/locales'
import { useAppStore } from '@/store/useAppStore'
import { usePeriodView } from '@/store/useCalc'
import { useT } from '@/store/useT'
import { XONIM } from '@/xonim/config'
import { XonimCard } from '@/xonim/XonimCard'

export default function SettingsPage() {
  const t = useT()
  const b = useAppStore((s) => s.model.business)
  const update = useAppStore((s) => s.updateBusiness)
  const model = useAppStore((s) => s.model)
  const locale = useAppStore((s) => s.locale)
  const setLocale = useAppStore((s) => s.setLocale)
  const loadDemo = useAppStore((s) => s.loadDemo)
  const clearAll = useAppStore((s) => s.clearAll)
  const importModel = useAppStore((s) => s.importModel)
  const { calc, currency } = usePeriodView()
  const fileRef = useRef<HTMLInputElement>(null)

  const periodOptions = PERIODS.map((p) => ({ value: p, label: t(PERIOD_LABEL_KEY[p]) }))

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(model, null, 2)], { type: 'application/json' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `${b.name || 'cafe'}-model.json`
    a.click()
    URL.revokeObjectURL(a.href)
  }

  const importJson = (file: File) => {
    const reader = new FileReader()
    reader.onload = () => {
      try {
        // Недостающие списки и поля дополняются: неполный файл не должен ронять приложение.
        const parsed = parseModel(JSON.parse(String(reader.result)))
        if (!parsed) throw new Error('bad')
        importModel(parsed)
      } catch {
        alert(t('settings.importError'))
      }
    }
    reader.readAsText(file)
  }

  return (
    <div className="space-y-5">
      {XONIM && <XonimCard />}
      <Card>
        <SectionTitle
          icon={<Building2 size={18} />}
          title={t('settings.title')}
          subtitle={t('settings.subtitle')}
        />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Field label={t('settings.cafeName')}>
            <TextInput value={b.name} onChange={(v) => update({ name: v })} />
          </Field>
          <Field label={t('settings.currency')} hint={t('settings.currencyHint')}>
            <TextInput
              value={b.currency}
              placeholder={t('currency.default')}
              onChange={(v) => update({ currency: v })}
            />
          </Field>
          <Field label={t('settings.planningPeriod')}>
            <Select<Period>
              value={b.planningPeriod}
              onChange={(v) => update({ planningPeriod: v })}
              options={periodOptions}
            />
          </Field>
          <Field label={t('settings.daysPerMonth')} hint={t('settings.daysPerMonthHint')}>
            <NumberInput
              value={b.workingDaysPerMonth}
              onChange={(v) => update({ workingDaysPerMonth: v })}
              min={1}
              max={31}
            />
          </Field>
          <Field label={t('settings.daysPerWeek')} hint={t('settings.daysPerWeekHint')}>
            <NumberInput
              value={b.workingDaysPerWeek}
              onChange={(v) => update({ workingDaysPerWeek: v })}
              min={1}
              max={7}
            />
          </Field>
          <Field label={t('settings.hoursPerDay')}>
            <NumberInput
              value={b.hoursPerDay}
              onChange={(v) => update({ hoursPerDay: v })}
              min={1}
              max={24}
            />
          </Field>
          <Field label={t('settings.seats')}>
            <NumberInput value={b.seats} onChange={(v) => update({ seats: v })} min={0} />
          </Field>
          <Field label={t('settings.guestsPerOrder')} hint={t('settings.guestsPerOrderHint')}>
            <NumberInput
              value={b.guestsPerOrder}
              onChange={(v) => update({ guestsPerOrder: v })}
              min={1}
            />
          </Field>
          <Field label={t('settings.itemsPerGuest')} hint={t('settings.itemsPerGuestHint')}>
            <NumberInput
              value={b.itemsPerGuest}
              onChange={(v) => update({ itemsPerGuest: v })}
              min={0.1}
            />
          </Field>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <SectionTitle
            icon={<Languages size={18} />}
            title={t('settings.language')}
            subtitle={t('settings.languageHint')}
          />
          <div className="grid gap-2 sm:grid-cols-3">
            {LOCALES.map((l) => (
              <button
                key={l}
                onClick={() => setLocale(l)}
                className={
                  l === locale
                    ? 'btn btn-primary justify-start'
                    : 'btn btn-ghost justify-start'
                }
              >
                {LOCALE_NAMES[l]}
              </button>
            ))}
          </div>
        </Card>

        <Card>
          <SectionTitle title={t('target.title')} subtitle={t('settings.targetSubtitle')} />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('settings.targetAmount')}>
              <NumberInput
                value={b.targetProfit}
                onChange={(v) => update({ targetProfit: v })}
                min={0}
                suffix={currency}
              />
            </Field>
            <Field label={t('target.forPeriod')}>
              <Select<Period>
                value={b.targetProfitPeriod}
                onChange={(v) => update({ targetProfitPeriod: v })}
                options={periodOptions}
              />
            </Field>
          </div>
          <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:bg-slate-800/50 dark:text-slate-300">
            {t('settings.targetMonthly', { value: money(calc.target.targetMonthly, currency) })}
          </div>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <SectionTitle
            title={t('settings.periodsTitle')}
            subtitle={t('settings.periodsSubtitle')}
          />
          <StatRow
            label={t('settings.oneDay')}
            value={t('settings.workDaysValue', { count: 1 })}
          />
          <StatRow
            label={t('settings.oneWeek')}
            value={t('settings.workDaysValue', { count: calc.factors.week })}
          />
          <StatRow
            label={t('settings.oneMonth')}
            value={t('settings.workDaysValue', { count: calc.factors.month })}
          />
          <StatRow
            label={t('settings.oneYear')}
            value={t('settings.workDaysValue', { count: calc.factors.year })}
            strong
          />
          <StatRow
            label={t('settings.weeksInMonth')}
            value={num(calc.factors.month / calc.factors.week, 2)}
            hint={t('settings.weeksInMonthHint')}
          />
        </Card>

        <Card>
          <SectionTitle
            icon={<Database size={18} />}
            title={t('settings.dataTitle')}
            subtitle={t('settings.dataSubtitle')}
          />
          <div className="flex flex-wrap gap-2">
            <button className="btn btn-ghost" onClick={exportJson}>
              <Download size={16} /> {t('settings.exportJson')}
            </button>
            <button className="btn btn-ghost" onClick={() => fileRef.current?.click()}>
              <Upload size={16} /> {t('settings.importJson')}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="application/json"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) importJson(f)
                e.target.value = ''
              }}
            />
            {/* Внутри Xonim демо-кафе только путало бы с настоящими цифрами. */}
            {!XONIM && (
              <button
                className="btn btn-ghost"
                onClick={() => {
                  if (confirm(t('settings.confirmDemo'))) loadDemo()
                }}
              >
                <RotateCcw size={16} /> {t('settings.loadDemo')}
              </button>
            )}
            <button
              className="btn btn-danger"
              onClick={() => {
                if (confirm(t('settings.confirmClear'))) clearAll()
              }}
            >
              <Trash2 size={16} /> {t('settings.clearAll')}
            </button>
          </div>
        </Card>
      </div>
    </div>
  )
}
