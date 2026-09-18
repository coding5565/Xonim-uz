import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { Bot, LoaderCircle, Send, Sparkles } from 'lucide-react'
import { api, money } from '../api'

interface Chart {
  title: string
  labels: string[]
  values: string[]
}

interface Message {
  role: 'user' | 'assistant'
  text: string
  charts?: Chart[]
}

const prompts = [
  'Bugun qanday o‘tdi?',
  'Bugun kechaga nisbatan o‘sdimi?',
  'Oxirgi 7 kun tahlili',
  'Qaysi taomlar ko‘p sotildi?',
  'Omborda nima kamaygan?',
  'Xarajatlar qayerga ketdi?',
]

const greeting: Message = {
  role: 'assistant',
  text: 'Salom! Men Honim AI yordamchisiman. Restorandagi savdo, xarajat, ombor, xodimlar va buyurtmalar bo‘yicha savol bering.',
}

const maxValue = (chart: Chart) => Math.max(1, ...chart.values.map(Number))

/** Escapes the answer first, then allows only bold and line breaks. */
function formatAnswer(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
}

export default function AssistantPage() {
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [messages, setMessages] = useState<Message[]>([greeting])
  const threadEnd = useRef<HTMLDivElement>(null)

  // Yangi javob kelganda ro'yxat pastga suriladi — foydalanuvchi o'zi
  // aylantirib izlamasligi uchun.
  useEffect(() => {
    threadEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, sending])

  /** Enter yuboradi, Shift+Enter yangi satr qo'shadi. */
  function onKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      send()
    }
  }

  async function send(text = message) {
    const question = text.trim()
    if (!question || sending) return
    setMessages(previous => [...previous, { role: 'user', text: question }])
    setMessage('')
    setSending(true)
    setError('')
    try {
      const result = await api<{ answer: string; charts: Chart[] }>('assistant/chat/', {
        method: 'POST',
        body: JSON.stringify({ question }),
      })
      setMessages(previous => [...previous, { role: 'assistant', text: result.answer, charts: result.charts }])
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="assistant-page">
      <div className="page-heading assistant-heading">
        <div>
          <span className="eyebrow">HONIM AI</span>
          <h1>AI yordamchi<span className="heading-dot">.</span></h1>
          <p>Restoraningizdagi raqamlarni so‘rang, aniq tahlil oling.</p>
        </div>
        <span className="assistant-status"><span />Tizim ma’lumotlari himoyalangan</span>
      </div>
      <section className="assistant-panel panel">
        <header>
          <div className="assistant-avatar"><Bot size={24} /></div>
          <div><h2>Restoran tahlilchisi</h2><p>Faqat Super Admin uchun</p></div>
        </header>
        <div className="chat-thread" aria-live="polite">
          {messages.map((item, index) => (
            <article key={index} className={`chat-message ${item.role}`}>
              {item.role === 'assistant' && <span className="chat-bot"><Bot size={16} /></span>}
              <div>
                <p dangerouslySetInnerHTML={{ __html: formatAnswer(item.text) }} />
                {item.charts?.map(chart => (
                  <div key={chart.title} className="chat-chart">
                    <strong>{chart.title}</strong>
                    {chart.labels.map((label, chartIndex) => (
                      <div key={label} className="chat-chart-row">
                        <span>{label}</span>
                        <div><i style={{ width: `${Number(chart.values[chartIndex]) / maxValue(chart) * 100}%` }} /></div>
                        <b>{money(chart.values[chartIndex])} so‘m</b>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </article>
          ))}
          {sending && (
            <article className="chat-message assistant">
              <span className="chat-bot"><Bot size={16} /></span>
              <div className="typing"><LoaderCircle size={16} className="spin" />Tahlil qilinmoqda…</div>
            </article>
          )}
          <div ref={threadEnd} />
        </div>
        {error && <p className="alert error">{error}</p>}
        <form className="assistant-input" onSubmit={(event: FormEvent) => { event.preventDefault(); send() }}>
          <div className="quick-prompts">
            <span>Tezkor savollar</span>
            <div>
              {prompts.map(prompt => (
                <button key={prompt} type="button" disabled={sending} onClick={() => send(prompt)}>
                  <Sparkles size={13} />{prompt}
                </button>
              ))}
            </div>
          </div>
          <div className="assistant-compose">
            <textarea
              value={message}
              onChange={event => setMessage(event.target.value)}
              onKeyDown={onKey}
              rows={2}
              maxLength={800}
              placeholder="Masalan: bugun tushum kechagiga nisbatan necha foiz o‘zgardi?"
            />
            <button className="button primary" disabled={!message.trim() || sending} aria-label="Savolni yuborish">
              <Send size={18} />Yuborish
            </button>
          </div>
          <p className="compose-hint">Enter — yuborish · Shift+Enter — yangi satr</p>
        </form>
      </section>
    </div>
  )
}
