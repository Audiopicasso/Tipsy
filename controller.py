# controller.py
import logging
logger = logging.getLogger(__name__)

import time
import os
import json
import concurrent.futures

from settings import *
from bottle_monitor import bottle_monitor
from gpio_lock import GPIOLock
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# GPIO-Initialisierung mit gpiozero
if not DEBUG:
    try:
        from gpiozero import DigitalOutputDevice
        logger.info('gpiozero erfolgreich geladen - Pi 5 kompatibel')
    except ModuleNotFoundError:
        DEBUG = True
        logger.info('Controller modules not found. Pump control will be disabled')
    except Exception as e:
        DEBUG = True
        logger.error(f'GPIO-Initialisierung fehlgeschlagen: {e}')
        logger.info('Pump control will be disabled')

# Ingredient Mapping: Cocktail-Zutaten zu Flaschen-IDs
INGREDIENT_MAPPING = {
    "rum (weiß)": "rum_(weiß)",
    "rum (weiss)": "rum_(weiß)",  # Alternative Schreibweise
    "wodka": "wodka",
    "gin": "gin",
    "tequila": "tequila",
    "pfirsichlikör": "pfirsichlikör",
    "pfirsichlikoer": "pfirsichlikör",  # Alternative Schreibweise ohne Umlaut
    "grenadinensirup": "grenadinensirup",
    "limettensaft": "limettensaft",
    "orangensaft": "orangensaft",
    "tonic water": "tonic_water",
    "sprite": "sprite",
    "triple sec": "triple_sec",
    "cranberrysaft": "cranberrysaft",
    "cranberry juice": "cranberrysaft",
    "lime juice": "limettensaft",
    "lemon juice": "limettensaft",
    "orange juice": "orangensaft"
}

# Define GPIO pins for each motor here (same as your test).
# Adjust these if needed to match your hardware.
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

"""Motor-Controller werden on-demand erstellt und sofort wieder freigegeben.
Wir halten nur während eines aktiven Laufes Referenzen in-memory.
"""
active_devices = {}
lock_held = False
gpio_lock = GPIOLock()
OWNER_FILE = os.path.join(BASE_DIR, 'gpio_owner.txt')
PROCESS_ROLE = os.getenv('TIPSY_PROCESS', 'interface')

def _read_gpio_owner() -> str:
    try:
        if os.path.exists(OWNER_FILE):
            with open(OWNER_FILE, 'r', encoding='utf-8') as f:
                return f.read().strip().lower()
    except Exception:
        pass
    # Standardmäßig gehört die GPIO-Steuerung der Oberfläche (interface)
    return 'interface'

def _get_or_create_devices(pump_index):
    """Gibt (dev_a, dev_b) für die Pumpe zurück; erstellt sie falls nötig."""
    if pump_index in active_devices:
        return active_devices[pump_index]
    ia, ib = MOTORS[pump_index]
    dev_a = DigitalOutputDevice(ia)
    dev_b = DigitalOutputDevice(ib)
    active_devices[pump_index] = (dev_a, dev_b)
    return dev_a, dev_b

def _close_devices(pump_index):
    pair = active_devices.pop(pump_index, None)
    if not pair:
        return
    dev_a, dev_b = pair
    try:
        dev_a.off(); dev_b.off()
    except Exception:
        pass
    try:
        dev_a.close(); dev_b.close()
    except Exception:
        pass

def _acquire_gpio_or_raise():
    """Versucht exklusiven Zugriff auf GPIO zu bekommen und prüft Besitzrecht per Toggle-Datei."""
    global lock_held
    if DEBUG:
        return
    owner = _read_gpio_owner()
    if owner not in ('interface', 'streamlit'):
        owner = 'interface'
    if owner != PROCESS_ROLE:
        raise RuntimeError(f'GPIO an {owner} vergeben – bitte Toggle in Streamlit ändern')
    # Versuche Lock zu bekommen
    if not lock_held:
        if not gpio_lock.acquire():
            raise RuntimeError('GPIO busy')
        lock_held = True

def _release_gpio_if_held():
    """Gibt Lock und Controller frei, falls gehalten."""
    global lock_held
    if DEBUG:
        return
    _release_motor_controllers()
    if lock_held:
        try:
            gpio_lock.release()
        finally:
            lock_held = False

def setup_gpio():
    """Set up all motor pins for OUTPUT."""
    if DEBUG:
        logger.debug('setup_gpio() called — Not actually initializing GPIO pins.')
    else:
        _acquire_gpio_or_raise()
        logger.debug('GPIO pins initialized with gpiozero')

