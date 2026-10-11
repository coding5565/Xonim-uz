"""Chek shapkasidagi logotipni ESC/POS rastriga aylantiradi.

Nega oldindan hisoblaymiz: serverda Pillow yo'q va uni faqat shu ish
uchun qo'shish — butun bir kutubxonani har bir chek uchun olib yurish
demakdir. Rasm esa deyarli o'zgarmaydi. Shuning uchun natija bir marta
shu yerda hisoblanadi va `receipt_logo.bin` bo'lib omborga tushadi;
printing.py uni shunchaki o'qiydi.

Ishlatish (Pillow kerak, faqat shu skriptga):

    python deploy/make_receipt_logo.py logo.png

Natija: xonim_backend/operations/receipt_logo.bin
"""
import sys
from pathlib import Path

from PIL import Image, ImageOps

# 80 mm printerda bosiladigan maydon 72 mm, ya'ni 203 dpi da 576 nuqta.
# Bu printerning chekkasi: kattaroq rasm o'ng tomondan qirqiladi.
WIDTH = 576

# Rastr bir buyruqda emas, lentalarga bo'lib yuboriladi. Baland rasmni
# bitta `GS v 0` bilan yuborganda ba'zi XP modellari bufer to'lib
# qolib, qatorlarni surib bosadi.
BAND = 64

TARGET = Path(__file__).resolve().parent.parent / 'xonim_backend' / 'operations' / 'receipt_logo.bin'


def to_ink(path):
    """Rasmni «qog'ozda qanday ko'rinishi kerak» holiga keltiradi.

    Logotip shaffof fon ustida OQ chizilgan — ekran uchun. Termal
    printerda esa aksincha: qora joy — siyoh, oq joy — toza qog'oz.
    Shuning uchun rasm qora fonga qo'yiladi va teskarisiga o'giriladi,
    natijada oq shakllar qora siyohga aylanadi.
    """
    image = Image.open(path).convert('RGBA')
    flat = Image.new('RGBA', image.size, (0, 0, 0, 255))
    flat.alpha_composite(image)
    ink = ImageOps.invert(flat.convert('L'))

    # Atrofdagi bo'sh joyni olib tashlaymiz: aks holda chekda logotip
    # tepasida va pastida sababsiz bo'shliq qoladi.
    box = ink.getbbox()
    if box:
        ink = ink.crop(box)

    height = round(ink.height * WIDTH / ink.width)
    ink = ink.resize((WIDTH, height), Image.LANCZOS)
    # Ataylab dizering yo'q: logotip — yirik tekis shakl, nuqtalarga
    # bo'lish uni faqat kirlantiradi.
    return ink.point(lambda value: 255 if value >= 128 else 0, mode='1')


def to_escpos(image):
    """`GS v 0` rastr buyruqlari ketma-ketligi."""
    row_bytes = image.width // 8
    # mode '1' da 0 — qora. Printerda esa 1 — siyoh, shuning uchun
    # bitlarni teskarisiga olamiz.
    raw = bytes(~byte & 0xFF for byte in image.tobytes())

    out = bytearray()
    for top in range(0, image.height, BAND):
        rows = min(BAND, image.height - top)
        out += b'\x1d\x76\x30\x00'
        out += bytes((row_bytes & 0xFF, row_bytes >> 8, rows & 0xFF, rows >> 8))
        out += raw[top * row_bytes:(top + rows) * row_bytes]
    return bytes(out)


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    image = to_ink(argv[1])
    data = to_escpos(image)
    TARGET.write_bytes(data)
    print(f'{image.width}x{image.height} nuqta -> {TARGET.name}, {len(data)} bayt')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
