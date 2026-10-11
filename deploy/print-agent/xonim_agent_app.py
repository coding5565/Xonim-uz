"""Xonim — chek printeri agenti. Windows uchun bitta .exe.

Bitta fayl uch ishni bajaradi:

  1. O'RNATADI. Birinchi marta ishga tushirilganda sozlama oynasi
     ochiladi: server, token, printer. So'ng o'zini
     %LOCALAPPDATA%\\XonimAgent ga ko'chiradi va Windows vazifasini
     yaratadi — kompyuter yoqilganda o'zi ishga tushadi.

  2. CHOP ETADI. Serverdan «chop etadigan narsa bormi?» deb so'rab
     turadi va olgan baytlarni printerga yuboradi. Aloqani har doim
     agent boshlaydi, shuning uchun restoranda oq IP ham, ochiq port
     ham, VPN ham kerak emas.

  3. O'ZINI YANGILAYDI. Soatiga bir marta serverdan yangi versiya
     bor-yo'qligini so'raydi. «Yangilash» tugmasi ham bor — kutib
     o'tirmasdan hoziroq yangilash uchun.

Nega bitta fayl: restoranda dastur o'rnatishni biladigan odam
bo'lmasligi mumkin. Python o'rnatish, papka yaratish, fayl ko'chirish —
bularning har biri xato qilish joyi. Bu yerda ularning hech biri yo'q.
"""
import base64
import configparser
import ctypes
import hashlib
import json
import logging
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox, ttk

VERSION = '1.5'
APP_NAME = 'XonimAgent'
TASK_NAME = 'Xonim print agent'
# Yangilanish shuncha vaqtda bir marta tekshiriladi.
UPDATE_EVERY = 3600
# Yangi talon shuncha soniyada bir so'raladi.
POLL_EVERY = 2

LOG = logging.getLogger('xonim')


def home():
    """Dastur va sozlamalar turadigan papka."""
    base = os.environ.get('LOCALAPPDATA') or str(Path.home())
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def installed_exe():
    return home() / 'xonim-agent.exe'


def config_path():
    return home() / 'agent.ini'


def running_frozen():
    """PyInstaller yig'gan .exe ichidamizmi yoki oddiy .py sifatidami."""
    return getattr(sys, 'frozen', False)


# --------------------------------------------------------------------
# Printer
# --------------------------------------------------------------------
class PrinterError(Exception):
    """Talon chiqmadi. Server xabardor bo'ladi va keyin qayta uradi."""


class _DocInfo(ctypes.Structure):
    _fields_ = [
        ('pDocName', wintypes.LPWSTR),
        ('pOutputFile', wintypes.LPWSTR),
        ('pDatatype', wintypes.LPWSTR),
    ]


class _PrinterInfo2(ctypes.Structure):
    """Windows navbati haqida to'liq ma'lumot.

    4-daraja faqat nomni beradi, 2-daraja esa PORT va HAYDOVCHI ni ham.
    Ular kerak: «XP-80C» degan nomning o'zi hech narsa aytmaydi,
    «USB001» yoki «192.168.1.50» esa qaysi printer ekanini ko'rsatadi.
    """

    _fields_ = [
        ('pServerName', wintypes.LPWSTR),
        ('pPrinterName', wintypes.LPWSTR),
        ('pShareName', wintypes.LPWSTR),
        ('pPortName', wintypes.LPWSTR),
        ('pDriverName', wintypes.LPWSTR),
        ('pComment', wintypes.LPWSTR),
        ('pLocation', wintypes.LPWSTR),
        ('pDevMode', wintypes.LPVOID),
        ('pSepFile', wintypes.LPWSTR),
        ('pPrintProcessor', wintypes.LPWSTR),
        ('pDatatype', wintypes.LPWSTR),
        ('pParameters', wintypes.LPWSTR),
        ('pSecurityDescriptor', wintypes.LPVOID),
        ('Attributes', wintypes.DWORD),
        ('Priority', wintypes.DWORD),
        ('DefaultPriority', wintypes.DWORD),
        ('StartTime', wintypes.DWORD),
        ('UntilTime', wintypes.DWORD),
        ('Status', wintypes.DWORD),
        ('cJobs', wintypes.DWORD),
        ('AveragePPM', wintypes.DWORD),
    ]


# Bu «printerlar» qog'ozga emas, faylga yozadi. Ro'yxatdan olib
# tashlamaymiz — ba'zan ataylab kerak bo'ladi — lekin oxiriga suramiz
# va belgilab qo'yamiz. Aynan shu xato bir marta sodir bo'lgan: agent
# «Microsoft Print to PDF» ga sozlanib qolib, chek o'rniga Hujjatlar
# papkasiga PDF yozardi.
VIRTUAL_HINTS = ('print to pdf', 'microsoft xps', 'xps document', 'onenote',
                 'fax', 'pdfcreator', 'dopdf', 'bullzip')


def windows_printers():
    """Kompyuterdagi navbatlar: nom, port, haydovchi."""
    spooler = ctypes.WinDLL('winspool.drv')
    needed = wintypes.DWORD(0)
    returned = wintypes.DWORD(0)
    # PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
    flags = 0x00000002 | 0x00000004
    spooler.EnumPrintersW(flags, None, 2, None, 0, ctypes.byref(needed), ctypes.byref(returned))
    if not needed.value:
        return []
    buffer = ctypes.create_string_buffer(needed.value)
    if not spooler.EnumPrintersW(flags, None, 2, buffer, needed.value,
                                 ctypes.byref(needed), ctypes.byref(returned)):
        return []

    array = ctypes.cast(buffer, ctypes.POINTER(_PrinterInfo2))
    found = []
    for index in range(returned.value):
        item = array[index]
        if not item.pPrinterName:
            continue
        found.append({
            'name': item.pPrinterName,
            'port': item.pPortName or '',
            'driver': item.pDriverName or '',
        })
    return found


def local_ipv4():
    """Shu kompyuterning tarmoqdagi manzillari."""
    found = set()
    try:
        # Hech narsa yuborilmaydi: UDP «ulanishi» shunchaki qaysi tarmoq
        # kartasi ishlatilishini aniqlashga xizmat qiladi.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(('8.8.8.8', 53))
            found.add(probe.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(info[4][0])
    except OSError:
        pass
    return sorted(ip for ip in found if not ip.startswith('127.'))


def scan_network(timeout=0.4, workers=128):
    """LAN da 9100 portini ochgan qurilmalarni topadi.

    9100 — RAW chop etish porti; termal printerlar deyarli har doim shu
    portda turadi. Qurilmaga hech narsa YUBORILMAYDI, faqat ulanib
    ko'riladi: begona printerga sinov bayti yuborilsa, u yerda qog'oz
    behuda chiqib ketardi.
    """
    hosts = []
    seen = set()
    for ip in local_ipv4():
        head = ip.rsplit('.', 1)[0]
        for last in range(1, 255):
            host = f'{head}.{last}'
            if host != ip and host not in seen:
                seen.add(host)
                hosts.append(host)
    if not hosts:
        return []

    found = []
    lock = threading.Lock()

    def probe(host):
        try:
            with socket.create_connection((host, 9100), timeout=timeout):
                pass
        except OSError:
            return
        with lock:
            found.append(host)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(probe, hosts))
    return sorted(found, key=lambda ip: [int(part) for part in ip.split('.')])


