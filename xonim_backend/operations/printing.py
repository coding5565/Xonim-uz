"""Chekni ESC/POS termal printerga chiqarish.

Qurilma: Xprinter XP-T80Q (80 mm, ESC/POS, avtomatik kesuvchi, pul qutisi chiqishi).
Windows'ga "Generic / Text Only" haydovchisi bilan navbat sifatida o'rnatiladi va
baytlar spooler orqali RAW holatda yuboriladi.

Ikkita qaror sinov cheklari asosida qabul qilingan, taxmin emas:

1. Kenglik 48 belgi. 48 raqamli qator bitta qatorga sig'di, 49 belgilik qator
   ko'chdi.
2. Matn ASCII ga tushiriladi. Printer xitoycha ieroglif rejimida ishlaydi va
   `ESC t` codepage buyrug'ini e'tiborsiz qoldiradi: CP1252, CP437, CP866 va xom
   UTF-8 ning hammasi ieroglif berdi. ASCII apostrof esa printerning o'z shriftida
   tipografik ko'rinishda chiqadi, ya'ni "so'm" allaqachon chiroyli.

Yangi bog'liqlik qo'shilmagan: `ctypes` standart kutubxonada bor.
"""
import ctypes
import logging
import socket
import sys
from ctypes import wintypes
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from .models import SALE_PAYMENT_LABELS

logger = logging.getLogger(__name__)

WIDTH = 48

# ESC/POS buyruqlari
INIT = b'\x1b\x40'
ALIGN_LEFT = b'\x1b\x61\x00'
ALIGN_CENTER = b'\x1b\x61\x01'
BOLD_ON = b'\x1b\x45\x01'
BOLD_OFF = b'\x1b\x45\x00'
SIZE_BIG = b'\x1d\x21\x11'
SIZE_NORMAL = b'\x1d\x21\x00'
CUT = b'\x1d\x56\x42\x00'
OPEN_DRAWER = b'\x1b\x70\x00\x32\xfa'

# Printer typografik belgilarni bilmaydi, shuning uchun ularni ASCII ga tushiramiz.
ASCII_MAP = {
    '‘': "'", '’': "'", 'ʻ': "'", 'ʼ': "'",
    '“': '"', '”': '"', '«': '"', '»': '"',
    '–': '-', '—': '-', '−': '-',
    '·': '*', '•': '*', '…': '...', '→': '->',
    ' ': ' ', ' ': ' ', ' ': ' ',
    '₽': 'so\'m',
}


class PrinterError(Exception):
    """Chek chiqmadi. Savdo baribir saqlanadi."""


def ascii_only(text):
    for source, target in ASCII_MAP.items():
        text = text.replace(source, target)
    return text.encode('ascii', 'replace').decode('ascii')


def som_text(value):
    """Chek uchun: 40000.00 -> '40 000'.

    Bu API javoblaridagi `operations/money.py: som_text()` dan ataylab farq
    qiladi — chekda tiyin ko'rsatilmaydi va razryadlar probel bilan
    ajratiladi. Nomi ham shuning uchun boshqacha.
    """
    return f'{int(Decimal(value)):,}'.replace(',', ' ')


class Ticket:
    """ESC/POS bayt oqimini bosqichma-bosqich yig'adi."""

    def __init__(self, width=WIDTH):
        self.width = width
        self.data = bytearray(INIT)

    def raw(self, code):
        self.data.extend(code)
        return self

    def text(self, line=''):
        self.data.extend(ascii_only(line).encode('ascii', 'replace'))
        self.data.append(0x0A)
        return self

    def rule(self, char='-'):
        return self.text(char * self.width)

    def row(self, left, right):
        """Chapda matn, o'ngda summa. Sig'masa chap tomon qisqartiriladi."""
        left, right = ascii_only(left), ascii_only(right)
        gap = self.width - len(left) - len(right)
        if gap < 1:
            left = left[:max(0, self.width - len(right) - 1)]
            gap = 1
        return self.text(f'{left}{" " * gap}{right}')

    def finish(self):
        return bytes(self.data + b'\n\n\n\n' + CUT)


