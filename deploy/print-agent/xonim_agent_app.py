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
from ctypes import wintypes
from pathlib import Path
from tkinter import messagebox, ttk

VERSION = '1.0'
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


def windows_printers():
    """Kompyuterdagi printerlar ro'yxati — sozlama oynasidagi tanlov uchun."""
    spooler = ctypes.WinDLL('winspool.drv')
    needed = wintypes.DWORD(0)
    returned = wintypes.DWORD(0)
    # PRINTER_ENUM_LOCAL | PRINTER_ENUM_CONNECTIONS
    flags = 0x00000002 | 0x00000004
    spooler.EnumPrintersW(flags, None, 4, None, 0, ctypes.byref(needed), ctypes.byref(returned))
    if not needed.value:
        return []
    buffer = ctypes.create_string_buffer(needed.value)
    if not spooler.EnumPrintersW(flags, None, 4, buffer, needed.value,
                                 ctypes.byref(needed), ctypes.byref(returned)):
        return []

    class PrinterInfo4(ctypes.Structure):
        _fields_ = [
            ('pPrinterName', wintypes.LPWSTR),
            ('pServerName', wintypes.LPWSTR),
            ('Attributes', wintypes.DWORD),
        ]

    array = ctypes.cast(buffer, ctypes.POINTER(PrinterInfo4))
    return [array[i].pPrinterName for i in range(returned.value) if array[i].pPrinterName]


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


def send_network(data, target):
    host, _, port = target.partition(':')
    try:
        with socket.create_connection((host, int(port or 9100)), timeout=5) as link:
            link.settimeout(10)
            link.sendall(data)
    except OSError as error:
        raise PrinterError(f'Printerga ulanib bolmadi ({target}): {error}') from error


def send(data, device):
    if ':' in device or device.replace('.', '').isdigit():
        send_network(data, device)
    else:
        send_windows(data, device)


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


def register_autostart():
    """Kompyuter yoqilganda o'zi ishga tushsin.

    Windows vazifasi xizmatdan sodda: u foydalanuvchi seansida ishlaydi
    va printerga o'sha seansning huquqlari bilan murojaat qiladi —
    xizmat esa alohida seansda turib printerni ko'rmay qolishi mumkin.
    """
    target = str(installed_exe())
    subprocess.run(
        ['schtasks', '/Create', '/F', '/SC', 'ONLOGON', '/TN', TASK_NAME,
         '/TR', f'"{target}"', '/RL', 'LIMITED'],
        capture_output=True, text=True, check=False,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )


