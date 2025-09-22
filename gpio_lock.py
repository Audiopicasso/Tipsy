# gpio_lock.py
import os
import time
import fcntl
import logging

logger = logging.getLogger(__name__)

class GPIOLock:
    def __init__(self, lock_file="/tmp/gpio.lock"):
        self.lock_file = lock_file
        self.lock_fd = None
    
    def acquire(self, timeout=5):
        """Versuche GPIO-Lock zu erhalten (mit Timeout in Sekunden)."""
        start = time.time()
        # Öffne/erstelle Lock-Datei
        if self.lock_fd is None:
            try:
                self.lock_fd = os.open(self.lock_file, os.O_CREAT | os.O_WRONLY)
            except Exception:
                self.lock_fd = None
                return False
        # Versuche Exklusiv-Lock wiederholt bis Timeout
        while True:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug("GPIO-Lock erhalten")
                return True
            except (OSError, IOError):
                if time.time() - start >= max(0, float(timeout)):
                    logger.warning("GPIO-Lock Timeout — weiterhin belegt")
                    return False
                time.sleep(0.1)
    
    def release(self):
        """GPIO-Lock freigeben"""
        if self.lock_fd:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
                os.close(self.lock_fd)
                os.unlink(self.lock_file)
                logger.debug("GPIO-Lock freigegeben")
            except:
                pass
            self.lock_fd = None
    
    def __enter__(self):
        return self.acquire()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()