def discover(scan=False):
    """Tanlash uchun printerlar ro'yxati.

    Har bir yozuv: `device` — sozlamaga tushadigan qiymat, `label` —
    odamga ko'rsatiladigan matn.
    """
    real, virtual = [], []
    for item in windows_printers():
        low = f"{item['name']} {item['driver']}".lower()
        where = item['port'] or 'port noma’lum'
        if any(hint in low for hint in VIRTUAL_HINTS):
            virtual.append({
                'device': item['name'],
                'label': f"{item['name']} — faylga yozadi, chek chiqmaydi",
            })
        else:
            real.append({
                'device': item['name'],
                'label': f"{item['name']} — {where}",
            })

    entries = list(real)
    if scan:
        for host in scan_network():
            # Windows'da shu manzilga navbat allaqachon bo'lsa, ikki
            # marta ko'rsatmaymiz.
            if any(host in item['label'] for item in real):
                continue
            entries.append({
                'device': f'{host}:9100',
                'label': f'{host}:9100 — tarmoq printeri',
            })
    return entries + virtual


def send_windows(data, queue_name):
    """Baytlarni Windows navbatiga RAW holatda beradi.

    RAW bo'lgani uchun haydovchi baytlarga tegmaydi — ESC/POS buyruqlari
    printerga o'zgarmagan yetib boradi. Shuning uchun printer
    "Generic / Text Only" haydovchisi bilan o'rnatilishi kerak.
    """
    spooler = ctypes.WinDLL('winspool.drv')
    spooler.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), wintypes.LPVOID]
    spooler.StartDocPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(_DocInfo)]
    spooler.WritePrinter.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]

    handle = wintypes.HANDLE()
    if not spooler.OpenPrinterW(queue_name, ctypes.byref(handle), None):
        raise PrinterError(f'"{queue_name}" printeri topilmadi yoki band.')
    try:
        info = _DocInfo('Xonim chek', None, 'RAW')
        if not spooler.StartDocPrinterW(handle, 1, ctypes.byref(info)):
            raise PrinterError('Printer topshiriqni qabul qilmadi.')
        try:
            if not spooler.StartPagePrinter(handle):
                raise PrinterError('Printer topshiriqni boshlamadi.')
            written = wintypes.DWORD(0)
            payload = ctypes.create_string_buffer(data, len(data))
            ok = spooler.WritePrinter(handle, payload, len(data), ctypes.byref(written))
            spooler.EndPagePrinter(handle)
            if not ok or written.value != len(data):
                raise PrinterError('Talon toliq yuborilmadi. Qogoz va ulanishni tekshiring.')
        finally:
            spooler.EndDocPrinter(handle)
    finally:
        spooler.ClosePrinter(handle)


# Tarmoq printeri ba'zan bitta urinishda javob bermaydi: Wi-Fi uzilib
# ulanadi, printer boshqa talonni chop etayotgan bo'ladi yoki uyqu
# rejimidan uyg'onadi. Shuning uchun darhol qayta urinamiz — bu server
# urinishini sarflamaydi va kassir xatoni umuman ko'rmaydi.
NET_RETRIES = 3
NET_RETRY_WAIT = 0.6


def send_network(data, target):
    host, _, port = target.partition(':')
    port = int(port or 9100)
    last = None
    for attempt in range(1, NET_RETRIES + 1):
        try:
            # Ulanish 3 soniyada bo'lmasa, printer uyqu yoki o'chiq —
            # cheksiz kutmaymiz. Printer o'chiq bo'lsa bu talon serverga
            # «chiqmadi» deb qaytadi va u yana navbatga tushadi, kassa
            # taloni esa behuda bloklanib turmaydi.
            with socket.create_connection((host, port), timeout=3) as link:
                link.settimeout(15)
                link.sendall(data)
                # MUHIM: sendall baytlarni OS buferiga topshirgach qaytadi,
                # printer ularni haqiqatan olganini bildirmaydi. Soketni
                # darhol yopsak, oxirgi qism yo'lda qirqilib, chek yarim
                # chiqardi yoki umuman chiqmasdi — aynan shu «ba'zan
                # chiqmaydi» xatosi. Yozuvni yopib, printer ulanishni
                # o'zi uzguncha kutamiz: shunda hamma bayt yetib boradi.
                try:
                    link.shutdown(socket.SHUT_WR)
                    link.recv(64)
                except OSError:
                    # Printer hech narsa qaytarmasligi mumkin — muhimi,
                    # shu paytgacha baytlar yetib bo'ladi.
                    pass
            return
        except OSError as error:
            last = error
            if attempt < NET_RETRIES:
                time.sleep(NET_RETRY_WAIT)
    raise PrinterError(f'Printerga ulanib bo‘lmadi ({target}): {last}')


def send(data, device):
    if ':' in device or device.replace('.', '').isdigit():
        send_network(data, device)
    else:
        send_windows(data, device)


def test_ticket(device, station=''):
    """Qisqa sinov taloni.

    Printerni ko'z bilan aniqlash uchun: ikkitasidan qaysi biri
    oshxonada turganini faqat qog'ozdan bilib bo'ladi.
    """
    esc, gs = b'\x1b', b'\x1d'
    out = esc + b'@'
    out += esc + b'a\x01' + esc + b'!\x30' + b'XONIM\n' + esc + b'!\x00'
    out += b'SINOV TALONI\n' + b'-' * 48 + b'\n'
    out += esc + b'a\x00'
    if station:
        out += f'Stansiya: {station}\n'.encode('ascii', 'replace')
    out += f'Printer:  {device}\n'.encode('ascii', 'replace')
    out += f'Agent:    v{VERSION}\n'.encode('ascii', 'replace')
    out += b'-' * 48 + b'\n'
    out += esc + b'a\x01' + b'Shu talon chiqdi = printer tayyor\n\n\n'
    out += gs + b'V\x00'
    return out


# --------------------------------------------------------------------
# Server
# --------------------------------------------------------------------
class Server:
    def __init__(self, url, token):
        self.base = url.rstrip('/')
        self.token = token

    def _open(self, path, payload=None, timeout=25):
        request = urllib.request.Request(
            f'{self.base}{path}',
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={
                'Content-Type': 'application/json',
                'X-Print-Agent-Token': self.token,
                # Server shu orqali qaysi versiya ishlayotganini biladi.
                'X-Print-Agent-Version': VERSION,
            },
            method='POST' if payload is not None else 'GET',
        )
        return urllib.request.urlopen(request, timeout=timeout)

    def call(self, path, payload=None):
        with self._open(path, payload) as response:
            return json.loads(response.read() or b'{}')

    def claim(self, agent, branch, stations):
        return self.call('/api/v1/print/claim/', {
            'agent': agent, 'branch': branch, 'stations': stations,
        }).get('jobs', [])

    def ack(self, job_id, ok, error=''):
        self.call('/api/v1/print/ack/', {'id': job_id, 'ok': ok, 'error': error[:300]})

    def latest_version(self):
        return self.call('/api/v1/print/agent/version/')

    def download(self, expected_sha, size_hint=0):
        """Yangi .exe ni yuklab oladi va yig'indisini tekshiradi.

        Tekshiruvsiz yarim yuklangan fayl bilan o'zini almashtirgan agent
        boshqa ishga tushmasdi.
        """
        with self._open('/api/v1/print/agent/download/', timeout=300) as response:
            data = response.read()
        if size_hint and len(data) != size_hint:
            raise OSError(f'Hajmi mos kelmadi: {len(data)} / {size_hint}')
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected_sha:
            raise OSError('Yuklangan fayl buzilgan (sha256 mos kelmadi).')
        return data