def receipt_bytes(order, *, open_drawer=False):
    """Buyurtmadan chop etishga tayyor bayt oqimini yasaydi."""
    moment = timezone.localtime(order.paid_at or order.created_at)
    branch = order.branch.name if order.branch else 'Xonim'

    ticket = Ticket()
    if open_drawer:
        ticket.raw(OPEN_DRAWER)

    ticket.raw(ALIGN_CENTER).raw(SIZE_BIG).text('XONIM').raw(SIZE_NORMAL)
    ticket.text(branch)
    ticket.raw(ALIGN_LEFT).rule('=')

    ticket.row(f'Chek:  #{order.id:04d}', moment.strftime('%d.%m.%Y %H:%M'))
    if order.table:
        place = f'Stol:  {order.table}'
        if order.waiter:
            place += f'   Ofitsiant: {order.waiter}'
        ticket.text(place)
    else:
        ticket.text('Tezkor savdo')
    ticket.text(f'Kassir: {order.cashier.first_name or order.cashier.username}')
    ticket.rule()

    for line in order.lines.all():
        name = line.name + ('   (qo‘shimcha)' if line.batch_key else '')
        ticket.text(name)
        ticket.row(f'   {line.quantity} x {som_text(line.price)}',
                   som_text(Decimal(line.price) * line.quantity))
        if line.note:
            ticket.text(f'   izoh: {line.note}')

    ticket.rule()
    # Chegirma bo'lsa mijoz uni chekda ko'rishi kerak: aks holda summa
    # nega kamayganini tushunmaydi.
    if order.discount:
        ticket.row('Oraliq jami', som_text(order.total + order.discount))
        ticket.row(f'Chegirma ({ascii_only(order.discount_reason)})', f'-{som_text(order.discount)}')
    # Xizmat haqi chekda alohida turadi: mijoz nima uchun to'layotganini
    # ko'rishi kerak, aks holda summa sababsiz katta ko'rinadi.
    if order.service_charge:
        ticket.row('Taomlar', som_text(order.total))
        ticket.row(f'Xizmat haqi ({order.waiter_commission:.0f}%)', som_text(order.service_charge))
    ticket.raw(BOLD_ON).row('JAMI', f'{som_text(order.payable)} so‘m').raw(BOLD_OFF)
    if order.status == 'paid':
        label = SALE_PAYMENT_LABELS.get(order.payment_method, order.payment_method or '-')
        ticket.text(f'To‘lov: {label}')
    else:
        ticket.text('To‘lov kutilmoqda')
    ticket.rule('=')

    ticket.raw(ALIGN_CENTER)
    ticket.text('ICHKI TO‘LOV QAYDI')
    ticket.text('FISKAL CHEK EMAS')
    ticket.text()
    ticket.text('Rahmat! Yana kutamiz.')
    ticket.raw(ALIGN_LEFT)
    return ticket.finish()


def group_by_station(lines):
    """Buyurtma qatorlarini printerlar bo'yicha ajratadi: {'kitchen': [...], 'counter': [...]}."""
    groups = {}
    for line in lines:
        groups.setdefault(line.dish.print_station, []).append(line)
    return groups


