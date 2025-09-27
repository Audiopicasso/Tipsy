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
    },
    'SMALL_COCKTAIL_SIZE_ML': {
        'parse_method': int,
        'default': '220'
    },
    'LARGE_COCKTAIL_SIZE_ML': {
        'parse_method': int,
        'default': '350'
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

# Lade gespeicherte Kalibrierungswerte aus der Datei (falls vorhanden)
def _load_calibration_from_file():
    """Lädt Kalibrierungswerte aus der settings.py Datei selbst"""
    try:
        import re
        with open(__file__, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Suche nach gespeicherten Werten in der Datei
        membrane_match = re.search(r'# SAVED: MEMBRANE_ML_COEFFICIENT = ([\d.]+)', content)
        carbonated_match = re.search(r'# SAVED: CARBONATED_MEMBRANE_ML_COEFFICIENT = ([\d.]+)', content)
        
        if membrane_match:
            globals()['MEMBRANE_ML_COEFFICIENT'] = float(membrane_match.group(1))
        if carbonated_match:
            globals()['CARBONATED_MEMBRANE_ML_COEFFICIENT'] = float(carbonated_match.group(1))
            
    except Exception as e:
        logger.debug(f"Konnte gespeicherte Kalibrierungswerte nicht laden: {e}")

# Lade gespeicherte Werte
_load_calibration_from_file()

# SAVED: MEMBRANE_ML_COEFFICIENT = 0.0740
# SAVED: CARBONATED_MEMBRANE_ML_COEFFICIENT = 0.0740

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
