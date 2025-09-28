#!/usr/bin/env python3
"""
Test-Script für den Tipsy Web-Server
Testet ob der Web-Server auf dem Hotspot erreichbar ist
"""

import requests
import socket
import subprocess
import time
from pathlib import Path

def test_hotspot_ip():
    """Teste ob die Hotspot-IP erreichbar ist"""
    try:
        # Teste Ping zur Hotspot-IP
        result = subprocess.run(['ping', '-c', '1', '192.168.4.1'], 
                              capture_output=True, timeout=5)
        if result.returncode == 0:
            print("✅ Hotspot-IP 192.168.4.1 ist erreichbar")
            return True
        else:
            print("❌ Hotspot-IP 192.168.4.1 ist nicht erreichbar")
            return False
    except Exception as e:
        print(f"❌ Fehler beim Ping-Test: {e}")
        return False

def test_web_server_ports():
    """Teste verschiedene Ports für den Web-Server"""
    ports_to_test = [80, 8080, 8000]
    
    for port in ports_to_test:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex(('192.168.4.1', port))
            sock.close()
            
            if result == 0:
                print(f"✅ Port {port} ist offen auf 192.168.4.1")
                return port
            else:
                print(f"❌ Port {port} ist geschlossen auf 192.168.4.1")
        except Exception as e:
            print(f"❌ Fehler beim Testen von Port {port}: {e}")
    
    return None

def test_http_request(port=80):
    """Teste HTTP-Request zur Setup-Seite"""
    urls_to_test = [
        f'http://192.168.4.1:{port}/',
        f'http://192.168.4.1:{port}/index.html',
        f'http://192.168.4.1:{port}/status'
    ]
    
    for url in urls_to_test:
        try:
            print(f"🔍 Teste {url}...")
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ {url} antwortet mit Status 200")
                print(f"   Content-Type: {response.headers.get('content-type', 'unknown')}")
                print(f"   Content-Length: {len(response.text)} Zeichen")
                
                 if 'Prost WLAN Setup' in response.text:
                    print("✅ Setup-Seite enthält erwarteten Inhalt")
                else:
                    print("⚠️  Setup-Seite enthält nicht den erwarteten Inhalt")
                    print(f"   Erste 200 Zeichen: {response.text[:200]}")
                
                return True
            else:
                print(f"❌ {url} antwortet mit Status {response.status_code}")
                
        except requests.exceptions.ConnectTimeout:
            print(f"❌ Timeout bei {url}")
        except requests.exceptions.ConnectionError:
            print(f"❌ Verbindungsfehler bei {url}")
        except Exception as e:
            print(f"❌ Fehler bei {url}: {e}")
    
    return False

def check_wifi_manager_status():
    """Prüfe WiFi-Manager Status"""
    try:
        status_file = Path('/tmp/tipsy_wifi_status.json')
        if status_file.exists():
            import json
            with open(status_file, 'r') as f:
                status = json.load(f)
            
            print("📊 WiFi-Manager Status:")
            print(f"   Modus: {status.get('mode', 'unknown')}")
            print(f"   Status: {status.get('status', 'unknown')}")
            print(f"   Hotspot aktiv: {status.get('hotspot_active', False)}")
            print(f"   IP: {status.get('ip', 'keine')}")
            print(f"   SSID: {status.get('ssid', 'keine')}")
            
            return status.get('hotspot_active', False)
        else:
            print("❌ WiFi-Manager Status-Datei nicht gefunden")
            return False
            
    except Exception as e:
        print(f"❌ Fehler beim Lesen des WiFi-Manager Status: {e}")
        return False

def check_network_interface():
    """Prüfe Netzwerk-Interface Status"""
    try:
        # Prüfe wlan0 Interface
        result = subprocess.run(['ip', 'addr', 'show', 'wlan0'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("📡 wlan0 Interface Status:")
            lines = result.stdout.split('\n')
            for line in lines:
                if '192.168.4.1' in line:
                    print(f"✅ Hotspot-IP gefunden: {line.strip()}")
                elif 'state UP' in line:
                    print(f"✅ Interface ist aktiv: {line.strip()}")
        else:
            print("❌ Konnte wlan0 Interface nicht abfragen")
            
    except Exception as e:
        print(f"❌ Fehler beim Prüfen des Netzwerk-Interface: {e}")

def main():
    print("🧪 Prost Web-Server Test")
    print("=" * 40)
    
    # 1. Prüfe WiFi-Manager Status
    hotspot_active = check_wifi_manager_status()
    
    if not hotspot_active:
        print("\n⚠️  Hotspot ist nicht aktiv. Starte zuerst den Hotspot!")
        return
    
    print("\n" + "=" * 40)
    
    # 2. Prüfe Netzwerk-Interface
    check_network_interface()
    
    print("\n" + "=" * 40)
    
    # 3. Teste Hotspot-IP Erreichbarkeit
    if not test_hotspot_ip():
        print("\n❌ Hotspot-IP nicht erreichbar - weitere Tests übersprungen")
        return
    
    print("\n" + "=" * 40)
    
    # 4. Teste Web-Server Ports
    open_port = test_web_server_ports()
    
    if open_port is None:
        print("\n❌ Kein offener Web-Server Port gefunden")
        print("\n🔧 Mögliche Lösungen:")
        print("   1. Prüfe ob WiFi-Manager läuft: sudo systemctl status tipsy-wifi")
        print("   2. Prüfe Logs: sudo journalctl -u tipsy-wifi -f")
        print("   3. Starte Service neu: sudo systemctl restart tipsy-wifi")
        return
    
    print("\n" + "=" * 40)
    
    # 5. Teste HTTP-Requests
    if test_http_request(open_port):
        print("\n✅ Web-Server funktioniert korrekt!")
        print(f"\n🌐 Setup-Seite erreichbar unter:")
        print(f"   http://192.168.4.1:{open_port}/")
    else:
        print("\n❌ Web-Server antwortet nicht korrekt")
        print("\n🔧 Mögliche Lösungen:")
        print("   1. Prüfe Web-Server Logs in /var/log/tipsy_wifi.log")
        print("   2. Teste manuell: curl http://192.168.4.1/")
        print("   3. Prüfe Firewall: sudo ufw status")

if __name__ == "__main__":
    main()
