import os
import io
import json
import base64
import time
from pathlib import Path

import streamlit as st
from dotenv import set_key

import assist
from settings import *
from helpers import *
from bottle_monitor import bottle_monitor

# Import your controller module
import controller


# ===================== Small Utilities =====================

def _safe_name(name: str) -> str:
    return get_safe_name(name or "")

def _logo_path(safe_name: str) -> Path:
    return Path(LOGO_FOLDER) / f"{safe_name}.png"

def _send_interface_refresh_signal():
    """Tell the pygame interface to reload assets immediately."""
    try:
        refresh_signal = {"action": "refresh_cocktails", "timestamp": time.time()}
        with open("interface_signal.json", "w", encoding="utf-8") as f:
            json.dump(refresh_signal, f)
        
        # Force immediate file system sync
        os.sync()
        
        return True
    except Exception as e:
        st.warning(f"Could not send refresh signal: {e}")
        return False

def _verify_image_immediately(safe_name: str):
    """Überprüfe sofort, ob das Bild verfügbar ist und zeige es an"""
    # Stelle sicher, dass safe_name keine Dateiendung hat
    safe_name = safe_name.replace('.png', '').replace('.jpg', '').replace('.jpeg', '')
    
    img_path = _logo_path(safe_name)
    if img_path.exists() and img_path.stat().st_size > 0:
        try:
            # Teste, ob das Bild geladen werden kann
            from PIL import Image
            test_img = Image.open(img_path)
            test_img.verify()
            test_img.close()
            return True
        except Exception:
            return False
    return False

def _force_image_reload():
    """Force Streamlit to reload images by updating session state"""
    # Update timestamp for cache busting
    st.session_state.image_update_timestamp = time.time()
    
    # Force a longer delay to ensure file system changes are processed
    time.sleep(0.5)
    
    # Clear any potential image cache
    if hasattr(st, 'cache_data'):
        st.cache_data.clear()
    
    # Use the modern st.rerun() instead of experimental_rerun
    st.rerun()

