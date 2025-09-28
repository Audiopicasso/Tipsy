#!/bin/bash
# Setup-Script für Raspberry Pi 5 Hotspot-Funktionalität
# Behebt bekannte Probleme mit Bookworm OS und Pi 5

echo "🍻 Prost Pi 5 Hotspot Setup"
echo "=========================="

# Prüfe ob auf Pi 5 mit Bookworm
if ! grep -q "Raspberry Pi 5" /proc/cpuinfo; then
    echo "⚠️  Warnung: Dieses Script ist für Raspberry Pi 5 optimiert"
fi

# Update System
echo "📦 Aktualisiere System..."
sudo apt update
sudo apt upgrade -y

# Installiere erforderliche Pakete
echo "📦 Installiere erforderliche Pakete..."
sudo apt install -y \
    hostapd \
    dnsmasq \
    dhcpcd5 \
    iptables-persistent \
    network-manager \
    rfkill

# Aktiviere WiFi (falls deaktiviert)
echo "📡 Aktiviere WiFi..."
sudo rfkill unblock wifi
sudo rfkill unblock all

# Konfiguriere NetworkManager für Hotspot-Unterstützung
echo "⚙️  Konfiguriere NetworkManager..."

# Erstelle NetworkManager-Konfiguration für WiFi-Hotspot
sudo tee /etc/NetworkManager/conf.d/wifi-hotspot.conf > /dev/null << 'EOF'
[main]
plugins=ifupdown,keyfile

[ifupdown]
managed=false

[device]
wifi.scan-rand-mac-address=no

[connection]
wifi.powersave=2
EOF

# Stoppe und starte NetworkManager neu
echo "🔄 Starte NetworkManager neu..."
sudo systemctl stop NetworkManager
sleep 2
sudo systemctl start NetworkManager
sleep 3

# Konfiguriere hostapd für Pi 5
echo "⚙️  Konfiguriere hostapd..."
sudo tee /etc/hostapd/hostapd.conf > /dev/null << 'EOF'
# Raspberry Pi 5 optimierte hostapd-Konfiguration
interface=wlan0
driver=nl80211
ssid=Prost-Setup
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=prost123
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP CCMP
rsn_pairwise=CCMP
country_code=DE
ieee80211n=1
ieee80211d=1
EOF

# Konfiguriere dnsmasq
echo "⚙️  Konfiguriere dnsmasq..."
sudo cp /etc/dnsmasq.conf /etc/dnsmasq.conf.backup
sudo tee /etc/dnsmasq.conf > /dev/null << 'EOF'
# Prost dnsmasq-Konfiguration für Pi 5
interface=wlan0
bind-interfaces
server=8.8.8.8
server=8.8.4.4
domain-needed
bogus-priv
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
dhcp-option=3,192.168.4.1
dhcp-option=6,192.168.4.1
dhcp-authoritative
log-queries
log-dhcp
log-facility=/var/log/dnsmasq.log
EOF

# Erstelle systemd-Service für Tipsy WiFi Manager (Backend bleibt tipsy)
echo "⚙️  Konfiguriere Tipsy WiFi Service..."
sudo tee /etc/systemd/system/tipsy-wifi.service > /dev/null << 'EOF'
[Unit]
Description=Tipsy WiFi Manager
After=network.target NetworkManager.service
Wants=network.target
Requires=NetworkManager.service

[Service]
Type=simple
User=root
WorkingDirectory=/home/pi/Tipsy
ExecStart=/usr/bin/python3 /home/pi/Tipsy/wifi_manager.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Umgebungsvariablen
Environment=PYTHONPATH=/home/pi/Tipsy

[Install]
WantedBy=multi-user.target
EOF

# Aktiviere Services
echo "🔄 Aktiviere Services..."
sudo systemctl daemon-reload
sudo systemctl enable tipsy-wifi.service

# Deaktiviere Standard-hostapd und dnsmasq (werden vom WiFi-Manager gesteuert)
sudo systemctl disable hostapd
sudo systemctl disable dnsmasq
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq

# Erstelle Log-Verzeichnisse
echo "📁 Erstelle Log-Verzeichnisse..."
sudo mkdir -p /var/log
sudo touch /var/log/tipsy_wifi.log
sudo touch /var/log/dnsmasq.log
sudo chown pi:pi /var/log/tipsy_wifi.log
sudo chmod 644 /var/log/tipsy_wifi.log

# Erstelle Konfigurationsverzeichnis
sudo mkdir -p /etc/tipsy
sudo chown pi:pi /etc/tipsy

# Setze Berechtigungen für temporäre Dateien
sudo mkdir -p /tmp
sudo chmod 755 /tmp

# Teste NetworkManager-Funktionalität
echo "🧪 Teste NetworkManager..."
if command -v nmcli &> /dev/null; then
    echo "✅ nmcli verfügbar"
    nmcli --version
