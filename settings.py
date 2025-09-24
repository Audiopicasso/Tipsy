import os
import json
import logging

logger = logging.getLogger(__name__)

if 'PYTEST_CURRENT_TEST' not in os.environ:
    from dotenv import load_dotenv
    load_dotenv()

    
CONFIG_FILE = os.getenv('PUMP_CONFIG_FILE', 'pump_config.json')
COCKTAILS_FILE = os.getenv('COCKTAILS_FILE', 'cocktails.json')
LOGO_FOLDER = os.getenv('LOGO_FOLDER', 'drink_logos')

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

settings = {
    'DEBUG': {
        'parse_method': json.loads,
        'default': 'false'
    }, 
    'ML_COEFFICIENT': {
        'parse_method': float,
        'default': '0.16'
    }, 
    'PERISTALTIC_ML_COEFFICIENT': {
        'parse_method': float,
        'default': '0.16'
    },
    'MEMBRANE_ML_COEFFICIENT': {
        'parse_method': float,
        'default': '0.16'
    },
    'CARBONATED_MEMBRANE_ML_COEFFICIENT': {
        'parse_method': float,
        'default': '0.125'
    },
    'PUMP_CONCURRENCY': {
        'parse_method': int,
        'default': '6'
    }, 
    'RELOAD_COCKTAILS_TIMEOUT': {
        'parse_method': int,
        'default': '0'
    }, 
    'RETRACTION_TIME': {
        'parse_method': float,
        'default': '0'
    }, 
    'COCKTAIL_IMAGE_SCALE': {
        'parse_method': float,
        'default': '0.7'
    }, 
    'INVERT_PUMP_PINS': {
        'parse_method': json.loads,
        'default': 'false'
    }, 
    'FULL_SCREEN': {
        'parse_method': json.loads,
        'default': 'true'
    }, 
    'SHOW_RELOAD_COCKTAILS_BUTTON': {
        'parse_method': json.loads,
        'default': 'false'
    }, 
    'USE_GPT_TRANSPARENCY': {
        'parse_method': json.loads,
        'default': 'false'
    },
    'ALLOW_FAVORITES': {
        'parse_method': json.loads,
        'default': 'false'
    }
}
for name in settings:
    try:
        value = settings[name]['parse_method'](os.getenv(name))
    except (ValueError, json.decoder.JSONDecodeError, TypeError):
        # logger.exception(f'invalid ENV value for {name}')
        value = settings[name]['parse_method'](settings[name]['default'])
    exec(f'{name} = value')

if DEBUG:
    logging.basicConfig(level=logging.DEBUG)

# ===================== PUMP CALIBRATION =====================

# ML_COEFFICIENT: How many seconds to pump 1ml of liquid (Legacy - wird durch spezifische Koeffizienten ersetzt)
# Example: If it takes 8 seconds to pump 50ml, then ML_COEFFICIENT = 8.0 / 50.0 = 0.16
ML_COEFFICIENT = 0.16  # Sekunden pro ml

# PERISTALTIC_ML_COEFFICIENT: Kalibrierung für peristaltische Pumpen (Pumpen 1-6)
# Beispiel: Wenn es 12 Sekunden braucht, um 50ml zu pumpen, dann PERISTALTIC_ML_COEFFICIENT = 12.0 / 50.0 = 0.24
PERISTALTIC_ML_COEFFICIENT = 0.24  # Sekunden pro ml für peristaltische Pumpen (dünne Schläuche, langsam)

# MEMBRANE_ML_COEFFICIENT: Kalibrierung für Membranpumpen (Pumpen 7-12)
# Beispiel: Wenn es 6 Sekunden braucht, um 50ml zu pumpen, dann MEMBRANE_ML_COEFFICIENT = 6.0 / 50.0 = 0.12
MEMBRANE_ML_COEFFICIENT = 0.12  # Sekunden pro ml für Membranpumpen (dickere Schläuche, schnell)

# CARBONATED_MEMBRANE_ML_COEFFICIENT: Kalibrierung für kohlensäurehaltige Getränke auf Membranpumpen
# Beispiel: ca. 8 ml/s => 0.125 s/ml
CARBONATED_MEMBRANE_ML_COEFFICIENT = 0.125

# RETRACTION_TIME: Retract/Reverse ist für Membranpumpen deaktiviert
RETRACTION_TIME = 0.0  # seconds (deaktiviert)

# PUMP_CONCURRENCY: How many pumps can run simultaneously
PUMP_CONCURRENCY = 6

# INVERT_PUMP_PINS: Set to True if your pump motors run in the opposite direction
INVERT_PUMP_PINS = False

# Pumpentypen: Alle 12 Pumpen sind Membranpumpen; peristaltische Pumpen entfallen
PERISTALTIC_PUMPS = []
MEMBRANE_PUMPS    = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]

def get_pump_coefficient(pump_number, carbonated=False):
    """Gibt den Kalibrierungskoeffizienten für eine Pumpe zurück.

    Bei Membranpumpen wird zwischen still (MEMBRANE_ML_COEFFICIENT) und
    kohlensäurehaltig (CARBONATED_MEMBRANE_ML_COEFFICIENT) unterschieden.
    """
    if pump_number in PERISTALTIC_PUMPS:
        # legacy
        return PERISTALTIC_ML_COEFFICIENT
    elif pump_number in MEMBRANE_PUMPS:
        return CARBONATED_MEMBRANE_ML_COEFFICIENT if carbonated else MEMBRANE_ML_COEFFICIENT
    else:
        logger.warning(f"Unbekannte Pumpennummer {pump_number}, verwende Standard-Koeffizient")
        return ML_COEFFICIENT
