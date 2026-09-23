import { useCallback, useEffect, useState } from 'react'
import { CircleCheck, Rocket, Sparkles, Wrench } from 'lucide-react'
import { api } from '../api'
import { COMMIT as BUNDLE_COMMIT, stamped as bundleStamped } from '../build-stamp'
import { useI18n } from '../i18n'
import { PanelSkeleton } from '../components/Skeleton'
import { markSeen } from '../version'
import type { VersionInfo } from '../types'

const KIND_NAMES: Record<string, string> = {
  yangi: 'Yangi', tuzatish: 'Tuzatildi', yaxshi: 'Yaxshilandi',
}

function KindIcon({ kind }: { kind: string }) {
  if (kind === 'tuzatish') return <Wrench size={15} />
  if (kind === 'yaxshi') return <Sparkles size={15} />
  return <CircleCheck size={15} />
}

/**
 * Yangilanishlar: qaysi versiya ishlayapti va unda nima o'zgargan.
 *
 * Ro'yxatni server rolga qarab filtrlaydi — kassirga moliya zanjiridagi
 * o'zgarish ko'rsatilmaydi, chunki u ro'yxatni uzaytirib, o'ziga
 * tegishlisini ko'rinmas qilib qo'yardi.
 *
 * Sahifa ochilishining o'zi «ko'rdim» degani: yon menyudagi nuqta
 * shundan keyin o'chadi. Modal oyna ataylab yo'q — kassirni mijoz oldida
 * to'xtatib qo'yadigan narsa bu yerda bo'lmasligi kerak.
 */
export default function ReleasesPage() {
  const { t, tn } = useI18n()
  const [data, setData] = useState<VersionInfo>()
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setError('')
    try {
      const info = await api<VersionInfo>('version/')
      setData(info)
      markSeen(info.version)
    } catch (exception) {
      setError((exception as Error).message)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // Brauzerdagi sahifa serverdagi koddan eski bo'lishi mumkin: nginx
  // index.html ni keshlamaydi, lekin ochiq turgan oyna o'z-o'zidan
  // yangilanmaydi. Ikkala muhr ham bor va farq qilsa — aynan shu hol.
  const stale = !!data?.build.stamped && bundleStamped && data.build.commit !== BUNDLE_COMMIT

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('DASTUR YANGILANISHLARI')}</span>
          <h1>{t('Yangilanishlar')}<span className="heading-dot">.</span></h1>
          <p>{t('Qaysi versiya ishlayapti va unda nima o‘zgargan.')}</p>
        </div>
      </div>

      {error && <p className="alert error">{error}</p>}

      {stale && (
        <p className="alert">
          {t('Brauzeringizdagi sahifa serverdagi versiyadan eski. Sahifani yangilang (Ctrl+R) — ochiq hisobingiz bo‘lsa, avval uni yoping.')}
        </p>
      )}

      {!data && <section className="panel"><PanelSkeleton rows={6} /></section>}

      {data && (
        <>
          <section className="panel release-now">
            <div>
              <span className="eyebrow">{t('HOZIRGI VERSIYA')}</span>
              <strong>{data.version}</strong>
              {!!data.releases.length && <p>{data.releases[0].title}</p>}
            </div>
            <div className="release-build">
              {data.build.stamped ? (
                <>
                  <small>{t('Serverga qo‘yilgan')}</small>
                  <span>{data.build.committed_at.slice(0, 10)}</span>
                  <code>{data.build.commit}</code>
                </>
              ) : (
                <>
                  <small>{t('Ishlab chiqish nusxasi')}</small>
                  <span>{t('serverga qo‘yilmagan')}</span>
                </>
              )}
            </div>
          </section>

          <div className="release-list">
            {data.releases.map((release, index) => (
              <section key={release.version} className={`panel release${index === 0 ? ' current' : ''}`}>
                <header className="panel-heading">
                  <div>
                    <h2>
                      {index === 0 && <Rocket size={16} />}
                      {t('Versiya {version}', { version: release.version })}
                    </h2>
                    <p>{release.title}</p>
                  </div>
                  <span className="muted">{release.released}</span>
                </header>
                <ul className="release-changes">
                  {release.changes.map((change, position) => (
                    <li key={position} className={change.kind}>
                      <span className="release-kind">
                        <KindIcon kind={change.kind} />
                        {t(KIND_NAMES[change.kind] || change.kind)}
                      </span>
                      <p>{change.text}</p>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>

          {!data.releases.length && (
            <section className="panel">
              <div className="empty-state">
                <strong>{t('Bu versiya uchun izoh yozilmagan')}</strong>
                <p>{t('Kod yangilangan, lekin o‘zgarishlar ro‘yxati to‘ldirilmagan.')}</p>
              </div>
            </section>
          )}

          <p className="data-note">
            {tn('Ro‘yxatda {count} ta versiya ko‘rsatilgan. Faqat sizga tegishli o‘zgarishlar ko‘rinadi.',
              data.releases.length)}
          </p>
        </>
      )}
    </>
  )
}
