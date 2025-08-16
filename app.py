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
    if st.button("Submit"):
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

saved_config = load_saved_config()
cocktail_data = _load_cocktails()


# ===================== Tabs =====================
tabs = st.tabs(["My Bar", "Settings", "Cocktail Menu", "Add Cocktail"])


# ================ TAB 1: My Bar ================
with tabs[0]:
    st.markdown('<h1 style="text-align: center;">My Bar</h1>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center;">Enter the drink names for each pump:</p>', unsafe_allow_html=True)

    def _default_for(pump_name):
        if pump_name in saved_config:
            return saved_config[pump_name]
        return "vodka" if pump_name == "Pump 1" else ""

    pump_inputs = {}
    col1, col2 = st.columns(2)
    with col1:
        for i in range(1, 7):
            pump_name = f"Pump {i}"
            pump_inputs[pump_name] = st.text_input(pump_name, value=_default_for(pump_name))
    with col2:
        for i in range(7, 13):
            pump_name = f"Pump {i}"
            pump_inputs[pump_name] = st.text_input(pump_name, value=_default_for(pump_name))

    st.markdown('<h3 style="text-align: center;">Requests for the bartender</h3>', unsafe_allow_html=True)
    bartender_requests = st.text_area("Enter any special requests for the bartender", height=100)
    clear_cocktails = st.checkbox("Remove existing cocktails from the menu")

    if st.button("Generate Recipes"):
        pump_to_drink = {p: d for p, d in pump_inputs.items() if d.strip()}
        save_config(pump_to_drink)

        st.markdown(f'<p style="text-align: center;">Pump configuration: {pump_to_drink}</p>', unsafe_allow_html=True)

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

    st.subheader("Prime Pumps")
    if st.button("Prime Pumps"):
        st.info("Priming all pumps for 10 seconds each...")
        try:
            controller.prime_pumps(duration=10)
            st.success("Pumps primed successfully!")
        except Exception as e:
            st.error(f"Error priming pumps: {e}")

    st.subheader("Clean Pumps")
    if st.button("Clean Pumps"):
        st.info("Reversing all pumps for 10 seconds each (cleaning mode)...")
        try:
            controller.clean_pumps(duration=10)
            st.success("All pumps reversed (cleaned).")
        except Exception as e:
            st.error(f"Error cleaning pumps: {e}")

    st.subheader("Interface Control")
    if st.button("Refresh Interface"):
        st.info("Signaling interface to refresh cocktail list...")
        if _send_interface_refresh_signal():
            st.success("Interface refresh signal sent!")