def motor_forward(ia, ib):
    """Drive motor forward."""
    if DEBUG:
        logger.debug(f'motor_forward({ia}, {ib}) called')
    else:
        for i, (motor_ia, motor_ib) in enumerate(MOTORS):
            if motor_ia == ia and motor_ib == ib:
                dev_a, dev_b = _get_or_create_devices(i)
                dev_a.on(); dev_b.off()
                break

def motor_stop(ia, ib):
    """Stop motor."""
    if DEBUG:
        logger.debug(f'motor_stop({ia}, {ib}) called')
    else:
        for i, (motor_ia, motor_ib) in enumerate(MOTORS):
            if motor_ia == ia and motor_ib == ib:
                dev_a, dev_b = _get_or_create_devices(i)
                dev_a.off(); dev_b.off()
                _close_devices(i)
                break

def motor_reverse(ia, ib):
    """Drive motor in reverse."""
    if DEBUG:
        logger.debug(f'motor_reverse({ia}, {ib}) called')
    else:
        for i, (motor_ia, motor_ib) in enumerate(MOTORS):
            if motor_ia == ia and motor_ib == ib:
                dev_a, dev_b = _get_or_create_devices(i)
                dev_a.off(); dev_b.on()
                break

class Pour:
    def __str__(self):
        return f'{self.ingredient_name}: {self.amount} ml.'

    def __init__(self, pump_index, amount, ingredient_name):
        self.pump_index = pump_index
        self.amount = amount  # amount ist jetzt in ml
        self.ingredient_name = ingredient_name
        self.running = False

    def run(self):
        self.running = True
        ia, ib = MOTORS[self.pump_index]

        # Verwende pumpenspezifischen Kalibrierungskoeffizienten
        pump_number = self.pump_index + 1  # pump_index ist 0-basiert, aber wir brauchen 1-basierte Nummer
        pump_coefficient = get_pump_coefficient(pump_number)

        # Berechne Pumpzeit basierend auf pumpenspezifischem Koeffizienten
        seconds_to_pour = self.amount * pump_coefficient

        if RETRACTION_TIME:
            logger.debug(f'Retraction time is set to {RETRACTION_TIME:.2f} seconds. Adding this time to pour time')
            seconds_to_pour = seconds_to_pour + RETRACTION_TIME

        logger.info(f'Pouring {self.amount} ml of Pump {pump_number} (Type: {"Peristaltic" if pump_number in PERISTALTIC_PUMPS else "Membrane"}) for {seconds_to_pour:.2f} seconds using coefficient {pump_coefficient:.4f}.')
        motor_forward(ia, ib)
        time.sleep(seconds_to_pour)

        if RETRACTION_TIME:
            logger.info(f'Retracting Pump {pump_number} for {RETRACTION_TIME:.2f} seconds')
            motor_reverse(ia, ib)
            time.sleep(RETRACTION_TIME)

        motor_stop(ia, ib)
        self.running = False

def prime_pumps(duration=10):
    """
    Primes each pump for `duration` seconds in sequence (one after another).
    """
    setup_gpio()
    try:
        for index, (ia, ib) in enumerate(MOTORS, start=1):
            logger.info(f'Priming pump {index} for {duration} seconds...')
            motor_forward(ia, ib)
            time.sleep(duration)
            motor_stop(ia, ib)
    finally:
        if not DEBUG:
            _release_gpio_if_held()
        else:
            logger.debug('prime_pumps() complete — no GPIO cleanup in debug mode.')

def clean_pumps(duration=10):
    """
    Reverse each pump for `duration` seconds (one after another),
    e.g. for cleaning lines.
    """
    setup_gpio()
    try:
        for index, (ia, ib) in enumerate(MOTORS, start=1):
            logger.info(f'Reversing pump {index} for {duration} seconds (cleaning)...')
            motor_reverse(ia, ib)
            time.sleep(duration)
            motor_stop(ia, ib)
    finally:
        if not DEBUG:
            _release_gpio_if_held()
        else:
            logger.debug('clean_pumps() complete no GPIO cleanup in debug mode.')

class ExecutorWatcher:

    def __init__(self):
        self.executors = []
        self.pours = []

    def done(self):
        if any([not executor.done() for executor in self.executors]):
            return False
        return True

