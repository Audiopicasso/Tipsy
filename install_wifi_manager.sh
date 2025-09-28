#!/bin/bash
# Installationsskript für Tipsy WiFi Manager

echo "🍹 Tipsy WiFi Manager Installation"
echo "=================================="

# Prüfe ob als root ausgeführt
if [ "$EUID" -ne 0 ]; then
    echo "❌ Bitte als root ausführen: sudo ./install_wifi_manager.sh"
    exit 1
fi

echo "📦 Installiere benötigte Pakete..."
apt update
apt install -y hostapd dnsmasq

echo "🔧 Konfiguriere Services..."

# Stoppe und deaktiviere Services (werden vom WiFi Manager gesteuert)
systemctl stop hostapd
systemctl stop dnsmasq
systemctl disable hostapd
systemctl disable dnsmasq

# Erstelle Konfigurationsverzeichnis
mkdir -p /etc/tipsy

# Kopiere Service-Datei
cp tipsy-wifi.service /etc/systemd/system/

# Mache WiFi Manager ausführbar
chmod +x wifi_manager.py

echo "🚀 Aktiviere Tipsy WiFi Manager Service..."
systemctl daemon-reload
systemctl enable tipsy-wifi.service

echo "📝 Erstelle Backup der originalen wpa_supplicant.conf..."
if [ -f /etc/wpa_supplicant/wpa_supplicant.conf ]; then
    cp /etc/wpa_supplicant/wpa_supplicant.conf /etc/wpa_supplicant/wpa_supplicant.conf.backup
fi

echo "🔄 Konfiguriere WLAN-Interface..."
# Stelle sicher, dass wlan0 nicht von dhcpcd verwaltet wird wenn im Hotspot-Modus
cat > /etc/dhcpcd.conf.tipsy << 'EOF'
# Tipsy WiFi Manager Konfiguration
# wlan0 wird vom WiFi Manager gesteuert
denyinterfaces wlan0
EOF

# Backup der originalen dhcpcd.conf
if [ ! -f /etc/dhcpcd.conf.original ]; then
    cp /etc/dhcpcd.conf /etc/dhcpcd.conf.original
fi

# Füge Tipsy-Konfiguration hinzu
if ! grep -q "# Tipsy WiFi Manager" /etc/dhcpcd.conf; then
    echo "" >> /etc/dhcpcd.conf
    echo "# Tipsy WiFi Manager Konfiguration" >> /etc/dhcpcd.conf
    echo "denyinterfaces wlan0" >> /etc/dhcpcd.conf
fi

echo "✅ Installation abgeschlossen!"
echo ""
echo "📋 Nächste Schritte:"
echo "1. Starte das System neu: sudo reboot"
echo "2. Der WiFi Manager startet automatisch beim Boot"
echo "3. Wenn kein bekanntes WLAN gefunden wird, startet der Hotspot 'Tipsy-Setup'"
echo "4. Verbinde dich mit dem Hotspot (Passwort: cocktail123)"
echo "5. Öffne http://192.168.4.1 im Browser für WLAN-Setup"
echo ""
echo "🔧 Service-Befehle:"
echo "   Status prüfen: sudo systemctl status tipsy-wifi"
echo "   Logs anzeigen: sudo journalctl -u tipsy-wifi -f"
echo "   Service stoppen: sudo systemctl stop tipsy-wifi"
echo "   Service starten: sudo systemctl start tipsy-wifi"
echo ""
echo "📁 Konfigurationsdateien:"
echo "   WLAN-Netzwerke: /etc/tipsy/wifi_networks.json"
echo "   Status: /tmp/tipsy_wifi_status.json"
echo "   Logs: /var/log/tipsy_wifi.log"