# ================ TAB 3: Cocktail Menu ================
with tabs[2]:
    st.markdown('<h1 style="text-align: center;">Cocktail Menu</h1>', unsafe_allow_html=True)

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

            c1, c2, c3, c4 = st.columns(4)

            with c1:
                if st.button("Save changes", key="save_changes_btn"):
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
                if st.button("Delete cocktail", key="delete_cocktail_btn"):
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
                if st.button("🔄 Generate New Image", key="generate_detail_img_btn"):
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
                if st.button("Back to Menu", key="back_to_menu_btn"):
                    st.session_state.selected_cocktail = None
                    st.rerun()

            st.divider()
            st.markdown('<h2 style="text-align: center;">Recipe</h2>', unsafe_allow_html=True)
            recipe_adj = {}
            for ingredient, measurement in selected.get("ingredients", {}).items():
                parts = str(measurement).split()
                try:
                    default_val = float(parts[0])
                    unit = " ".join(parts[1:]) if len(parts) > 1 else ""
                except Exception:
                    default_val = 1.0
                    unit = str(measurement)
                val = st.slider(
                    f"{ingredient} ({measurement})",
                    min_value=0.0,
                    max_value=max(default_val * 4, 1.0),
                    value=default_val,
                    step=0.1
                )
                recipe_adj[ingredient] = f"{val} {unit}".strip()
            st.markdown('<h3 style="text-align: center;"><strong>Adjusted Recipe</strong></h3>', unsafe_allow_html=True)
            st.json(recipe_adj)

            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("Save Recipe", key="save_recipe_btn"):
                    data = _load_cocktails()
                    updated = False
                    for idx, cktl in enumerate(data.get("cocktails", [])):
                        if _safe_name(cktl.get("normal_name", "")) == st.session_state.selected_cocktail:
                            data["cocktails"][idx]["ingredients"] = recipe_adj
                            updated = True
                            break
                    if updated and _write_cocktails(data):
                        _send_interface_refresh_signal()
                        st.success("Recipe saved and interface refreshed!")
                    elif not updated:
                        st.error("Failed to update recipe.")
            with cc2:
                if st.button("Pour", key="pour_btn"):
                    note = st.info("Pouring a single serving...")
                    try:
                        executor_watcher = controller.make_drink(selected, single_or_double="single")
                        while not executor_watcher.done():
                            pass
                        note.empty()
                    except Exception as e:
                        st.error(f"Error while pouring: {e}")

    else:
        # GALLERY VIEW
        cocktails_list = cocktail_data.get("cocktails", [])
        if cocktails_list:
            for c in cocktails_list:
                norm = c.get("normal_name", "unknown_drink")
                fun = c.get("fun_name", norm)
                safe_c = _safe_name(norm)
                path = Path(get_cocktail_image_path(c))

                st.markdown(f'<h3 style="text-align: center;">{fun} <small>({norm})</small></h3>', unsafe_allow_html=True)
                if path.exists():
                    # Bytes + Cache-Buster mit zusätzlichem Timestamp
                    img_bytes = path.read_bytes()
                    cache_timestamp = _cache_buster(path)
                    # Füge Session State Timestamp hinzu für zusätzlichen Cache-Bust
                    session_timestamp = st.session_state.get("image_update_timestamp", 0)
                    st.image(img_bytes, width=300, caption=f"updated@{cache_timestamp}@{session_timestamp}")
                else:
                    st.markdown('<p style="text-align: center;">Image not found.</p>', unsafe_allow_html=True)

                b1, b2, b3, b4, b5 = st.columns([1, 1, 1, 1, 1])
                with b1:
                    if st.button("View", key=f"view_{safe_c}"):
                        st.session_state.selected_cocktail = safe_c
                        st.rerun()
                with b2:
                    if st.button("Pour", key=f"pour_{safe_c}"):
                        note = st.info(f"Pouring a single serving of {norm} ...")
                        try:
                            executor_watcher = controller.make_drink(c, single_or_double="single")
                            while not executor_watcher.done():
                                pass
                            note.empty()
                        except Exception as e:
                            st.error(f"Error while pouring: {e}")
                with b3:
                    if st.button("Delete", key=f"delete_{safe_c}"):
                        confirm = st.checkbox(f"Really delete {norm}?", key=f"confirm_delete_{safe_c}")
                        if confirm:
                            with st.spinner(f"Deleting {norm}..."):
                                if _delete_cocktail_and_assets(safe_c):
                                    st.success(f"✅ {norm} successfully deleted!")
                                    # Force immediate interface refresh
                                    _send_interface_refresh_signal()
                                    # Update session state to force reload
                                    st.session_state.image_update_timestamp = time.time()
                                    # Rerun to show updated cocktail list
                                    st.rerun()
                                else:
                                    st.error("❌ Failed to delete cocktail. Please try again.")
                with b4:
                    if st.button("Change Image", key=f"change_img_{safe_c}"):
                        st.session_state.changing_image_for = safe_c
                        st.rerun()
                with b5:
                    if st.button("🔄 Generate New Image", key=f"generate_img_{safe_c}"):
                        with st.spinner(f"Generating new image for {norm}..."):
                            try:
                                # Generiere ein neues Bild für diesen spezifischen Cocktail
                                api_key = st.session_state.get("openai_api_key") or OPENAI_API_KEY
                                if generate_image(norm, regenerate=True, ingredients=c.get("ingredients", {}), api_key=api_key):
                                    st.success(f"✅ New image generated for {norm}!")
                                    # Sende Interface-Refresh-Signal
                                    _send_interface_refresh_signal()
                                    # Update session state to force reload
                                    st.session_state.image_update_timestamp = time.time()
                                    # Rerun to show new image
                                    st.rerun()
                                else:
                                    st.error(f"❌ Failed to generate new image for {norm}")
                            except Exception as e:
                                st.error(f"❌ Error generating image: {e}")
                
                # Bild-Upload-Bereich (wird nur angezeigt wenn "Change Image" geklickt wurde)
                if st.session_state.get("changing_image_for") == safe_c:
                    # Debug info
                    st.info(f"Debug: changing_image_for = {st.session_state.get('changing_image_for')}, safe_c = {safe_c}")
                    st.markdown("---")
                    st.markdown(f"**🖼️ Change image for {fun}**")
                    
                    # Zeige aktuelles Bild mit Cache-Buster
                    current_path = Path(get_cocktail_image_path(c))
                    if current_path.exists():
                        st.markdown("**Current image:**")
                        img_bytes = current_path.read_bytes()
                        st.image(img_bytes, width=200, caption=f"Current image (updated@{_cache_buster(current_path)})")
                    
                    uploaded_image = st.file_uploader(
                        f"📤 Upload new image for {fun} (PNG/JPG)",
                        type=["png", "jpg", "jpeg"],
                        key=f"image_upload_{safe_c}",
                        help="Select a new image file to replace the current cocktail image"
                    )
                    
                    col_upload1, col_upload2 = st.columns(2)
                    with col_upload1:
                        if st.button("💾 Save New Image", key=f"save_img_{safe_c}", type="primary"):
                            if uploaded_image is not None:
                                with st.spinner("Saving image..."):
                                    if _save_uploaded_logo(safe_c, uploaded_image):
                                        # Überprüfe sofort, ob das Bild verfügbar ist
                                        if _verify_image_immediately(safe_c):
                                            # Sende Interface-Refresh-Signal
                                            _send_interface_refresh_signal()
                                            st.success(f"✅ Image updated for {fun}! Interface refreshed.")
                                            st.session_state.changing_image_for = None
                                            # Einfacher Rerun ohne komplexe Cache-Invalidierung
                                            st.rerun()
                                        else:
                                            st.error("❌ Image saved but not immediately available. Please refresh the page.")
                                    else:
                                        st.error("❌ Failed to save image.")
                            else:
                                st.warning("⚠️ Please select an image first.")
                    
                    with col_upload2:
                        if st.button("❌ Cancel", key=f"cancel_img_{safe_c}"):
                            st.session_state.changing_image_for = None
                            st.rerun()
        else:
            st.markdown('<p style="text-align: center;">No recipes generated yet. Please use the "My Bar" tab to generate recipes.</p>', unsafe_allow_html=True)