else
    echo "❌ nmcli nicht verfügbar"
fi

# Teste WiFi-Interface
echo "🧪 Teste WiFi-Interface..."
if ip link show wlan0 &> /dev/null; then
    echo "✅ wlan0 Interface gefunden"
    ip link show wlan0
else
    echo "❌ wlan0 Interface nicht gefunden"
fi

# Setze Berechtigungen für Web-Server
echo "🔧 Konfiguriere Web-Server Berechtigungen..."
# Erlaube non-root Prozessen Port 80 zu verwenden (falls nötig)
sudo setcap 'cap_net_bind_service=+ep' /usr/bin/python3 2>/dev/null || true

# Erstelle Test-Scripts
echo "📝 Erstelle Test-Scripts..."

# Web-Server Test-Script
cat > /home/pi/test_webserver.py << 'EOF'
#!/usr/bin/env python3
import requests
import socket
import subprocess
import time
from pathlib import Path

def test_web_server():
    print("🧪 Teste Web-Server...")
    
    # Teste verschiedene Ports
    ports = [80, 8080, 8000]
    for port in ports:
        try:
            response = requests.get(f'http://192.168.4.1:{port}/', timeout=5)
            if response.status_code == 200:
                print(f"✅ Web-Server läuft auf Port {port}")
                if 'Tipsy WLAN Setup' in response.text:
                    print("✅ Setup-Seite funktioniert korrekt")
                    return True
                else:
                    print("⚠️  Setup-Seite lädt, aber Inhalt fehlt")
        except:
            print(f"❌ Port {port} nicht erreichbar")
    
    return False

if __name__ == "__main__":
    test_web_server()
EOF

chmod +x /home/pi/test_webserver.py

# Hotspot Test-Script
cat > /home/pi/test_hotspot.py << 'EOF'
#!/usr/bin/env python3
import subprocess
import time

def test_networkmanager_hotspot():
    print("🧪 Teste NetworkManager Hotspot...")
    
    # Lösche existierende Verbindung
    subprocess.run(['sudo', 'nmcli', 'connection', 'delete', 'Test-Hotspot'], 
                   capture_output=True)
    
    # Erstelle Test-Hotspot
    cmd = [
        'sudo', 'nmcli', 'connection', 'add',
        'type', 'wifi',
        'ifname', 'wlan0',
        'con-name', 'Test-Hotspot',
        'autoconnect', 'no',
        'ssid', 'Test-Tipsy'
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ Hotspot-Verbindung erstellt")
        
        # Konfiguriere als Access Point
        config_commands = [
            ['sudo', 'nmcli', 'connection', 'modify', 'Test-Hotspot', 'wifi.mode', 'ap'],
            ['sudo', 'nmcli', 'connection', 'modify', 'Test-Hotspot', 'wifi-sec.key-mgmt', 'wpa-psk'],
            ['sudo', 'nmcli', 'connection', 'modify', 'Test-Hotspot', 'wifi-sec.psk', 'test123'],
            ['sudo', 'nmcli', 'connection', 'modify', 'Test-Hotspot', 'ipv4.method', 'shared']
        ]
        
        for cmd in config_commands:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ Konfiguration fehlgeschlagen: {result.stderr}")
                return False
        
        print("✅ NetworkManager Hotspot-Test erfolgreich")
        
        # Lösche Test-Verbindung
        subprocess.run(['sudo', 'nmcli', 'connection', 'delete', 'Test-Hotspot'], 
                       capture_output=True)
        return True
    else:
        print(f"❌ Hotspot-Erstellung fehlgeschlagen: {result.stderr}")
        return False

if __name__ == "__main__":
    test_networkmanager_hotspot()
EOF

chmod +x /home/pi/test_hotspot.py

echo ""
echo "✅ Setup abgeschlossen!"
echo ""
echo "📋 Nächste Schritte:"
echo "1. Starte den Tipsy WiFi Service: sudo systemctl start tipsy-wifi"
echo "2. Prüfe Service-Status: sudo systemctl status tipsy-wifi"
echo "3. Teste Hotspot-Funktionalität: python3 /home/pi/test_hotspot.py"
echo "4. Teste Web-Server: python3 /home/pi/test_webserver.py"
echo "5. Prüfe Logs: sudo journalctl -u tipsy-wifi -f"
echo ""
echo "🔧 Hotspot-Informationen:"
echo "   SSID: Prost-Setup"
echo "   Passwort: prost123"
echo "   IP: 192.168.4.1"
echo ""
echo "🚨 Bei Problemen:"
echo "   - Neustart: sudo reboot"
echo "   - Logs prüfen: tail -f /var/log/tipsy_wifi.log"
echo "   - NetworkManager neu starten: sudo systemctl restart NetworkManager"
