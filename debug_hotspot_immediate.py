#!/usr/bin/env python3
"""
Sofort-Debug für Hotspot-Problem
Testet warum Hotspot nicht automatisch startet
"""

import subprocess
import socket
import json
import time
from pathlib import Path

def check_current_status():
    """Prüfe aktuellen Status"""
    print("🔍 Aktueller Status:")
    
    # 1. Internet-Verbindung
    try:
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            ip = result.stdout.strip().split()[0]
            print(f"   IP-Adresse: {ip}")
            
            if ip.startswith('192.168.4.'):
                print("   🔥 Hotspot-IP erkannt - im Hotspot-Modus")
                return 'hotspot'
            else:
                print(f"   🌐 Client-IP: {ip}")
                
                # Teste Internet
                try:
                    socket.setdefaulttimeout(3)
                    socket.gethostbyname('google.com')
                    print("   ✅ Internet verfügbar")
                    return 'internet'
                except:
                    print("   ❌ Kein Internet trotz IP")
                    return 'no_internet'
        else:
            print("   ❌ Keine IP-Adresse")
            return 'no_ip'
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
        return 'error'

def check_wifi_manager_service():
    """Prüfe WiFi-Manager Service"""
    print("\n⚙️  WiFi-Manager Service:")
    
    try:
        # Service Status
        result = subprocess.run(['systemctl', 'is-active', 'tipsy-wifi'], 
                              capture_output=True, text=True)
        print(f"   Status: {result.stdout.strip()}")
        
        if result.stdout.strip() != 'active':
            print("   🚨 Service ist nicht aktiv!")
            return False
        
        # Letzte Logs
        result = subprocess.run(['journalctl', '-u', 'tipsy-wifi', '--no-pager', '-n', '10'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("   📋 Letzte 10 Log-Einträge:")
            for line in result.stdout.split('\n')[-10:]:
                if line.strip():
                    print(f"      {line}")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
        return False

def check_known_networks():
    """Prüfe bekannte Netzwerke"""
    print("\n📋 Bekannte Netzwerke:")
    
    config_file = Path('/etc/tipsy/wifi_networks.json')
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                networks = json.load(f)
            print(f"   ✅ {len(networks)} bekannte Netzwerke:")
            for ssid in networks.keys():
                print(f"      - {ssid}")
            return networks
        except Exception as e:
            print(f"   ❌ Fehler beim Laden: {e}")
            return {}
    else:
        print("   ❌ Keine Konfigurationsdatei gefunden")
        return {}

def check_available_networks():
    """Prüfe verfügbare Netzwerke"""
    print("\n🔍 Verfügbare Netzwerke:")
    
    try:
        result = subprocess.run(['iwlist', 'wlan0', 'scan'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            networks = []
            lines = result.stdout.split('\n')
            for line in lines:
                if 'ESSID:' in line and 'ESSID:""' not in line:
                    ssid = line.split('ESSID:')[1].strip().strip('"')
                    if ssid:
                        networks.append(ssid)
            
            print(f"   ✅ {len(networks)} Netzwerke gefunden:")
            for ssid in networks[:10]:  # Nur erste 10
                print(f"      - {ssid}")
            return networks
        else:
            print(f"   ❌ Scan fehlgeschlagen: {result.stderr}")
            return []
    except Exception as e:
        print(f"   ❌ Scan Fehler: {e}")
        return []

def check_hotspot_capability():
    """Prüfe Hotspot-Fähigkeiten"""
    print("\n🔥 Hotspot-Fähigkeiten:")
    
    # NetworkManager
    try:
        result = subprocess.run(['which', 'nmcli'], capture_output=True)
        if result.returncode == 0:
            print("   ✅ NetworkManager verfügbar")
            
            # Prüfe wlan0
            result = subprocess.run(['nmcli', 'device', 'status'], 
                                  capture_output=True, text=True)
            if 'wlan0' in result.stdout:
                print("   ✅ wlan0 Interface gefunden")
            else:
                print("   ❌ wlan0 Interface nicht gefunden")
        else:
            print("   ❌ NetworkManager nicht verfügbar")
    except Exception as e:
        print(f"   ❌ NetworkManager Test Fehler: {e}")
    
    # Legacy Tools
    for tool in ['hostapd', 'dnsmasq']:
        try:
            result = subprocess.run(['which', tool], capture_output=True)
            if result.returncode == 0:
                print(f"   ✅ {tool} verfügbar")
            else:
                print(f"   ❌ {tool} nicht verfügbar")
        except:
            print(f"   ❌ {tool} nicht verfügbar")

def force_hotspot_test():
    """Teste manuellen Hotspot-Start"""
    print("\n🚀 Teste manuellen Hotspot-Start:")
    
    try:
        # Sende Toggle-Befehl
        command_file = Path('/tmp/tipsy_wifi_command.json')
        command = {'action': 'toggle_hotspot', 'timestamp': time.time()}
        
        with open(command_file, 'w') as f:
            json.dump(command, f)
        
        print("   ✅ Toggle-Befehl gesendet")
        print("   ⏳ Warte 30 Sekunden...")
        
        for i in range(30):
            time.sleep(1)
            if i % 5 == 0:
                print(f"      {30-i} Sekunden verbleibend...")
        
        # Prüfe Ergebnis
        status = check_current_status()
        if status == 'hotspot':
            print("   ✅ Manueller Hotspot erfolgreich!")
            return True
        else:
            print("   ❌ Manueller Hotspot fehlgeschlagen")
            return False
            
    except Exception as e:
        print(f"   ❌ Fehler: {e}")
        return False

def main():
    print("🚨 Hotspot-Problem Debug")
    print("=" * 50)
    
    # 1. Aktueller Status
    current_status = check_current_status()
    
    # 2. Service Status
    service_ok = check_wifi_manager_service()
    
    # 3. Bekannte Netzwerke
    known_networks = check_known_networks()
    
    # 4. Verfügbare Netzwerke
    available_networks = check_available_networks()
    
    # 5. Hotspot-Fähigkeiten
    check_hotspot_capability()
    
    print("\n" + "=" * 50)
    print("📋 DIAGNOSE:")
    
    if current_status == 'hotspot':
        print("✅ Hotspot läuft bereits!")
    elif current_status == 'internet':
        print("✅ Internet verfügbar - Hotspot nicht nötig")
    elif not service_ok:
        print("🚨 PROBLEM: WiFi-Manager Service läuft nicht!")
        print("   Lösung: sudo systemctl restart tipsy-wifi")
    elif current_status in ['no_internet', 'no_ip']:
        print("🚨 PROBLEM: Kein Internet, aber auch kein Hotspot!")
        
        # Prüfe ob bekannte Netzwerke verfügbar sind
        if known_networks and available_networks:
            common = set(known_networks.keys()) & set(available_networks)
            if common:
                print(f"   Bekannte Netzwerke verfügbar: {list(common)}")
                print("   → WiFi-Manager sollte diese versuchen")
            else:
                print("   Keine bekannten Netzwerke verfügbar")
                print("   → Hotspot sollte starten!")
        
        print("\n🔧 EMPFOHLENE AKTIONEN:")
        print("   1. Service neu starten: sudo systemctl restart tipsy-wifi")
        print("   2. Neue Version aktivieren: cp wifi_manager_fixed.py wifi_manager.py")
        print("   3. Logs verfolgen: sudo journalctl -u tipsy-wifi -f")
        
        if input("\n   Manuellen Hotspot-Test durchführen? (j/n): ").lower() == 'j':
            force_hotspot_test()

if __name__ == "__main__":
    main()
