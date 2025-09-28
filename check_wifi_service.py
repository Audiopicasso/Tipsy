#!/usr/bin/env python3
"""
Test-Script um zu prüfen ob der WiFi-Manager Service läuft
und die Kommunikation funktioniert
"""

import json
import time
from pathlib import Path

def check_wifi_status():
    """Prüfe WiFi-Status"""
    status_file = Path('/tmp/tipsy_wifi_status.json')
    if status_file.exists():
        try:
            with open(status_file, 'r') as f:
                status = json.load(f)
            print("✅ WiFi-Status gefunden:")
            print(f"   Modus: {status.get('mode', 'unknown')}")
            print(f"   Status: {status.get('status', 'unknown')}")
            print(f"   IP: {status.get('ip', 'keine')}")
            print(f"   SSID: {status.get('ssid', 'keine')}")
            print(f"   Hotspot aktiv: {status.get('hotspot_active', False)}")
            print(f"   Manueller Hotspot: {status.get('manual_hotspot_requested', False)}")
            return True
        except Exception as e:
            print(f"❌ Fehler beim Lesen der Status-Datei: {e}")
            return False
    else:
        print("❌ WiFi-Status-Datei nicht gefunden")
        return False

def test_hotspot_toggle():
    """Teste Hotspot-Toggle Befehl"""
    print("\n🔄 Teste Hotspot-Toggle...")
    
    command_file = Path('/tmp/tipsy_wifi_command.json')
    command = {'action': 'toggle_hotspot', 'timestamp': time.time()}
    
    try:
        with open(command_file, 'w') as f:
            json.dump(command, f)
        print("✅ Toggle-Befehl gesendet")
        
        # Warte und prüfe ob Befehl verarbeitet wurde
        time.sleep(2)
        if not command_file.exists():
            print("✅ Befehl wurde vom WiFi-Manager verarbeitet")
            return True
        else:
            print("❌ Befehl wurde nicht verarbeitet (Datei existiert noch)")
            return False
            
    except Exception as e:
        print(f"❌ Fehler beim Senden des Befehls: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Tipsy WiFi-Manager Service Test")
    print("=" * 40)
    
    # Prüfe Status
    status_ok = check_wifi_status()
    
    if status_ok:
        # Teste Toggle
        toggle_ok = test_hotspot_toggle()
        
        # Warte und prüfe Status erneut
        print("\n⏳ Warte 3 Sekunden und prüfe Status erneut...")
        time.sleep(3)
        check_wifi_status()
        
        if toggle_ok:
            print("\n✅ WiFi-Manager Service funktioniert korrekt!")
        else:
            print("\n⚠️  WiFi-Manager läuft, aber Toggle funktioniert nicht")
    else:
        print("\n❌ WiFi-Manager Service läuft nicht oder Status-Datei fehlt")
        print("   Starte den Service mit: sudo systemctl start tipsy-wifi")
        print("   Prüfe Service-Status: sudo systemctl status tipsy-wifi")
        print("   Logs anzeigen: sudo journalctl -u tipsy-wifi -f")
    
    print("\n📋 Hotspot-Informationen:")
    print("   SSID: Tipsy-Setup")
    print("   Passwort: tipsy123")
    print("   Setup-URL: http://192.168.4.1")
