#!/usr/bin/env python3
"""
Debug-Script für WiFi-Manager Probleme
Testet alle Komponenten einzeln
"""

import subprocess
import socket
import json
import time
from pathlib import Path

def test_internet_connection():
    """Teste Internet-Verbindung mit verschiedenen Methoden"""
    print("🌐 Teste Internet-Verbindung...")
    
    # Methode 1: IP-Adresse prüfen
    try:
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            ip = result.stdout.strip().split()[0]
            print(f"   IP-Adresse: {ip}")
            
            if ip.startswith('192.168.4.'):
                print("   ❌ Hotspot-IP erkannt - im Hotspot-Modus")
                return False
            else:
                print(f"   ✅ Client-IP gefunden: {ip}")
        else:
            print("   ❌ Keine IP-Adresse gefunden")
            return False
    except Exception as e:
        print(f"   ❌ IP-Test Fehler: {e}")
        return False
    
    # Methode 2: DNS-Test
    try:
        socket.setdefaulttimeout(3)
        socket.gethostbyname('google.com')
        print("   ✅ DNS-Auflösung funktioniert")
        return True
    except (socket.timeout, socket.gaierror):
        print("   ❌ DNS-Auflösung fehlgeschlagen")
    except Exception as e:
        print(f"   ❌ DNS-Test Fehler: {e}")
    
    # Methode 3: Direkte Verbindung
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(('8.8.8.8', 53))
        sock.close()
        if result == 0:
            print("   ✅ Direkte Verbindung zu 8.8.8.8:53 erfolgreich")
            return True
        else:
            print("   ❌ Direkte Verbindung fehlgeschlagen")
    except Exception as e:
        print(f"   ❌ Socket-Test Fehler: {e}")
    
    return False

def test_wifi_status():
    """Teste WLAN-Status"""
    print("\n📡 Teste WLAN-Status...")
    
    # iwgetid Test
    try:
        result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            ssid = result.stdout.strip()
            print(f"   ✅ Verbunden mit WLAN: {ssid}")
            return ssid
        else:
            print("   ❌ Nicht mit WLAN verbunden")
            return None
    except Exception as e:
        print(f"   ❌ iwgetid Fehler: {e}")
        return None

def test_known_networks():
    """Teste bekannte Netzwerke"""
    print("\n📋 Teste bekannte Netzwerke...")
    
    config_file = Path('/etc/tipsy/wifi_networks.json')
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                networks = json.load(f)
            print(f"   ✅ {len(networks)} bekannte Netzwerke gefunden:")
            for ssid in networks.keys():
                print(f"      - {ssid}")
            return networks
        except Exception as e:
            print(f"   ❌ Fehler beim Laden: {e}")
            return {}
    else:
        print("   ❌ Keine Konfigurationsdatei gefunden")
        return {}

def test_hotspot_status():
    """Teste Hotspot-Status"""
    print("\n🔥 Teste Hotspot-Status...")
    
    # NetworkManager Verbindungen
    try:
        result = subprocess.run(['nmcli', 'connection', 'show'], 
                              capture_output=True, text=True)
        if 'Prost-Hotspot' in result.stdout:
            print("   ✅ Prost-Hotspot Verbindung existiert")
            
            # Prüfe ob aktiv
            result = subprocess.run(['nmcli', 'connection', 'show', '--active'], 
                                  capture_output=True, text=True)
            if 'Prost-Hotspot' in result.stdout:
                print("   ✅ Prost-Hotspot ist aktiv")
                return True
            else:
                print("   ❌ Prost-Hotspot ist inaktiv")
                return False
        else:
            print("   ❌ Prost-Hotspot Verbindung nicht gefunden")
            return False
    except Exception as e:
        print(f"   ❌ NetworkManager Test Fehler: {e}")
        return False

def test_wifi_manager_service():
    """Teste WiFi-Manager Service"""
    print("\n⚙️  Teste WiFi-Manager Service...")
    
    try:
        result = subprocess.run(['systemctl', 'is-active', 'tipsy-wifi'], 
                              capture_output=True, text=True)
        if result.stdout.strip() == 'active':
            print("   ✅ tipsy-wifi Service läuft")
        else:
            print(f"   ❌ tipsy-wifi Service Status: {result.stdout.strip()}")
        
        # Prüfe Status-Datei
        status_file = Path('/tmp/tipsy_wifi_status.json')
        if status_file.exists():
            with open(status_file, 'r') as f:
                status = json.load(f)
            print("   📊 WiFi-Manager Status:")
            print(f"      Mode: {status.get('mode', 'unknown')}")
            print(f"      Status: {status.get('status', 'unknown')}")
            print(f"      Hotspot aktiv: {status.get('hotspot_active', False)}")
            print(f"      IP: {status.get('ip', 'keine')}")
            print(f"      SSID: {status.get('ssid', 'keine')}")
            return status
        else:
            print("   ❌ Status-Datei nicht gefunden")
            return None
            
    except Exception as e:
        print(f"   ❌ Service Test Fehler: {e}")
        return None