def prep_ticket_bytes(order, station, lines, *, addition=False):
    """Oshxona yoki kassa uchun tayyorlash taloni.

    Narx yo'q va bo'lmasligi ham kerak: oshpazga summa emas, nima va qancha
    tayyorlanishi kerakligi lozim. Miqdor va taom nomi ikki barobar shriftda,
    chunki talon issiq oshxonada bir metrdan o'qiladi.
    """
    moment = timezone.localtime(order.created_at)
    ticket = Ticket()

    ticket.raw(ALIGN_CENTER).raw(SIZE_BIG)
    ticket.text('OSHXONA' if station == 'kitchen' else 'KASSA')
    ticket.raw(SIZE_NORMAL)
    if addition:
        ticket.raw(BOLD_ON).text('*** QO‘SHIMCHA BUYURTMA ***').raw(BOLD_OFF)
    ticket.raw(ALIGN_LEFT).rule('=')

    ticket.raw(SIZE_BIG).text(f'#{order.id:04d}').raw(SIZE_NORMAL)
    ticket.raw(BOLD_ON)
    ticket.text(f'{order.table}-STOL' if order.table else 'TEZKOR SAVDO')
    ticket.raw(BOLD_OFF)
    if order.waiter:
        ticket.text(f'Ofitsiant: {order.waiter}')
    ticket.row(f'Kassir: {order.cashier.first_name or order.cashier.username}',
               moment.strftime('%H:%M'))
    ticket.rule('=')

    for line in lines:
        ticket.raw(SIZE_BIG).text(f'{line.quantity} x {line.name}').raw(SIZE_NORMAL)
        if line.note:
            ticket.raw(BOLD_ON).text(f'   >> {line.note}').raw(BOLD_OFF)
        ticket.text()

    ticket.rule('=')
    ticket.raw(ALIGN_CENTER)
    total_items = sum(line.quantity for line in lines)
    ticket.text(f'Jami {total_items} porsiya')
    ticket.raw(ALIGN_LEFT)
    return ticket.finish()


class _DocInfo(ctypes.Structure):
    _fields_ = [
        ('pDocName', wintypes.LPWSTR),
        ('pOutputFile', wintypes.LPWSTR),
        ('pDatatype', wintypes.LPWSTR),
    ]


def send_bytes(data, printer):
    """Baytlarni Windows spooleriga RAW holatda yuboradi.

    RAW bo'lgani uchun haydovchi baytlarga tegmaydi va ESC/POS printerga
    o'zgarmagan holda yetib boradi.
    """
    if not sys.platform.startswith('win'):
        raise PrinterError('Chek chiqarish hozircha faqat Windows’da ishlaydi.')

    spooler = ctypes.WinDLL('winspool.drv')
    spooler.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), wintypes.LPVOID]
    spooler.StartDocPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(_DocInfo)]
    spooler.WritePrinter.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]

    handle = wintypes.HANDLE()
    if not spooler.OpenPrinterW(printer, ctypes.byref(handle), None):
        raise PrinterError(f'«{printer}» printeri topilmadi yoki band.')
    try:
        info = _DocInfo('Xonim chek', None, 'RAW')
        if not spooler.StartDocPrinterW(handle, 1, ctypes.byref(info)):
            raise PrinterError('Printer topshiriqni qabul qilmadi.')
        try:
            if not spooler.StartPagePrinter(handle):
                raise PrinterError('Printer topshiriqni boshlamadi.')
            written = wintypes.DWORD(0)
            buffer = ctypes.create_string_buffer(data, len(data))
            ok = spooler.WritePrinter(handle, buffer, len(data), ctypes.byref(written))
            spooler.EndPagePrinter(handle)
            if not ok or written.value != len(data):
                raise PrinterError('Chek to‘liq yuborilmadi. Qog‘oz va ulanishni tekshiring.')
        finally:
            spooler.EndDocPrinter(handle)
    finally:
        spooler.ClosePrinter(handle)


def send_to_network(data, target):
    """Printerning o'z Ethernet portiga xom TCP orqali yuboradi (JetDirect, 9100).

    Hozir ishlatilmaydi, lekin transport shu yerda ajratilgani uchun LAN'ga
    o'tish RECEIPT_PRINTER ni "192.168.0.50:9100" ga almashtirish bilan bo'ladi.
    """
    host, _, port = target.partition(':')
    try:
        with socket.create_connection((host, int(port or 9100)), timeout=4) as link:
            link.settimeout(6)
            link.sendall(data)
    except OSError as error:
        raise PrinterError(f'Printerga ulanib bo‘lmadi ({target}). Tarmoq va quvvatni tekshiring.') from error


STATION_LABELS = {'kitchen': 'Oshxona', 'counter': 'Kassa'}


def station_target(station):
    """Bo'lim nomini printer manziliga aylantiradi. Bo'sh qiymat - chop etish o'chiq."""
    if station == 'kitchen':
        return getattr(settings, 'KITCHEN_PRINTER', '')
    return getattr(settings, 'RECEIPT_PRINTER', '')


