/**
 * Bu faylni QO'LDA TAHRIRLAMANG — uni `git archive` to'ldiradi.
 *
 * Ish katalogida qiymatlar `$Format:...$` bo'lib turadi. Serverga
 * ketayotgan arxivda git ularni haqiqiy commit izi bilan almashtiradi
 * (`.gitattributes` dagi `export-subst`).
 *
 * Nega frontendda ALOHIDA nusxa kerak: `Dockerfile.web` faqat
 * `xonim_frontend/` papkasini ko'chiradi, ya'ni backend'dagi muhrni u
 * umuman ko'rmaydi. Ikkita nusxa bo'lgani esa foydali bo'lib chiqdi —
 * ular farq qilsa, demak brauzerdagi sahifa eskirgan.
 */

export const COMMIT = '$Format:%h$'
export const COMMITTED_AT = '$Format:%cI$'

/** Muhr almashtirilganmi. Lokal ishlab chiqishda — yo'q. */
export const stamped = !COMMIT.startsWith('$Format')
