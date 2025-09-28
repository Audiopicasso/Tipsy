# 🍻 Prost Hotspot Verbindung (Raspberry Pi 5 Optimiert)

## ⚠️ Wichtiger Hinweis für Raspberry Pi 5

Der Raspberry Pi 5 mit Bookworm OS hat bekannte Probleme mit traditionellen Hotspot-Lösungen. Diese Implementation verwendet eine **moderne NetworkManager-basierte Lösung** mit automatischem Fallback.

## Hotspot-Informationen

**SSID:** `Prost-Setup`  
**Passwort:** `prost123`  
**IP-Adresse:** `192.168.4.1`  
**Verschlüsselung:** WPA2-PSK

## Verbindung herstellen

1. **WLAN-Netzwerke suchen** auf deinem Gerät (Handy, Laptop, etc.)
2. **"Prost-Setup"** auswählen
3. **Passwort eingeben:** `prost123`
4. **Warten** bis Verbindung hergestellt ist
5. **Browser öffnen** und zu `http://192.168.4.1` navigieren

## Setup-Webseite

Sobald du verbunden bist, öffnet sich automatisch die Setup-Seite oder du gehst manuell zu:
- **URL:** `http://192.168.4.1`
- **Funktion:** WLAN-Netzwerk auswählen und konfigurieren

## Hotspot aktivieren

### Automatisch
- Der Hotspot startet automatisch wenn keine WLAN-Verbindung vorhanden ist
- Nach 30 Sekunden ohne Internetverbindung wird der Hotspot gestartet

### Manuell über Interface
1. **Settings öffnen:** Vom unteren Bildschirmrand nach oben wischen
2. **"Hotspot AN" Button** drücken
3. **Warten** bis Hotspot aktiv ist (ca. 10-15 Sekunden)
4. **Mit Hotspot verbinden** wie oben beschrieben

### Hotspot deaktivieren
1. **Settings öffnen:** Vom unteren Bildschirmrand nach oben wischen  
2. **"Hotspot AUS" Button** drücken
3. **System** versucht automatisch wieder eine WLAN-Verbindung herzustellen

## Troubleshooting

### Hotspot nicht sichtbar
- Warte 15-20 Sekunden nach dem Aktivieren
- WLAN auf deinem Gerät aus- und wieder einschalten
- Näher zum Raspberry Pi gehen

### Verbindung schlägt fehl
- Passwort korrekt eingeben: `prost123`
- WLAN-Cache auf deinem Gerät löschen
- Anderen Kanal probieren (automatisch nach Neustart)

### Setup-Seite lädt nicht
- Sicherstellen dass du mit "Prost-Setup" verbunden bist
- Browser-Cache leeren
- Direkt zu `192.168.4.1` navigieren
- Anderen Browser probieren

## Technische Details

- **Verschlüsselung:** WPA2-PSK
- **Kanal:** 7 (2.4 GHz)
- **DHCP-Bereich:** 192.168.4.2 - 192.168.4.20
- **DNS:** 8.8.8.8 (Google DNS)
- **Gateway:** 192.168.4.1

## 🛠️ Setup für Raspberry Pi 5

**Vor der ersten Nutzung ausführen:**
```bash
chmod +x setup_pi5_hotspot.sh
sudo ./setup_pi5_hotspot.sh
```

## 🔧 Service-Status prüfen

```bash
# WiFi-Manager Status
sudo systemctl status tipsy-wifi

# NetworkManager Hotspot-Verbindungen
nmcli connection show
nmcli device status

# Legacy Hotspot-Prozesse prüfen (Fallback)
ps aux | grep hostapd
ps aux | grep dnsmasq

# Logs anzeigen
sudo journalctl -u tipsy-wifi -f
tail -f /var/log/tipsy_wifi.log
```

## 🧪 Hotspot-Test

```bash
# Teste NetworkManager-Funktionalität
python3 /home/pi/test_hotspot.py

# Manuelle NetworkManager-Tests
sudo nmcli connection add type wifi ifname wlan0 con-name Test-AP ssid TestAP
sudo nmcli connection modify Test-AP wifi.mode ap
sudo nmcli connection modify Test-AP wifi-sec.key-mgmt wpa-psk
sudo nmcli connection modify Test-AP wifi-sec.psk test123
sudo nmcli connection modify Test-AP ipv4.method shared
sudo nmcli connection up Test-AP
```

## 🚨 Bekannte Pi 5 Probleme & Lösungen

### Problem: Hotspot erscheint nicht
**Ursache:** NetworkManager-Konflikte mit dhcpcd  
**Lösung:** Setup-Script ausführen, NetworkManager neu starten

### Problem: Verbindung schlägt fehl
**Ursache:** Veraltete hostapd-Konfiguration  
**Lösung:** Moderne NetworkManager-Methode wird automatisch verwendet

### Problem: WLAN-Interface nicht verfügbar
**Ursache:** Interface von NetworkManager nicht verwaltet  
**Lösung:** `sudo nmcli device set wlan0 managed yes`

### Problem: Service startet nicht
**Ursache:** Fehlende Abhängigkeiten  
**Lösung:** `sudo apt install network-manager hostapd dnsmasq dhcpcd5`
