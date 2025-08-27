#!/usr/bin/env python3
"""
Pump Test Tool für Tipsy Cocktail Mixer
Ermöglicht das direkte Testen und Kalibrieren einzelner Pumpen
"""

import time
import json
import logging
from pathlib import Path

# Logging konfigurieren
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Importiere Controller-Funktionen
try:
    from controller import setup_gpio, motor_forward, motor_stop, motor_reverse, MOTORS
    from settings import PERISTALTIC_PUMPS, MEMBRANE_PUMPS, get_pump_coefficient
    DEBUG = False
except ImportError as e:
    logger.warning(f"Controller-Module nicht gefunden: {e}")
    logger.info("Verwende Debug-Modus - keine echten GPIO-Befehle")
    DEBUG = True

def print_pump_info():
    """Zeigt Informationen über alle Pumpen an"""
    print("\n" + "="*60)
    print("🔧 TIPSY PUMP TEST TOOL")
    print("="*60)
    
    print("\n📊 Pumpen-Übersicht:")
    print("-" * 40)
    
    for i, (ia, ib) in enumerate(MOTORS, 1):
        pump_type = "Peristaltisch" if i in PERISTALTIC_PUMPS else "Membran"
        coefficient = get_pump_coefficient(i)
        time_for_50ml = coefficient * 50
        
        print(f"Pumpe {i:2d}: {pump_type:12s} | GPIO: ({ia:2d}, {ib:2d}) | "
              f"50ml in {time_for_50ml:5.1f}s | Koeff: {coefficient:.4f} s/ml")
    
    print("\n💡 Pumpentypen:")
    print(f"   Peristaltische Pumpen: {', '.join(map(str, PERISTALTIC_PUMPS))}")
    print(f"   Membranpumpen:         {', '.join(map(str, MEMBRANE_PUMPS))}")

def test_single_pump(pump_number, duration, direction="forward"):
    """Testet eine einzelne Pumpe"""
    if pump_number < 1 or pump_number > len(MOTORS):
        print(f"❌ Ungültige Pumpennummer: {pump_number}")
        return False
    
    pump_index = pump_number - 1
    ia, ib = MOTORS[pump_index]
    pump_type = "Peristaltisch" if pump_number in PERISTALTIC_PUMPS else "Membran"
    coefficient = get_pump_coefficient(pump_number)
    
    print(f"\n🔄 Teste Pumpe {pump_number} ({pump_type})")
    print(f"   GPIO-Pins: ({ia}, {ib})")
    print(f"   Richtung: {direction}")
    print(f"   Dauer: {duration} Sekunden")
    print(f"   Aktueller Koeffizient: {coefficient:.4f} s/ml")
    print(f"   Erwartete Menge: {duration / coefficient:.1f} ml")
    
    if not DEBUG:
        try:
            setup_gpio()
            
            print(f"   ⏱️  Starte Pumpe...")
            if direction == "forward":
                motor_forward(ia, ib)
            elif direction == "reverse":
                motor_reverse(ia, ib)
            
            time.sleep(duration)
            motor_stop(ia, ib)
            print(f"   ✅ Pumpe gestoppt")
            
        except Exception as e:
            print(f"   ❌ Fehler beim Steuern der Pumpe: {e}")
            return False
    else:
        print(f"   🔍 DEBUG-Modus: Simuliere Pumpenlauf für {duration}s")
    
    return True

def calibration_test(pump_number, test_duration=10):
    """Führt einen Kalibrierungstest durch"""
    if pump_number < 1 or pump_number > len(MOTORS):
        print(f"❌ Ungültige Pumpennummer: {pump_number}")
        return
    
    pump_type = "Peristaltisch" if pump_number in PERISTALTIC_PUMPS else "Membran"
    coefficient = get_pump_coefficient(pump_number)
    
    print(f"\n🧪 KALIBRIERUNGSTEST - Pumpe {pump_number} ({pump_type})")
    print("=" * 50)
    
    print(f"📋 Aktuelle Kalibrierung:")
    print(f"   Koeffizient: {coefficient:.4f} s/ml")
    print(f"   Zeit für 50ml: {coefficient * 50:.1f} Sekunden")
    
    print(f"\n🔬 Testdurchführung:")
    print(f"   1. Stelle einen Messbecher unter die Pumpe")
    print(f"   2. Notiere den Startstand")
    print(f"   3. Pumpe läuft {test_duration} Sekunden")
    print(f"   4. Miss den Endstand")
    print(f"   5. Berechne die gepumpte Menge")
    
    input(f"\n⏸️  Drücke ENTER, wenn der Messbecher bereit ist...")
    
    # Führe den Test durch
    if test_single_pump(pump_number, test_duration):
        print(f"\n📊 Test abgeschlossen!")
        print(f"   Bitte miss die gepumpte Menge in ml")
        
        try:
            pumped_ml = float(input("   Gepumpte Menge (ml): "))
            
            if pumped_ml > 0:
                # Berechne neue Kalibrierung
                new_coefficient = test_duration / pumped_ml
                new_time_for_50ml = new_coefficient * 50
                
                print(f"\n🧮 Neue Kalibrierung berechnet:")
                print(f"   Testdauer: {test_duration}s")
                print(f"   Gepumpte Menge: {pumped_ml}ml")
                print(f"   Neuer Koeffizient: {new_coefficient:.4f} s/ml")
                print(f"   Neue Zeit für 50ml: {new_time_for_50ml:.1f}s")
                
                # Zeige Vergleich
                old_time_for_50ml = coefficient * 50
                difference = abs(new_time_for_50ml - old_time_for_50ml)
                print(f"   Unterschied zur alten Kalibrierung: {difference:.1f}s")
                
                # Frage nach Speichern
                save = input(f"\n💾 Neue Kalibrierung speichern? (j/n): ").lower().strip()
                if save in ['j', 'ja', 'y', 'yes']:
                    save_calibration(pump_number, new_coefficient)
                else:
                    print("   Kalibrierung nicht gespeichert")
            else:
                print("   ❌ Ungültige Menge eingegeben")
                
        except ValueError:
            print("   ❌ Ungültige Eingabe")
        except KeyboardInterrupt:
            print("\n   ⏹️  Abgebrochen")

