# 🍹 Tipsy Hotspot Verbindung

## Hotspot-Informationen

**SSID:** `Tipsy-Setup`  
**Passwort:** `tipsy123`  
**IP-Adresse:** `192.168.4.1`

## Verbindung herstellen

1. **WLAN-Netzwerke suchen** auf deinem Gerät (Handy, Laptop, etc.)
2. **"Tipsy-Setup"** auswählen
3. **Passwort eingeben:** `tipsy123`
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
- Passwort korrekt eingeben: `tipsy123`
- WLAN-Cache auf deinem Gerät löschen
- Anderen Kanal probieren (automatisch nach Neustart)

### Setup-Seite lädt nicht
- Sicherstellen dass du mit "Tipsy-Setup" verbunden bist
- Browser-Cache leeren
- Direkt zu `192.168.4.1` navigieren
- Anderen Browser probieren

## Technische Details

- **Verschlüsselung:** WPA2-PSK
- **Kanal:** 7 (2.4 GHz)
- **DHCP-Bereich:** 192.168.4.2 - 192.168.4.20
- **DNS:** 8.8.8.8 (Google DNS)
- **Gateway:** 192.168.4.1

## Service-Status prüfen

```bash
# WiFi-Manager Status
sudo systemctl status tipsy-wifi

# Hotspot-Prozesse prüfen
ps aux | grep hostapd
ps aux | grep dnsmasq

# Logs anzeigen
sudo journalctl -u tipsy-wifi -f
tail -f /var/log/tipsy_wifi.log
```