def pour_ingredients(ingredients, single_or_double, pump_config, parent_watcher):
    executor = concurrent.futures.ThreadPoolExecutor()
    executor_watcher = ExecutorWatcher()
    factor = 2 if single_or_double.lower() == 'double' else 1
    index = 1

    # Überprüfe zuerst alle Flaschen-Füllstände
    ingredients_to_pour = []
    for ingredient_name, measurement_str in sorted(ingredients.items(), key=lambda x: x[1], reverse=True):
        parts = measurement_str.split()
        if not parts:
            logger.critical(f'Cannot parse measurement for {ingredient_name}. Skipping.')
            continue
        try:
            ml_amount = float(parts[0])  # parse numeric (direkt in ml)
        except ValueError:
            logger.critical(f'Cannot parse numeric amount "{parts[0]}" for {ingredient_name}. Skipping.')
            continue

        ml_needed = ml_amount * factor

        # Überprüfe Flaschen-Füllstand
        # Verwende das Ingredient Mapping, um die korrekte Flaschen-ID zu finden
        ingredient_key = ingredient_name.lower().strip()
        bottle_id = INGREDIENT_MAPPING.get(ingredient_key, ingredient_key.replace(' ', '_'))

        logger.info(f'Überprüfe Flasche: {ingredient_name} -> ingredient_key: {ingredient_key} -> bottle_id: {bottle_id}, benötigt: {ml_needed:.1f}ml')

        if not bottle_monitor.consume_liquid(bottle_id, ml_needed):
            logger.error(f'Flasche {ingredient_name} (ID: {bottle_id}) hat nicht genug Flüssigkeit für {ml_needed:.1f}ml')
            # Stoppe alle Pumpen und gebe Fehler zurück
            if not DEBUG:
                # GPIO cleanup not needed with gpiozero
                pass
            return None
        else:
            logger.info(f'Flasche {ingredient_name} (ID: {bottle_id}) hat genug Flüssigkeit. Verbraucht: {ml_needed:.1f}ml')

        ingredients_to_pour.append((ingredient_name, ml_needed))

    # Jetzt alle Zutaten ausgeben
    for ingredient_name, ml_needed in ingredients_to_pour:
        # find a matching pump label in pump_config
        chosen_pump = None
        for pump_label, config_ing_name in pump_config.items():
            if config_ing_name.strip().lower() == ingredient_name.strip().lower():
                chosen_pump = pump_label
                break

        if not chosen_pump:
            logger.critical(f'No pump mapped to ingredient "{ingredient_name}". Skipping.')
            continue

        # parse 'Pump 1' -> index=0
        try:
            pump_num_str = chosen_pump.replace('Pump', '').strip()
            pump_index = int(pump_num_str) - 1
        except ValueError:
            logger.critical(f'Could not parse pump label "{chosen_pump}". Skipping.')
            continue

        if pump_index < 0 or pump_index >= len(MOTORS):
            logger.critical(f'Pump index {pump_index} out of range for "{ingredient_name}". Skipping.')
            continue

        pour = Pour(pump_index, ml_needed, ingredient_name)
        parent_watcher.pours.append(pour)
        executor_watcher.executors.append(executor.submit(pour.run))

        if index % PUMP_CONCURRENCY == 0:
            while not executor_watcher.done():
                pass
        index += 1

    while not executor_watcher.done():
        pass

    # Nach dem Cocktail-Zubereiten: Flaschen-Status synchronisieren
    logger.info("Cocktail-Zubereitung abgeschlossen - synchronisiere Flaschen-Status")
    try:
        logger.info("Alle Flaschen sind nach Cocktail-Zubereitung konsistent")
    except Exception as e:
        logger.error(f"Fehler beim Synchronisieren der Flaschen-Status: {e}")

    if not DEBUG:
        _release_gpio_if_held()
    else:
        logger.debug('pour_ingredients() complete — no GPIO cleanup in debug mode.')

def make_drink(recipe, single_or_double="single"):
    """
    Prepare a drink using the hardware pumps, based on:
      1) a `recipe` dict from cocktails.json (with "ingredients": {...})
      2) single_or_double parameter (either "single" or "double").

    In debug mode, only prints messages instead of driving motors.
    """
    # 1) Load the pump config dictionary, e.g. {"Pump 1": "vodka", "Pump 2": "gin", ...}
    if not os.path.exists(CONFIG_FILE):
        logger.critical(f'pump_config file not found: {CONFIG_FILE}')
        return

    try:
        with open(CONFIG_FILE, 'r') as f:
            pump_config = json.load(f)
    except Exception as e:
        logger.critical(f'Error reading {CONFIG_FILE}: {e}')
        return

    # 2) Extract the recipe's ingredients
    ingredients = recipe.get('ingredients', {})
    if not ingredients:
        logger.critical('No ingredients found in recipe.')
        return

    setup_gpio()
    executor = concurrent.futures.ThreadPoolExecutor()
    executor_watcher = ExecutorWatcher()
    executor_watcher.executors.append(executor.submit(pour_ingredients, ingredients, single_or_double, pump_config, executor_watcher))

    return executor_watcher