def test_network_scan():
    """Teste Netzwerk-Scan"""
    print("\n🔍 Teste Netzwerk-Scan...")
    
    try:
        result = subprocess.run(['iwlist', 'wlan0', 'scan'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            networks = []
            for line in lines:
                if 'ESSID:' in line and 'ESSID:""' not in line:
                    ssid = line.split('ESSID:')[1].strip().strip('"')
                    networks.append(ssid)
            
            print(f"   ✅ {len(networks)} Netzwerke gefunden:")
            for ssid in networks[:5]:  # Nur erste 5 zeigen
                print(f"      - {ssid}")
            if len(networks) > 5:
                print(f"      ... und {len(networks) - 5} weitere")
            return networks
        else:
            print("   ❌ Netzwerk-Scan fehlgeschlagen")
            return []
    except Exception as e:
        print(f"   ❌ Scan Fehler: {e}")
        return []

def test_manual_hotspot():
    """Teste manuellen Hotspot-Start"""
    print("\n🚀 Teste manuellen Hotspot-Start...")
    
    try:
        # Sende Toggle-Befehl
        command_file = Path('/tmp/tipsy_wifi_command.json')
        command = {'action': 'toggle_hotspot', 'timestamp': time.time()}
        
        with open(command_file, 'w') as f:
            json.dump(command, f)
        
        print("   ✅ Toggle-Befehl gesendet")
        print("   ⏳ Warte 10 Sekunden...")
        time.sleep(10)
        
        # Prüfe Ergebnis
        if test_hotspot_status():
            print("   ✅ Manueller Hotspot erfolgreich gestartet")
            return True
        else:
            print("   ❌ Manueller Hotspot-Start fehlgeschlagen")
            return False
            
    except Exception as e:
        print(f"   ❌ Manueller Test Fehler: {e}")
        return False

def main():
    print("🔧 WiFi-Manager Debug-Tool")
    print("=" * 50)
    
    # 1. Service-Status
    service_status = test_wifi_manager_service()
    
    # 2. Internet-Verbindung
    has_internet = test_internet_connection()
    
    # 3. WLAN-Status
    current_ssid = test_wifi_status()
    
    # 4. Bekannte Netzwerke
    known_networks = test_known_networks()
    
    # 5. Verfügbare Netzwerke
    available_networks = test_network_scan()
    
    # 6. Hotspot-Status
    hotspot_active = test_hotspot_status()
    
    print("\n" + "=" * 50)
    print("📋 ZUSAMMENFASSUNG:")
    print(f"   Internet: {'✅' if has_internet else '❌'}")
    print(f"   WLAN verbunden: {'✅ ' + current_ssid if current_ssid else '❌'}")
    print(f"   Bekannte Netzwerke: {len(known_networks)}")
    print(f"   Verfügbare Netzwerke: {len(available_networks)}")
    print(f"   Hotspot aktiv: {'✅' if hotspot_active else '❌'}")
    
    # Logik-Test
    print("\n🧠 LOGIK-ANALYSE:")
    if has_internet:
        print("   ✅ Internet verfügbar → Hotspot sollte AUS sein")
        if hotspot_active:
            print("   ⚠️  PROBLEM: Hotspot ist trotzdem aktiv!")
    else:
        print("   ❌ Kein Internet → Hotspot sollte AN sein")
        if not hotspot_active:
            print("   🚨 PROBLEM: Hotspot ist nicht aktiv!")
            print("\n🔧 EMPFOHLENE AKTIONEN:")
            print("   1. Service neu starten: sudo systemctl restart tipsy-wifi")
            print("   2. Logs prüfen: sudo journalctl -u tipsy-wifi -f")
            print("   3. Manuellen Hotspot testen:")
            
            if input("\n   Manuellen Hotspot-Test durchführen? (j/n): ").lower() == 'j':
                test_manual_hotspot()
        else:
            print("   ✅ Hotspot ist korrekt aktiv")

if __name__ == "__main__":
    main()
