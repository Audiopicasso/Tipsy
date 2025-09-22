# controller_streamlit.py - Speziell für Streamlit
import logging
import time
import os
import json
import concurrent.futures

logger = logging.getLogger(__name__)

from settings import *
from bottle_monitor import bottle_monitor

# GPIO-Pins für Pumpen - Verwende die gleichen Pins wie das Interface
# Aber mit direkter GPIO-Methode statt gpiozero
MOTORS = [
    (17, 4),   # Pump 1 - Gleiche Pins wie Interface
    (22, 27),  # Pump 2 - Gleiche Pins wie Interface
    (9, 10),   # Pump 3 - Gleiche Pins wie Interface
    (5, 11),   # Pump 4 - Gleiche Pins wie Interface
    (13, 6),   # Pump 5 - Gleiche Pins wie Interface
    (26, 19),  # Pump 6 - Gleiche Pins wie Interface
    (20, 21),  # Pump 7 - Gleiche Pins wie Interface
    (16, 12),  # Pump 8 - Gleiche Pins wie Interface
    (7, 8),    # Pump 9 - Gleiche Pins wie Interface
    (25, 24),  # Pump 10 - Gleiche Pins wie Interface
    (23, 18),  # Pump 11 - Gleiche Pins wie Interface
    (15, 14),  # Pump 12 - Gleiche Pins wie Interface
]

def _gpio_export(pin):
    """Export GPIO pin"""
    try:
        with open(f'/sys/class/gpio/export', 'w') as f:
            f.write(str(pin))
    except:
        pass  # Pin bereits exportiert

def _gpio_unexport(pin):
    """Unexport GPIO pin"""
    try:
        with open(f'/sys/class/gpio/unexport', 'w') as f:
            f.write(str(pin))
    except:
        pass

def _gpio_set_direction(pin, direction):
    """Set GPIO direction (in/out)"""
    try:
        with open(f'/sys/class/gpio/gpio{pin}/direction', 'w') as f:
            f.write(direction)
    except:
        pass

def _gpio_set_value(pin, value):
    """Set GPIO value (0/1)"""
    try:
        with open(f'/sys/class/gpio/gpio{pin}/value', 'w') as f:
            f.write(str(value))
    except:
        pass

def motor_forward(ia, ib):
    """Drive motor forward."""
    if DEBUG:
        logger.debug(f'motor_forward({ia}, {ib}) called')
    else:
        try:
            _gpio_export(ia)
            _gpio_export(ib)
            _gpio_set_direction(ia, 'out')
            _gpio_set_direction(ib, 'out')
            _gpio_set_value(ia, 1)
            _gpio_set_value(ib, 0)
        except Exception as e:
            logger.error(f'Fehler motor_forward: {e}')
            raise Exception("GPIO busy")

def motor_stop(ia, ib):
    """Stop motor."""
    if DEBUG:
        logger.debug(f'motor_stop({ia}, {ib}) called')
    else:
        try:
            _gpio_export(ia)
            _gpio_export(ib)
            _gpio_set_direction(ia, 'out')
            _gpio_set_direction(ib, 'out')
            _gpio_set_value(ia, 0)
            _gpio_set_value(ib, 0)
        except Exception as e:
            logger.error(f'Fehler motor_stop: {e}')
            raise Exception("GPIO busy")

def motor_reverse(ia, ib):
    """Drive motor in reverse."""
    if DEBUG:
        logger.debug(f'motor_reverse({ia}, {ib}) called')
    else:
        try:
            _gpio_export(ia)
            _gpio_export(ib)
            _gpio_set_direction(ia, 'out')
            _gpio_set_direction(ib, 'out')
            _gpio_set_value(ia, 0)
            _gpio_set_value(ib, 1)
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
            # GPIO-Pins freigeben
            _gpio_unexport(ia)
            _gpio_unexport(ib)
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
            # GPIO-Pins freigeben
            _gpio_unexport(ia)
            _gpio_unexport(ib)
    except Exception as e:
        logger.error(f'Clean Pumps Fehler: {e}')
        raise Exception("GPIO busy")