def _load_cocktails():
    if os.path.exists(COCKTAILS_FILE):
        try:
            with open(COCKTAILS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {"cocktails": []}
            if "cocktails" not in data or not isinstance(data["cocktails"], list):
                data["cocktails"] = []
            return data
        except Exception as e:
            st.error(f"Error loading cocktails: {e}")
            return {"cocktails": []}
    return {"cocktails": []}

def _write_cocktails(data: dict):
    try:
        with open(COCKTAILS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Error saving cocktails: {e}")
        return False

def _clear_ui_overlays():
    """Bereinigt UI-Overlays und Session State Variablen die Probleme verursachen können"""
    # Liste der Session State Keys die potentielle Overlay-Probleme verursachen
    overlay_keys = [
        "changing_image_for",
        "selected_cocktail",
        "editing_bottle_level",
        "editing_bottle_capacity", 
        "editing_bottle_thresholds"
    ]
    
    # Entferne spezifische Keys
    for key in overlay_keys:
        if key in st.session_state:
            del st.session_state[key]
    
    # Entferne alle Upload-bezogenen Keys
    upload_keys = [key for key in st.session_state.keys() if "upload" in key.lower()]
    for key in upload_keys:
        del st.session_state[key]
    
    # Entferne alle Edit-bezogenen Keys
    edit_keys = [key for key in st.session_state.keys() if "editing_" in key]
    for key in edit_keys:
        del st.session_state[key]

def _filter_available_cocktails(cocktails: list) -> tuple:
    """Filtert Cocktails basierend auf verfügbaren Zutaten"""
    available_cocktails = []
    unavailable_cocktails = []
    
    for cocktail in cocktails:
        ingredients = cocktail.get("ingredients", {})
        can_make, missing_ingredients = bottle_monitor.can_make_cocktail(
            [(ingredient.lower(), float(amount.split()[0])) 
             for ingredient, amount in ingredients.items()]
        )
        
        if can_make:
            available_cocktails.append(cocktail)
        else:
            cocktail["missing_ingredients"] = missing_ingredients
            unavailable_cocktails.append(cocktail)
    
    return available_cocktails, unavailable_cocktails

def _rename_logo(old_safe: str, new_safe: str):
    src = _logo_path(old_safe)
    dst = _logo_path(new_safe)
    if src.exists():
        try:
            if dst.exists():
                dst.unlink()  # überschreiben erzwingen
            src.replace(dst)
            return True
        except Exception as e:
            st.warning(f"Image rename failed: {e}")
    return False

def _force_delete_image(safe_name: str):
    """Lösche ein Bild vollständig und warte auf Dateisystem-Updates"""
    # Stelle sicher, dass safe_name keine Dateiendung hat
    safe_name = safe_name.replace('.png', '').replace('.jpg', '').replace('.jpeg', '')
    
    img_path = _logo_path(safe_name)
    if img_path.exists():
        try:
            # Lösche die Datei
            img_path.unlink()
            logger.info(f"Image deleted: {img_path}")
            
            # Warte, bis die Datei wirklich gelöscht ist
            max_wait = 10  # Maximal 10 Versuche
            wait_count = 0
            while img_path.exists() and wait_count < max_wait:
                time.sleep(0.1)
                wait_count += 1
            
            if not img_path.exists():
                logger.info(f"Image successfully deleted after {wait_count} attempts")
                return True
            else:
                logger.warning(f"Image still exists after deletion attempts: {img_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error deleting image {img_path}: {e}")
            return False
    return True  # Datei existierte nicht

def _save_uploaded_logo(safe_name: str, uploaded_file):
    """Speichere Upload *immer* als drink_logos/{safe}.png (überschreiben)."""
    try:
        from PIL import Image
    except Exception:
        st.error("Pillow ist nötig: pip install Pillow")
        return False

    try:
        # Stelle sicher, dass safe_name keine Dateiendung hat
        safe_name = safe_name.replace('.png', '').replace('.jpg', '').replace('.jpeg', '')
        
        out_path = _logo_path(safe_name)
        
        # Lösche zuerst das alte Bild vollständig
        if not _force_delete_image(safe_name):
            st.warning("Could not completely delete old image. Upload may fail.")
        
        # Stelle sicher, dass der Ordner existiert
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Lade das neue Bild und speichere es
        uploaded_file.seek(0)
        img = Image.open(io.BytesIO(uploaded_file.read()))
        
        # Konvertiere zu RGBA und speichere
        img = img.convert("RGBA")
        img.save(out_path, "PNG")
        
        # Force file system sync
        img.close()
        
        # Warte länger, damit das Dateisystem die Änderung verarbeitet
        time.sleep(0.5)
        
        # Überprüfe, ob die Datei tatsächlich existiert und lesbar ist
        if out_path.exists() and out_path.stat().st_size > 0:
            # Teste, ob das Bild tatsächlich geladen werden kann
            try:
                test_img = Image.open(out_path)
                test_img.verify()
                test_img.close()
                logger.info(f"New image saved successfully to {out_path}")
                return True
            except Exception as verify_error:
                st.error(f"Image verification failed: {verify_error}")
                return False
        else:
            st.error(f"Image file was not created or is empty. Path: {out_path}")
            return False
            
    except Exception as e:
        st.error(f"Saving uploaded image failed: {e}")
        logger.exception(f"Error saving image for {safe_name}")
        return False

def _delete_cocktail_and_assets(safe_name: str):
    """Lösche einen Cocktail und alle zugehörigen Assets"""
    # Stelle sicher, dass safe_name keine Dateiendung hat
    safe_name = safe_name.replace('.png', '').replace('.jpg', '').replace('.jpeg', '')
    
    data = _load_cocktails()
    before = len(data.get("cocktails", []))
    
    # Filtere den zu löschenden Cocktail heraus
    data["cocktails"] = [
        c for c in data.get("cocktails", [])
        if _safe_name(c.get("normal_name", "")) != safe_name
    ]
    
    # Speichere die aktualisierten Cocktails
    ok = _write_cocktails(data)
    
    # Lösche das zugehörige Bild
    img = _logo_path(safe_name)
    if img.exists():
        try:
            img.unlink()
            logger.info(f"Image deleted: {img}")
        except Exception as e:
            st.warning(f"Could not remove image file: {e}")
    
    # Sende Interface-Refresh-Signal
    _send_interface_refresh_signal()
    
    # Überprüfe, ob der Cocktail tatsächlich gelöscht wurde
    after = len(data.get("cocktails", []))
    deleted = before > after
    
    if deleted:
        logger.info(f"Cocktail {safe_name} successfully deleted. Before: {before}, After: {after}")
    else:
        logger.warning(f"Cocktail {safe_name} was not found or could not be deleted")
    
    return ok and deleted

def _cache_buster(path: Path) -> float:
    """Ändert sich bei Dateitausch – damit Streamlit wirklich neu rendert."""
    try:
        return path.stat().st_mtime
    except Exception:
        return time.time()


# ===================== API KEY SETUP =====================

if not OPENAI_API_KEY and "openai_api_key" not in st.session_state:
    st.title("Enter OpenAI API Key")
    key_input = st.text_input("OpenAI API Key", type="password")
    if st.button("Submit", use_container_width=True):
        st.session_state["openai_api_key"] = key_input
        set_key(".env", "OPENAI_API_KEY", key_input)
        st.rerun()
    st.stop()

Path(LOGO_FOLDER).mkdir(parents=True, exist_ok=True)

# Track current detail view target
if "selected_cocktail" not in st.session_state:
    st.session_state.selected_cocktail = None

# Track which cocktail image is being changed
if "changing_image_for" not in st.session_state:
    st.session_state.changing_image_for = None

# Track image updates for cache busting
if "image_update_timestamp" not in st.session_state:
    st.session_state.image_update_timestamp = 0

from helpers import migrate_pump_config_to_extended
migrate_pump_config_to_extended()
saved_config = load_saved_config()
cocktail_data = _load_cocktails()


# ===================== Tabs =====================

# Globaler "Clear UI" Button für Overlay-Probleme  
col_title, col_clear = st.columns([4, 1])
with col_clear:
    if st.button("🧹 Clear UI", help="Behebt Overlay-Probleme und setzt UI-Elemente zurück", use_container_width=True):
        _clear_ui_overlays()
        st.success("✅ UI zurückgesetzt!")
        st.rerun()

tabs = st.tabs(["My Bar", "Settings", "Cocktail Menu", "Bottle Monitor"])


# ================ TAB 1: My Bar ================
with tabs[0]:
    st.markdown('<h1 style="text-align: center;">My Bar</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center;">Enter the drink names for each pump:</p>', unsafe_allow_html=True)

    def _default_for(pump_name):
        if pump_name in saved_config:
            return saved_config[pump_name]
        return "vodka" if pump_name == "Pump 1" else ""

    pump_inputs = {}
    pump_carbonated = {}
    col1, col2 = st.columns(2)
    with col1:
        for i in range(1, 7):
            pump_name = f"Pump {i}"
            c1, c2 = st.columns([3,1])
            with c1:
                pump_inputs[pump_name] = st.text_input(pump_name, value=_default_for(pump_name))
            with c2:
                default_carbonated = False
                if pump_name in saved_config and isinstance(saved_config[pump_name], dict):
                    default_carbonated = bool(saved_config[pump_name].get('carbonated', False))
                pump_carbonated[pump_name] = st.checkbox("carbonated", value=default_carbonated, key=f"carbon_{pump_name}")
    with col2:
        for i in range(7, 13):
            pump_name = f"Pump {i}"
            c1, c2 = st.columns([3,1])
            with c1:
                pump_inputs[pump_name] = st.text_input(pump_name, value=_default_for(pump_name))
            with c2:
                default_carbonated = False
                if pump_name in saved_config and isinstance(saved_config[pump_name], dict):
                    default_carbonated = bool(saved_config[pump_name].get('carbonated', False))
                pump_carbonated[pump_name] = st.checkbox("carbonated", value=default_carbonated, key=f"carbon_{pump_name}")

    st.markdown('<h3 style="text-align: center;">Requests for the bartender</h3>', unsafe_allow_html=True)
    bartender_requests = st.text_area("Enter any special requests for the bartender", height=100)
    clear_cocktails = st.checkbox("Remove existing cocktails from the menu")

    if st.button("Generate Recipes", use_container_width=True):
        pump_to_drink = {p: d for p, d in pump_inputs.items() if d.strip()}
        # Speichere extended Konfiguration (inkl. Carbonated)
        from helpers import save_config_with_carbonation
        save_config_with_carbonation(pump_to_drink, pump_carbonated)

        st.markdown(f'<p style="text-align: center;">Pump configuration saved.</p>', unsafe_allow_html=True)

        api_key = st.session_state.get("openai_api_key") or OPENAI_API_KEY
        cocktails_json = assist.generate_cocktails(pump_to_drink, bartender_requests, not clear_cocktails, api_key=api_key)
        save_cocktails(cocktails_json, not clear_cocktails)

        st.markdown('<h2 style="text-align: center;">Generating Cocktail Logos...</h2>', unsafe_allow_html=True)
        cocktails = cocktails_json.get("cocktails", [])
        total = len(cocktails) if cocktails else 1
        bar = st.progress(0, text="Generating images...")

        for idx, c in enumerate(cocktails):
            normal_name = c.get("normal_name", "unknown_drink")
            generate_image(normal_name, False, c.get("ingredients", {}), api_key=api_key)
            bar.progress((idx + 1) / total)

        bar.empty()
        st.success("Image generation complete.")
        _send_interface_refresh_signal()


# ================ TAB 2: Settings ================
with tabs[1]:
    st.title("Settings")

    st.subheader("🔧 Pumpenkalibrierung (alle 12 Membranpumpen)")
    st.info("💡 Kalibriere hier die Koeffizienten für stille und kohlensäurehaltige Getränke.")

    # Membranpumpen Kalibrierung (still)
    membrane_ml_coefficient = st.number_input(
        "Sekunden für 50ml (still)",
        min_value=1.0,
        max_value=120.0,
        value=6.0,
        step=0.5,
        help="Wie viele Sekunden brauchen die Membranpumpen (1-12), um 50ml still zu pumpen?",
        key="membrane_ml_coefficient_input"
    )

    membrane_coefficient = membrane_ml_coefficient / 50.0  # Sekunden pro ml
    st.metric(
        "Kalibrierungskoeffizient",
        f"{membrane_coefficient:.4f} s/ml",
        help="Sekunden pro Milliliter für alle Membranpumpen"
    )

    if st.button("💾 Kalibrierung (still) speichern", use_container_width=True, key="save_membrane_button_all"):
        try:
            settings_file = Path("settings.py")
            if settings_file.exists():
                with open(settings_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                import re
                # Ersetze MEMBRANE_ML_COEFFICIENT
                content = re.sub(r'MEMBRANE_ML_COEFFICIENT = \d+\.?\d*', f'MEMBRANE_ML_COEFFICIENT = {membrane_coefficient:.4f}', content)
                # Setze PERISTALTIC_ML_COEFFICIENT optional gleich, um alte Codepfade unkritisch zu halten
                content = re.sub(r'PERISTALTIC_ML_COEFFICIENT = \d+\.?\d*', f'PERISTALTIC_ML_COEFFICIENT = {membrane_coefficient:.4f}', content)
                with open(settings_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                st.success(f"✅ Kalibrierung (still) gespeichert: {membrane_ml_coefficient}s für 50ml ({membrane_coefficient:.4f}s/ml)")
        except Exception as e:
            st.error(f"❌ Fehler beim Speichern der Kalibrierung: {e}")

    # Kohlensäurehaltig
    carbon_ml_coefficient = st.number_input(
        "Sekunden für 50ml (kohlensäurehaltig)",
        min_value=1.0,
        max_value=120.0,
        value=6.25,
        step=0.5,
        help="Wie viele Sekunden brauchen die Membranpumpen (1-12), um 50ml kohlensäurehaltig zu pumpen?",
        key="carbon_membrane_ml_coefficient_input"
    )

    carbon_coefficient = carbon_ml_coefficient / 50.0
    st.metric(
        "Kalibrierungskoeffizient (kohlensäurehaltig)",
        f"{carbon_coefficient:.4f} s/ml",
        help="Sekunden pro Milliliter für Membranpumpen (CO₂)"
    )

    if st.button("💾 Kalibrierung (kohlensäurehaltig) speichern", use_container_width=True, key="save_carbon_membrane_button"):
        try:
            settings_file = Path("settings.py")
            if settings_file.exists():
                with open(settings_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                import re
                content = re.sub(r'CARBONATED_MEMBRANE_ML_COEFFICIENT = \d+\.?\d*', f'CARBONATED_MEMBRANE_ML_COEFFICIENT = {carbon_coefficient:.4f}', content)
                with open(settings_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                st.success(f"✅ Kalibrierung (CO₂) gespeichert: {carbon_ml_coefficient}s für 50ml ({carbon_coefficient:.4f}s/ml)")
        except Exception as e:
            st.error(f"❌ Fehler beim Speichern der Kalibrierung: {e}")
    
    # Aktuelle Kalibrierung anzeigen (direkt aus geladenen Settings)
    st.markdown("---")
    st.markdown("### 📊 Aktuelle Kalibrierungswerte")
    try:
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric(
                "Membran (still)",
                f"{MEMBRANE_ML_COEFFICIENT * 50:.1f}s / 50ml",
                f"{MEMBRANE_ML_COEFFICIENT:.4f} s/ml"
            )
        with col_b:
            st.metric(
                "Membran (CO₂)",
                f"{CARBONATED_MEMBRANE_ML_COEFFICIENT * 50:.1f}s / 50ml",
                f"{CARBONATED_MEMBRANE_ML_COEFFICIENT:.4f} s/ml"
            )
    except Exception as e:
        st.error(f"❌ Fehler beim Anzeigen der Kalibrierung: {e}")
    
    # Kalibrierungshilfe
    st.markdown("---")
    st.markdown("### 🎯 Kalibrierungshilfe")
    
    with st.expander("📖 Wie kalibriere ich meine Pumpen?"):
        st.markdown("""
        **Schritt-für-Schritt Anleitung:**
        
        1. **Vorbereitung**: Stelle einen Messbecher unter die Pumpe und notiere den Startstand
        2. **Testlauf**: Starte die Pumpe für eine bekannte Zeit (z.B. 10 Sekunden)
        3. **Messung**: Miss die gepumpte Menge in ml
        4. **Berechnung**: Berechne die Zeit für 50ml: `Zeit = (10s × 50ml) ÷ gepumpte_ml`
        5. **Eingabe**: Gib den berechneten Wert in das entsprechende Feld ein
        6. **Speichern**: Klicke auf den Speichern-Button
        
        **Beispiel**: Wenn eine Pumpe in 10 Sekunden 25ml pumpt:
        - Zeit für 50ml = (10s × 50ml) ÷ 25ml = 20 Sekunden
        - Eingabe: 20.0 Sekunden
        """)
    
    # Hinweis: Alle Pumpen sind Membranpumpen
    with st.expander("ℹ️ Info: Pumpentypen"):
        st.markdown("""
        Alle 12 Pumpen sind Membranpumpen. Peristaltische Pumpen wurden entfernt, daher gibt es kein Retract/Reverse mehr.
        """)

    st.subheader("Prime Pumps")
    
    # Kalibrierungsrechner (pumpenagnostisch, ein Speicher-Button)
    st.markdown("---")
    st.markdown("### 🧮 Kalibrierungsrechner")
    st.info("Gib Testzeit und gemessene ml ein. Danach kannst du still oder CO₂ speichern.")
    calc_col1, calc_col2, calc_col3 = st.columns(3)
    with calc_col1:
        calc_time = st.number_input("Testdauer (s)", min_value=1.0, max_value=120.0, value=10.0, step=0.5, key="calc_time")
    with calc_col2:
        calc_ml = st.number_input("Gepumpte Menge (ml)", min_value=0.1, max_value=200.0, value=50.0, step=0.1, key="calc_ml")
    with calc_col3:
        if calc_time > 0 and calc_ml > 0:
            time_for_50ml = (calc_time * 50) / calc_ml
            coeff_calc = calc_time / calc_ml
            st.metric("Ergebnis", f"{time_for_50ml:.1f}s / 50ml", f"{coeff_calc:.4f} s/ml")

    save_col1, save_col2 = st.columns(2)
    with save_col1:
        if st.button("💾 Speichern: still", use_container_width=True, disabled=not (calc_time > 0 and calc_ml > 0)):
            try:
                settings_file = Path("settings.py")
                if settings_file.exists():
                    content = settings_file.read_text(encoding='utf-8')
                    import re
                    content = re.sub(r'MEMBRANE_ML_COEFFICIENT = \d+\.?\d*', f'MEMBRANE_ML_COEFFICIENT = {coeff_calc:.4f}', content)
                    content = re.sub(r'PERISTALTIC_ML_COEFFICIENT = \d+\.?\d*', f'PERISTALTIC_ML_COEFFICIENT = {coeff_calc:.4f}', content)
                    settings_file.write_text(content, encoding='utf-8')
                    st.success("✅ Kalibrierung (still) gespeichert")
            except Exception as e:
                st.error(f"❌ Fehler beim Speichern: {e}")
    with save_col2:
        if st.button("💾 Speichern: CO₂", use_container_width=True, disabled=not (calc_time > 0 and calc_ml > 0)):
            try:
                settings_file = Path("settings.py")
                if settings_file.exists():
                    content = settings_file.read_text(encoding='utf-8')
                    import re
                    content = re.sub(r'CARBONATED_MEMBRANE_ML_COEFFICIENT = \d+\.?\d*', f'CARBONATED_MEMBRANE_ML_COEFFICIENT = {coeff_calc:.4f}', content)
                    settings_file.write_text(content, encoding='utf-8')
                    st.success("✅ Kalibrierung (CO₂) gespeichert")
            except Exception as e:
                st.error(f"❌ Fehler beim Speichern: {e}")
        try:
            settings_file = Path("settings.py")
            if settings_file.exists():
                content = settings_file.read_text(encoding='utf-8')
                import re
                content = re.sub(r'MEMBRANE_ML_COEFFICIENT = \d+\.?\d*', f'MEMBRANE_ML_COEFFICIENT = {coeff_calc:.4f}', content)
                # Optional auch PERISTALTIC_ML_COEFFICIENT spiegeln, um Altpfade konsistent zu halten
                content = re.sub(r'PERISTALTIC_ML_COEFFICIENT = \d+\.?\d*', f'PERISTALTIC_ML_COEFFICIENT = {coeff_calc:.4f}', content)
                settings_file.write_text(content, encoding='utf-8')
                st.success("✅ Membran-Kalibrierung gespeichert")
        except Exception as e:
            st.error(f"❌ Fehler beim Speichern: {e}")

    if st.button("Prime Pumps", use_container_width=True):
        st.info("Priming all pumps for 10 seconds each...")
        try:
            controller.prime_pumps(duration=10)
            st.success("Pumps primed successfully!")
        except Exception as e:
            st.error(f"Error priming pumps: {e}")

    st.subheader("Clean Pumps")
    if st.button("Clean Pumps", use_container_width=True):
        st.info("Flushing all pumps forward for 10 seconds each (cleaning mode)...")
        try:
            controller.clean_pumps(duration=10)
            st.success("All pumps flushed (cleaned).")
        except Exception as e:
            st.error(f"Error cleaning pumps: {e}")

    st.subheader("Interface Control")
    if st.button("Refresh Interface", use_container_width=True):
        st.info("Signaling interface to refresh cocktail list...")
        if _send_interface_refresh_signal():
            st.success("Interface refresh signal sent!")


# ================ TAB 3: Cocktail Menu ================
with tabs[2]:
    st.markdown('<h1 style="text-align: center;">Cocktail Menu</h1>', unsafe_allow_html=True)

    # Flaschen-Status anzeigen
    overall_status = bottle_monitor.get_overall_status()
    if overall_status["empty_bottles"] > 0 or overall_status["low_bottles"] > 0:
        st.warning(f"⚠️ **Flaschen-Status:** {overall_status['empty_bottles']} leere Flaschen, {overall_status['low_bottles']} niedrige Füllstände")
    
    if st.session_state.selected_cocktail:
        # DETAIL VIEW
        safe_name = st.session_state.selected_cocktail

        # re-load to be fresh
        cocktail_data = _load_cocktails()
        selected = None
        for c in cocktail_data.get("cocktails", []):
            if _safe_name(c.get("normal_name", "")) == safe_name:
                selected = c
                break

        if not selected:
            st.error("Cocktail not found.")
        else:
            fun_cur = selected.get("fun_name", "Cocktail")
            norm_cur = selected.get("normal_name", "")

            st.markdown(f'<h1 style="text-align: center;">{fun_cur}</h1>', unsafe_allow_html=True)
            st.markdown(f'<h3 style="text-align: center;">{norm_cur}</h3>', unsafe_allow_html=True)

            # Überprüfe, ob der Cocktail zubereitet werden kann
            ingredients = selected.get("ingredients", {})
            can_make, missing_ingredients = bottle_monitor.can_make_cocktail(
                [(ingredient.lower(), float(amount.split()[0])) 
                 for ingredient, amount in ingredients.items()]
            )
            
            if not can_make:
                st.error(f"❌ **Cocktail kann nicht zubereitet werden:**")
                for missing in missing_ingredients:
                    st.write(f"• {missing}")
                st.info("💡 Fülle die entsprechenden Flaschen auf oder überprüfe den Flaschenstatus im 'Bottle Monitor' Tab")
            else:
                st.success("✅ **Cocktail kann zubereitet werden** - alle Zutaten verfügbar")

            # Rezept/Zutaten anzeigen
            st.divider()
            st.subheader("🍹 Rezept")
            
            if ingredients:
                # Erstelle eine schöne Tabelle für das Rezept
                recipe_data = []
                total_volume = 0
                
                for ingredient, amount in ingredients.items():
                    # Prüfe, ob die Zutat verfügbar ist
                    ingredient_key = ingredient.lower().strip()
                    amount_ml = float(amount.split()[0])
                    total_volume += amount_ml
                    
                    ingredient_mapping = bottle_monitor._get_ingredient_mapping()
                    bottle_id = ingredient_mapping.get(ingredient_key, ingredient_key.replace(' ', '_'))
                    bottle = bottle_monitor.get_bottle_status(bottle_id)
                    
                    if bottle and bottle["current_ml"] >= amount_ml:
                        status = "✅"
                        availability = f"Verfügbar ({bottle['current_ml']:.0f}ml vorrätig)"
                    else:
                        status = "❌"
                        if bottle:
                            availability = f"Nicht genug ({bottle['current_ml']:.0f}ml vorrätig)"
                        else:
                            availability = "Flasche nicht gefunden"
                    
                    recipe_data.append({
                        "Status": status,
                        "Zutat": ingredient,
                        "Menge": amount,
                        "Verfügbarkeit": availability
                    })
                
                # Zeige die Rezept-Tabelle
                col_status, col_ingredient, col_amount, col_availability = st.columns([0.5, 2, 1, 2])
                
                with col_status:
                    st.write("**Status**")
                with col_ingredient:
                    st.write("**Zutat**")
                with col_amount:
                    st.write("**Menge**")
                with col_availability:
                    st.write("**Verfügbarkeit**")
                
                for item in recipe_data:
                    col_status, col_ingredient, col_amount, col_availability = st.columns([0.5, 2, 1, 2])
                    
                    with col_status:
                        st.write(item["Status"])
                    with col_ingredient:
                        st.write(item["Zutat"])
                    with col_amount:
                        st.write(item["Menge"])
                    with col_availability:
                        st.caption(item["Verfügbarkeit"])
                
                # Zeige Gesamtvolumen
                st.info(f"🥃 **Gesamtvolumen:** {total_volume:.0f}ml")
                
            else:
                st.write("Keine Zutaten verfügbar")

            # Bild *hart* neu laden (Cache-Buster)
            img_path = Path(get_cocktail_image_path(selected))
            if img_path.exists():
                # -> Bytes lesen, damit Browser-Cache sicher umgangen wird
                img_bytes = img_path.read_bytes()
                st.image(img_bytes, use_container_width=True, caption=f"updated@{_cache_buster(img_path)}")
            else:
                st.write("Image not found.")

            st.divider()
            st.subheader("Edit Name & Image")

            col_a, col_b = st.columns(2)
            with col_a:
                new_fun = st.text_input("Fun name (display)", value=fun_cur, key="edit_fun_name")
            with col_b:
                new_norm = st.text_input("Normal name (technical)", value=norm_cur, key="edit_normal_name")

            uploaded_logo = st.file_uploader(
                "Replace cocktail image (PNG/JPG) — will overwrite current image",
                type=["png", "jpg", "jpeg"],
                key="edit_logo_uploader"
            )

            c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.5, 1])

            with c1:
                if st.button("Save changes", key="save_changes_btn", use_container_width=True):
                    data = _load_cocktails()
                    cur_safe = _safe_name(norm_cur)
                    new_norm_clean = (new_norm or norm_cur).strip()
                    new_fun_clean = (new_fun or fun_cur).strip()
                    new_safe = _safe_name(new_norm_clean)

                    updated = False
                    for i, cktl in enumerate(data.get("cocktails", [])):
                        if _safe_name(cktl.get("normal_name", "")) == cur_safe:
                            data["cocktails"][i]["fun_name"] = new_fun_clean
                            data["cocktails"][i]["normal_name"] = new_norm_clean
                            updated = True
                            break

                    if not updated:
                        st.error("Could not locate cocktail in cocktails.json")
                    else:
                        # Bild speichern/umbenennen
                        if uploaded_logo is not None:
                            ok_img = _save_uploaded_logo(new_safe, uploaded_logo)
                            if ok_img:
                                st.success("Image uploaded and applied.")
                        else:
                            if new_safe != cur_safe:
                                if _rename_logo(cur_safe, new_safe):
                                    st.info("Image renamed to match the new cocktail name.")

                        if _write_cocktails(data):
                            _send_interface_refresh_signal()
                            st.success("Saved. Interface refreshed.")
                            st.session_state.selected_cocktail = new_safe
                            st.rerun()

            with c2:
                if st.button("Delete cocktail", key="delete_cocktail_btn", use_container_width=True):
                    confirm = st.checkbox("Really delete this cocktail?", key="confirm_delete_chk")
                    if confirm:
                        with st.spinner("Deleting cocktail..."):
                            if _delete_cocktail_and_assets(safe_name):
                                st.success("✅ Cocktail successfully deleted!")
                                # Force immediate interface refresh
                                _send_interface_refresh_signal()
                                # Update session state to force reload
                                st.session_state.image_update_timestamp = time.time()
                                # Clear selected cocktail and return to menu
                                st.session_state.selected_cocktail = None
                                st.rerun()
                            else:
                                st.error("❌ Failed to delete cocktail. Please try again.")

            with c3:
                if st.button("🔄 Generate New Image", key="generate_detail_img_btn", use_container_width=True):
                    with st.spinner("Generating new image..."):
                        try:
                            # Generiere ein neues Bild für diesen spezifischen Cocktail
                            api_key = st.session_state.get("openai_api_key") or OPENAI_API_KEY
                            if generate_image(norm_cur, regenerate=True, ingredients=selected.get("ingredients", {}), api_key=api_key):
                                st.success("✅ New image generated!")
                                # Sende Interface-Refresh-Signal
                                _send_interface_refresh_signal()
                                # Update session state to force reload
                                st.session_state.image_update_timestamp = time.time()
                                # Rerun to show new image
                                st.rerun()
                            else:
                                st.error("❌ Failed to generate new image")
                        except Exception as e:
                            st.error(f"❌ Error generating image: {e}")

            with c4:
                if st.button("🔙 Back to Menu", key="back_to_menu_btn", use_container_width=True):
                    st.session_state.selected_cocktail = None
                    st.rerun()

    else:
        # GALLERY VIEW
        cocktail_data = _load_cocktails()
        cocktails = cocktail_data.get("cocktails", [])
        
        if not cocktails:
            st.info("No cocktails found. Go to 'My Bar' to generate some!")
        else:
            # Add New Cocktail Section
            st.subheader("➕ Neuen Cocktail hinzufügen")
            
            # Container für bessere Kontrolle über das Layout
            with st.container():
                col_add1, col_add2, col_add3 = st.columns([1.2, 1, 1.5])
                with col_add1:
                    new_cocktail_name = st.text_input("Cocktail Name", placeholder="z.B. Margarita", key="new_cocktail_name")
                with col_add2:
                    new_cocktail_fun = st.text_input("Fun Name", placeholder="z.B. Citrus Snap", key="new_cocktail_fun")
                with col_add3:
                    # Text Area in eigenem Container für bessere Kontrolle
                    ingredients_container = st.container()
                    with ingredients_container:
                        new_cocktail_ingredients = st.text_area("Zutaten (Format: Zutat: Menge ml)", 
                                                               placeholder="Tequila: 50 ml\nTriple Sec: 25 ml\nLime Juice: 25 ml", 
                                                               height=100, key="new_cocktail_ingredients")
            
            if st.button("➕ Cocktail hinzufügen", key="add_cocktail_btn", type="primary", use_container_width=True):
                if new_cocktail_name and new_cocktail_fun and new_cocktail_ingredients:
                    try:
                        # Parse ingredients
                        ingredients_dict = {}
                        for line in new_cocktail_ingredients.strip().split('\n'):
                            if ':' in line:
                                ingredient, amount = line.split(':', 1)
                                ingredients_dict[ingredient.strip()] = amount.strip()
                        
                        if ingredients_dict:
                            # Create new cocktail
                            new_cocktail = {
                                "normal_name": new_cocktail_name.strip(),
                                "fun_name": new_cocktail_fun.strip(),
                                "ingredients": ingredients_dict
                            }
                            
                            # Add to cocktails
                            cocktail_data["cocktails"].append(new_cocktail)
                            if _write_cocktails(cocktail_data):
                                st.success(f"✅ Cocktail '{new_cocktail_name}' erfolgreich hinzugefügt!")
                                
                                # Generate image for new cocktail
                                with st.spinner("Generiere Bild für neuen Cocktail..."):
                                    api_key = st.session_state.get("openai_api_key") or OPENAI_API_KEY
                                    if generate_image(new_cocktail_name, regenerate=True, ingredients=ingredients_dict, api_key=api_key):
                                        st.success("✅ Bild erfolgreich generiert!")
                                        _send_interface_refresh_signal()
                                        st.rerun()
                                    else:
                                        st.warning("⚠️ Cocktail hinzugefügt, aber Bildgenerierung fehlgeschlagen")
                                        st.rerun()
                            else:
                                st.error("❌ Fehler beim Speichern des Cocktails")
                        else:
                            st.error("❌ Bitte geben Sie gültige Zutaten ein")
                    except Exception as e:
                        st.error(f"❌ Fehler beim Hinzufügen des Cocktails: {e}")
                else:
                    st.warning("⚠️ Bitte füllen Sie alle Felder aus")
            
            st.markdown("---")
            
            # Cocktails nach Verfügbarkeit filtern
            available_cocktails, unavailable_cocktails = _filter_available_cocktails(cocktails)
            
            # Verfügbare Cocktails anzeigen
            if available_cocktails:
                st.subheader("🍹 Verfügbare Cocktails")
                for c in available_cocktails:
                    fun = c.get("fun_name", "Cocktail")
                    norm = c.get("normal_name", "cocktail")
                    safe_c = _safe_name(norm)
                    
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{fun}** ({norm})")
                    with col2:
                        st.success("✅ Verfügbar")
                    
                    # Bild anzeigen
                    path = Path(get_cocktail_image_path(c))
                    if path.exists():
                        # Bytes + Cache-Buster mit zusätzlichem Timestamp
                        img_bytes = path.read_bytes()
                        cache_timestamp = _cache_buster(path)
                        # Füge Session State Timestamp hinzu für zusätzlichen Cache-Bust
                        session_timestamp = st.session_state.get("image_update_timestamp", 0)
                        st.image(img_bytes, width=300, caption=f"updated@{cache_timestamp}@{session_timestamp}")
                    else:
                        st.markdown('<p style="text-align: center;">Image not found.</p>', unsafe_allow_html=True)
                    
                    # Buttons
                    b1, b2, b3, b4, b5 = st.columns([1, 1, 1, 1, 1.2])
                    with b1:
                        if st.button("View", key=f"view_{safe_c}", use_container_width=True):
                            st.session_state.selected_cocktail = safe_c
                            st.rerun()
                    with b2:
                        if st.button("Pour", key=f"pour_{safe_c}", use_container_width=True):
                            note = st.info(f"Pouring a single serving of {norm} ...")
                            try:
                                executor_watcher = controller.make_drink(c, single_or_double="single")
                                while not executor_watcher.done():
                                    pass
                                
                                # Nach dem Cocktail-Zubereiten: Flaschen-Status synchronisieren
                                # WICHTIG: Nur die Konfiguration neu laden, NICHT refresh_bottles_from_pumps aufrufen
                                # da das die verbrauchten Mengen überschreiben würde
                                bottle_monitor.reload_config_from_file()
                                
                                # Session State für UI-Update setzen
                                st.session_state.cocktail_just_made = True
                                st.session_state.last_bottle_update = 0
                                st.session_state.bottle_update_timestamp = time.time()
                                
                                # Sofortiges Rerun ohne Nachrichten
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"Error while pouring: {e}")
                    with b3:
                        if st.button("Delete", key=f"delete_{safe_c}", use_container_width=True):
                            confirm = st.checkbox(f"Really delete {norm}?", key=f"confirm_delete_{safe_c}")
                            if confirm:
                                with st.spinner(f"Deleting {norm}..."):
                                    if _delete_cocktail_and_assets(safe_c):
                                        st.success(f"✅ {norm} successfully deleted!")
                                        # Force immediate interface refresh
                                        _send_interface_refresh_signal()
                                        # Update session state to force reload
                                        st.session_state.image_update_timestamp = time.time()
                                        # Rerun to refresh the list
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Failed to delete {norm}")
                    with b4:
                        if st.button("🖼️ Change Image", key=f"change_img_{safe_c}", use_container_width=True):
                            st.session_state.changing_image_for = safe_c
                            st.rerun()
                    with b5:
                        if st.button("🎨 Generate New Image", key=f"generate_img_{safe_c}", use_container_width=True):
                            with st.spinner(f"Generating new image for {fun}..."):
                                try:
                                    api_key = st.session_state.get("openai_api_key") or OPENAI_API_KEY
                                    if generate_image(norm, regenerate=True, ingredients=c.get("ingredients", {}), api_key=api_key):
                                        st.success(f"✅ New image generated for {fun}!")
                                        # Sende Interface-Refresh-Signal
                                        _send_interface_refresh_signal()
                                        # Update session state to force reload
                                        st.session_state.image_update_timestamp = time.time()
                                        # Rerun to show new image
                                        st.rerun()
                                    else:
                                        st.error(f"❌ Failed to generate new image for {fun}")
                                except Exception as e:
                                    st.error(f"❌ Error generating image: {e}")
                    
                    # Bild-Upload-Bereich (wird nur angezeigt wenn "Change Image" geklickt wurde)
                    if st.session_state.get("changing_image_for") == safe_c:
                        # Container für das Upload-Menü mit expliziter Kontrolle
                        with st.container():
                            st.markdown("---")
                            st.markdown(f"**🖼️ Change image for {fun}**")
                            
                            # Zeige aktuelles Bild
                            current_path = Path(get_cocktail_image_path(c))
                            if current_path.exists():
                                st.markdown("**Current image:**")
                                img_bytes = current_path.read_bytes()
                                st.image(img_bytes, width=200, caption="Current image")
                            
                            # Upload-Bereich in eigenem Container
                            upload_container = st.container()
                            with upload_container:
                                uploaded_image = st.file_uploader(
                                    f"📤 Upload new image for {fun} (PNG/JPG)",
                                    type=["png", "jpg", "jpeg"],
                                    key=f"image_upload_{safe_c}",
                                    help="Upload a new image to replace the current one"
                                )
                            
                            # Buttons in eigener Zeile
                            col_upload1, col_upload2, col_upload3 = st.columns([1.2, 1, 1])
                            with col_upload1:
                                if st.button("💾 Save New Image", key=f"save_img_{safe_c}", type="primary", use_container_width=True):
                                    if uploaded_image is not None:
                                        with st.spinner("Saving image..."):
                                            if _save_uploaded_logo(safe_c, uploaded_image):
                                                # Überprüfe sofort, ob das Bild verfügbar ist
                                                if _verify_image_immediately(safe_c):
                                                    # Sende Interface-Refresh-Signal
                                                    _send_interface_refresh_signal()
                                                    st.success(f"✅ Image updated for {fun}! Interface refreshed.")
                                                    # Explizit Session State zurücksetzen
                                                    st.session_state.changing_image_for = None
                                                    if f"image_upload_{safe_c}" in st.session_state:
                                                        del st.session_state[f"image_upload_{safe_c}"]
                                                    st.rerun()
                                                else:
                                                    st.error("❌ Image saved but could not be verified. Please refresh the page.")
                                            else:
                                                st.error("❌ Failed to save image.")
                                    else:
                                        st.warning("⚠️ Please select an image first.")
                            
                            with col_upload2:
                                if st.button("❌ Cancel", key=f"cancel_img_{safe_c}", use_container_width=True):
                                    # Explizit alle relevanten Session State Variablen zurücksetzen
                                    st.session_state.changing_image_for = None
                                    if f"image_upload_{safe_c}" in st.session_state:
                                        del st.session_state[f"image_upload_{safe_c}"]
                                    st.rerun()
                            
                            with col_upload3:
                                # Zusätzlicher "Clear" Button um sicherzustellen, dass alles zurückgesetzt wird
                                if st.button("🧹 Clear", key=f"clear_img_{safe_c}", use_container_width=True):
                                    # Alle relevanten Session State Variablen löschen
                                    keys_to_delete = [key for key in st.session_state.keys() if safe_c in key]
                                    for key in keys_to_delete:
                                        del st.session_state[key]
                                    st.session_state.changing_image_for = None
                                    st.rerun()
                    
                    st.markdown("---")
            
            # Nicht verfügbare Cocktails anzeigen
            if unavailable_cocktails:
                st.subheader("🚫 Nicht verfügbare Cocktails")
                st.warning("Diese Cocktails können nicht zubereitet werden, da Zutaten fehlen:")
                
                for c in unavailable_cocktails:
                    fun = c.get("fun_name", "Cocktail")
                    norm = c.get("normal_name", "cocktail")
                    missing_ingredients = c.get("missing_ingredients", [])
                    
                    st.write(f"**{fun}** ({norm})")
                    st.write("Fehlende Zutaten:")
                    for missing in missing_ingredients:
                        st.write(f"• {missing}")
                    
                    # Bild anzeigen (grau gestrichelt)
                    path = Path(get_cocktail_image_path(c))
                    if path.exists():
                        img_bytes = path.read_bytes()
                        st.image(img_bytes, width=300, caption="❌ Nicht verfügbar")
                    else:
                        st.markdown('<p style="text-align: center; color: gray;">Image not found.</p>', unsafe_allow_html=True)
                    
                    st.markdown("---")


# ================ TAB 4: Bottle Monitor ================
with tabs[3]:
    st.markdown('<h1 style="text-align: center;">🍾 Flaschen-Überwachung</h1>', unsafe_allow_html=True)
    
    # Prüfe, ob gerade ein Cocktail zubereitet wurde
    if st.session_state.get('cocktail_just_made', False):
        st.success("🍹 Cocktail erfolgreich zubereitet! Füllstände wurden aktualisiert.")
        st.session_state.cocktail_just_made = False
    
    # Automatische Aktualisierung alle 5 Sekunden ODER nach Cocktail-Zubereitung
    if 'last_bottle_update' not in st.session_state:
        st.session_state.last_bottle_update = 0
    
    if 'bottle_update_timestamp' not in st.session_state:
        st.session_state.bottle_update_timestamp = 0
    
    current_time = time.time()
    # Aktualisiere alle 5 Sekunden ODER wenn ein Cocktail zubereitet wurde
    if (current_time - st.session_state.last_bottle_update > 5 or 
        st.session_state.bottle_update_timestamp > st.session_state.last_bottle_update):
        
        # Lade Konfiguration aus Datei neu (behält verbrauchte Mengen bei)
        bottle_monitor.reload_config_from_file()
        
        st.session_state.last_bottle_update = current_time
    
    # Refresh-Button für Flaschen aus Pumpen-Konfiguration
    col_refresh, col_sync, col_info = st.columns([1, 1, 2])
    with col_refresh:
        if st.button("🔄 Flaschen aktualisieren", use_container_width=True):
            with st.spinner("Aktualisiere Flaschen aus Pumpen-Konfiguration..."):
                bottle_monitor.refresh_bottles_from_pumps()
                st.session_state.last_bottle_update = time.time()
                st.success("Flaschen aktualisiert!")
                st.rerun()
    
    with col_sync:
        if st.button("🔗 IDs synchronisieren", use_container_width=True):
            with st.spinner("Synchronisiere Flaschen-IDs mit Controller..."):
                bottle_monitor.sync_bottle_ids_with_controller()
                st.session_state.last_bottle_update = time.time()
                st.success("Flaschen-IDs synchronisiert!")
                st.rerun()
    
    with col_info:
        st.info("💡 Flaschen werden automatisch aus der Pumpen-Konfiguration im 'My Bar' Tab generiert")
    
    # Gesamtstatus anzeigen
    overall_status = bottle_monitor.get_overall_status()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Gesamt-Flaschen", overall_status["total_bottles"])
    with col2:
        st.metric("Leere Flaschen", overall_status["empty_bottles"], delta=f"-{overall_status['empty_bottles']}")
    with col3:
        st.metric("Niedrige Füllstände", overall_status["low_bottles"], delta=f"-{overall_status['low_bottles']}")
    with col4:
        st.metric("Gesamt-Füllstand", f"{overall_status['overall_percentage']}%")
    
    st.markdown("---")
    
    # Einzelne Flaschen anzeigen
    st.subheader("📊 Einzelne Flaschen")
    
    # Lade die aktuellsten Daten vor der Anzeige
    bottle_monitor.reload_config_from_file()
    bottles = bottle_monitor.get_all_bottles()
    
    # Debug-Info für Entwicklung
    if len(bottles) == 0:
        st.warning("⚠️ Keine Flaschen gefunden. Klicke auf '🔄 Flaschen aktualisieren' um sie zu laden.")
    for bottle_id, bottle in bottles.items():
        col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 2])
        
        with col1:
            st.write(f"**{bottle['name']}** ({bottle_id})")
        
        with col2:
            percentage = bottle_monitor.get_bottle_usage_percentage(bottle_id)
            st.progress(percentage / 100, text=f"{percentage:.1f}%")
        
        with col3:
            st.write(f"{bottle['current_ml']:.0f}ml")
        
        with col4:
            st.write(f"Kapazität: {bottle['capacity_ml']:.0f}ml")
            st.caption(f"Warnung: {bottle['warning_threshold_ml']:.0f}ml | Kritisch: {bottle['critical_threshold_ml']:.0f}ml")
        
        with col5:
            # Füllstand und Kapazität manuell setzen - alle Buttons untereinander
            if st.button(f"📝 Füllstand", key=f"set_{bottle_id}"):
                st.session_state[f"editing_{bottle_id}"] = True
            
            if st.button(f"📏 Kapazität", key=f"cap_{bottle_id}"):
                st.session_state[f"editing_cap_{bottle_id}"] = True
            
            if st.button(f"⚙️ Schwellen", key=f"thresh_{bottle_id}"):
                st.session_state[f"editing_thresh_{bottle_id}"] = True
            
            # Neuer Button: Flasche auffüllen (auf 100%)
            if st.button(f"🔄 Auffüllen", key=f"refill_{bottle_id}", type="primary", use_container_width=True):
                if bottle_monitor.set_bottle_level(bottle_id, bottle['capacity_ml']):
                    # Erzwinge globale Synchronisation
                    bottle_monitor.force_global_sync()
                    
                    # Session State für UI-Update setzen
                    st.session_state.last_bottle_update = 0
                    st.session_state.bottle_update_timestamp = time.time()
                    
                    st.success(f"🔄 Flasche {bottle['name']} auf {bottle['capacity_ml']:.0f}ml aufgefüllt!")
                    # UI sofort aktualisieren
                    st.rerun()
                else:
                    st.error("Fehler beim Auffüllen der Flasche")
            
            # Füllstand bearbeiten
            if st.session_state.get(f"editing_{bottle_id}", False):
                new_level = st.number_input(
                    f"Neuer Füllstand (ml)",
                    min_value=0.0,
                    max_value=float(bottle['capacity_ml']),
                    value=float(bottle['current_ml']),
                    step=50.0,
                    key=f"level_{bottle_id}"
                )
                
                # Speichern und Abbrechen Buttons untereinander
                if st.button("💾 Speichern", key=f"save_{bottle_id}", use_container_width=True):
                    if bottle_monitor.set_bottle_level(bottle_id, new_level):
                        st.success(f"Füllstand für {bottle['name']} auf {new_level}ml gesetzt")
                        st.session_state[f"editing_{bottle_id}"] = False
                        # UI sofort aktualisieren
                        st.rerun()
                    else:
                        st.error("Fehler beim Setzen des Füllstands")
                
                if st.button("❌ Abbrechen", key=f"cancel_{bottle_id}", use_container_width=True):
                    st.session_state[f"editing_{bottle_id}"] = False
                    st.rerun()
            
            # Kapazität bearbeiten
            if st.session_state.get(f"editing_cap_{bottle_id}", False):
                new_capacity = st.number_input(
                    f"Neue Kapazität (ml)",
                    min_value=100.0,
                    max_value=5000.0,
                    value=float(bottle['capacity_ml']),
                    step=100.0,
                    key=f"cap_input_{bottle_id}"
                )
                
                # Speichern und Abbrechen Buttons untereinander
                if st.button("💾 Kapazität speichern", key=f"save_cap_{bottle_id}", use_container_width=True):
                    if bottle_monitor.set_bottle_capacity(bottle_id, new_capacity):
                        st.success(f"Kapazität für {bottle['name']} auf {new_capacity}ml gesetzt")
                        st.session_state[f"editing_cap_{bottle_id}"] = False
                        st.rerun()
                    else:
                        st.error("Fehler beim Setzen der Kapazität")
                
                if st.button("❌ Abbrechen", key=f"cancel_cap_{bottle_id}", use_container_width=True):
                    st.session_state[f"editing_cap_{bottle_id}"] = False
                    st.rerun()
            
            # Warnschwellen bearbeiten
            if st.session_state.get(f"editing_thresh_{bottle_id}", False):
                col_warn, col_crit = st.columns(2)
                
                with col_warn:
                    new_warning = st.number_input(
                        f"Warnschwelle (ml)",
                        min_value=10.0,
                        max_value=float(bottle['capacity_ml'] * 0.8),
                        value=float(bottle['warning_threshold_ml']),
                        step=10.0,
                        key=f"warn_input_{bottle_id}"
                    )
                
                with col_crit:
                    new_critical = st.number_input(
                        f"Kritische Schwelle (ml)",
                        min_value=5.0,
                        max_value=float(new_warning),
                        value=float(bottle['critical_threshold_ml']),
                        step=5.0,
                        key=f"crit_input_{bottle_id}"
                    )
                
                # Speichern und Abbrechen Buttons untereinander
                if st.button("💾 Schwellen speichern", key=f"save_thresh_{bottle_id}", use_container_width=True):
                    if bottle_monitor.set_bottle_thresholds(bottle_id, new_warning, new_critical):
                        st.success(f"Warnschwellen für {bottle['name']} gesetzt")
                        st.session_state[f"editing_thresh_{bottle_id}"] = False
                        st.rerun()
                    else:
                        st.error("Fehler beim Setzen der Warnschwellen")
                
                if st.button("❌ Abbrechen", key=f"cancel_thresh_{bottle_id}", use_container_width=True):
                    st.session_state[f"editing_thresh_{bottle_id}"] = False
                    st.rerun()
        
        # Trennlinie zwischen den Flaschen
        st.markdown("---")
    
    st.markdown("---")
    
    # Telegram-Konfiguration
    st.subheader("📱 Telegram-Benachrichtigungen")
    
    if st.button("⚙️ Telegram konfigurieren", use_container_width=True):
        st.session_state["configuring_telegram"] = True
    
    if st.session_state.get("configuring_telegram", False):
        telegram_config = bottle_monitor.telegram_config
        
        col1, col2 = st.columns([1.2, 1])
        with col1:
            enabled = st.checkbox("Telegram aktivieren", value=telegram_config.get("enabled", False))
            bot_token = st.text_input("Bot Token", value=telegram_config.get("bot_token", ""), type="password")
        
        with col2:
            chat_id = st.text_input("Chat ID", value=telegram_config.get("chat_id", ""))
            
            st.write("**Benachrichtigungen:**")
            warning_notif = st.checkbox("Warnungen", value=telegram_config["notifications"].get("warning", True))
            critical_notif = st.checkbox("Kritische Warnungen", value=telegram_config["notifications"].get("critical", True))
            empty_notif = st.checkbox("Leere Flaschen", value=telegram_config["notifications"].get("empty", True))
        
        col_save_telegram, col_cancel_telegram = st.columns([1.5, 1])
        with col_save_telegram:
            if st.button("💾 Telegram-Einstellungen speichern", use_container_width=True):
                # Neue Konfiguration speichern
                new_config = {
                    "enabled": enabled,
                    "bot_token": bot_token,
                    "chat_id": chat_id,
                    "notifications": {
                        "warning": warning_notif,
                        "critical": critical_notif,
                        "empty": empty_notif
                    }
                }
                
                try:
                    with open("telegram_config.json", "w", encoding="utf-8") as f:
                        json.dump(new_config, f, indent=2, ensure_ascii=False)
                    
                    # BottleMonitor neu laden
                    bottle_monitor.telegram_config = new_config
                    st.success("Telegram-Einstellungen gespeichert!")
                    st.session_state["configuring_telegram"] = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Fehler beim Speichern: {e}")
        
        with col_cancel_telegram:
            if st.button("❌ Abbrechen", use_container_width=True):
                st.session_state["configuring_telegram"] = False
                st.rerun()
    
    # Test-Nachricht senden
    if st.button("📤 Test-Nachricht senden", use_container_width=True):
        if bottle_monitor.telegram_config.get("enabled", False):
            if bottle_monitor._send_telegram_message("🧪 Test-Nachricht von Tipsy Cocktail Mixer"):
                st.success("Test-Nachricht erfolgreich gesendet!")
            else:
                st.error("Fehler beim Senden der Test-Nachricht")
        else:
            st.warning("Telegram ist nicht aktiviert")