def send_to(target, data):
    """Manzil ko'rinishiga qarab transportni tanlaydi: IP bo'lsa tarmoq, aks holda Windows navbati."""
    if ':' in target or target.replace('.', '').isdigit():
        send_to_network(data, target)
    else:
        send_bytes(data, target)


def print_receipt(order, *, open_drawer=None):
    """Mijoz chekini kassa printeridan chiqaradi."""
    target = station_target('counter')
    if not target:
        raise PrinterError('Kassa printeri sozlanmagan. RECEIPT_PRINTER ni .env da ko‘rsating.')
    if open_drawer is None:
        open_drawer = getattr(settings, 'RECEIPT_OPEN_DRAWER', False)
    send_to(target, receipt_bytes(order, open_drawer=open_drawer))


def print_prep_tickets(order, lines=None, *, addition=False):
    """Tayyorlash talonlarini tegishli printerlarga tarqatadi.

    Xatolarni ro'yxat qilib qaytaradi, ko'tarmaydi: buyurtma allaqachon yozilgan.
    Lekin chiqmagan oshxona taloni - ovqat pishmasligi demak, shuning uchun
    chaqiruvchi bu ro'yxatni kassirga ko'rsatishi shart.
    """
    problems = []
    rows = list(lines) if lines is not None else list(order.lines.select_related('dish__category'))
    for station, station_lines in group_by_station(rows).items():
        target = station_target(station)
        label = STATION_LABELS.get(station, station)
        if not target:
            problems.append(f'{label} printeri sozlanmagan — talon chiqmadi.')
            continue
        try:
            send_to(target, prep_ticket_bytes(order, station, station_lines, addition=addition))
        except PrinterError as error:
            problems.append(f'{label}: {error}')
        except Exception as error:
            logger.warning('Talon chiqmadi: #%s %s', order.id, station, exc_info=True)
            problems.append(f'{label}: talon chiqmadi ({error}).')
    return problems


def void_ticket_bytes(order, message):
    """Bekor qilish taloni: oshxona nimani pishirmasligini bilishi uchun."""
    ticket = Ticket()
    ticket.raw(b'\x1b\x61\x01')          # markazga
    ticket.raw(b'\x1d\x21\x11')          # ikki baravar
    ticket.text('BEKOR')
    ticket.raw(b'\x1d\x21\x00')
    ticket.text(ascii_only(message))
    ticket.raw(b'\x1b\x61\x00')          # chapga
    ticket.rule()
    ticket.row('Buyurtma', f'#{order.id:04d}')
    ticket.row('Stol', ascii_only(order.table or '-'))
    ticket.row('Vaqt', timezone.localtime().strftime('%H:%M  %d.%m.%Y'))
    return ticket.finish()


def print_void_ticket(order, message):
    """Bekor qilinganini har ikkala printerga ham chiqaradi.

    Qaysi stansiyaga ketganini aniq bilmaymiz, shuning uchun sozlangan
    printerlarning hammasiga yuboriladi — pishirilib qolgandan ko'ra
    ortiqcha qog'oz yaxshi.
    """
    problems = []
    seen = set()
    for station in ('kitchen', 'counter'):
        target = station_target(station)
        if not target or target in seen:
            continue
        seen.add(target)
        label = STATION_LABELS.get(station, station)
        try:
            send_to(target, void_ticket_bytes(order, message))
        except Exception as error:
            logger.warning('Bekor taloni chiqmadi: #%s %s', order.id, station, exc_info=True)
            problems.append(f'{label}: bekor taloni chiqmadi ({error}).')
    return problems


def print_receipt_quietly(order):
    """Avtomatik chop etish uchun. Hech qachon xato ko'tarmaydi.

    Savdo allaqachon yozilgan; printer o'chiq bo'lsa ham uni bekor qilib
    bo'lmaydi. Shuning uchun nosozlik faqat jurnalga tushadi.
    """
    if not getattr(settings, 'RECEIPT_PRINTER', ''):
        return False
    try:
        print_receipt(order)
        return True
    except Exception:
        logger.warning('Chek chiqmadi: buyurtma #%s', order.id, exc_info=True)
        return False
