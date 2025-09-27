import base64
import os
import json
import streamlit as st
import settings
import assist
from rembg import remove
from PIL import Image

import logging
logger = logging.getLogger(__name__)


def load_saved_config():
    if os.path.exists(settings.CONFIG_FILE):
        try:
            with open(settings.CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.exception(f'Error loading pump configuration')
            raise e
    return {}


def save_config(data):
    try:
        with open(settings.CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.exception('Error saving pump configuration')


def save_config_with_carbonation(data, carbonation_map):
    """Speichert Pumpenkonfiguration inklusive Carbonated-Flags.

    data: {"Pump 1": "gin", ...}
    carbonation_map: {"Pump 1": True/False, ...}
    Ergebnisdatei speichert Struktur:
      {"Pump 1": {"ingredient": "gin", "carbonated": true}, ...}
    Abwärtskompatibilität: Wenn carbonation_map leer ist, wird das alte Format verwendet.
    """
    try:
        use_extended = any(isinstance(v, bool) for v in carbonation_map.values())
        if not use_extended:
            return save_config(data)
        extended = {}
        for pump, ingredient in data.items():
            extended[pump] = {
                "ingredient": ingredient,
                "carbonated": bool(carbonation_map.get(pump, False))
            }
        with open(settings.CONFIG_FILE, 'w') as f:
            json.dump(extended, f, indent=2)
    except Exception:
        logger.exception('Error saving extended pump configuration')


def migrate_pump_config_to_extended():
    """Migriert eine bestehende pump_config.json ins erweiterte Format.

    Falls Werte als String vorliegen, werden sie in Objekte mit Feldern
    {"ingredient": <str>, "carbonated": false} umgewandelt.
    Fehlende carbonated-Felder werden auf false ergänzt.
    Gibt True zurück, wenn eine Änderung geschrieben wurde, sonst False.
    """
    try:
        if not os.path.exists(settings.CONFIG_FILE):
            return False
        with open(settings.CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False
        changed = False
        migrated = {}
        for pump, val in data.items():
            if isinstance(val, dict):
                ingredient = val.get('ingredient')
                carbonated = val.get('carbonated')
                if ingredient is None and isinstance(val.get('name'), str):
                    # sehr alter Schlüsselname -> angleichen
                    ingredient = val.get('name')
                if carbonated is None:
                    val['carbonated'] = False
                    changed = True
                migrated[pump] = {'ingredient': ingredient or '', 'carbonated': bool(val.get('carbonated', False))}
            else:
                # String-Format -> migrieren
                migrated[pump] = {'ingredient': str(val), 'carbonated': False}
                changed = True
        if changed:
            with open(settings.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(migrated, f, indent=2, ensure_ascii=False)
        return changed
    except Exception:
        logger.exception('Error migrating pump configuration to extended format')
        return False


def load_cocktails():
    if os.path.exists(settings.COCKTAILS_FILE):
        try:
            with open(settings.COCKTAILS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            logger.exception('Error loading cocktails')
    return {}


def save_cocktails(data, append=True):
    """Save the given list of cocktails to the cocktails file."""
    try:
        cocktails = load_cocktails()
        with open(settings.COCKTAILS_FILE, 'w') as f:
            if append:
                cocktails['cocktails'] += data['cocktails']
            else:
                cocktails = data
            cocktails['cocktails'] = sorted(cocktails['cocktails'], key=lambda cocktail: not cocktail.get('favorite', False))
            json.dump(cocktails, f, indent=2)
    except Exception as e:
        st.error(f'Error saving cocktails: {e}')


def get_safe_name(name):
    """Convert a cocktail name to a safe filename-friendly string."""
    return f'{name.lower().replace(" ", "_")}.png'


def get_cocktail_image_path(cocktail):
    """Given a Cocktail object, get the path to the image for that cocktail.
    Image file name is assumed to be the normal_name in lower snake_case"""
    file_name = get_safe_name(cocktail.get("normal_name", ""))
    path = os.path.join(settings.LOGO_FOLDER, file_name)
    return path


def get_valid_cocktails():
    """Get the list of cocktails that have images associated with them."""
    cocktail_data = load_cocktails().get('cocktails', [])
    cocktails = []
    for cocktail in cocktail_data:
        if os.path.exists(get_cocktail_image_path(cocktail)):
            cocktails.append(cocktail)
    return cocktails

def get_available_cocktails():
    """Get the list of cocktails that have images AND can be made with current bottle levels."""
    from bottle_monitor import bottle_monitor
    
    cocktail_data = load_cocktails().get('cocktails', [])
    available_cocktails = []
    
    for cocktail in cocktail_data:
        # Prüfe zuerst, ob ein Bild existiert
        if not os.path.exists(get_cocktail_image_path(cocktail)):
            continue
            
        # Prüfe dann, ob alle Zutaten verfügbar sind
        ingredients = cocktail.get("ingredients", {})
        if not ingredients:
            continue
            
        try:
            # Konvertiere Zutaten in das Format für can_make_cocktail
            ingredient_list = []
            for ingredient_name, measurement_str in ingredients.items():
                parts = measurement_str.split()
                if parts:
                    try:
                        ml_amount = float(parts[0])
                        ingredient_list.append((ingredient_name.lower(), ml_amount))
                    except ValueError:
                        # Überspringe Zutaten mit ungültigen Mengenangaben
                        continue
            
            # Prüfe Verfügbarkeit mit Bottle-Monitor
            can_make, missing_ingredients = bottle_monitor.can_make_cocktail(ingredient_list)
            
            if can_make:
                available_cocktails.append(cocktail)
                
        except Exception as e:
            # Bei Fehlern überspringe den Cocktail sicherheitshalber
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Fehler beim Prüfen der Verfügbarkeit von {cocktail.get('normal_name', 'Unknown')}: {e}")
            continue
    
    return available_cocktails


def favorite_cocktail(cocktail_index):
    """Mark a cocktail as a favorite. Returns the new index of the cocktail"""
    cocktails = get_available_cocktails()  # Verwende sichere Filterung
    if cocktail_index >= len(cocktails):
        return cocktail_index  # Index außerhalb des Bereichs
    cocktail = cocktails[cocktail_index]
    cocktail['favorite'] = True
    
    # Speichere in der vollständigen Cocktail-Liste
    all_cocktails = load_cocktails().get('cocktails', [])
    for i, c in enumerate(all_cocktails):
        if c.get('normal_name') == cocktail.get('normal_name'):
            all_cocktails[i]['favorite'] = True
            break
    save_cocktails({'cocktails': all_cocktails}, append=False)
    
    # Gib neuen Index in der gefilterten Liste zurück
    updated_cocktails = get_available_cocktails()
    for i, c in enumerate(updated_cocktails):
        if c.get('normal_name') == cocktail.get('normal_name'):
            return i
    return cocktail_index


def unfavorite_cocktail(cocktail_index):
    """Unmark a cocktail as a favorite. Returns the new index of the cocktail"""
    cocktails = get_available_cocktails()  # Verwende sichere Filterung
    if cocktail_index >= len(cocktails):
        return cocktail_index  # Index außerhalb des Bereichs
    cocktail = cocktails[cocktail_index]
    cocktail['favorite'] = False
    
    # Speichere in der vollständigen Cocktail-Liste
    all_cocktails = load_cocktails().get('cocktails', [])
    for i, c in enumerate(all_cocktails):
        if c.get('normal_name') == cocktail.get('normal_name'):
            all_cocktails[i]['favorite'] = False
            break
    save_cocktails({'cocktails': all_cocktails}, append=False)
    
    # Gib neuen Index in der gefilterten Liste zurück
    updated_cocktails = get_available_cocktails()
    for i, c in enumerate(updated_cocktails):
        if c.get('normal_name') == cocktail.get('normal_name'):
            return i
    return cocktail_index


def save_base64_image(base64_string, output_path):
    """
    Decodes a base64 string and saves it as an image file.

    Args:
        base64_string: The base64 encoded string of the image.
        output_path: The path to save the image file.
    """
    try:
        image_data = base64.b64decode(base64_string)
        with open(output_path, 'wb') as file:
            file.write(image_data)
        logger.debug(f'Image saved to {output_path}')
        return output_path
    except Exception:
        logger.exception(f'Error decoding or saving image')


def wrap_text(text, font, width):
    """Wrap text to fit inside a given width when rendered.

    :param text: The text to be wrapped.
    :param font: The font the text will be rendered in.
    :param width: The width to wrap to.

    """
    text_lines = text.replace('\t', '    ').split('\n')
    if width is None or width == 0:
        return text_lines

    wrapped_lines = []
    for line in text_lines:
        line = line.rstrip() + ' '
        if line == ' ':
            wrapped_lines.append(line)
            continue

        # Get the leftmost space ignoring leading whitespace
        start = len(line) - len(line.lstrip())
        start = line.index(' ', start)
        while start + 1 < len(line):
            # Get the next potential splitting point
            next = line.index(' ', start + 1)
            if font.size(line[:next])[0] <= width:
                start = next
            else:
                wrapped_lines.append(line[:start])
                line = line[start+1:]
                start = line.index(' ')
        line = line[:-1]
        if line:
            wrapped_lines.append(line)
    return wrapped_lines


def get_image_prompt(cocktail_name, ingredients=None, use_gpt_transparency=False):
    """Create a prompt for OpenAI to generate a cocktail image"""
    background_color = 'plain white'
    if use_gpt_transparency:
        background_color = 'transparent'
    prompt = (
        f'A realistic illustration of a {cocktail_name} cocktail on a {background_color} background. '
        'The lighting and shading create depth and realism, making the drink appear fresh and inviting. '
        'Do not include shadows, reflections, or the cocktail name in the image. Only generate an image of the cocktail in the glass, not any other objects.'
    )
    if ingredients:
        prompt = f'{prompt} The cocktail ingredients are: {", ".join([ingredient for ingredient in ingredients])}'
    return prompt


def generate_image(normal_name, regenerate=False, ingredients=None, api_key=None, use_gpt_transparency=None):
    if use_gpt_transparency is None:
        use_gpt_transparency = settings.USE_GPT_TRANSPARENCY
    filename = os.path.join(settings.LOGO_FOLDER, get_safe_name(normal_name))

    if not regenerate and os.path.exists(filename):
        # If it already exists, skip generation
        return filename
    else:
        get_image_prompt(normal_name, ingredients)
        try:
            prompt = get_image_prompt(normal_name, ingredients, use_gpt_transparency)
            # Generate the image URL
            b64_image = assist.generate_image(prompt, api_key)
            logger.debug(f'Image generated for {normal_name}')

            if use_gpt_transparency:
                save_base64_image(b64_image, filename)
            else:
                # Download + remove background in memory
                logger.debug(f'Removing background from image for {normal_name}')
                from io import BytesIO
                with Image.open(BytesIO(base64.b64decode(b64_image))) as original_img:
                    img = remove(original_img.convert('RGBA'))
                    logger.debug(f'Saving image with removed background for {normal_name}')
                    img.save(filename, 'PNG')

            return filename

        except Exception:
            logger.exception('Image generation error')
