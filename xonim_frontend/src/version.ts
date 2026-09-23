/**
 * «Bu yangilanishni ko'rdimmi» belgisi.
 *
 * Brauzerda saqlanadi, serverda emas. Ya'ni bu «shu KOMPYUTER oxirgi
 * marta qachon qaragan» degani, «shu ODAM» emas. Kassa terminalida
 * bitta login bilan bir necha kishi ishlaydi, shuning uchun aniqroq
 * qilishning iloji yo'q — va kerak ham emas: nuqta shunchaki «bir qarab
 * qo'ying» deydi, hech narsani majburlamaydi.
 *
 * `localStorage` maxfiy rejimda yoki sayt ma'lumotlari yopiq bo'lganda
 * xato ko'tarishi mumkin, shuning uchun har o'qish va yozish try/catch
 * ichida. U ishlamasa nuqta ko'rinmaydi — sahifa esa baribir ochiladi.
 */
const KEY = 'xonim-seen-version'

function read() {
  try {
    return localStorage.getItem(KEY) || ''
  } catch {
    return ''
  }
}

function write(version: string) {
  try {
    localStorage.setItem(KEY, version)
  } catch {
    // Saqlab bo'lmasa nuqta har safar ko'rinadi. Bezovta qiladi, lekin
    // hech narsani buzmaydi.
  }
}

/** Shu versiya izohlari o'qilgan deb belgilaydi. */
export function markSeen(version: string) {
  if (version) write(version)
}

/**
 * Yon menyuda nuqta ko'rsatilsinmi.
 *
 * Birinchi kirishda ko'rsatilmaydi: nuqta «oxirgi qaraganingizdan beri
 * o'zgardi» degani, birinchi marta kirgan odamda esa «oxirgi qaragan»
 * degan nuqta yo'q. Shu sababli birinchi kirishda versiya jimgina
 * belgilanadi va nuqta keyingi yangilanishdan boshlab ishlaydi.
 */
export function isUnseen(version: string) {
  if (!version) return false
  const seen = read()
  if (!seen) {
    write(version)
    return false
  }
  return seen !== version
}
