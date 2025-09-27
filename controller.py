# controller.py
import logging
logger = logging.getLogger(__name__)

import time
import os
import json
import concurrent.futures

from settings import *
from bottle_monitor import bottle_monitor

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

def get_bottle_id_from_ingredient(ingredient_name):
    """
    Erstellt automatisch eine Flaschen-ID aus dem Zutatennamen.
    Normalisiert den Namen für Flaschen-IDs (ohne Leerzeichen, mit Unterstrichen).
    """
    # Normalisiere den Namen für Flaschen-ID
    bottle_id = ingredient_name.lower().strip()
    # Ersetze Leerzeichen mit Unterstrichen
    bottle_id = bottle_id.replace(' ', '_')
    # Entferne Klammern und deren Inhalt
    bottle_id = bottle_id.replace('(', '').replace(')', '')
    # Ersetze Umlaute für bessere Kompatibilität
    bottle_id = bottle_id.replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    
    return bottle_id

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

# Motor-Controller werden erst bei Bedarf erstellt
motor_controllers_a = None
motor_controllers_b = None

def _init_motor_controllers():
    """Initialisiert die Motor-Controller nur wenn nötig"""
    global motor_controllers_a, motor_controllers_b
    if motor_controllers_a is None and not DEBUG:
        motor_controllers_a = [DigitalOutputDevice(ia) for ia, ib in MOTORS]
        motor_controllers_b = [DigitalOutputDevice(ib) for ia, ib in MOTORS]

def setup_gpio():
    """Set up all motor pins for OUTPUT."""
    if DEBUG:
        logger.debug('setup_gpio() called — Not actually initializing GPIO pins.')
    else:
        _init_motor_controllers()
        logger.debug('GPIO pins initialized with gpiozero')

def motor_forward(ia, ib):
    """Drive motor forward."""
    if DEBUG:
        logger.debug(f'motor_forward({ia}, {ib}) called')
    else:
        _init_motor_controllers()
        for i, (motor_ia, motor_ib) in enumerate(MOTORS):
            if motor_ia == ia and motor_ib == ib:
                motor_controllers_a[i].on()
                motor_controllers_b[i].off()
                break

def motor_stop(ia, ib):
    """Stop motor."""
    if DEBUG:
        logger.debug(f'motor_stop({ia}, {ib}) called')
    else:
        _init_motor_controllers()
        for i, (motor_ia, motor_ib) in enumerate(MOTORS):
            if motor_ia == ia and motor_ib == ib:
                motor_controllers_a[i].off()
                motor_controllers_b[i].off()
                break

def motor_reverse(ia, ib):
    """Drive motor in reverse."""
    if DEBUG:
        logger.debug(f'motor_reverse({ia}, {ib}) called')
    else:
        _init_motor_controllers()
        for i, (motor_ia, motor_ib) in enumerate(MOTORS):
            if motor_ia == ia and motor_ib == ib:
                motor_controllers_a[i].off()
                motor_controllers_b[i].on()
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
        # Nutze ggf. kohlensäure-Koeffizienten
        carbonated = getattr(self, 'carbonated', False)
        pump_coefficient = get_pump_coefficient(pump_number, carbonated=carbonated)

        # Berechne Pumpzeit basierend auf pumpenspezifischem Koeffizienten
        seconds_to_pour = self.amount * pump_coefficient

        # Kein Retract mehr: Membranpumpen können nicht rückwärts laufen

        logger.info(f'Pouring {self.amount} ml of Pump {pump_number} for {seconds_to_pour:.2f} seconds using coefficient {pump_coefficient:.4f} (carbonated={carbonated}).')
        motor_forward(ia, ib)
        time.sleep(seconds_to_pour)

        # Retract entfällt vollständig

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
            # GPIO cleanup not needed with gpiozero
            pass
        else:
            logger.debug('prime_pumps() complete — no GPIO cleanup in debug mode.')

def clean_pumps(duration=10):
    """
    Run each pump forward for `duration` seconds (one after another) to flush/clean lines.
    """
    setup_gpio()
    try:
        for index, (ia, ib) in enumerate(MOTORS, start=1):
            logger.info(f'Flushing pump {index} forward for {duration} seconds (cleaning)...')
            motor_forward(ia, ib)
            time.sleep(duration)
            motor_stop(ia, ib)
    finally:
        if not DEBUG:
            # GPIO cleanup not needed with gpiozero
            pass
        else:
            logger.debug('clean_pumps() complete — no GPIO cleanup in debug mode.')

class ExecutorWatcher:

    def __init__(self):
        self.executors = []
        self.pours = []

    def done(self):
        if any([not executor.done() for executor in self.executors]):
            return False
        return True

def pour_ingredients(ingredients, single_or_double, pump_config, parent_watcher):
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=PUMP_CONCURRENCY)
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
        # Erstelle Flaschen-ID automatisch aus Zutatennamen
        bottle_id = get_bottle_id_from_ingredient(ingredient_name)

        logger.info(f'Überprüfe Flasche: {ingredient_name} -> bottle_id: {bottle_id}, benötigt: {ml_needed:.1f}ml')

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
        # find a matching pump label in pump_config (supports legacy and extended formats)
        chosen_pump = None
        for pump_label, config_entry in pump_config.items():
            # extended format: { "ingredient": "gin", "carbonated": true }
            if isinstance(config_entry, dict):
                config_ing_name = config_entry.get('ingredient', '')
                is_carbonated = bool(config_entry.get('carbonated', False))
            else:
                config_ing_name = config_entry
                is_carbonated = False

            if str(config_ing_name).strip().lower() == ingredient_name.strip().lower():
                chosen_pump = (pump_label, is_carbonated)
                break

        if not chosen_pump:
            logger.critical(f'No pump mapped to ingredient "{ingredient_name}". Skipping.')
            continue

        # parse 'Pump 1' -> index=0
        try:
            pump_label = chosen_pump[0] if isinstance(chosen_pump, tuple) else chosen_pump
            pump_num_str = pump_label.replace('Pump', '').strip()
            pump_index = int(pump_num_str) - 1
        except ValueError:
            logger.critical(f'Could not parse pump label "{chosen_pump}". Skipping.')
            continue

        if pump_index < 0 or pump_index >= len(MOTORS):
            logger.critical(f'Pump index {pump_index} out of range for "{ingredient_name}". Skipping.')
            continue

        # Carbonation-Flag ermitteln
        carbonated_flag = False
        if isinstance(chosen_pump, tuple):
            carbonated_flag = bool(chosen_pump[1])

        pour = Pour(pump_index, ml_needed, ingredient_name)
        pour.carbonated = carbonated_flag
        parent_watcher.pours.append(pour)
        executor_watcher.executors.append(executor.submit(pour.run))

        index += 1

    # Warten bis alle gestarteten Pours fertig sind (ohne Busy-Wait)
    concurrent.futures.wait(executor_watcher.executors)

    # Nach dem Cocktail-Zubereiten: Flaschen-Status synchronisieren
    logger.info("Cocktail-Zubereitung abgeschlossen - synchronisiere Flaschen-Status")
    try:
        logger.info("Alle Flaschen sind nach Cocktail-Zubereitung konsistent")
    except Exception as e:
        logger.error(f"Fehler beim Synchronisieren der Flaschen-Status: {e}")

    if not DEBUG:
        # GPIO cleanup not needed with gpiozero
        pass
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