"""Xonim — chop etish agenti. Restoran kompyuterida ishlaydi.

Server bulutda, printer esa shu yerda USB'da. Serverdan USB'ga yo'l yo'q,
shuning uchun yo'nalish teskari: agent serverdan «chop etadigan narsa
bormi?» deb so'raydi va olgan baytlarni printerga yuboradi.

Shundan kelib chiqadigan narsalar:
  · restoranda oq IP ham, ochiq port ham, VPN ham kerak emas — faqat
    oddiy chiquvchi internet;
  · internet uzilsa talon serverda navbatda turadi va aloqa tiklangach
    chiqadi, ya'ni chek yo'qolmaydi;
  · agent yiqilsa, olingan-u chop etilmagan talon server tomonda ijara
    muddati tugagach navbatga o'zi qaytadi.

Talonning KO'RINISHI bu yerda emas, serverda yasaladi. Agent faqat
yetkazib beruvchi: shunda chekning ko'rinishini o'zgartirish uchun har
bir restorandagi dasturni yangilash shart bo'lmaydi.

Tashqi kutubxona ishlatilmaydi: faqat standart Python. Shunda o'rnatish
«Python o'rnat va ishga tushir» dan iborat bo'ladi.

Ishga tushirish:
    python xonim_print_agent.py --config agent.ini
    python xonim_print_agent.py --config agent.ini --test
"""
import argparse
import base64
import configparser
import ctypes
import json
import logging
import socket
import sys
import time
import urllib.error
import urllib.request
from ctypes import wintypes

LOG = logging.getLogger('xonim-agent')


class PrinterError(Exception):
    """Talon chiqmadi. Server bu haqda xabar oladi va keyin qayta uradi."""


class _DocInfo(ctypes.Structure):
    _fields_ = [
        ('pDocName', wintypes.LPWSTR),
        ('pOutputFile', wintypes.LPWSTR),
        ('pDatatype', wintypes.LPWSTR),
    ]


def send_windows(data, queue_name):
    """Baytlarni Windows navbatiga RAW holatda beradi.

    RAW bo'lgani uchun haydovchi baytlarga tegmaydi va ESC/POS buyruqlari
    printerga o'zgarmagan holda yetib boradi. Aynan shuning uchun printer
    "Generic / Text Only" haydovchisi bilan o'rnatiladi.
    """
    if not sys.platform.startswith('win'):
        raise PrinterError('Windows navbati faqat Windows da ishlaydi.')
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
            buffer = ctypes.create_string_buffer(data, len(data))
            ok = spooler.WritePrinter(handle, buffer, len(data), ctypes.byref(written))
            spooler.EndPagePrinter(handle)
            if not ok or written.value != len(data):
                raise PrinterError('Talon toliq yuborilmadi. Qogoz va ulanishni tekshiring.')
        finally:
            spooler.EndDocPrinter(handle)
    finally:
        spooler.ClosePrinter(handle)


def send_network(data, target):
    """Tarmoqdagi printerga xom TCP (JetDirect, 9100-port)."""
    host, _, port = target.partition(':')
    try:
        with socket.create_connection((host, int(port or 9100)), timeout=5) as link:
            link.settimeout(10)
            link.sendall(data)
    except OSError as error:
        raise PrinterError(f'Printerga ulanib bolmadi ({target}): {error}') from error


def send(data, device):
    """Qurilma nomiga qarab transportni tanlaydi: IP bolsa tarmoq, aks holda navbat."""
    if ':' in device or device.replace('.', '').isdigit():
        send_network(data, device)
    else:
        send_windows(data, device)


