# 🍹 Tipsy WiFi Manager

Automatisches WLAN-Setup mit Hotspot-Fallback für den Tipsy Cocktail Mixer.

## 🎯 Problem gelöst

Wenn du mit dem Tipsy auf eine Party kommst, war das Gerät noch nie mit dem dortigen WLAN verbunden. Der WiFi Manager löst dieses Problem elegant:

1. **Automatische Erkennung**: Beim Boot versucht der Pi sich mit bekannten WLANs zu verbinden
2. **Hotspot-Fallback**: Wenn kein bekanntes WLAN gefunden wird, startet automatisch ein Hotspot
3. **Einfache Konfiguration**: Über eine Web-Oberfläche kannst du neue WLANs hinzufügen
4. **Nahtloser Wechsel**: Nach erfolgreicher Konfiguration wechselt das Gerät automatisch ins Zielnetzwerk

## 🚀 Installation

### 1. Dateien auf den Pi kopieren
```bash
# Kopiere alle WiFi-Manager Dateien in das Tipsy-Verzeichnis
scp wifi_manager.py pi@tipsy-pi:/home/pi/Documents/3D\ Drucker/Tipsy\ Cocktail\ Mixer/Software/Tipsy/Tipsy/
scp tipsy-wifi.service pi@tipsy-pi:/home/pi/Documents/3D\ Drucker/Tipsy\ Cocktail\ Mixer/Software/Tipsy/Tipsy/
scp install_wifi_manager.sh pi@tipsy-pi:/home/pi/Documents/3D\ Drucker/Tipsy\ Cocktail\ Mixer/Software/Tipsy/Tipsy/
```

### 2. Installation ausführen
```bash
# Auf dem Pi:
cd /home/pi/Documents/3D\ Drucker/Tipsy\ Cocktail\ Mixer/Software/Tipsy/Tipsy/
chmod +x install_wifi_manager.sh
sudo ./install_wifi_manager.sh
```

### 3. System neu starten
```bash
sudo reboot
```

## 📱 Verwendung

### Erste Einrichtung / Neue Party
1. **Boot**: Pi startet und sucht nach bekannten WLANs
2. **Hotspot**: Wenn keins gefunden wird, startet Hotspot "Tipsy-Setup"
3. **Verbinden**: Verbinde dein Smartphone mit "Tipsy-Setup" (Passwort: `cocktail123`)
4. **Konfiguration**: Öffne `http://192.168.4.1` im Browser
5. **WLAN auswählen**: Wähle das Party-WLAN aus der Liste
6. **Passwort eingeben**: Gib das WLAN-Passwort ein
7. **Verbinden**: Klicke "Verbinden" - der Pi wechselt automatisch ins neue Netzwerk
8. **Fertig**: Streamlit ist jetzt über die neue IP erreichbar

### Interface-Integration
- **QR-Code**: Zeigt automatisch die richtige URL (Setup oder Streamlit)
- **Pull-up Menü**: Zeigt aktuellen WiFi-Status und IP-Adresse
- **Farbcodierung**: 
  - 🟢 Grün = Verbunden mit WLAN
  - 🟠 Orange = Hotspot aktiv (Setup-Modus)
  - 🔴 Rot = Keine Verbindung

## 🔧 Technische Details

### Dateien
- `wifi_manager.py` - Hauptscript für WLAN-Management
- `tipsy-wifi.service` - Systemd Service für automatischen Start
- `install_wifi_manager.sh` - Installationsskript
- `/etc/tipsy/wifi_networks.json` - Gespeicherte WLAN-Netzwerke
- `/tmp/tipsy_wifi_status.json` - Aktueller Status für Interface

### Service-Befehle
```bash
# Status prüfen
sudo systemctl status tipsy-wifi

# Logs anzeigen
sudo journalctl -u tipsy-wifi -f

# Service neu starten
sudo systemctl restart tipsy-wifi

# Service stoppen/starten
sudo systemctl stop tipsy-wifi
sudo systemctl start tipsy-wifi
```

### Hotspot-Konfiguration
- **SSID**: Tipsy-Setup
- **Passwort**: cocktail123
- **IP-Bereich**: 192.168.4.1 - 192.168.4.20
- **Setup-URL**: http://192.168.4.1

## 🛠️ Fehlerbehebung

### Hotspot startet nicht
```bash
# Prüfe ob hostapd und dnsmasq installiert sind
sudo apt install hostapd dnsmasq

# Prüfe Service-Status
sudo systemctl status tipsy-wifi
```

### Web-Interface nicht erreichbar
```bash
# Prüfe ob Port 80 frei ist
sudo netstat -tlnp | grep :80

# Prüfe WiFi-Manager Logs
sudo journalctl -u tipsy-wifi -n 50
```

### WLAN-Verbindung schlägt fehl
```bash
# Prüfe verfügbare Netzwerke
sudo iwlist wlan0 scan | grep ESSID

# Prüfe wpa_supplicant
sudo wpa_cli status
```

## 🔄 Workflow-Beispiel

### Szenario: Party bei Freunden
1. **Transport**: Tipsy im Auto, noch mit Heimnetz-Konfiguration
2. **Ankunft**: Pi bootet, findet Heimnetz nicht
3. **Automatisch**: Hotspot "Tipsy-Setup" startet nach 30 Sekunden
4. **Setup**: Du verbindest dein Handy mit Hotspot
5. **Konfiguration**: Öffnest http://192.168.4.1, wählst "FriendsWiFi"
6. **Eingabe**: Gibst Passwort ein, klickst "Verbinden"
7. **Wechsel**: Pi verbindet sich mit FriendsWiFi, Hotspot stoppt
8. **Bereit**: Interface zeigt neue IP, QR-Code für Streamlit-Zugang
9. **Party**: Alle können über QR-Code auf Cocktail-App zugreifen

### Nächste Party
- Pi erkennt "FriendsWiFi" automatisch und verbindet sich
- Kein Setup mehr nötig!

## 🎉 Vorteile

✅ **Plug & Play**: Funktioniert überall ohne manuelle Konfiguration  
✅ **Benutzerfreundlich**: Einfache Web-Oberfläche für WLAN-Setup  
✅ **Automatisch**: Merkt sich alle konfigurierten Netzwerke  
✅ **Robust**: Fallback auf Hotspot wenn keine Verbindung möglich  
✅ **Integriert**: Nahtlose Integration ins bestehende Interface  
✅ **Professionell**: Wie bei kommerziellen IoT-Geräten  

Das macht den Tipsy zu einem echten "Party-ready" Gerät! 🎊
