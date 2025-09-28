#!/usr/bin/env python3
"""
WLAN Manager für Tipsy Cocktail Mixer
Automatisches WLAN-Setup mit Hotspot-Fallback

Funktionsweise:
1. Versucht sich mit bekannten WLANs zu verbinden
2. Wenn kein bekanntes WLAN gefunden wird, startet einen Hotspot
3. Über den Hotspot kann ein neues WLAN konfiguriert werden
4. Nach erfolgreicher Konfiguration wechselt zu Client-Modus
"""

import subprocess
import time
import json
import os
import logging
import threading
from pathlib import Path
import socket
import signal
import sys

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/tipsy_wifi.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WiFiManager:
    def __init__(self):
        self.config_file = Path('/etc/tipsy/wifi_networks.json')
        self.hotspot_active = False
        self.web_server = None
        self.current_mode = 'client'  # 'client' or 'hotspot'
        self.status_file = Path('/tmp/tipsy_wifi_status.json')
        self.manual_hotspot_requested = False  # Flag für manuell angeforderten Hotspot
        
        # Hotspot Konfiguration
        self.hotspot_ssid = "Tipsy-Setup"
        self.hotspot_password = "tipsy123"  # Einfaches Passwort für Stabilität
        self.hotspot_ip = "192.168.4.1"
        self.web_server_running = False  # Flag um mehrfache Web-Server zu vermeiden
        
        # Stelle sicher, dass Konfigurationsverzeichnis existiert
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Lade bekannte Netzwerke
        self.known_networks = self.load_known_networks()
        
    def load_known_networks(self):
        """Lade bekannte WLAN-Netzwerke aus der Konfigurationsdatei"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Fehler beim Laden der WLAN-Konfiguration: {e}")
        return {}
    
    def save_known_networks(self):
        """Speichere bekannte WLAN-Netzwerke"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.known_networks, f, indent=2)
            logger.info("WLAN-Konfiguration gespeichert")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der WLAN-Konfiguration: {e}")
    
    def update_status(self, status, message="", ip="", ssid=""):
        """Aktualisiere Status-Datei für andere Prozesse"""
        status_data = {
            'mode': self.current_mode,
            'status': status,
            'message': message,
            'ip': ip,
            'ssid': ssid,
            'hotspot_active': self.hotspot_active,
            'hotspot_ssid': self.hotspot_ssid if self.hotspot_active else "",
            'manual_hotspot_requested': self.manual_hotspot_requested,
            'timestamp': time.time()
        }
        
        try:
            with open(self.status_file, 'w') as f:
                json.dump(status_data, f, indent=2)
        except Exception as e:
            logger.error(f"Fehler beim Schreiben der Status-Datei: {e}")
    
    def request_manual_hotspot(self):
        """Fordere manuell einen Hotspot an"""
        logger.info("Manueller Hotspot angefordert")
        self.manual_hotspot_requested = True
        
        # Wenn bereits verbunden, trenne Verbindung
        if self.current_mode == 'client':
            logger.info("Trenne aktuelle WLAN-Verbindung für manuellen Hotspot")
            subprocess.run(['sudo', 'killall', 'wpa_supplicant'], capture_output=True)
            subprocess.run(['sudo', 'dhclient', '-r', 'wlan0'], capture_output=True)
        
        # Starte Hotspot
        if not self.hotspot_active:
            self.start_hotspot()
    
    def stop_manual_hotspot(self):
        """Stoppe manuell angeforderten Hotspot"""
        logger.info("Manueller Hotspot wird gestoppt")
        self.manual_hotspot_requested = False
        
        if self.hotspot_active:
            self.stop_hotspot()
            # Versuche wieder zu bekannten Netzwerken zu verbinden
            self.try_known_networks()
    
    def toggle_manual_hotspot(self):
        """Toggle zwischen manuellem Hotspot und normalem Modus"""
        if self.manual_hotspot_requested:
            self.stop_manual_hotspot()
        else:
            self.request_manual_hotspot()
    
    def scan_networks(self):
        """Scanne verfügbare WLAN-Netzwerke"""
        try:
            result = subprocess.run(['iwlist', 'wlan0', 'scan'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                networks = []
                lines = result.stdout.split('\n')
                current_network = {}
                
                for line in lines:
                    line = line.strip()
                    if 'ESSID:' in line:
                        ssid = line.split('ESSID:')[1].strip('"')
                        if ssid and ssid != '':
                            current_network['ssid'] = ssid
                    elif 'Quality=' in line:
                        # Extrahiere Signalstärke
                        try:
                            quality = line.split('Quality=')[1].split(' ')[0]
                            current_network['quality'] = quality
                        except:
                            current_network['quality'] = 'unknown'
                    elif 'Encryption key:' in line:
                        encrypted = 'on' in line.lower()
                        current_network['encrypted'] = encrypted
                        
                        # Netzwerk zur Liste hinzufügen wenn vollständig
                        if 'ssid' in current_network:
                            networks.append(current_network.copy())
                        current_network = {}
                
                return networks
            else:
                logger.error(f"WLAN-Scan fehlgeschlagen: {result.stderr}")
                return []
        except Exception as e:
            logger.error(f"Fehler beim WLAN-Scan: {e}")
            return []
    
    def connect_to_network(self, ssid, password=None):
        """Verbinde mit einem WLAN-Netzwerk"""
        try:
            logger.info(f"Versuche Verbindung zu {ssid}...")
            
            # Erstelle wpa_supplicant Konfiguration
            if password:
                auth_config = f'psk="{password}"'
            else:
                auth_config = "key_mgmt=NONE"
            
            wpa_config = f"""country=DE
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
    ssid="{ssid}"
    {auth_config}
}}
"""
            
            # Schreibe temporäre wpa_supplicant.conf
            with open('/tmp/wpa_supplicant_temp.conf', 'w') as f:
                f.write(wpa_config)
            
            # Stoppe aktuellen wpa_supplicant
            subprocess.run(['sudo', 'killall', 'wpa_supplicant'], 
                         capture_output=True)
            time.sleep(2)
            
            # Starte wpa_supplicant mit neuer Konfiguration
            subprocess.run(['sudo', 'wpa_supplicant', '-B', '-i', 'wlan0', 
                          '-c', '/tmp/wpa_supplicant_temp.conf'], 
                         capture_output=True)
            time.sleep(5)
            
            # Fordere IP-Adresse an
            result = subprocess.run(['sudo', 'dhclient', 'wlan0'], 
                                  capture_output=True, timeout=30)
            
            # Prüfe Verbindung
            if self.check_internet_connection():
                logger.info(f"Erfolgreich mit {ssid} verbunden")
                
                # Speichere Netzwerk als bekannt
                self.known_networks[ssid] = password
                self.save_known_networks()
                
                # Kopiere Konfiguration nach /etc/wpa_supplicant/
                subprocess.run(['sudo', 'cp', '/tmp/wpa_supplicant_temp.conf', 
                              '/etc/wpa_supplicant/wpa_supplicant.conf'])
                
                return True
            else:
                logger.warning(f"Verbindung zu {ssid} fehlgeschlagen")
                return False
                
        except Exception as e:
            logger.error(f"Fehler bei Verbindung zu {ssid}: {e}")
            return False
    
    def check_internet_connection(self):
        """Prüfe Internetverbindung"""
        try:
            # Hole aktuelle IP-Adresse zuerst
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
            if result.returncode == 0:
                ip = result.stdout.strip().split()[0] if result.stdout.strip() else ""
                if ip and not ip.startswith('192.168.4.'):  # Nicht Hotspot-IP
                    # Versuche DNS-Auflösung mit Timeout
                    try:
                        socket.setdefaulttimeout(5)  # 5 Sekunden Timeout
                        socket.gethostbyname('8.8.8.8')  # Google DNS
                        logger.debug(f"Internetverbindung aktiv, IP: {ip}")
                        return True
                    except socket.timeout:
                        logger.debug("DNS-Timeout - keine Internetverbindung")
                        return False
                    except Exception as e:
                        logger.debug(f"DNS-Fehler: {e}")
                        return False
                else:
                    logger.debug(f"Keine gültige Client-IP gefunden: {ip}")
                    return False
            else:
                logger.debug("Keine IP-Adresse gefunden")
                return False
        except Exception as e:
            logger.debug(f"Fehler bei Internetverbindungsprüfung: {e}")
            return False
    
    def try_known_networks(self):
        """Versuche Verbindung zu bekannten Netzwerken"""
        if not self.known_networks:
            logger.info("Keine bekannten Netzwerke gespeichert")
            return False
            
        available_networks = self.scan_networks()
        available_ssids = [net['ssid'] for net in available_networks]
        
        logger.info(f"Verfügbare Netzwerke: {available_ssids}")
        logger.info(f"Bekannte Netzwerke: {list(self.known_networks.keys())}")
        
        for ssid, password in self.known_networks.items():
            if ssid in available_ssids:
                logger.info(f"Versuche Verbindung zu bekanntem Netzwerk: {ssid}")
                if self.connect_to_network(ssid, password):
                    return True
            else:
                logger.debug(f"Bekanntes Netzwerk '{ssid}' nicht verfügbar")
        
        logger.info("Keine bekannten Netzwerke verfügbar oder Verbindung fehlgeschlagen")
        return False
    
    def start_hotspot(self):
        """Starte WLAN-Hotspot"""
        try:
            logger.info("Starte WLAN-Hotspot...")
            
            # Stoppe alle WLAN-Services
            subprocess.run(['sudo', 'killall', 'wpa_supplicant'], capture_output=True)
            subprocess.run(['sudo', 'killall', 'hostapd'], capture_output=True)
            subprocess.run(['sudo', 'killall', 'dnsmasq'], capture_output=True)
            time.sleep(3)
            
            # Bringe WLAN-Interface runter und wieder hoch
            subprocess.run(['sudo', 'ifconfig', 'wlan0', 'down'], capture_output=True)
            time.sleep(1)
            subprocess.run(['sudo', 'ifconfig', 'wlan0', 'up'], capture_output=True)
            time.sleep(2)
            
            # Konfiguriere hostapd mit WPA2-Verschlüsselung
            hostapd_config = f"""interface=wlan0
driver=nl80211
ssid={self.hotspot_ssid}
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase={self.hotspot_password}
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
"""
            
            with open('/tmp/hostapd.conf', 'w') as f:
                f.write(hostapd_config)
            
            # Konfiguriere dnsmasq
            dnsmasq_config = f"""interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h
dhcp-option=3,192.168.4.1
dhcp-option=6,192.168.4.1
server=8.8.8.8
log-queries
log-dhcp
listen-address=192.168.4.1
"""
            
            with open('/tmp/dnsmasq.conf', 'w') as f:
                f.write(dnsmasq_config)
            
            # Setze statische IP mit Netzmaske
            subprocess.run(['sudo', 'ifconfig', 'wlan0', f'{self.hotspot_ip}', 'netmask', '255.255.255.0'], 
                         capture_output=True, check=True)
            time.sleep(1)
            
            # Starte hostapd im Hintergrund
            hostapd_process = subprocess.Popen(['sudo', 'hostapd', '/tmp/hostapd.conf'], 
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(5)
            
            # Prüfe ob hostapd läuft
            if hostapd_process.poll() is not None:
                logger.error("hostapd konnte nicht gestartet werden")
                return False
            
            # Starte dnsmasq
            result = subprocess.run(['sudo', 'dnsmasq', '-C', '/tmp/dnsmasq.conf'], 
                                  capture_output=True)
            if result.returncode != 0:
                logger.error(f"dnsmasq Start fehlgeschlagen: {result.stderr.decode()}")
                return False
            
            self.hotspot_active = True
            self.current_mode = 'hotspot'
            
            logger.info(f"Hotspot '{self.hotspot_ssid}' erfolgreich gestartet auf {self.hotspot_ip}")
            logger.info(f"Hotspot-Passwort: {self.hotspot_password}")
            self.update_status('hotspot_active', 
                             f"Hotspot aktiv: {self.hotspot_ssid}", 
                             self.hotspot_ip, self.hotspot_ssid)
            
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Starten des Hotspots: {e}")
            self.hotspot_active = False
            return False
    
    def stop_hotspot(self):
        """Stoppe WLAN-Hotspot"""
        try:
            logger.info("Stoppe WLAN-Hotspot...")
            
            # Stoppe Services
            subprocess.run(['sudo', 'killall', 'hostapd'], capture_output=True)
            subprocess.run(['sudo', 'killall', 'dnsmasq'], capture_output=True)
            time.sleep(2)
            
            # Bringe Interface runter und wieder hoch für sauberen Reset
            subprocess.run(['sudo', 'ifconfig', 'wlan0', 'down'], capture_output=True)
            time.sleep(1)
            subprocess.run(['sudo', 'ifconfig', 'wlan0', 'up'], capture_output=True)
            time.sleep(2)
            
            # Entferne statische IP-Konfiguration
            subprocess.run(['sudo', 'dhclient', '-r', 'wlan0'], capture_output=True)
            time.sleep(1)
            
            self.hotspot_active = False
            self.current_mode = 'client'
            self.web_server_running = False
            
            logger.info("Hotspot erfolgreich gestoppt")
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Stoppen des Hotspots: {e}")
            return False
    
    def start_web_server(self):
        """Starte Web-Server für Konfiguration"""
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import urllib.parse
        
        class ConfigHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == '/':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    
                    # Scanne verfügbare Netzwerke
                    networks = self.server.wifi_manager.scan_networks()
                    
                    html = self.generate_config_page(networks)
                    self.wfile.write(html.encode())
                    
                elif self.path == '/status':
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    status = {
                        'mode': self.server.wifi_manager.current_mode,
                        'hotspot_active': self.server.wifi_manager.hotspot_active
                    }
                    self.wfile.write(json.dumps(status).encode())
                    
            def do_POST(self):
                if self.path == '/connect':
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    data = urllib.parse.parse_qs(post_data.decode())
                    
                    ssid = data.get('ssid', [''])[0]
                    password = data.get('password', [''])[0]
                    
                    if ssid:
                        logger.info(f"Verbindungsversuch zu {ssid} über Web-Interface")
                        
                        # Antwort senden bevor Verbindung versucht wird
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        
                        html = """
                        <html><body>
                        <h2>Verbindung wird hergestellt...</h2>
                        <p>Bitte warten Sie einen Moment. Das Gerät versucht sich zu verbinden.</p>
                        <p>Bei erfolgreicher Verbindung wird der Hotspot automatisch deaktiviert.</p>
                        <script>
                        setTimeout(function() {
                            window.location.href = '/';
                        }, 10000);
                        </script>
                        </body></html>
                        """
                        self.wfile.write(html.encode())
                        
                        # Verbindung in separatem Thread versuchen
                        def connect_thread():
                            time.sleep(2)  # Kurz warten damit Response gesendet wird
                            if self.server.wifi_manager.connect_to_network(ssid, password):
                                logger.info("Verbindung erfolgreich, stoppe Hotspot")
                                time.sleep(5)
                                self.server.wifi_manager.stop_hotspot()
                        
                        threading.Thread(target=connect_thread, daemon=True).start()
            
            def generate_config_page(self, networks):
                """Generiere HTML-Konfigurationsseite"""
                networks_html = ""
                for network in networks:
                    quality_bar = "🟢" if "70/" in network.get('quality', '') else "🟡" if "40/" in network.get('quality', '') else "🔴"
                    lock_icon = "🔒" if network.get('encrypted', True) else "🔓"
                    
                    networks_html += f"""
                    <div class="network-item" onclick="selectNetwork('{network['ssid']}', {str(network.get('encrypted', True)).lower()})">
                        <span class="network-name">{lock_icon} {network['ssid']}</span>
                        <span class="signal-strength">{quality_bar}</span>
                    </div>
                    """
                
                return f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Tipsy WLAN Setup</title>
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <style>
                        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }}
                        .container {{ max-width: 500px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                        h1 {{ color: #333; text-align: center; }}
                        .network-item {{ padding: 15px; border: 1px solid #ddd; margin: 5px 0; cursor: pointer; border-radius: 5px; display: flex; justify-content: space-between; }}
                        .network-item:hover {{ background: #f5f5f5; }}
                        .network-item.selected {{ background: #e3f2fd; border-color: #2196f3; }}
                        .form-group {{ margin: 15px 0; }}
                        label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
                        input[type="text"], input[type="password"] {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }}
                        button {{ background: #4CAF50; color: white; padding: 12px 20px; border: none; border-radius: 5px; cursor: pointer; width: 100%; font-size: 16px; }}
                        button:hover {{ background: #45a049; }}
                        .info {{ background: #e7f3ff; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🍹 Tipsy WLAN Setup</h1>
                        
                        <div class="info">
                            <strong>🍹 Willkommen beim Tipsy WLAN-Setup!</strong><br>
                            Sie sind mit dem Hotspot <strong>{self.hotspot_ssid}</strong> verbunden.<br>
                            Wählen Sie ein WLAN-Netzwerk aus der Liste und geben Sie das Passwort ein.
                        </div>
                        
                        <h3>Verfügbare Netzwerke:</h3>
                        <div id="networks">
                            {networks_html}
                        </div>
                        
                        <form method="post" action="/connect" id="connectForm">
                            <div class="form-group">
                                <label for="ssid">Netzwerk:</label>
                                <input type="text" id="ssid" name="ssid" readonly>
                            </div>
                            
                            <div class="form-group" id="passwordGroup" style="display: none;">
                                <label for="password">Passwort:</label>
                                <input type="password" id="password" name="password">
                            </div>
                            
                            <button type="submit" id="connectBtn" disabled>Verbinden</button>
                        </form>
                    </div>
                    
                    <script>
                        function selectNetwork(ssid, encrypted) {{
                            // Entferne vorherige Auswahl
                            document.querySelectorAll('.network-item').forEach(item => {{
                                item.classList.remove('selected');
                            }});
                            
                            // Markiere ausgewähltes Netzwerk
                            event.currentTarget.classList.add('selected');
                            
                            // Setze SSID
                            document.getElementById('ssid').value = ssid;
                            
                            // Zeige/verstecke Passwort-Feld
                            const passwordGroup = document.getElementById('passwordGroup');
                            if (encrypted) {{
                                passwordGroup.style.display = 'block';
                                document.getElementById('password').required = true;
                            }} else {{
                                passwordGroup.style.display = 'none';
                                document.getElementById('password').required = false;
                                document.getElementById('password').value = '';
                            }}
                            
                            // Aktiviere Connect-Button
                            document.getElementById('connectBtn').disabled = false;
                        }}
                    </script>
                </body>
                </html>
                """
            
            def log_message(self, format, *args):
                # Unterdrücke HTTP-Logs
                pass
        
        try:
            server = HTTPServer(('0.0.0.0', 80), ConfigHandler)
            server.wifi_manager = self
            self.web_server = server
            
            logger.info("Web-Server gestartet auf Port 80")
            server.serve_forever()
            
        except Exception as e:
            logger.error(f"Fehler beim Starten des Web-Servers: {e}")
    
    def check_for_commands(self):
        """Prüfe auf Befehle vom Interface"""
        command_file = Path('/tmp/tipsy_wifi_command.json')
        if command_file.exists():
            try:
                with open(command_file, 'r') as f:
                    command = json.load(f)
                
                # Lösche Befehlsdatei nach dem Lesen
                command_file.unlink()
                
                if command.get('action') == 'toggle_hotspot':
                    logger.info("Toggle-Hotspot Befehl empfangen")
                    self.toggle_manual_hotspot()
                    return True
                    
            except Exception as e:
                logger.error(f"Fehler beim Verarbeiten des Befehls: {e}")
                try:
                    command_file.unlink()
                except:
                    pass
        return False
    
    def run(self):
        """Hauptschleife des WiFi-Managers"""
        logger.info("Tipsy WiFi Manager gestartet")
        
        while True:
            try:
                # Prüfe auf Befehle vom Interface
                self.check_for_commands()
                
                # Prüfe ob manueller Hotspot angefordert wurde
                if self.manual_hotspot_requested:
                    if not self.hotspot_active:
                        logger.info("Starte manuell angeforderten Hotspot")
                        if self.start_hotspot():
                            # Starte Web-Server nur wenn er noch nicht läuft
                            if not self.web_server_running:
                                web_thread = threading.Thread(target=self.start_web_server, daemon=True)
                                web_thread.start()
                                self.web_server_running = True
                    else:
                        self.update_status('hotspot_active', 
                                         f"Manueller Hotspot aktiv: {self.hotspot_ssid}", 
                                         self.hotspot_ip, self.hotspot_ssid)
                
                # Normale Logik nur wenn kein manueller Hotspot angefordert
                elif self.check_internet_connection():
                    # Internetverbindung vorhanden
                    if self.hotspot_active:
                        logger.info("Internetverbindung erkannt, stoppe automatischen Hotspot")
                        self.stop_hotspot()
                    
                    # Hole aktuelle IP und SSID
                    result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
                    ip = result.stdout.strip().split()[0] if result.returncode == 0 and result.stdout.strip() else ""
                    
                    # Versuche SSID zu ermitteln
                    result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True)
                    ssid = result.stdout.strip() if result.returncode == 0 else "Unknown"
                    
                    self.update_status('connected', 'Mit WLAN verbunden', ip, ssid)
                    logger.debug(f"Verbunden mit {ssid}, IP: {ip}")
                    
                else:
                    # Keine Internetverbindung und kein manueller Hotspot
                    logger.debug("Keine Internetverbindung erkannt")
                    
                    if not self.hotspot_active:
                        logger.info("Keine Internetverbindung, versuche bekannte Netzwerke...")
                        
                        if not self.try_known_networks():
                            logger.info("Keine bekannten Netzwerke verfügbar, starte automatischen Hotspot")
                            if self.start_hotspot():
                                # Starte Web-Server nur wenn er noch nicht läuft
                                if not self.web_server_running:
                                    web_thread = threading.Thread(target=self.start_web_server, daemon=True)
                                    web_thread.start()
                                    self.web_server_running = True
                            else:
                                logger.error("Automatischer Hotspot konnte nicht gestartet werden")
                                self.update_status('error', 'Hotspot-Start fehlgeschlagen', '', '')
                    else:
                        self.update_status('hotspot_active', 
                                         f"Automatischer Hotspot aktiv: {self.hotspot_ssid}", 
                                         self.hotspot_ip, self.hotspot_ssid)
                
                # Warte vor nächster Prüfung - kürzer für responsive Befehle
                time.sleep(5)
                
            except KeyboardInterrupt:
                logger.info("WiFi Manager wird beendet...")
                break
            except Exception as e:
                logger.error(f"Unerwarteter Fehler: {e}")
                time.sleep(10)
        
        # Cleanup
        if self.hotspot_active:
            self.stop_hotspot()

# Globale WiFi-Manager-Instanz für Service
_wifi_manager_instance = None

def signal_handler(signum, frame):
    """Signal Handler für sauberes Beenden"""
    logger.info("Signal empfangen, beende WiFi Manager...")
    sys.exit(0)

if __name__ == "__main__":
    # Signal Handler registrieren
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # WiFi Manager starten
    manager = WiFiManager()
    _wifi_manager_instance = manager
    manager.run()