# --------------------------------------------------------------------
# O'rnatish
# --------------------------------------------------------------------
def write_config(values):
    config = configparser.ConfigParser()
    config['server'] = {
        'url': values['url'],
        'token': values['token'],
        'branch': values['branch'],
        'name': values['name'],
    }
    config['printers'] = {
        'counter': values['counter'],
        'kitchen': values['kitchen'],
    }
    with config_path().open('w', encoding='utf-8') as handle:
        config.write(handle)


def read_config():
    if not config_path().exists():
        return None
    config = configparser.ConfigParser()
    config.read(config_path(), encoding='utf-8')
    if 'server' not in config or 'printers' not in config:
        return None
    return config


def run_quiet(args):
    """Buyruqni konsol oynasisiz bajaradi va javobini matn qilib qaytaradi.

    `text=True` ishlatilmaydi: `schtasks` javobini Windows OEM
    kodlashda beradi, Python esa uni tizim kodlashi bilan o'qishga
    urinib yiqilardi. Xato alohida oqimda ko'tarilgani uchun u
    sezilmasdi — jurnalga esa sababning o'rniga BO'SH qavs tushardi.
    """
    done = subprocess.run(
        args, capture_output=True, check=False,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    raw = (done.stdout or b'') + (done.stderr or b'')
    return done.returncode, raw.decode('cp866', 'replace').strip()


def register_autostart():
    """Kompyuter yoqilganda o'zi ishga tushsin.

    Windows vazifasi xizmatdan sodda: u foydalanuvchi seansida ishlaydi
    va printerga o'sha seansning huquqlari bilan murojaat qiladi —
    xizmat esa alohida seansda turib printerni ko'rmay qolishi mumkin.
    """
    target = installed_exe()
    code, said = run_quiet(
        ['schtasks', '/Create', '/F', '/SC', 'ONLOGON', '/TN', TASK_NAME,
         '/TR', f'"{target}"', '/RL', 'LIMITED'])
    if code == 0:
        LOG.info('Avtoishga tushirish: Windows vazifasi yaratildi')
        return 'task'

    # Vazifa yaratilmadi — odatda huquq yetmaydi va `schtasks` jim
    # qoladi. Zaxira yo'l: «Avtoyuklash» papkasiga yorliq. Unga huquq
    # kerak emas va u xuddi shunday ishlaydi.
    # Odatda sabab — huquq yetmasligi («Access is denied»): vazifa
    # yaratish administrator huquqini talab qiladi. Yorliq esa talab
    # qilmaydi va xuddi shunday ishlaydi, shuning uchun bu xato emas.
    LOG.warning('Windows vazifasi yaratilmadi (%s). Yorliq bilan urinamiz.',
                said[:120] or f'kod {code}')
    startup = Path(os.environ.get('APPDATA', '')) / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup'
    if not startup.exists():
        LOG.error('Avtoishga tushirish sozlanmadi: papka topilmadi')
        return ''
    link = startup / 'Xonim chek printeri.lnk'
    code, said = run_quiet(
        ['powershell', '-NoProfile', '-NonInteractive', '-Command',
         f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{link}');"
         f"$s.TargetPath='{target}';$s.WorkingDirectory='{target.parent}';$s.Save()"])
    if code == 0 and link.exists():
        LOG.info('Avtoishga tushirish: yorliq qo‘yildi')
        return 'shortcut'
    LOG.error('Avtoishga tushirish sozlanmadi: %s', said[:160] or f'kod {code}')
    return ''


def install_self():
    """O'zini doimiy papkaga ko'chiradi.

    Uch holatda hech narsa qilmaydi va bu UCHALASI ham xato emas:
      · allaqachon o'sha papkadan ishlayapti;
      · u yerda AYNAN shu fayl turibdi — nusxalashning ma'nosi yo'q;
      · fayl band, chunki o'sha nusxa hozir ishlab turibdi.

    Oxirgisi Windows'ning qoidasi: ishlab turgan .exe ustiga yozib
    bo'lmaydi. Ilgari bu tutib olinmasdi va foydalanuvchi ish stolidagi
    nusxani ikkinchi marta ochganda ekranga tushunarsiz traceback
    chiqardi — aslida esa hammasi joyida edi, agent ishlayotgan edi.
    """
    if not running_frozen():
        return False
    current = Path(sys.executable).resolve()
    target = installed_exe().resolve()
    if current == target:
        return False
    data = current.read_bytes()
    if target.exists() and target.read_bytes() == data:
        return False
    try:
        target.write_bytes(data)
    except PermissionError:
        LOG.info('O‘rnatilgan nusxa band — u ishlab turibdi, qayta yozilmadi')
        return False
    return True


def version_tuple(text):
    """'1.10' > '1.9' bo'lishi uchun raqamlab solishtiramiz."""
    parts = []
    for chunk in str(text or '').split('.'):
        digits = ''.join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


# Bitta nusxa qulfi. Handle global saqlanadi: u yopilsa qulf ham yo'qoladi.
_LOCK = None


def already_running():
    """Agent allaqachon ishlayaptimi.

    Ikki nusxa bir vaqtda ishlasa, ikkalasi ham navbatdan topshiriq
    oladi va bir xil chek ikki marta chiqishi mumkin — buni keyin
    faqat qog'ozdan bilib bo'ladi.
    """
    global _LOCK
    if not sys.platform.startswith('win'):
        return False
    kernel32 = ctypes.WinDLL('kernel32')
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    _LOCK = kernel32.CreateMutexW(None, False, 'XonimPrintAgentSingleInstance')
    ERROR_ALREADY_EXISTS = 183
    return kernel32.GetLastError() == ERROR_ALREADY_EXISTS


def release_lock():
    """Qulfni bo'shatadi.

    O'zini qayta ishga tushirishdan oldin shart: yangi nusxa qulfni
    band ko'rsa, «allaqachon ishlayapti» deb o'zini yopadi va
    natijada bitta ham agent qolmaydi.
    """
    global _LOCK
    if _LOCK:
        ctypes.WinDLL('kernel32').CloseHandle(wintypes.HANDLE(_LOCK))
        _LOCK = None


def apply_update(data):
    """Yangi .exe ni o'rniga qo'yadi va qayta ishga tushadi.

    Ishlab turgan dastur o'z faylini Windowsda qayta yoza olmaydi,
    shuning uchun almashtirishni kichik .bat bajaradi: u dastur
    yopilishini kutadi, faylni almashtiradi va yangisini ishga tushiradi.
    """
    new_file = home() / 'xonim-agent-new.exe'
    new_file.write_bytes(data)
    script = home() / 'update.bat'
    target = installed_exe()
    script.write_text(
        '@echo off\r\n'
        'ping 127.0.0.1 -n 4 >nul\r\n'
        f'move /y "{new_file}" "{target}" >nul\r\n'
        f'start "" "{target}"\r\n'
        'del "%~f0"\r\n',
        encoding='utf-8',
    )
    subprocess.Popen(
        ['cmd', '/c', str(script)],
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    return True


# --------------------------------------------------------------------
# Ishchi oqim
# --------------------------------------------------------------------
class Worker(threading.Thread):
    """Chop etish va yangilanish — alohida oqimda, oyna qotib qolmasin."""

    def __init__(self, config, events):
        super().__init__(daemon=True)
        self.config = config
        self.events = events
        self.server = Server(config['server']['url'], config['server']['token'])
        self.devices = dict(config['printers'])
        self.stations = sorted(self.devices)
        self.devices_read = 0.0
        self.agent = config['server'].get('name', 'kassa')
        self.branch = config['server']['branch']
        self.stop = threading.Event()
        self.update_now = threading.Event()
        self.printed = 0
        self.last_check = 0.0
        # Chop etilgan va xatoga uchragan talonlar tarixi. Oyna shuni
        # ko'rsatadi va kerak bo'lsa qayta chop etadi. Qulf bilan, chunki
        # ro'yxatni oyna oqimi o'qiydi, ishchi oqim yozadi.
        self.history = []
        self.history_lock = threading.Lock()
        # Qayta chop etish so'rovlari. Oyna bu yerga qo'yadi, ishchi oqim
        # oladi: chop etish HAR DOIM bitta oqimda bo'lsin, aks holda ikki
        # talon bir printerga aralashib ketardi.
        self.reprint_q = queue.Queue()

    def remember(self, job, status, error=''):
        """Talonni tarixga yozadi (yoki mavjudini yangilaydi)."""
        payload = base64.b64decode(job['payload']) if 'payload' in job else job.get('bytes', b'')
        record = {
            'id': job['id'],
            'station': job.get('station', ''),
            'kind': job.get('kind', ''),
            'bytes': payload,
            'status': status,
            'error': error[:120],
            'at': time.strftime('%H:%M:%S'),
        }
        with self.history_lock:
            for existing in self.history:
                if existing['id'] == record['id']:
                    existing.update(status=status, error=error[:120], at=record['at'])
                    if payload:
                        existing['bytes'] = payload
                    return
            self.history.append(record)
            # Oxirgi 200 ta yetarli: tarix kassir uchun, arxiv emas.
            if len(self.history) > 200:
                del self.history[:-200]

    def snapshot_history(self):
        with self.history_lock:
            return [dict(item) for item in reversed(self.history)]

    def request_reprint(self, job_id):
        self.reprint_q.put(job_id)

    def say(self, level, text):
        # Oynaga ham, faylga ham. Oyna kichraytirilgan bo'lsa nima
        # bo'layotganini faqat jurnaldan bilib bo'ladi, ilgari esa u
        # amalda bo'sh qolardi.
        self.events.put((level, text))
        LOG.log({'error': logging.ERROR, 'warn': logging.WARNING}.get(level, logging.INFO), text)

    def run(self):
        self.say('info', f'Agent ishga tushdi · versiya {VERSION}')
        backoff = POLL_EVERY
        while not self.stop.is_set():
            if self.update_now.is_set() or time.time() - self.last_check > UPDATE_EVERY:
                self.update_now.clear()
                self.last_check = time.time()
                self.check_update()
            self.refresh_devices()
            try:
                jobs = self.server.claim(self.agent, self.branch, self.stations)
                if backoff != POLL_EVERY:
                    self.say('ok', 'Server bilan aloqa tiklandi')
                backoff = POLL_EVERY
            except urllib.error.HTTPError as error:
                self.say('error', f'Server rad etdi: {error.code} — tokenni tekshiring')
                backoff = min(backoff * 2, 60)
                self.stop.wait(backoff)
                continue
            except Exception as error:  # noqa: BLE001 - tarmoq xatosi turlicha
                self.say('warn', f'Aloqa yo‘q: {str(error)[:70]}')
                backoff = min(backoff * 2, 60)
                self.stop.wait(backoff)
                continue

            self.do_reprints()
            if not jobs:
                self.stop.wait(POLL_EVERY)
                continue
            for job in jobs:
                self.print_one(job)

    def do_reprints(self):
        """Oynadan so'ralgan qayta chop etishlarni bajaradi."""
        while True:
            try:
                job_id = self.reprint_q.get_nowait()
            except queue.Empty:
                return
            with self.history_lock:
                record = next((dict(item) for item in self.history
                               if item['id'] == job_id), None)
            if not record or not record['bytes']:
                continue
            device = self.devices.get(record['station'])
            if not device:
                self.remember(record, 'failed', f'"{record["station"]}" sozlanmagan')
                self.say('error', f'#{job_id} qayta chiqmadi: "{record["station"]}" sozlanmagan')
                continue
            try:
                send(record['bytes'], device)
            except Exception as error:  # noqa: BLE001
                self.remember(record, 'failed', str(error))
                self.say('error', f'#{job_id} qayta chiqmadi: {str(error)[:60]}')
                continue
            self.printed += 1
            self.remember(record, 'done')
            self.say('ok', f'Talon #{job_id} qayta chiqdi ({record["station"]})')

    def refresh_devices(self):
        """agent.ini qaytadan o'qiladi.

        Printerlar nomi faqat ishga tushganda o'qilsa, faylni qo'lda
        to'g'rilagan odam uchun hech narsa o'zgarmaydi: talon yana
        avvalgi printerga ketadi. Shuning uchun har daqiqada bir marta
        qaytadan o'qiymiz.
        """
        if time.time() - self.devices_read < 60:
            return
        self.devices_read = time.time()
        fresh = read_config()
        if not fresh:
            return
        devices = dict(fresh['printers'])
        if devices and devices != self.devices:
            self.devices = devices
            self.stations = sorted(devices)
            self.say('ok', 'Printer sozlamalari yangilandi')

    def print_one(self, job):
        device = self.devices.get(job['station'])
        if not device:
            self.remember(job, 'failed', f'"{job["station"]}" sozlanmagan')
            self.server.ack(job['id'], False, f'"{job["station"]}" sozlanmagan')
            return
        try:
            send(base64.b64decode(job['payload']), device)
        except Exception as error:  # noqa: BLE001 - har qanday xato serverga xabar qilinadi
            self.remember(job, 'failed', str(error))
            self.say('error', f'Talon #{job["id"]} chiqmadi: {str(error)[:60]}')
            try:
                self.server.ack(job['id'], False, str(error))
            except Exception:  # noqa: BLE001 - aloqa yo'q bo'lsa server o'zi qaytaradi
                pass
            return
        self.printed += 1
        self.remember(job, 'done')
        self.say('ok', f'Talon #{job["id"]} chiqdi ({job["station"]})')
        try:
            self.server.ack(job['id'], True)
        except Exception:  # noqa: BLE001 - ijara tugagach server o'zi qaytaradi
            self.say('warn', f'#{job["id"]} chiqdi, lekin tasdiqlanmadi')

    def check_update(self):
        try:
            info = self.server.latest_version()
        except Exception as error:  # noqa: BLE001
            self.say('warn', f'Yangilanish tekshirilmadi: {str(error)[:60]}')
            return
        self.follow_server(info.get('server_url'))
        latest = info.get('version')
        if not latest or version_tuple(latest) <= version_tuple(VERSION):
            self.say('info', f'Versiya {VERSION} — eng so‘nggisi')
            return
        self.say('info', f'Yangi versiya topildi: {latest}. Yuklanmoqda…')
        try:
            data = self.server.download(info['sha256'], info.get('size', 0))
        except Exception as error:  # noqa: BLE001
            self.say('error', f'Yangilanish yuklanmadi: {str(error)[:60]}')
            return
        self.say('ok', f'Versiya {latest} o‘rnatilmoqda, dastur qayta ishga tushadi')
        apply_update(data)
        self.stop.set()
        os._exit(0)

    def follow_server(self, target):
        """Server boshqa manzilni asosiy deb aytsa, sozlamani shunga o'tkazadi.

        Domen almashganda restoranga borib agent.ini ni tahrirlash shart
        bo'lmasin. Yangi manzil avval shu token bilan tekshiriladi: javob
        bermasa eskisida qolamiz — ishlab turgan aloqani buzmaymiz.
        """
        target = (target or '').strip().rstrip('/')
        if not target.startswith('https://') or target == self.server.base:
            return
        candidate = Server(target, self.server.token)
        try:
            candidate.latest_version()
        except Exception as error:  # noqa: BLE001
            self.say('warn', f'Yangi manzil javob bermadi ({target}): {str(error)[:50]}')
            return
        self.config['server']['url'] = target
        try:
            with config_path().open('w', encoding='utf-8') as handle:
                self.config.write(handle)
        except OSError as error:
            self.say('warn', f'Sozlama yozilmadi: {str(error)[:60]}')
            return
        self.server = candidate
        self.say('ok', f'Server manzili yangilandi: {target}')


# --------------------------------------------------------------------
# Tizim treyi (soat yonidagi belgi)
# --------------------------------------------------------------------
# tkinter'da trey belgisi yo'q, shuning uchun Windows'ning o'z API'si
# (Shell_NotifyIcon) ctypes orqali ishlatiladi — butun agent kabi,
# tashqi kutubxonasiz. Belgi o'z oynasida, alohida oqimda yashaydi:
# Windows unga xabarlarni (sichqoncha bosilishi) o'sha oyna orqali
# yuboradi. Bosilganda natija navbatga qo'yiladi va tkinter uni o'z
# oqimida oladi — oynani boshqa oqimdan chaqirib bo'lmaydi.

WM_USER = 0x0400
TRAY_CALLBACK = WM_USER + 20
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_COMMAND = 0x0111
WM_DESTROY = 0x0002
NIM_ADD = 0x0
NIM_DELETE = 0x2
NIF_MESSAGE = 0x1
NIF_ICON = 0x2
NIF_TIP = 0x4
IDI_APPLICATION = 32512
ID_SHOW = 1001
ID_QUIT = 1002


class _NOTIFYICONDATA(ctypes.Structure):
    _fields_ = [
        ('cbSize', wintypes.DWORD),
        ('hWnd', wintypes.HWND),
        ('uID', wintypes.UINT),
        ('uFlags', wintypes.UINT),
        ('uCallbackMessage', wintypes.UINT),
        ('hIcon', wintypes.HICON),
        ('szTip', wintypes.WCHAR * 128),
        ('dwState', wintypes.DWORD),
        ('dwStateMask', wintypes.DWORD),
        ('szInfo', wintypes.WCHAR * 256),
        ('uTimeoutOrVersion', wintypes.UINT),
        ('szInfoTitle', wintypes.WCHAR * 64),
        ('dwInfoFlags', wintypes.DWORD),
    ]


# LRESULT va LPARAM 64-bitli Windowsda 64 bit. Oddiy c_int bo'lsa,
# oyna identifikatori (katta ko'rsatkich) butun songa sig'may, ctypes
# «int too long» bilan yiqilardi.
LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class _WNDCLASS(ctypes.Structure):
    _fields_ = [
        ('style', wintypes.UINT),
        ('lpfnWndProc', WNDPROC),
        ('cbClsExtra', ctypes.c_int),
        ('cbWndExtra', ctypes.c_int),
        ('hInstance', wintypes.HINSTANCE),
        ('hIcon', wintypes.HICON),
        ('hCursor', wintypes.HANDLE),
        ('hbrBackground', wintypes.HBRUSH),
        ('lpszMenuName', wintypes.LPCWSTR),
        ('lpszClassName', wintypes.LPCWSTR),
    ]


class Tray:
    """Soat yonidagi belgi: ikki marta bosilsa oyna ochiladi.

    on_show / on_quit — tkinter oqimida bajarilishi kerak bo'lgan
    ishlar; Tray ularni to'g'ridan-to'g'ri chaqirmaydi, chunki o'zi
    boshqa oqimda turadi. Shuning uchun ular navbatga qo'yiladigan
    oddiy chaqiruv bo'lishi kutiladi (MainWindow shunday beradi).
    """

    def __init__(self, on_show, on_quit, tip='Xonim chek printeri'):
        self.on_show = on_show
        self.on_quit = on_quit
        self.tip = tip[:127]
        self.hwnd = None
        self._thread = None
        # WNDPROC ga havola saqlanishi SHART: yo'qolsa, Windows uni
        # chaqirganda dastur yiqiladi.
        self._wndproc = WNDPROC(self._handle)
        self._u32 = ctypes.WinDLL('user32')
        self._shell = ctypes.WinDLL('shell32')
        self._k32 = ctypes.WinDLL('kernel32')
        # DefWindowProcW ga ko'rsatkich o'lchamidagi argumentlar ketadi;
        # imzosiz ctypes ularni int deb o'ylab, 64-bitli qiymatda yiqiladi.
        self._u32.DefWindowProcW.restype = LRESULT
        self._u32.DefWindowProcW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _load_icon(self):
        # Avval .exe ning o'z belgisini olishga urinamiz, bo'lmasa
        # standart dastur belgisi — belgisiz trey ko'rinmaydi.
        self._shell.ExtractIconW.restype = wintypes.HICON
        self._shell.ExtractIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT]
        try:
            hicon = self._shell.ExtractIconW(None, str(installed_exe()), 0)
            if hicon and hicon > 1:
                return hicon
        except Exception:  # noqa: BLE001
            pass
        self._u32.LoadIconW.restype = wintypes.HICON
        self._u32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]
        return self._u32.LoadIconW(None, wintypes.LPCWSTR(IDI_APPLICATION))

    def _run(self):
        hinst = self._k32.GetModuleHandleW(None)
        cls = _WNDCLASS()
        cls.lpfnWndProc = self._wndproc
        cls.hInstance = hinst
        cls.lpszClassName = 'XonimTrayWindow'
        self._u32.RegisterClassW.argtypes = [ctypes.POINTER(_WNDCLASS)]
        self._u32.RegisterClassW(ctypes.byref(cls))

        self._u32.CreateWindowExW.restype = wintypes.HWND
        self._u32.CreateWindowExW.argtypes = [
            wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
            ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
        self.hwnd = self._u32.CreateWindowExW(
            0, 'XonimTrayWindow', 'Xonim', 0, 0, 0, 0, 0, None, None, hinst, None)

        self._icon = _NOTIFYICONDATA()
        self._icon.cbSize = ctypes.sizeof(_NOTIFYICONDATA)
        self._icon.hWnd = self.hwnd
        self._icon.uID = 1
        self._icon.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        self._icon.uCallbackMessage = TRAY_CALLBACK
        self._icon.hIcon = self._load_icon()
        self._icon.szTip = self.tip
        self._shell.Shell_NotifyIconW(NIM_ADD, ctypes.byref(self._icon))

        # Xabarlar tsikli: Windows sichqoncha bosilishini shu yerga
        # yuboradi. GetMessageW oyna yopilguncha bloklanadi.
        msg = wintypes.MSG()
        while self._u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            self._u32.TranslateMessage(ctypes.byref(msg))
            self._u32.DispatchMessageW(ctypes.byref(msg))

    def _handle(self, hwnd, msg, wparam, lparam):
        if msg == TRAY_CALLBACK:
            event = lparam & 0xFFFF
            if event in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                self.on_show()
            elif event == WM_RBUTTONUP:
                self._menu()
        elif msg == WM_COMMAND:
            choice = wparam & 0xFFFF
            if choice == ID_SHOW:
                self.on_show()
            elif choice == ID_QUIT:
                self.on_quit()
        elif msg == WM_DESTROY:
            self._shell.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._icon))
        return self._u32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _menu(self):
        menu = self._u32.CreatePopupMenu()
        self._u32.AppendMenuW(menu, 0, ID_SHOW, 'Ochish')
        self._u32.AppendMenuW(menu, 0, ID_QUIT, 'Chiqish')
        point = wintypes.POINT()
        self._u32.GetCursorPos(ctypes.byref(point))
        # TrackPopupMenu'dan oldin SetForegroundWindow shart, aks holda
        # menyu tashqariga bosilganda yopilmay qoladi — Windows qoidasi.
        self._u32.SetForegroundWindow(self.hwnd)
        self._u32.TrackPopupMenu(menu, 0, point.x, point.y, 0, self.hwnd, None)
        self._u32.PostMessageW(self.hwnd, 0, 0, 0)

    def remove(self):
        if self.hwnd:
            try:
                self._shell.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(self._icon))
            except Exception:  # noqa: BLE001
                pass



