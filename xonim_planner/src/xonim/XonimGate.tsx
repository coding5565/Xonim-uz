import type { ReactNode } from 'react'
import { Gauge, LogIn, RefreshCw, ShieldAlert, WifiOff } from 'lucide-react'
import { Card } from '@/components/ui'
import { useAppStore } from '@/store/useAppStore'
import { useT } from '@/store/useT'
import { XONIM_HOME, XONIM_LOGIN } from './config'
import { checkAccess, loadMonth, useXonim } from './sync'

function Screen({
  icon,
  title,
  text,
  action,
}: {
  icon: ReactNode
  title: string
  text?: string
  action?: ReactNode
}) {
  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <Card className="w-full max-w-md text-center">
        <div className="mx-auto mb-3 inline-flex rounded-xl bg-brand-50 p-3 text-brand-600 dark:bg-brand-900/30 dark:text-brand-300">
          {icon}
        </div>
        <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-50">{title}</h1>
        {text && <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">{text}</p>}
        {action && <div className="mt-5 flex justify-center gap-2">{action}</div>}
      </Card>
    </div>
  )
}

/**
 * Пускает в калькулятор только суперадмина Xonim: пока сервер не подтвердил
 * вход и не отдал данные, приложение не отрисовывается вовсе.
 *
 * Заслон закрывает только экран. Чтобы финансы не остались в браузере
 * общего кассового компьютера, модель из Xonim ещё и не пишется на диск
 * (см. `persistedPart` в useAppStore) — каждое открытие загружает её заново.
 */
export function XonimGate({ children }: { children: ReactNode }) {
  const t = useT()
  const access = useXonim((s) => s.access)
  const failed = useXonim((s) => s.failed)
  const linked = useAppStore((s) => s.xonim !== null)

  if (access === 'owner' && linked) return <>{children}</>

  if (access === 'anonymous') {
    return (
      <Screen
        icon={<LogIn size={22} />}
        title={t('xonim.loginTitle')}
        text={t('xonim.loginText')}
        action={
          <a className="btn btn-primary" href={XONIM_LOGIN}>
            {t('xonim.loginButton')}
          </a>
        }
      />
    )
  }

  if (access === 'forbidden') {
    return (
      <Screen
        icon={<ShieldAlert size={22} />}
        title={t('xonim.forbiddenTitle')}
        text={t('xonim.forbiddenText')}
        action={
          <a className="btn btn-ghost" href={XONIM_HOME}>
            {t('xonim.back')}
          </a>
        }
      />
    )
  }

  if (access === 'offline' || (access === 'owner' && failed)) {
    const offline = access === 'offline'
    return (
      <Screen
        icon={<WifiOff size={22} />}
        title={t(offline ? 'xonim.offlineTitle' : 'xonim.loadFailedTitle')}
        text={t(offline ? 'xonim.offlineText' : 'xonim.loadFailedText')}
        action={
          <button
            className="btn btn-primary"
            onClick={() => void (offline ? checkAccess() : loadMonth())}
          >
            <RefreshCw size={16} /> {t('xonim.retry')}
          </button>
        }
      />
    )
  }

  // Проверка входа или первая загрузка: показывать пока нечего.
  return (
    <Screen
      icon={<Gauge size={22} />}
      title={t(access === 'checking' ? 'xonim.checking' : 'xonim.loadingFirst')}
    />
  )
}
