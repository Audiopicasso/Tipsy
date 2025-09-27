import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BottleMonitor:
    """Überwacht den Füllstand aller Flaschen und sendet Warnungen"""
    
    def __init__(self, config_file: str = "bottle_config.json"):
        self.config_file = Path(config_file)
        self.bottles = self._load_bottle_config()
        self.telegram_config = self._load_telegram_config()
        
    def _get_ingredient_mapping(self) -> Dict[str, str]:
        """Zentrale Ingredient Mapping Funktion für konsistente Flaschen-IDs"""
        # Importiere die normalize_bottle_id Funktion
        try:
            from controller import normalize_bottle_id
        except ImportError:
            # Fallback falls controller nicht verfügbar
            def normalize_bottle_id(name):
                return name.lower().strip().replace(' ', '_').replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
        
        # Erstelle Mapping mit normalisierten IDs
        raw_mappings = {
            "rum (weiß)": "rum (weiß)",
            "rum (weiss)": "rum (weiß)",  # Alternative Schreibweise
            "wodka": "wodka",
            "gin": "gin",
            "tequila": "tequila",
            "pfirsichlikör": "pfirsichlikör",
            "pfirsichlikoer": "pfirsichlikör",  # Alternative Schreibweise ohne Umlaut
            "grenadinensirup": "grenadinensirup",
            "limettensaft": "limettensaft",
            "orangensaft": "orangensaft",
            "tonic water": "tonic water",
            "sprite": "sprite",
            "triple sec": "triple sec",
            "cranberrysaft": "cranberrysaft",
            "cranberry juice": "cranberrysaft",
            "lime juice": "limettensaft",
            "lemon juice": "limettensaft",
            "orange juice": "orangensaft"
        }
        
        # Normalisiere alle Werte
        normalized_mappings = {}
        for key, value in raw_mappings.items():
            normalized_mappings[key] = normalize_bottle_id(value)
        
        return normalized_mappings
        
    def _load_bottle_config(self) -> Dict:
        """Lädt die Flaschen-Konfiguration basierend auf der Pumpen-Konfiguration"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Fehler beim Laden der Flaschen-Konfiguration: {e}")
        
        # Lade Pumpen-Konfiguration
        pump_config = self._load_pump_config()
        
        # Generiere Flaschen-Konfiguration basierend auf den konfigurierten Pumpen
        bottles_config = {}
        for pump_name, entry in pump_config.items():
            # Unterstützt alte und neue Formate
            if isinstance(entry, dict):
                ingredient = entry.get('ingredient', '')
            else:
                ingredient = entry
            if ingredient and str(ingredient).strip():
                # Konvertiere ingredient zu bottle_id (kleinbuchstaben, keine Leerzeichen)
                bottle_id = str(ingredient).strip().lower().replace(' ', '_')
                bottles_config[bottle_id] = {
                    "name": str(ingredient).strip(),
                    "capacity_ml": 1000,  # Standard 1L Flasche
                    "current_ml": 1000,   # Standard voll
                    "warning_threshold_ml": 200,  # Warnung bei 200ml
                    "critical_threshold_ml": 100   # Kritisch bei 100ml
                }
        
        # Falls keine Pumpen konfiguriert sind, verwende Standard-Flaschen
        if not bottles_config:
            bottles_config = {
                "gin": {"name": "Gin", "capacity_ml": 1000, "current_ml": 1000, "warning_threshold_ml": 200, "critical_threshold_ml": 100},
                "vodka": {"name": "Vodka", "capacity_ml": 1000, "current_ml": 1000, "warning_threshold_ml": 200, "critical_threshold_ml": 100},
                "rum": {"name": "Rum", "capacity_ml": 1000, "current_ml": 1000, "warning_threshold_ml": 200, "critical_threshold_ml": 100},
                "tequila": {"name": "Tequila", "capacity_ml": 1000, "current_ml": 1000, "warning_threshold_ml": 200, "critical_threshold_ml": 100},
                "whiskey": {"name": "Whiskey", "capacity_ml": 1000, "current_ml": 1000, "warning_threshold_ml": 200, "critical_threshold_ml": 100},
                "triple_sec": {"name": "Triple Sec", "capacity_ml": 1000, "current_ml": 1000, "warning_threshold_ml": 200, "critical_threshold_ml": 100},
                "lime_juice": {"name": "Lime Juice", "capacity_ml": 1000, "current_ml": 1000, "warning_threshold_ml": 200, "critical_threshold_ml": 100},
                "lemon_juice": {"name": "Lemon Juice", "capacity_ml": 1000, "current_ml": 1000, "warning_threshold_ml": 200, "critical_threshold_ml": 100},
                "simple_syrup": {"name": "Simple Syrup", "capacity_ml": 1000, "current_ml": 1000, "warning_threshold_ml": 200, "critical_threshold_ml": 100},
                "cranberry_juice": {"name": "Cranberry Juice", "capacity_ml": 1000, "current_ml": 1000, "warning_threshold_ml": 200, "critical_threshold_ml": 100},
                "orange_juice": {"name": "Orange Juice", "capacity_ml": 1000, "current_ml": 1000, "warning_threshold_ml": 200, "critical_threshold_ml": 100},
                "cola": {"name": "Cola", "capacity_ml": 1000, "current_ml": 1000, "warning_threshold_ml": 200, "critical_threshold_ml": 100}
            }
        
        config = {"bottles": bottles_config}
        
        # Speichere Standard-Konfiguration
        self._save_bottle_config(config)
        return config
    
    def _save_bottle_config(self, config: Dict):
        """Speichert die Flaschen-Konfiguration"""
        try:
            # Erstelle Backup der alten Konfiguration
            if self.config_file.exists():
                backup_file = self.config_file.with_suffix('.backup')
                import shutil
                shutil.copy2(self.config_file, backup_file)
                logger.debug(f"Backup der alten Konfiguration erstellt: {backup_file}")
            
            # Speichere neue Konfiguration
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            
            # Überprüfe, ob die Datei korrekt gespeichert wurde
            if self.config_file.exists():
                file_size = self.config_file.stat().st_size
                logger.info(f"Konfiguration erfolgreich gespeichert: {self.config_file} ({file_size} Bytes)")
                
                # Lade die gespeicherte Konfiguration zur Überprüfung
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    saved_config = json.load(f)
                
                if saved_config == config:
                    logger.info("Konfiguration erfolgreich verifiziert")
                else:
                    logger.error("Konfiguration wurde nicht korrekt gespeichert!")
                    return False
            else:
                logger.error("Konfigurationsdatei wurde nicht erstellt!")
                return False
                
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Flaschen-Konfiguration: {e}")
            return False
        
        return True
    
    def _load_telegram_config(self) -> Dict:
        """Lädt die Telegram-Konfiguration"""
        telegram_file = Path("telegram_config.json")
        if telegram_file.exists():
            try:
                with open(telegram_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Fehler beim Laden der Telegram-Konfiguration: {e}")
        
        # Standard-Telegram-Konfiguration (muss vom Benutzer konfiguriert werden)
        default_telegram = {
            "enabled": False,
            "bot_token": "",
            "chat_id": "",
            "notifications": {
                "warning": True,
                "critical": True,
                "empty": True
            }
        }
        
        # Speichere Standard-Telegram-Konfiguration
        try:
            with open(telegram_file, 'w', encoding='utf-8') as f:
                json.dump(default_telegram, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Telegram-Konfiguration: {e}")
        
        return default_telegram
    
    def _load_pump_config(self) -> Dict:
        """Lädt die Pumpen-Konfiguration aus pump_config.json"""
        pump_config_file = Path("pump_config.json")
        if pump_config_file.exists():
            try:
                with open(pump_config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Fehler beim Laden der Pumpen-Konfiguration: {e}")
        
        # Fallback: Leere Konfiguration
        return {}
    
    def refresh_bottles_from_pumps(self):
        """Aktualisiert die Flaschen-Konfiguration basierend auf der aktuellen Pumpen-Konfiguration"""
        pump_config = self._load_pump_config()
        ingredient_mapping = self._get_ingredient_mapping()
        
        # Neue Flaschen-Konfiguration generieren
        bottles_config = {}
        for pump_name, entry in pump_config.items():
            # Unterstützt alte und neue Formate
            if isinstance(entry, dict):
                ingredient = entry.get('ingredient', '')
            else:
                ingredient = entry
            if ingredient and str(ingredient).strip():
                # Verwende das zentrale Ingredient Mapping mit Normalisierung
                try:
                    from controller import normalize_bottle_id
                except ImportError:
                    # Fallback falls controller nicht verfügbar
                    def normalize_bottle_id(name):
                        return name.lower().strip().replace(' ', '_').replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
                
                ingredient_key = str(ingredient).strip().lower()
                bottle_id = ingredient_mapping.get(ingredient_key, normalize_bottle_id(ingredient))
                
                # Prüfe, ob die Flasche bereits existiert
                existing_bottle = self.bottles.get("bottles", {}).get(bottle_id)
                if existing_bottle:
                    # Behalte bestehende Werte
                    bottles_config[bottle_id] = existing_bottle
                    logger.debug(f"Flasche {bottle_id} beibehalten: {existing_bottle['current_ml']}ml")
                else:
                    # Neue Flasche mit Standard-Werten
                    bottles_config[bottle_id] = {
                        "name": ingredient.strip(),
                        "capacity_ml": 1000,
                        "current_ml": 1000,
                        "warning_threshold_ml": 200,
                        "critical_threshold_ml": 100
                    }
                    logger.debug(f"Neue Flasche {bottle_id} erstellt")
        
        # Aktualisiere die Konfiguration
        self.bottles["bottles"] = bottles_config
        self._save_bottle_config(self.bottles)
        
        logger.info(f"Flaschen-Konfiguration aktualisiert: {len(bottles_config)} Flaschen")
        return bottles_config
    
    def get_bottle_status(self, bottle_id: str) -> Optional[Dict]:
        """Gibt den aktuellen Status einer Flasche zurück"""
        return self.bottles.get("bottles", {}).get(bottle_id)
    
    def get_all_bottles(self) -> Dict:
        """Gibt alle Flaschen-Informationen zurück"""
        # WICHTIG: Lade immer die neueste Konfiguration vor der Rückgabe
        self.reload_config_from_file()
        return self.bottles.get("bottles", {})
    
    def consume_liquid(self, bottle_id: str, amount_ml: float) -> bool:
        """Verbraucht Flüssigkeit aus einer Flasche"""
        # WICHTIG: Lade immer die neueste Konfiguration vor dem Verbrauch
        self.reload_config_from_file()
        
        logger.info(f"consume_liquid aufgerufen: bottle_id='{bottle_id}', amount_ml={amount_ml}")
        logger.info(f"Verfügbare Flaschen: {list(self.bottles.get('bottles', {}).keys())}")
        
        if bottle_id not in self.bottles.get("bottles", {}):
            logger.warning(f"Flasche {bottle_id} nicht gefunden")
            return False
        
        bottle = self.bottles["bottles"][bottle_id]
        current_ml = bottle["current_ml"]
        
        logger.info(f"Flasche {bottle_id}: Aktueller Füllstand: {current_ml}ml, wird verbraucht: {amount_ml}ml")
        
        if current_ml < amount_ml:
            logger.warning(f"Flasche {bottle_id} hat nicht genug Flüssigkeit: {current_ml}ml < {amount_ml}ml")
            return False
        
        # Flüssigkeit verbrauchen
        old_ml = current_ml
        bottle["current_ml"] = max(0, current_ml - amount_ml)
        
        logger.info(f"Flasche {bottle_id}: Füllstand von {old_ml}ml auf {bottle['current_ml']}ml reduziert")
        
        # Status überprüfen und Warnungen senden
        self._check_bottle_status(bottle_id, bottle)
        
        # Konfiguration sofort speichern
        try:
            self._save_bottle_config(self.bottles)
            logger.info(f"Flasche {bottle_id}: Konfiguration erfolgreich gespeichert")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Konfiguration: {e}")
            # Rollback bei Fehler
            bottle["current_ml"] = old_ml
            return False
        
        logger.info(f"Flasche {bottle_id}: {amount_ml}ml verbraucht, verbleibend: {bottle['current_ml']}ml")
        return True
    
    def refill_bottle(self, bottle_id: str, amount_ml: float) -> bool:
        """Füllt eine Flasche auf"""
        if bottle_id not in self.bottles.get("bottles", {}):
            logger.warning(f"Flasche {bottle_id} nicht gefunden")
            return False
        
        bottle = self.bottles["bottles"][bottle_id]
        current_ml = bottle["current_ml"]
        capacity_ml = bottle["capacity_ml"]
        
        # Neue Menge berechnen (nicht über die Kapazität hinaus)
        new_amount = min(capacity_ml, current_ml + amount_ml)
        bottle["current_ml"] = new_amount
        
        # Konfiguration speichern
        self._save_bottle_config(self.bottles)
        
        logger.info(f"Flasche {bottle_id}: {amount_ml}ml aufgefüllt, aktuell: {new_amount}ml")
        
        # Telegram-Benachrichtigung senden
        if self.telegram_config.get("enabled", False):
            self._send_telegram_message(f"🔄 Flasche {bottle['name']} wurde aufgefüllt: {new_amount}ml")
        
        return True
    
    def set_bottle_level(self, bottle_id: str, level_ml: float) -> bool:
        """Setzt den Füllstand einer Flasche manuell"""
        if bottle_id not in self.bottles.get("bottles", {}):
            logger.warning(f"Flasche {bottle_id} nicht gefunden")
            return False
        
        bottle = self.bottles["bottles"][bottle_id]
        capacity_ml = bottle["capacity_ml"]
        
        # Füllstand auf gültigen Bereich beschränken
        new_level = max(0, min(capacity_ml, level_ml))
        bottle["current_ml"] = new_level
        
        # Konfiguration speichern
        self._save_bottle_config(self.bottles)
        
        # WICHTIG: Konfiguration sofort neu laden um Synchronisation zu erzwingen
        self.reload_config_from_file()
        
        logger.info(f"Flasche {bottle_id}: Füllstand auf {new_level}ml gesetzt und synchronisiert")
        
        # Status überprüfen
        self._check_bottle_status(bottle_id, bottle)
        
        return True
    
    def set_bottle_capacity(self, bottle_id: str, capacity_ml: float) -> bool:
        """Setzt die maximale Kapazität einer Flasche"""
        if bottle_id not in self.bottles.get("bottles", {}):
            logger.warning(f"Flasche {bottle_id} nicht gefunden")
            return False
        
        bottle = self.bottles["bottles"][bottle_id]
        old_capacity = bottle["capacity_ml"]
        current_ml = bottle["current_ml"]
        
        # Neue Kapazität setzen
        bottle["capacity_ml"] = capacity_ml
        
        # Füllstand anpassen, falls er über der neuen Kapazität liegt
        if current_ml > capacity_ml:
            bottle["current_ml"] = capacity_ml
            logger.info(f"Flasche {bottle_id}: Füllstand von {current_ml}ml auf {capacity_ml}ml reduziert (neue Kapazität)")
        
        # Warnschwellen proportional anpassen
        if old_capacity > 0:
            warning_ratio = bottle["warning_threshold_ml"] / old_capacity
            critical_ratio = bottle["critical_threshold_ml"] / old_capacity
            
            bottle["warning_threshold_ml"] = max(50, int(capacity_ml * warning_ratio))
            bottle["critical_threshold_ml"] = max(25, int(capacity_ml * critical_ratio))
        
        # Konfiguration speichern
        self._save_bottle_config(self.bottles)
        
        logger.info(f"Flasche {bottle_id}: Kapazität von {old_capacity}ml auf {capacity_ml}ml geändert")
        
        # Status überprüfen
        self._check_bottle_status(bottle_id, bottle)
        
        return True
    
    def set_bottle_thresholds(self, bottle_id: str, warning_threshold_ml: float, critical_threshold_ml: float) -> bool:
        """Setzt die Warnschwellen einer Flasche"""
        if bottle_id not in self.bottles.get("bottles", {}):
            logger.warning(f"Flasche {bottle_id} nicht gefunden")
            return False
        
        bottle = self.bottles["bottles"][bottle_id]
        capacity_ml = bottle["capacity_ml"]
        
        # Validierung der Schwellen
        if warning_threshold_ml >= capacity_ml:
            logger.warning(f"Warnschwelle {warning_threshold_ml}ml ist größer oder gleich der Kapazität {capacity_ml}ml")
            return False
        
        if critical_threshold_ml >= warning_threshold_ml:
            logger.warning(f"Kritische Schwelle {critical_threshold_ml}ml ist größer oder gleich der Warnschwelle {warning_threshold_ml}ml")
            return False
        
        # Schwellen setzen
        bottle["warning_threshold_ml"] = warning_threshold_ml
        bottle["critical_threshold_ml"] = critical_threshold_ml
        
        # Konfiguration speichern
        self._save_bottle_config(self.bottles)
        
        logger.info(f"Flasche {bottle_id}: Warnschwellen auf {warning_threshold_ml}ml (Warnung) und {critical_threshold_ml}ml (kritisch) gesetzt")
        
        return True
    
    def _check_bottle_status(self, bottle_id: str, bottle: Dict):
        """Überprüft den Flaschenstatus und sendet Warnungen"""
        current_ml = bottle["current_ml"]
        warning_threshold = bottle["warning_threshold_ml"]
        critical_threshold = bottle["critical_threshold_ml"]
        
        # Telegram-Benachrichtigungen senden
        if self.telegram_config.get("enabled", False):
            if current_ml <= 0:
                if self.telegram_config["notifications"].get("empty", True):
                    self._send_telegram_message(f"🚨 FLASCHE LEER: {bottle['name']} ist leer!")
            elif current_ml <= critical_threshold:
                if self.telegram_config["notifications"].get("critical", True):
                    self._send_telegram_message(f"⚠️ KRITISCHER FÜLLSTAND: {bottle['name']} hat nur noch {current_ml}ml")
            elif current_ml <= warning_threshold:
                if self.telegram_config["notifications"].get("warning", True):
                    self._send_telegram_message(f"🔶 WARNUNG: {bottle['name']} hat nur noch {current_ml}ml")
    
    def _send_telegram_message(self, message: str) -> bool:
        """Sendet eine Nachricht über Telegram"""
        if not self.telegram_config.get("enabled", False):
            return False
        
        bot_token = self.telegram_config.get("bot_token")
        chat_id = self.telegram_config.get("chat_id")
        
        if not bot_token or not chat_id:
            logger.warning("Telegram-Bot-Token oder Chat-ID nicht konfiguriert")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                logger.info(f"Telegram-Nachricht gesendet: {message}")
                return True
            else:
                logger.error(f"Fehler beim Senden der Telegram-Nachricht: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Fehler beim Senden der Telegram-Nachricht: {e}")
            return False
    
    def get_empty_bottles(self) -> List[str]:
        """Gibt eine Liste aller leeren Flaschen zurück"""
        empty_bottles = []
        for bottle_id, bottle in self.bottles.get("bottles", {}).items():
            if bottle["current_ml"] <= 0:
                empty_bottles.append(bottle_id)
        return empty_bottles
    
    def get_low_bottles(self) -> List[str]:
        """Gibt eine Liste aller Flaschen mit niedrigem Füllstand zurück"""
        low_bottles = []
        for bottle_id, bottle in self.bottles.get("bottles", {}).items():
            if bottle["current_ml"] <= bottle["warning_threshold_ml"] and bottle["current_ml"] > 0:
                low_bottles.append(bottle_id)
        return low_bottles
    
    def can_make_cocktail(self, ingredients: List[Tuple[str, float]]) -> Tuple[bool, List[str]]:
        """Überprüft, ob ein Cocktail mit den aktuellen Füllständen zubereitet werden kann"""
        ingredient_mapping = self._get_ingredient_mapping()
        missing_ingredients = []
        
        for ingredient_name, amount_ml in ingredients:
            # Verwende das Ingredient Mapping, um die korrekte Flaschen-ID zu finden
            try:
                from controller import normalize_bottle_id
            except ImportError:
                # Fallback falls controller nicht verfügbar
                def normalize_bottle_id(name):
                    return name.lower().strip().replace(' ', '_').replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
            
            ingredient_key = ingredient_name.lower().strip()
            bottle_id = ingredient_mapping.get(ingredient_key, normalize_bottle_id(ingredient_name))
            
            logger.debug(f"Checking ingredient: '{ingredient_name}' -> key: '{ingredient_key}' -> bottle_id: '{bottle_id}'")
            
            bottle = self.get_bottle_status(bottle_id)
            if not bottle:
                missing_ingredients.append(f"{ingredient_name} (Flasche '{bottle_id}' nicht gefunden)")
                continue
            
            if bottle["current_ml"] < amount_ml:
                missing_ingredients.append(f"{ingredient_name} (nur {bottle['current_ml']}ml verfügbar, {amount_ml}ml benötigt)")
        
        can_make = len(missing_ingredients) == 0
        return can_make, missing_ingredients
    
    def get_bottle_usage_percentage(self, bottle_id: str) -> float:
        """Gibt den Füllstand einer Flasche in Prozent zurück"""
        bottle = self.get_bottle_status(bottle_id)
        if not bottle:
            return 0.0
        
        return (bottle["current_ml"] / bottle["capacity_ml"]) * 100
    
    def get_overall_status(self) -> Dict:
        """Gibt eine Übersicht über alle Flaschen zurück"""
        bottles = self.get_all_bottles()
        total_bottles = len(bottles)
        empty_bottles = len(self.get_empty_bottles())
        low_bottles = len(self.get_low_bottles())
        
        total_capacity = sum(bottle["capacity_ml"] for bottle in bottles.values())
        total_current = sum(bottle["current_ml"] for bottle in bottles.values())
        overall_percentage = (total_current / total_capacity) * 100 if total_capacity > 0 else 0
        
        return {
            "total_bottles": total_bottles,
            "empty_bottles": empty_bottles,
            "low_bottles": low_bottles,
            "total_capacity_ml": total_capacity,
            "total_current_ml": total_current,
            "overall_percentage": round(overall_percentage, 1)
        }
    
    def save_config(self):
        """Speichert die aktuelle Flaschen-Konfiguration in die Datei"""
        try:
            config_data = {"bottles": self.bottles}
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Flaschen-Konfiguration gespeichert: {len(self.bottles)} Flaschen")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Flaschen-Konfiguration: {e}")
            raise

    def force_reload_config(self):
        """Lädt die Flaschen-Konfiguration neu und synchronisiert sie"""
        logger.info("Erzwinge Neuladen der Flaschen-Konfiguration")
        
        # Lade Konfiguration neu
        self.bottles = self._load_bottle_config()
        
        # Überprüfe Konsistenz
        bottles = self.get_all_bottles()
        logger.info(f"Flaschen-Konfiguration neu geladen: {len(bottles)} Flaschen")
        
        for bottle_id, bottle in bottles.items():
            logger.info(f"Flasche {bottle_id}: {bottle['current_ml']}ml / {bottle['capacity_ml']}ml")
        
        return bottles
    
    def verify_bottle_integrity(self):
        """Überprüft die Integrität aller Flaschen-Daten"""
        logger.info("Überprüfe Flaschen-Integrität")
        
        bottles = self.get_all_bottles()
        issues = []
        
        for bottle_id, bottle in bottles.items():
            # Überprüfe, ob alle erforderlichen Felder vorhanden sind
            required_fields = ["name", "capacity_ml", "current_ml", "warning_threshold_ml", "critical_threshold_ml"]
            for field in required_fields:
                if field not in bottle:
                    issues.append(f"Flasche {bottle_id}: Feld '{field}' fehlt")
            
            # Überprüfe logische Konsistenz
            if "current_ml" in bottle and "capacity_ml" in bottle:
                if bottle["current_ml"] > bottle["capacity_ml"]:
                    issues.append(f"Flasche {bottle_id}: Füllstand ({bottle['current_ml']}ml) übersteigt Kapazität ({bottle['capacity_ml']}ml)")
                
                if bottle["current_ml"] < 0:
                    issues.append(f"Flasche {bottle_id}: Negativer Füllstand ({bottle['current_ml']}ml)")
        
        if issues:
            logger.warning(f"Flaschen-Integritätsprobleme gefunden: {len(issues)}")
            for issue in issues:
                logger.warning(f"  - {issue}")
        else:
            logger.info("Alle Flaschen sind konsistent")
        
        return issues

    def sync_bottle_ids_with_controller(self):
        """Synchronisiert die Flaschen-IDs mit dem Controller-Mapping"""
        # Ingredient Mapping für konsistente Flaschen-IDs (muss mit Controller übereinstimmen)
        ingredient_mapping = {
            "rum (weiß)": "rum_(weiß)",
            "wodka": "wodka",
            "gin": "gin",
            "tequila": "tequila",
            "pfirsichlikör": "pfirsichlikör",
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
        
        # Erstelle eine neue Konfiguration mit den korrekten IDs
        new_bottles = {}
        existing_bottles = self.bottles.get("bottles", {})
        
        for old_id, bottle_data in existing_bottles.items():
            # Suche nach der korrekten ID basierend auf dem Namen
            bottle_name = bottle_data.get("name", "").lower().strip()
            correct_id = None
            
            # Suche nach exakter Übereinstimmung
            for ingredient, bottle_id in ingredient_mapping.items():
                if ingredient == bottle_name:
                    correct_id = bottle_id
                    break
            
            # Falls keine exakte Übereinstimmung, verwende den alten Namen
            if not correct_id:
                correct_id = bottle_name.replace(' ', '_')
            
            # Verwende die korrekte ID
            new_bottles[correct_id] = bottle_data
            logger.info(f"Flasche {old_id} -> {correct_id} synchronisiert")
        
        # Aktualisiere die Konfiguration
        self.bottles["bottles"] = new_bottles
        self._save_bottle_config(self.bottles)
        
        logger.info(f"Flaschen-IDs synchronisiert: {len(new_bottles)} Flaschen")
        return new_bottles

    def reload_config_from_file(self):
        """Lädt die Konfiguration aus der Datei neu"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.bottles = json.load(f)
                logger.info("Konfiguration aus Datei neu geladen")
                return True
            else:
                logger.warning("Konfigurationsdatei existiert nicht")
                return False
        except Exception as e:
            logger.error(f"Fehler beim Neuladen der Konfiguration: {e}")
            return False

    def force_global_sync(self):
        """Erzwingt eine globale Synchronisation aller Instanzen"""
        # Speichere die aktuelle Konfiguration
        self._save_bottle_config(self.bottles)
        
        # Lade sie sofort wieder neu
        self.reload_config_from_file()
        
        logger.info("Globale Synchronisation erzwungen")
        return True

# Globale Instanz für einfachen Zugriff
bottle_monitor = BottleMonitor()
