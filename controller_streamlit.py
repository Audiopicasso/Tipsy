# controller_streamlit.py - Speziell für Streamlit
import logging
import time
import os
import json
import concurrent.futures
from gpiozero import DigitalOutputDevice

logger = logging.getLogger(__name__)

from settings import *
from bottle_monitor import bottle_monitor

# GPIO-Pins für Pumpen
MOTORS = [
    (17, 4),   # Pump 1
    (22, 27),  # Pump 2
    (9, 10),   # Pump 3
    (5, 11),   # Pump 4
    (13, 6),   # Pump 5
    (26, 19),  # Pump 6
    (20, 21),  # Pump 7
    (16, 12),  # Pump 8
    (7, 8),    # Pump 9
    (25, 24),  # Pump 10
    (23, 18),  # Pump 11
    (15, 14),  # Pump 12
]

def motor_forward(ia, ib):
    """Drive motor forward."""
    if DEBUG:
        logger.debug(f'motor_forward({ia}, {ib}) called')
    else:
        try:
            pin_a = DigitalOutputDevice(ia)
            pin_b = DigitalOutputDevice(ib)
            pin_a.on()
            pin_b.off()
            time.sleep(0.1)  # Kurz warten
            pin_a.close()
            pin_b.close()
        except Exception as e:
            logger.error(f'Fehler motor_forward: {e}')
            raise Exception("GPIO busy")

def motor_stop(ia, ib):
    """Stop motor."""
    if DEBUG:
        logger.debug(f'motor_stop({ia}, {ib}) called')
    else:
        try:
            pin_a = DigitalOutputDevice(ia)
            pin_b = DigitalOutputDevice(ib)
            pin_a.off()
            pin_b.off()
            time.sleep(0.1)  # Kurz warten
            pin_a.close()
            pin_b.close()
        except Exception as e:
            logger.error(f'Fehler motor_stop: {e}')
            raise Exception("GPIO busy")

def motor_reverse(ia, ib):
    """Drive motor in reverse."""
    if DEBUG:
        logger.debug(f'motor_reverse({ia}, {ib}) called')
    else:
        try:
            pin_a = DigitalOutputDevice(ia)
            pin_b = DigitalOutputDevice(ib)
            pin_a.off()
            pin_b.on()
            time.sleep(0.1)  # Kurz warten
            pin_a.close()
            pin_b.close()
        except Exception as e:
            logger.error(f'Fehler motor_reverse: {e}')
            raise Exception("GPIO busy")

def prime_pumps(duration=10):
    """Primes each pump for `duration` seconds in sequence."""
    if DEBUG:
        logger.info(f'DEBUG: Would prime pumps for {duration} seconds')
        return
    
    try:
        for index, (ia, ib) in enumerate(MOTORS, start=1):
            logger.info(f'Priming pump {index} for {duration} seconds...')
            motor_forward(ia, ib)
            time.sleep(duration)
            motor_stop(ia, ib)
    except Exception as e:
        logger.error(f'Prime Pumps Fehler: {e}')
        raise Exception("GPIO busy")

def clean_pumps(duration=10):
    """Reverse each pump for `duration` seconds."""
    if DEBUG:
        logger.info(f'DEBUG: Would clean pumps for {duration} seconds')
        return
    
    try:
        for index, (ia, ib) in enumerate(MOTORS, start=1):
            logger.info(f'Reversing pump {index} for {duration} seconds (cleaning)...')
            motor_reverse(ia, ib)
            time.sleep(duration)
            motor_stop(ia, ib)
    except Exception as e:
        logger.error(f'Clean Pumps Fehler: {e}')
        raise Exception("GPIO busy")