class Server:
    """Server bilan aloqa. Faqat CHIQUVCHI so'rovlar."""

    def __init__(self, base, token, timeout=20):
        self.base = base.rstrip('/')
        self.token = token
        self.timeout = timeout

    def call(self, path, payload):
        request = urllib.request.Request(
            f'{self.base}{path}',
            data=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json', 'X-Print-Agent-Token': self.token},
            method='POST',
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read() or b'{}')

    def claim(self, agent, branch, stations):
        return self.call('/api/v1/print/claim/', {
            'agent': agent, 'branch': branch, 'stations': stations,
        }).get('jobs', [])

    def ack(self, job_id, ok, error=''):
        self.call('/api/v1/print/ack/', {'id': job_id, 'ok': ok, 'error': error[:300]})


def run(config):
    server = Server(config['server']['url'], config['server']['token'])
    agent = config['server'].get('name', 'kassa')
    branch = config['server']['branch']
    devices = dict(config['printers'])
    stations = sorted(devices)
    idle = float(config['server'].get('poll_seconds', '2'))

    LOG.info('Agent ishga tushdi: %s | bolimlar: %s', agent, ', '.join(stations))

    # Xatolikda kutish vaqti osib boradi. Internet yiqilganda har soniyada
    # urinish na tarmoqqa, na jurnalga foyda beradi.
    backoff = idle
    while True:
        try:
            jobs = server.claim(agent, branch, stations)
            backoff = idle
        except urllib.error.HTTPError as error:
            LOG.error('Server rad etdi: %s %s', error.code, error.reason)
            backoff = min(backoff * 2, 60)
            time.sleep(backoff)
            continue
        except Exception as error:  # noqa: BLE001 - tarmoq xatosi turlicha boladi
            LOG.warning('Serverga ulanib bolmadi: %s', error)
            backoff = min(backoff * 2, 60)
            time.sleep(backoff)
            continue

        if not jobs:
            time.sleep(idle)
            continue

        for job in jobs:
            device = devices.get(job['station'])
            if not device:
                # Bu bolim shu agentda sozlanmagan. Server buni bilishi
                # kerak, aks holda topshiriq ijara tugaguncha muzlab turadi.
                server.ack(job['id'], False, f'"{job["station"]}" bolimi bu agentda sozlanmagan')
                continue
            try:
                send(base64.b64decode(job['payload']), device)
            except PrinterError as error:
                LOG.error('Talon #%s chiqmadi: %s', job['id'], error)
                server.ack(job['id'], False, str(error))
            except Exception as error:  # noqa: BLE001 - kutilmagan holat ham xabar qilinadi
                LOG.exception('Talon #%s: kutilmagan xato', job['id'])
                server.ack(job['id'], False, str(error))
            else:
                LOG.info('Talon #%s chiqdi (%s -> %s)', job['id'], job['station'], device)
                server.ack(job['id'], True)


def self_test(config):
    """Har bir sozlangan printerga bitta sinov taloni yuboradi."""
    ok = True
    for station, device in config['printers'].items():
        ticket = (
            b'\x1b\x40\x1b\x61\x01'
            + b'XONIM\n'
            + f'Sinov taloni: {station}\n'.encode('ascii', 'replace')
            + b'\n\n\n\x1d\x56\x42\x00'
        )
        try:
            send(ticket, device)
            print(f'  {station} -> {device}: chiqdi')
        except Exception as error:  # noqa: BLE001
            ok = False
            print(f'  {station} -> {device}: XATO - {error}')
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description='Xonim print agent')
    parser.add_argument('--config', default='agent.ini')
    parser.add_argument('--test', action='store_true', help='Sinov talonini chiqarib korish')
    options = parser.parse_args()

    config = configparser.ConfigParser()
    if not config.read(options.config, encoding='utf-8'):
        print(f'Sozlama fayli topilmadi: {options.config}', file=sys.stderr)
        return 2

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s  %(levelname)-7s %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(config['server'].get('log', 'agent.log'), encoding='utf-8'),
        ],
    )

    if options.test:
        return self_test(config)

    try:
        run(config)
    except KeyboardInterrupt:
        LOG.info('Agent toxtatildi')
    return 0


if __name__ == '__main__':
    sys.exit(main())