# --------------------------------------------------------------------
# Oynalar
# --------------------------------------------------------------------
PALETTE = {'bg': '#f3f5f4', 'card': '#ffffff', 'ink': '#1f3b30', 'muted': '#6d7f76'}


class SetupWindow:
    """Birinchi ishga tushirishdagi sozlama."""

    def __init__(self, existing=None):
        self.result = None
        self.root = tk.Tk()
        self.root.title('Xonim — chek printerini sozlash')
        self.root.configure(bg=PALETTE['bg'])
        self.root.resizable(False, False)

        frame = tk.Frame(self.root, bg=PALETTE['bg'], padx=22, pady=18)
        frame.pack(fill='both', expand=True)

        tk.Label(frame, text='Chek printeri', font=('Segoe UI', 15, 'bold'),
                 bg=PALETTE['bg'], fg=PALETTE['ink']).grid(row=0, column=0, columnspan=2, sticky='w')
        tk.Label(frame, text='Bu sozlama bir marta kiritiladi.',
                 bg=PALETTE['bg'], fg=PALETTE['muted']).grid(row=1, column=0, columnspan=2,
                                                             sticky='w', pady=(0, 14))

        self.fields = {}
        rows = [
            ('url', 'Server manzili', 'https://xonimuz.uz'),
            ('token', 'Maxfiy so‘z (token)', ''),
            ('branch', 'Filial', 'xonim'),
            ('name', 'Shu kassaning nomi', 'kassa-1'),
        ]
        for index, (key, label, default) in enumerate(rows, start=2):
            tk.Label(frame, text=label, bg=PALETTE['bg'], fg=PALETTE['ink']).grid(
                row=index, column=0, sticky='w', pady=4)
            entry = tk.Entry(frame, width=42)
            current = existing['server'].get(key, default) if existing else default
            entry.insert(0, current)
            entry.grid(row=index, column=1, pady=4)
            self.fields[key] = entry

        # Ro'yxat ikki bosqichda to'ladi: avval Windows navbatlari —
        # ular bir zumda keladi — keyin fonda tarmoq qidiruvi. Agar
        # ikkalasini ham kutsak, oyna ochilishi sekin ko'rinardi.
        self.entries = discover(scan=False)
        self.scan_results = queue.Queue()
        self.boxes = {}
        for offset, (key, label) in enumerate([('counter', 'Kassa printeri'),
                                               ('kitchen', 'Oshxona printeri')]):
            row = 6 + offset
            tk.Label(frame, text=label, bg=PALETTE['bg'], fg=PALETTE['ink']).grid(
                row=row, column=0, sticky='w', pady=4)
            holder = tk.Frame(frame, bg=PALETTE['bg'])
            holder.grid(row=row, column=1, sticky='w', pady=4)
            # `readonly` EMAS: tarmoq printerining manzilini qo'lda ham
            # yozish mumkin bo'lsin — qidiruv uni topmasligi mumkin,
            # masalan printer boshqa quyi tarmoqda tursa.
            box = ttk.Combobox(holder, width=33)
            box.pack(side='left')
            tk.Button(holder, text='Sinov', command=lambda k=key: self.test_print(k),
                      bg=PALETTE['bg'], fg=PALETTE['ink'], relief='groove',
                      padx=8).pack(side='left', padx=(6, 0))
            self.boxes[key] = box
            self.fields[key] = box

        saved = existing['printers'] if existing else {}
        self.show_entries({key: saved.get(key, '') for key in self.boxes})

        hunt = tk.Frame(frame, bg=PALETTE['bg'])
        hunt.grid(row=8, column=0, columnspan=2, sticky='w', pady=(10, 0))
        self.scan_button = tk.Button(hunt, text='Printerlarni qidirish',
                                     command=self.rescan, bg=PALETTE['bg'],
                                     fg=PALETTE['ink'], relief='groove', padx=10)
        self.scan_button.pack(side='left')
        self.scan_note = tk.Label(hunt, text='', bg=PALETTE['bg'], fg=PALETTE['muted'])
        self.scan_note.pack(side='left', padx=(10, 0))

        tk.Label(frame,
                 text='USB printer ro‘yxatda o‘z porti bilan ko‘rinadi (USB001).\n'
                      'Tarmoq printeri 9100-port bo‘yicha topiladi; manzilini\n'
                      '192.168.0.50:9100 ko‘rinishida qo‘lda ham yozsa bo‘ladi.\n'
                      'Qaysi printer qayerda turganini «Sinov» tugmasi ko‘rsatadi.',
                 bg=PALETTE['bg'], fg=PALETTE['muted'], justify='left').grid(
            row=9, column=0, columnspan=2, sticky='w', pady=(8, 12))

        tk.Button(frame, text='Saqlash va ishga tushirish', command=self.save,
                  bg='#2f6f52', fg='white', relief='flat', padx=16, pady=7,
                  font=('Segoe UI', 10, 'bold')).grid(row=10, column=0, columnspan=2, sticky='e')

        # Oyna chizilib bo'lgach tarmoqni o'zi qidiradi: odam tugmani
        # bosishi shart emas, ro'yxat shundoq ham to'ladi.
        self.root.after(250, self.rescan)

    def show_entries(self, chosen):
        """Ro'yxatni qutilarga joylaydi va tanlovni tiklaydi."""
        labels = [item['label'] for item in self.entries]
        for key, box in self.boxes.items():
            box['values'] = labels
            want = chosen.get(key, '')
            # Saqlangan qiymat — qurilma nomi, ro'yxatda esa izohli
            # matn turadi. Mosini topamiz, topilmasa qiymatning o'zini
            # ko'rsatamiz: u qo'lda yozilgan bo'lishi mumkin.
            shown = next((item['label'] for item in self.entries
                          if item['device'] == want), want)
            box.set(shown or (labels[0] if labels else ''))

    def device_for(self, text):
        """Oynadagi matndan sozlamaga tushadigan qiymatni ajratadi."""
        text = (text or '').strip()
        for item in self.entries:
            if item['label'] == text:
                return item['device']
        return text

    def rescan(self):
        self.scan_note.config(text='Tarmoq qidirilmoqda…')
        self.scan_button.config(state='disabled')

        def work():
            try:
                self.scan_results.put(('topildi', discover(scan=True)))
            except Exception as error:  # noqa: BLE001 - qidiruv xatosi oynani yiqitmasin
                LOG.exception('Printer qidiruvi')
                self.scan_results.put(('xato', error))

        threading.Thread(target=work, daemon=True).start()
        self.root.after(200, self.collect_scan)

    def collect_scan(self):
        """Qidiruv natijasini ASOSIY oqimda oladi.

        tkinter ni boshqa oqimdan chaqirib bo'lmaydi — hatto `after()`
        ni ham: u interpretatorga yangi buyruq qo'shadi va buning
        uchun asosiy oqimda turish shart. Natijada «main thread is not
        in main loop» bilan yiqilardi. Shuning uchun qidiruv oqimi
        javobni navbatga qo'yadi, oyna esa uni shu yerda, o'z oqimida
        olib ketadi — jurnal xabarlari bilan qanday ishlansa, shunday.
        """
        try:
            kind, payload = self.scan_results.get_nowait()
        except queue.Empty:
            self.root.after(200, self.collect_scan)
            return
        if kind == 'topildi':
            self.scan_done(payload)
        else:
            self.scan_failed(payload)

    def scan_done(self, entries):
        # Odam allaqachon tanlagan bo'lsa, tanlovi saqlanib qolsin.
        chosen = {key: self.device_for(box.get()) for key, box in self.boxes.items()}
        self.entries = entries
        self.show_entries(chosen)
        network = sum(1 for item in entries if item['device'].endswith(':9100'))
        self.scan_note.config(
            text=f'Topildi: {len(entries)} ta, shundan tarmoqda {network} ta')
        self.scan_button.config(state='normal')

    def scan_failed(self, error):
        self.scan_note.config(text=f'Qidiruv bajarilmadi: {str(error)[:40]}')
        self.scan_button.config(state='normal')

    def test_print(self, key):
        device = self.device_for(self.boxes[key].get())
        if not device or device.startswith('('):
            messagebox.showwarning('Xonim', 'Avval printerni tanlang.')
            return
        try:
            send(test_ticket(device, key), device)
        except Exception as error:  # noqa: BLE001 - sabab odamga ko'rsatiladi
            messagebox.showerror('Xonim', f'Sinov taloni chiqmadi:\n\n{error}')
            return
        messagebox.showinfo(
            'Xonim',
            f'Sinov taloni yuborildi:\n{device}\n\n'
            'Qaysi printerdan chiqqanini qarang.')

    def save(self):
        values = {key: field.get().strip() for key, field in self.fields.items()}
        for key in self.boxes:
            values[key] = self.device_for(values[key])
        missing = [key for key in ('url', 'token', 'branch') if not values[key]]
        if missing:
            messagebox.showwarning('Xonim', 'Server, token va filial to‘ldirilishi shart.')
            return
        if not values['counter'] or values['counter'].startswith('('):
            messagebox.showwarning('Xonim', 'Avval kassa printerini tanlang.')
            return
        # Oshxona printeri ko'rsatilmasa, talon kassadan chiqaveradi:
        # bitta printerli joylar ham bor va ular uchun bu to'g'ri xatti-harakat.
        if not values['kitchen']:
            values['kitchen'] = values['counter']
        values.setdefault('name', 'kassa-1')
        self.result = values
        self.root.destroy()

    def run(self):
        self.root.mainloop()
        return self.result