def save_calibration(pump_number, new_coefficient):
    """Speichert die neue Kalibrierung in settings.py"""
    try:
        settings_file = Path("settings.py")
        if not settings_file.exists():
            print("   ❌ settings.py nicht gefunden")
            return
        
        with open(settings_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Bestimme welcher Koeffizient aktualisiert werden soll
        if pump_number in PERISTALTIC_PUMPS:
            setting_name = "PERISTALTIC_ML_COEFFICIENT"
        elif pump_number in MEMBRANE_PUMPS:
            setting_name = "MEMBRANE_ML_COEFFICIENT"
        else:
            print("   ❌ Unbekannter Pumpentyp")
            return
        
        # Ersetze den Koeffizienten
        import re
        pattern = rf'{setting_name} = \d+\.?\d*'
        replacement = f'{setting_name} = {new_coefficient:.4f}'
        
        if re.search(pattern, content):
            content = re.sub(pattern, replacement, content)
            
            with open(settings_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"   ✅ {setting_name} auf {new_coefficient:.4f} aktualisiert")
            print(f"   💡 Starte die App neu, um die Änderungen zu übernehmen")
        else:
            print(f"   ❌ {setting_name} nicht in settings.py gefunden")
            
    except Exception as e:
        print(f"   ❌ Fehler beim Speichern: {e}")

def interactive_menu():
    """Hauptmenü für interaktive Bedienung"""
    while True:
        print("\n" + "="*60)
        print("🎯 HAUPTMENÜ")
        print("="*60)
        print("1. Pumpen-Übersicht anzeigen")
        print("2. Einzelne Pumpe testen")
        print("3. Kalibrierungstest durchführen")
        print("4. Alle Pumpen primen (10s)")
        print("5. Alle Pumpen reinigen (10s)")
        print("0. Beenden")
        
        try:
            choice = input("\nWähle eine Option (0-5): ").strip()
            
            if choice == "0":
                print("👋 Auf Wiedersehen!")
                break
            elif choice == "1":
                print_pump_info()
            elif choice == "2":
                try:
                    pump_num = int(input("Pumpennummer (1-12): "))
                    duration = float(input("Dauer in Sekunden: "))
                    direction = input("Richtung (forward/reverse) [forward]: ").strip() or "forward"
                    test_single_pump(pump_num, duration, direction)
                except ValueError:
                    print("❌ Ungültige Eingabe")
            elif choice == "3":
                try:
                    pump_num = int(input("Pumpennummer für Kalibrierung (1-12): "))
                    duration = float(input("Testdauer in Sekunden [10]: ") or "10")
                    calibration_test(pump_num, duration)
                except ValueError:
                    print("❌ Ungültige Eingabe")
            elif choice == "4":
                print("🔄 Prime alle Pumpen für 10 Sekunden...")
                for i in range(1, 13):
                    test_single_pump(i, 10)
                    time.sleep(1)  # Kurze Pause zwischen Pumpen
                print("✅ Alle Pumpen geprimt")
            elif choice == "5":
                print("🧹 Reinige alle Pumpen für 10 Sekunden...")
                for i in range(1, 13):
                    test_single_pump(i, 10, "reverse")
                    time.sleep(1)  # Kurze Pause zwischen Pumpen
                print("✅ Alle Pumpen gereinigt")
            else:
                print("❌ Ungültige Option")
                
        except KeyboardInterrupt:
            print("\n\n👋 Programm beendet")
            break
        except Exception as e:
            print(f"❌ Fehler: {e}")

def main():
    """Hauptfunktion"""
    print_pump_info()
    
    if DEBUG:
        print("\n⚠️  DEBUG-Modus aktiv - keine echten GPIO-Befehle")
        print("   Verwende dieses Tool nur auf dem Raspberry Pi für echte Tests")
    
    print("\n💡 Tipps:")
    print("   - Führe Kalibrierungstests mit verschiedenen Testdauern durch")
    print("   - Teste jede Pumpe mehrmals für konsistente Ergebnisse")
    print("   - Berücksichtige Viskosität und Temperatur der Flüssigkeiten")
    
    interactive_menu()

if __name__ == "__main__":
    main()
