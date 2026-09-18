import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Bot, Check, Copy, RotateCcw, Send, Sparkles } from 'lucide-react'
import { api, money } from '../api'
import { useI18n } from '../i18n'

interface Chart {
  title: string
  labels: string[]
  values: string[]
}

interface Turn {
  role: 'user' | 'assistant'
  text: string
  charts?: Chart[]
}

const PROMPTS = [
  'Bugun qanday o‘tdi?',
  'Bugun kechaga nisbatan o‘sdimi?',
  'Oxirgi 7 kun tahlili',
  'Qaysi taomlar ko‘p sotildi?',
  'Omborda nima kamaygan?',
  'Xarajatlar qayerga ketdi?',
]

const maxValue = (chart: Chart) => Math.max(1, ...chart.values.map(Number))

/** Javob avval xavfsizlantiriladi, keyin faqat qalin matn va satr ko'chirish ruxsat etiladi. */
function formatAnswer(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

export default function AssistantPage() {
  const { t } = useI18n()
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [turns, setTurns] = useState<Turn[]>([])
  const [copied, setCopied] = useState<number>()
  const endOfThread = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)

  // Yangi javob kelganda pastga suriladi.
  useEffect(() => {
    endOfThread.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [turns, sending])

  // Matn maydoni yozilgan matnga qarab o'sadi, lekin cheksiz emas.
  useEffect(() => {
    const field = input.current
    if (!field) return
    field.style.height = 'auto'
    field.style.height = `${Math.min(field.scrollHeight, 168)}px`
  }, [message])

  async function send(text = message) {
    const question = text.trim()
    if (!question || sending) return
    setTurns(previous => [...previous, { role: 'user', text: question }])
    setMessage('')
    setSending(true)
    setError('')
    try {
      const result = await api<{ answer: string; charts: Chart[] }>('assistant/chat/', {
        method: 'POST',
        body: JSON.stringify({ question }),
      })
      setTurns(previous => [...previous, { role: 'assistant', text: result.answer, charts: result.charts }])
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setSending(false)
    }
  }

  /** Enter yuboradi, Shift+Enter yangi satr ochadi. */
  function onKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      send()
    }
  }

  async function copy(text: string, index: number) {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(index)
      window.setTimeout(() => setCopied(undefined), 1600)
    } catch {
      // Clipboard yopiq bo'lsa jim qolamiz — bu yordamchi amal.
    }
  }

  const started = turns.length > 0

  return (
    <div className="chat-page">
      <div className="chat-top">
        <div>
          <span className="eyebrow">HONIM AI</span>
          <h1>{t('AI yordamchi')}<span className="heading-dot">.</span></h1>
        </div>
        <div className="chat-top-actions">
          {started && (
            <button className="chat-reset" onClick={() => { setTurns([]); setError('') }}>
              <RotateCcw size={14} />{t('Yangi suhbat')}
            </button>
          )}
          <span className="chat-guard"><span />{t('Tizim ma’lumotlari himoyalangan')}</span>
        </div>
      </div>

      <div className="chat-scroll">
        {!started ? (
          <div className="chat-blank">
            <div className="chat-blank-mark"><Bot size={26} /></div>
            <h2>{t('Restoraningiz haqida so‘rang')}</h2>
            <p>{t('Savdo, xarajat, ombor, xodimlar va buyurtmalar bo‘yicha aniq raqamlar bilan javob beraman.')}</p>
            <div className="chat-cards">
              {PROMPTS.map(prompt => (
                <button key={prompt} onClick={() => send(t(prompt))}>
                  <Sparkles size={15} />{t(prompt)}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="chat-column" aria-live="polite">
            {turns.map((turn, index) => (
              <article key={index} className={`turn${turn.role === 'user' ? ' me' : ''}`}>
                {turn.role === 'assistant' && <span className="turn-avatar"><Bot size={16} /></span>}
                <div className="turn-body">
                  <div dangerouslySetInnerHTML={{ __html: formatAnswer(turn.text) }} />
                  {turn.charts?.map(chart => (
                    <div key={chart.title} className="turn-chart">
                      <strong>{chart.title}</strong>
                      {chart.labels.map((label, row) => (
                        <div key={label} className="turn-chart-row">
                          <span>{label}</span>
                          <div><i style={{ width: `${Number(chart.values[row]) / maxValue(chart) * 100}%` }} /></div>
                          <b>{money(chart.values[row])} {t('so‘m')}</b>
                        </div>
                      ))}
                    </div>
                  ))}
                  {turn.role === 'assistant' && (
                    <div className="turn-tools">
                      <button onClick={() => copy(turn.text, index)}>
                        {copied === index
                          ? <><Check size={12} />{t('Nusxa olindi')}</>
                          : <><Copy size={12} />{t('Nusxa olish')}</>}
                      </button>
                    </div>
                  )}
                </div>
              </article>
            ))}
            {sending && (
              <article className="turn">
                <span className="turn-avatar"><Bot size={16} /></span>
                <div className="turn-body">
                  <div className="turn-dots" aria-label={t('Tahlil qilinmoqda…')}><i /><i /><i /></div>
                </div>
              </article>
            )}
            <div ref={endOfThread} />
          </div>
        )}
      </div>

      {error && <p className="alert error">{error}</p>}

      <div className="chat-dock">
        <form className="chat-box" onSubmit={(event: FormEvent) => { event.preventDefault(); send() }}>
          <textarea
            ref={input}
            value={message}
            onChange={event => setMessage(event.target.value)}
            onKeyDown={onKey}
            rows={1}
            maxLength={800}
            placeholder={t('Restoran haqida so‘rang…')}
            aria-label={t('Savol')}
          />
          <button className="chat-send" disabled={!message.trim() || sending} aria-label={t('Yuborish')}>
            <Send size={17} />
          </button>
        </form>
        <p className="chat-note">{t('Enter — yuborish · Shift+Enter — yangi satr')}</p>
      </div>
    </div>
  )
}