# ================ TAB 4: Add Cocktail ================
with tabs[3]:
    st.markdown('<h1 style="text-align: center;">Add Cocktail</h1>', unsafe_allow_html=True)
    st.markdown('<h2 style="text-align: center;">Recipe</h2>', unsafe_allow_html=True)

    recipe = {"ingredients": {}}
    recipe["normal_name"] = st.text_input("Cocktail Name")
    recipe["fun_name"] = st.text_input("Fun Name (optional)", value=recipe["normal_name"])
    upload_logo = st.file_uploader(
        "Upload cocktail image (PNG/JPG) — optional (will be saved as {safe_name}.png)",
        type=["png", "jpg", "jpeg"],
        key="add_logo"
    )

    for _, pump in enumerate(saved_config):
        ingredient = saved_config[pump]
        val = st.slider(f"{ingredient} (oz)", min_value=0.0, max_value=4.0, value=0.0, step=0.25)
        if val > 0:
            recipe["ingredients"][ingredient] = f"{val} oz".strip()

    if st.button("Save", key="add_save_btn") and recipe["normal_name"] and len(recipe["ingredients"]) > 0:
        data = _load_cocktails()
        existing = [x.get("normal_name", "") for x in data.get("cocktails", [])]
        if recipe["normal_name"] not in existing:
            api_key = st.session_state.get("openai_api_key") or OPENAI_API_KEY
            safe_new = _safe_name(recipe["normal_name"])

            if upload_logo is not None:
                ok_img = _save_uploaded_logo(safe_new, upload_logo)
                if not ok_img:
                    st.warning("Could not save uploaded image; generating one instead.")
                    generate_image(recipe["normal_name"], False, recipe["ingredients"], api_key=api_key)
            else:
                generate_image(recipe["normal_name"], False, recipe["ingredients"], api_key=api_key)

            data.setdefault("cocktails", []).append({
                "normal_name": recipe["normal_name"],
                "fun_name": recipe.get("fun_name") or recipe["normal_name"],
                "ingredients": recipe["ingredients"]
            })

            if _write_cocktails(data):
                _send_interface_refresh_signal()
                st.success("Cocktail saved and interface refresh signal sent!")
        else:
            st.error("A cocktail with this name already exists.")
