"""Bu faylni QO'LDA TAHRIRLAMANG — uni `git archive` to'ldiradi.

Ish katalogida qiymatlar `$Format:...$` bo'lib turadi va shundayligicha
qolishi kerak. Serverga ketayotgan arxivda esa git ularni haqiqiy commit
izi bilan almashtiradi (`.gitattributes` dagi `export-subst`).

Ikkalasi ham qo'shtirnoq ichida — shuning uchun fayl ikkala holatda ham
to'g'ri Python bo'lib qoladi va hech qachon import xatosiga aylanmaydi.

O'qiladigan versiya raqami bu yerda YO'Q: u `core/releases.py` da,
chunki teg asosidagi raqamni git arxivning ikkinchi fayliga to'g'ri
yozmaydi (sababi `.gitattributes` da yozilgan).
"""

COMMIT = '$Format:%h$'
COMMITTED_AT = '$Format:%cI$'
