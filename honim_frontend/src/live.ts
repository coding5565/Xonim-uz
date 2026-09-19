import { useEffect } from 'react'

/**
 * Ekrandagi ma'lumotni tirik ushlab turadi.
 *
 * Kassa ekranlarida eskirgan raqam shunchaki noqulaylik emas — u xato
 * harakatga olib keladi: boshqa kassir sotib bo'lgan taom bu yerda hali
 * «bor» bo'lib turadi, to'langan hisob esa «to'lov kutilmoqda» bo'lib
 * qoladi. Shuning uchun ma'lumot o'zi yangilanadi.
 *
 * Uch payt yangilanadi:
 *   · belgilangan oraliqda;
 *   · oyna yashirindan qaytganda (boshqa ilovadan kelinganda) — darhol;
 *   · oyna fokusga qaytganda.
 *
 * Yashirin oynada so'rov yuborilmaydi: planshet cho'ntakda turganda tarmoq
 * va quvvatni behuda sarflashning ma'nosi yo'q, qaytilgan zahoti baribir
 * yangilanadi.
 *
 * `load` har renderda yangi funksiya bo'lmasligi kerak — uni `useCallback`
 * bilan o'rang, aks holda taymer har safar qayta qurilib ketadi.
 */
export function useLiveData(load: () => void, seconds: number) {
  useEffect(() => {
    const refresh = () => {
      if (!document.hidden) load()
    }
    const timer = window.setInterval(refresh, seconds * 1000)
    document.addEventListener('visibilitychange', refresh)
    window.addEventListener('focus', refresh)
    return () => {
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', refresh)
      window.removeEventListener('focus', refresh)
    }
  }, [load, seconds])
}