def install_self():
    """O'zini doimiy papkaga ko'chiradi. Allaqachon o'sha yerda bo'lsa — hech narsa."""
    if not running_frozen():
        return False
    current = Path(sys.executable).resolve()
    target = installed_exe().resolve()
    if current == target:
        return False
    target.write_bytes(current.read_bytes())
    return True


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
        self.agent = config['server'].get('name', 'kassa')
        self.branch = config['server']['branch']
        self.stop = threading.Event()
        self.update_now = threading.Event()
        self.printed = 0
        self.last_check = 0.0

    def say(self, level, text):
        self.events.put((level, text))

    def run(self):
        self.say('info', f'Agent ishga tushdi · versiya {VERSION}')
        backoff = POLL_EVERY
        while not self.stop.is_set():
            if self.update_now.is_set() or time.time() - self.last_check > UPDATE_EVERY:
                self.update_now.clear()
                self.last_check = time.time()
                self.check_update()
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

            if not jobs:
                self.stop.wait(POLL_EVERY)
                continue
            for job in jobs:
                self.print_one(job)

    def print_one(self, job):
        device = self.devices.get(job['station'])
        if not device:
            self.server.ack(job['id'], False, f'"{job["station"]}" sozlanmagan')
            return
        try:
            send(base64.b64decode(job['payload']), device)
        except Exception as error:  # noqa: BLE001 - har qanday xato serverga xabar qilinadi
            self.say('error', f'Talon #{job["id"]} chiqmadi: {str(error)[:60]}')
            try:
                self.server.ack(job['id'], False, str(error))
            except Exception:  # noqa: BLE001 - aloqa yo'q bo'lsa server o'zi qaytaradi
                pass
            return
        self.printed += 1
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
        latest = info.get('version')
        if not latest or latest == VERSION:
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
            ('url', 'Server manzili', 'https://37-140-216-170.sslip.io'),
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

        printers = windows_printers() or ['(printer topilmadi)']
        for offset, (key, label) in enumerate([('counter', 'Kassa printeri'),
                                               ('kitchen', 'Oshxona printeri')]):
            row = 6 + offset
            tk.Label(frame, text=label, bg=PALETTE['bg'], fg=PALETTE['ink']).grid(
                row=row, column=0, sticky='w', pady=4)
            box = ttk.Combobox(frame, values=printers, width=39, state='readonly')
            saved = existing['printers'].get(key, '') if existing else ''
            box.set(saved if saved in printers else printers[0])
            box.grid(row=row, column=1, pady=4)
            self.fields[key] = box

        tk.Label(frame,
                 text='Printer "Generic / Text Only" haydovchisi bilan\n'
                      'o‘rnatilgan bo‘lishi kerak, aks holda avtomatik kesish ishlamaydi.',
                 bg=PALETTE['bg'], fg=PALETTE['muted'], justify='left').grid(
            row=8, column=0, columnspan=2, sticky='w', pady=(10, 12))

        tk.Button(frame, text='Saqlash va ishga tushirish', command=self.save,
                  bg='#2f6f52', fg='white', relief='flat', padx=16, pady=7,
                  font=('Segoe UI', 10, 'bold')).grid(row=9, column=0, columnspan=2, sticky='e')

    def save(self):
        values = {key: field.get().strip() for key, field in self.fields.items()}
        missing = [key for key in ('url', 'token', 'branch') if not values[key]]
        if missing:
            messagebox.showwarning('Xonim', 'Server, token va filial to‘ldirilishi shart.')
            return
        if values['counter'].startswith('('):
            messagebox.showwarning('Xonim', 'Avval printerni Windows‘ga qo‘shing.')
            return
        values.setdefault('name', 'kassa-1')
        self.result = values
        self.root.destroy()

    def run(self):
        self.root.mainloop()
        return self.result


class MainWindow:
    """Ishlab turgan agentning oynasi: holat, jurnal va tugmalar."""

    def __init__(self, config):
        self.config = config
        self.events = queue.Queue()
        self.worker = Worker(config, self.events)

        self.root = tk.Tk()
        self.root.title(f'Xonim — chek printeri · {VERSION}')
        self.root.configure(bg=PALETTE['bg'])
        self.root.geometry('620x420')

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

        body = tk.Frame(self.root, bg=PALETTE['bg'], padx=18, pady=12)
        body.pack(fill='both', expand=True)
        self.log = tk.Text(body, height=14, bg=PALETTE['card'], fg=PALETTE['ink'],
                           relief='flat', font=('Consolas', 9), wrap='word')
        self.log.pack(fill='both', expand=True)
        self.log.configure(state='disabled')

        # Oyna yopilganda dastur to'xtamaydi — u kichrayadi. Kassir
        # tasodifan yopib qo'ysa cheklar chiqmay qolardi.
        self.root.protocol('WM_DELETE_WINDOW', self.root.iconify)

        self.worker.start()
        self.root.after(300, self.drain)

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
        self.status_line()
        self.root.after(500, self.drain)

    def status_line(self):
        if self.worker.printed:
            self.root.title(f'Xonim — chek printeri · {VERSION} · {self.worker.printed} ta talon')

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

    config = read_config()
    if config is None:
        values = SetupWindow().run()
        if not values:
            return 0
        write_config(values)
        config = read_config()

    # O'rnatish: o'zini doimiy joyga ko'chirish va avtoishga tushirish.
    if running_frozen():
        moved = install_self()
        register_autostart()
        if moved:
            subprocess.Popen([str(installed_exe())],
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return 0

    MainWindow(config).run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
