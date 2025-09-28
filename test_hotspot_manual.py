#!/usr/bin/env python3
"""
Manueller Hotspot-Test
Testet den Hotspot-Start direkt ohne WiFi-Manager
"""

import subprocess
import time
import socket

def test_networkmanager_hotspot():
    """Teste NetworkManager Hotspot direkt"""
    print("🔥 Teste NetworkManager Hotspot direkt...")
    
    try:
        # 1. Lösche existierende Verbindung
        print("   1. Lösche existierende Prost-Hotspot Verbindung...")
        subprocess.run(['sudo', 'nmcli', 'connection', 'delete', 'Prost-Hotspot'], 
                     capture_output=True)
        
        # 2. Erstelle neue Hotspot-Verbindung
        print("   2. Erstelle neue Hotspot-Verbindung...")
        cmd = [
            'sudo', 'nmcli', 'connection', 'add',
            'type', 'wifi',
            'ifname', 'wlan0',
            'con-name', 'Prost-Hotspot',
            'autoconnect', 'no',
            'ssid', 'Prost-Setup'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"   ❌ Fehler beim Erstellen: {result.stderr}")
            return False
        else:
            print("   ✅ Hotspot-Verbindung erstellt")
        
        # 3. Konfiguriere Hotspot-Einstellungen
        print("   3. Konfiguriere Hotspot-Einstellungen...")
        config_commands = [
            ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 
             'wifi.mode', 'ap'],
            ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 
             'wifi.band', 'bg'],
            ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 
             'wifi.channel', '7'],
            ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 
             'wifi-sec.key-mgmt', 'wpa-psk'],
            ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 
             'wifi-sec.psk', 'prost123'],
            ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 
             'ipv4.method', 'shared'],
            ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 
             'ipv4.addresses', '192.168.4.1/24']
        ]
        
        for cmd in config_commands:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"   ❌ Fehler bei Konfiguration {' '.join(cmd[3:])}: {result.stderr}")
                return False
        
        print("   ✅ Hotspot konfiguriert")
        
        # 4. Aktiviere Hotspot
        print("   4. Aktiviere Hotspot...")
        result = subprocess.run(['sudo', 'nmcli', 'connection', 'up', 'Prost-Hotspot'], 
                              capture_output=True, text=True)
        if result.returncode != 0:
            print(f"   ❌ Fehler beim Aktivieren: {result.stderr}")
            return False
        
        print("   ✅ Hotspot aktiviert")
        
        # 5. Warte und prüfe Status
        print("   5. Warte 10 Sekunden und prüfe Status...")
        time.sleep(10)
        
        # Prüfe IP-Adresse
        result = subprocess.run(['ip', 'addr', 'show', 'wlan0'], 
                              capture_output=True, text=True)
        if '192.168.4.1' in result.stdout:
            print("   ✅ Hotspot-IP 192.168.4.1 ist aktiv")
        else:
            print("   ❌ Hotspot-IP nicht gefunden")
            print(f"   wlan0 Status: {result.stdout}")
        
        # Prüfe NetworkManager Status
        result = subprocess.run(['nmcli', 'connection', 'show', '--active'], 
                              capture_output=True, text=True)
        if 'Prost-Hotspot' in result.stdout:
            print("   ✅ Prost-Hotspot ist aktiv in NetworkManager")
            return True
        else:
            print("   ❌ Prost-Hotspot nicht aktiv in NetworkManager")
            return False
            
    except Exception as e:
        print(f"   ❌ Fehler beim NetworkManager Test: {e}")
        return False

def test_web_server():
    """Teste ob Web-Server auf Hotspot erreichbar ist"""
    print("\n🌐 Teste Web-Server Erreichbarkeit...")
    
    # Warte kurz
    time.sleep(5)
    
    ports_to_test = [80, 8080, 8000]
    
    for port in ports_to_test:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex(('192.168.4.1', port))
            sock.close()
            
            if result == 0:
                print(f"   ✅ Port {port} ist offen auf 192.168.4.1")
                return port
            else:
                print(f"   ❌ Port {port} ist geschlossen")
        except Exception as e:
            print(f"   ❌ Fehler beim Testen von Port {port}: {e}")
    
    print("   ❌ Kein Web-Server Port gefunden")
    return None

def cleanup_hotspot():
    """Räume Hotspot auf"""
    print("\n🧹 Räume Hotspot auf...")
    
    try:
        # Stoppe Hotspot
        subprocess.run(['sudo', 'nmcli', 'connection', 'down', 'Prost-Hotspot'], 
                     capture_output=True)
        
        # Lösche Verbindung
        subprocess.run(['sudo', 'nmcli', 'connection', 'delete', 'Prost-Hotspot'], 
                     capture_output=True)
        
        print("   ✅ Hotspot aufgeräumt")
        
    except Exception as e:
        print(f"   ❌ Fehler beim Aufräumen: {e}")

def main():
    print("🧪 Manueller Hotspot-Test")
    print("=" * 40)
    
    try:
        # 1. Teste NetworkManager Hotspot
        if test_networkmanager_hotspot():
            print("\n✅ Hotspot erfolgreich gestartet!")
            
            # 2. Teste Web-Server
            open_port = test_web_server()
            if open_port:
                print(f"\n🌐 Setup-Seite sollte erreichbar sein unter:")
                print(f"   http://192.168.4.1:{open_port}/")
                print("\n📱 Teste jetzt mit deinem Handy:")
                print("   1. WLAN-Einstellungen öffnen")
                print("   2. 'Prost-Setup' auswählen")
                print("   3. Passwort 'prost123' eingeben")
                print("   4. Browser öffnen und zu http://192.168.4.1 gehen")
            
            # Warte auf Benutzereingabe
            input("\n⏳ Drücke Enter wenn du fertig mit dem Test bist...")
            
        else:
            print("\n❌ Hotspot-Start fehlgeschlagen!")
            print("\n🔧 Mögliche Probleme:")
            print("   1. NetworkManager nicht installiert: sudo apt install network-manager")
            print("   2. wlan0 Interface nicht verfügbar: ip link show")
            print("   3. Berechtigungen: Script als root ausführen")
            
    finally:
        # Aufräumen
        cleanup_hotspot()

if __name__ == "__main__":
    main()
