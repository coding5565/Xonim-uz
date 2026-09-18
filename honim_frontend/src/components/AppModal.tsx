import { useEffect, useId, useRef, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { useI18n } from '../i18n'

interface Props {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
}

export default function AppModal({ open, title, onClose, children }: Props) {
  const { t } = useI18n()
  const dialog = useRef<HTMLDialogElement>(null)
  // Pages render several modals at once, so the heading needs an id of its own
  // or every dialog would be announced with the first modal's title.
  const titleId = useId()

  useEffect(() => {
    const element = dialog.current
    if (!element) return
    if (open && !element.open) element.showModal()
    if (!open && element.open) element.close()
  }, [open])

  useEffect(() => () => dialog.current?.close(), [])

  return (
    <dialog
      ref={dialog}
      className="modal"
      aria-labelledby={titleId}
      onCancel={event => {
        event.preventDefault()
        onClose()
      }}
    >
      <header>
        <div>
          <span className="eyebrow">{t('HONIM • BOSHQARUV')}</span>
          <h2 id={titleId}>{title}</h2>
        </div>
        <button className="icon-button" aria-label={t('Yopish')} onClick={onClose}><X size={20} /></button>
      </header>
      {children}
    </dialog>
  )
}
