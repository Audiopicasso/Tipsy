import os
import fcntl
import time
from typing import Dict, Tuple

try:
    from gpiozero import DigitalOutputDevice
except Exception:  # type: ignore
    DigitalOutputDevice = None  # for type checkers / non-pi env


class GPIOPairController:
    """
    Steuert Pumpen mit je zwei Pins (vor/zurück) per gpiozero.
    Nutzt ein /tmp File-Lock, damit nur EIN Prozess gleichzeitig die Pins nutzt.
    Erstellt Geräte nur temporär pro Aktion und schließt sie sofort wieder,
    um "GPIOPinInUse" zwischen Prozessen zu vermeiden.
    """

    def __init__(self, pump_index_to_pins: Dict[int, Tuple[int, int]], lock_file: str = "/tmp/gpio.lock"):
        self.pump_index_to_pins = pump_index_to_pins
        self.lock_file = lock_file

    def _acquire_lock(self, timeout: float = 3.0):
        start = time.time()
        fd = os.open(self.lock_file, os.O_CREAT | os.O_WRONLY)
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return fd
            except OSError:
                if time.time() - start >= timeout:
                    os.close(fd)
                    raise RuntimeError('GPIO busy')
                time.sleep(0.1)

    @staticmethod
    def _open_pair(pin_a: int, pin_b: int):
        dev_a = DigitalOutputDevice(pin_a)  # type: ignore
        dev_b = DigitalOutputDevice(pin_b)  # type: ignore
        return dev_a, dev_b

    @staticmethod
    def _close_pair(dev_a, dev_b):
        try:
            dev_a.off(); dev_b.off()
        except Exception:
            pass
        try:
            dev_a.close(); dev_b.close()
        except Exception:
            pass

    def _with_pair(self, pump_index: int):
        if pump_index not in self.pump_index_to_pins:
            raise ValueError('invalid pump index')
        pin_a, pin_b = self.pump_index_to_pins[pump_index]
        dev_a, dev_b = self._open_pair(pin_a, pin_b)
        return dev_a, dev_b

    def forward(self, pump_index: int):
        fd = self._acquire_lock()
        try:
            dev_a, dev_b = self._with_pair(pump_index)
            try:
                dev_a.on(); dev_b.off()
            finally:
                self._close_pair(dev_a, dev_b)
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def reverse(self, pump_index: int):
        fd = self._acquire_lock()
        try:
            dev_a, dev_b = self._with_pair(pump_index)
            try:
                dev_a.off(); dev_b.on()
            finally:
                self._close_pair(dev_a, dev_b)
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def stop(self, pump_index: int):
        fd = self._acquire_lock()
        try:
            dev_a, dev_b = self._with_pair(pump_index)
            try:
                dev_a.off(); dev_b.off()
            finally:
                self._close_pair(dev_a, dev_b)
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)

    def pulse_forward(self, pump_index: int, seconds: float):
        fd = self._acquire_lock()
        try:
            dev_a, dev_b = self._with_pair(pump_index)
            try:
                dev_a.on(); dev_b.off()
                time.sleep(max(0.0, float(seconds)))
                dev_a.off(); dev_b.off()
            finally:
                self._close_pair(dev_a, dev_b)
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)