class MainWindow:
    """Ishlab turgan agentning oynasi: holat, navbat va tugmalar."""

    STATUS_LABEL = {'done': 'Chiqdi', 'failed': 'Xato', 'queued': 'Navbatda'}

    def __init__(self, config):
        self.config = config
        self.events = queue.Queue()
        self.worker = Worker(config, self.events)
        # Treydan keladigan buyruqlar (ochish/chiqish). Trey boshqa oqimda
        # turadi, oynani esa faqat shu oqimdan chaqirish mumkin, shuning
        # uchun u shu navbat orqali gaplashadi.
        self.tray_q = queue.Queue()
        self.history_sig = None

        self.root = tk.Tk()
        self.root.title(f'Xonim — chek printeri · {VERSION}')
        self.root.configure(bg=PALETTE['bg'])
        self.root.geometry('660x460')

        top = tk.Frame(self.root, bg=PALETTE['bg'], padx=18, pady=14)
        top.pack(fill='x')
        tk.Label(top, text='Chek printeri ishlayapti', font=('Segoe UI', 14, 'bold'),
                 bg=PALETTE['bg'], fg=PALETTE['ink']).pack(anchor='w')
        self.status = tk.Label(top, text='Ishga tushmoqda…', bg=PALETTE['bg'], fg=PALETTE['muted'])
        self.status.pack(anchor='w')

        buttons = tk.Frame(self.root, bg=PALETTE['bg'], padx=18)
        buttons.pack(fill='x')
        tk.Button(buttons, text='Yangilanishni tekshirish', command=self.check_update,
                  bg='#2f6f52', fg='white', relief='flat', padx=14, pady=6).pack(side='left')
        tk.Button(buttons, text='Sinov taloni', command=self.test_print,
                  relief='flat', padx=14, pady=6).pack(side='left', padx=8)
        tk.Button(buttons, text='Sozlamalar', command=self.reconfigure,
                  relief='flat', padx=14, pady=6).pack(side='left')

        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=18, pady=12)

        # 1-varaq: jurnal.
        log_tab = tk.Frame(notebook, bg=PALETTE['bg'])
        notebook.add(log_tab, text='  Holat  ')
        self.log = tk.Text(log_tab, height=12, bg=PALETTE['card'], fg=PALETTE['ink'],
                           relief='flat', font=('Consolas', 9), wrap='word')
        self.log.pack(fill='both', expand=True, padx=4, pady=4)
        self.log.configure(state='disabled')

        # 2-varaq: chop etilgan talonlar navbati va qayta chop etish.
        queue_tab = tk.Frame(notebook, bg=PALETTE['bg'])
        notebook.add(queue_tab, text='  Chop navbati  ')
        bar = tk.Frame(queue_tab, bg=PALETTE['bg'])
        bar.pack(fill='x', padx=4, pady=(4, 0))
        tk.Button(bar, text='Qayta chop etish', command=self.reprint_selected,
                  relief='flat', bg='#2f6f52', fg='white', padx=12, pady=5).pack(side='left')
        tk.Label(bar, text='Chiqmagan talonni tanlab, qayta chop eting.',
                 bg=PALETTE['bg'], fg=PALETTE['muted']).pack(side='left', padx=10)

        columns = ('at', 'id', 'station', 'status', 'error')
        self.table = ttk.Treeview(queue_tab, columns=columns, show='headings', height=11)
        for key, title, width in (('at', 'Vaqt', 70), ('id', '#', 60),
                                  ('station', 'Printer', 90), ('status', 'Holat', 80),
                                  ('error', 'Izoh', 260)):
            self.table.heading(key, text=title)
            self.table.column(key, width=width, anchor='w')
        self.table.tag_configure('done', foreground='#1f7a4d')
        self.table.tag_configure('failed', foreground='#b23030')
        self.table.pack(fill='both', expand=True, padx=4, pady=4)

        # Oyna yopilganda dastur to'xtamaydi — treyga yashiriladi. Kassir
        # tasodifan yopib qo'ysa cheklar chiqmay qolardi. Treydan ikki
        # marta bosib qaytariladi.
        self.root.protocol('WM_DELETE_WINDOW', self.hide_to_tray)

        self.tray = Tray(
            on_show=lambda: self.tray_q.put('show'),
            on_quit=lambda: self.tray_q.put('quit'),
            tip=f'Xonim chek printeri · {config["server"].get("name", "kassa")}')
        self.tray.start()

        self.worker.start()
        self.root.after(300, self.drain)

    # ---- trey ----
    def hide_to_tray(self):
        self.root.withdraw()

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def quit_fully(self):
        self.worker.stop.set()
        self.tray.remove()
        os._exit(0)

    # ---- jurnal ----
    def write(self, level, text):
        marks = {'ok': '  ', 'info': '  ', 'warn': '! ', 'error': 'X '}
        self.log.configure(state='normal')
        self.log.insert('end', f'{time.strftime("%H:%M:%S")} {marks.get(level, "  ")}{text}\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def drain(self):
        while True:
            try:
                level, text = self.events.get_nowait()
            except queue.Empty:
                break
            self.write(level, text)
            if level in ('ok', 'error'):
                self.status.config(text=text)
        while True:
            try:
                command = self.tray_q.get_nowait()
            except queue.Empty:
                break
            if command == 'show':
                self.show_window()
            elif command == 'quit':
                self.quit_fully()
        self.refresh_table()
        self.status_line()
        self.root.after(500, self.drain)

    def refresh_table(self):
        rows = self.worker.snapshot_history()
        # Faqat o'zgarganda qayta chizamiz: aks holda har yarim soniyada
        # tanlov yo'qolib, ro'yxat miltillab turardi.
        sig = tuple((r['id'], r['status']) for r in rows)
        if sig == self.history_sig:
            return
        self.history_sig = sig
        chosen = set(self.table.selection())
        self.table.delete(*self.table.get_children())
        for row in rows:
            iid = str(row['id'])
            self.table.insert('', 'end', iid=iid, tags=(row['status'],), values=(
                row['at'], f"#{row['id']}", row['station'],
                self.STATUS_LABEL.get(row['status'], row['status']),
                row['error'],
            ))
        keep = [iid for iid in chosen if self.table.exists(iid)]
        if keep:
            self.table.selection_set(keep)

    def status_line(self):
        if self.worker.printed:
            self.root.title(f'Xonim — chek printeri · {VERSION} · {self.worker.printed} ta talon')

    # ---- amallar ----
    def reprint_selected(self):
        chosen = self.table.selection()
        if not chosen:
            messagebox.showinfo('Xonim', 'Avval ro‘yxatdan talonni tanlang.')
            return
        for iid in chosen:
            self.worker.request_reprint(int(iid))
        self.write('info', f'{len(chosen)} ta talon qayta chop etishga yuborildi…')

    def check_update(self):
        self.write('info', 'Yangilanish so‘raldi…')
        self.worker.update_now.set()

    def test_print(self):
        for station, device in self.config['printers'].items():
            ticket = (b'\x1b\x40\x1b\x61\x01XONIM\n'
                      + f'Sinov taloni: {station}\n'.encode('ascii', 'replace')
                      + b'\n\n\n\x1d\x56\x42\x00')
            try:
                send(ticket, device)
                self.write('ok', f'Sinov taloni chiqdi: {station} -> {device}')
            except Exception as error:  # noqa: BLE001
                self.write('error', f'{station}: {error}')

    def reconfigure(self):
        self.root.withdraw()
        values = SetupWindow(self.config).run()
        if values:
            write_config(values)
            messagebox.showinfo('Xonim', 'Saqlandi. Dastur qayta ishga tushadi.')
            self.tray.remove()
            release_lock()
            subprocess.Popen([str(installed_exe())],
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            os._exit(0)
        self.root.deiconify()

    def run(self):
        self.root.mainloop()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        filename=str(home() / 'agent.log'),
        encoding='utf-8',
    )

    # Ikkinchi nusxa ishga tushirilsa — to'xtaymiz. Ikkalasi navbatdan
    # topshiriq olsa, bitta chek ikki marta chiqishi mumkin.
    if already_running():
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            'Xonim',
            'Chek printeri allaqachon ishlab turibdi.\n\n'
            'Uning oynasi yopilmagan — kichraytirilgan. Vazifalar '
            'panelidan oching.')
        root.destroy()
        return 0

    config = read_config()
    if config is None:
        values = SetupWindow().run()
        if not values:
            return 0
        write_config(values)
        config = read_config()

    # O'rnatish: o'zini doimiy joyga ko'chirish va avtoishga tushirish.
    #
    # Bu qadam ishlamasa ham dastur TO'XTAMAYDI: u shu yerdan ishlayveradi.
    # O'rnatish qulaylik uchun, chek chiqarish esa asosiy ish — birinchisi
    # ikkinchisini to'xtatib qo'ymasligi kerak.
    if running_frozen():
        try:
            moved = install_self()
        except Exception:  # noqa: BLE001 - sabab jurnalda qoladi
            LOG.exception('Ko‘chirish bajarilmadi')
            moved = False
        # Avtoishga tushirish — ALOHIDA. Ilgari ikkisi bitta `try` da
        # edi: yorliq qo'yilmasa, `moved` ham False bo'lib qolardi va
        # ish stolidagi nusxa o'rnatilganiga topshirmay, o'zi doimiy
        # agentga aylanardi — natijada u fayl band bo'lib, keyingi
        # marta ustiga yangi versiya yozilmay qolardi.
        try:
            register_autostart()
        except Exception:  # noqa: BLE001 - sabab jurnalda qoladi
            LOG.exception('Avtoishga tushirish sozlanmadi')
        if moved:
            subprocess.Popen([str(installed_exe())],
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return 0

    MainWindow(config).run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
