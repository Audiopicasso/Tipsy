#!/usr/bin/env python3
"""
WLAN Manager für Tipsy Cocktail Mixer
Automatisches WLAN-Setup mit Hotspot-Fallback

PRIORITÄTEN:
1. Bekannte Netzwerke haben IMMER Priorität
2. Hotspot nur als letzter Ausweg
3. Web-Interface funktioniert im Hotspot
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
        self.manual_hotspot_requested = False
        
        # Hotspot Konfiguration
        self.hotspot_ssid = "Prost-Setup"
        self.hotspot_password = "prost123"
        self.hotspot_ip = "192.168.4.1"
        self.web_server_running = False
        
        # Stelle sicher, dass Konfigurationsverzeichnis existiert
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Lade bekannte Netzwerke
        self.known_networks = self.load_known_networks()
        
        # Timing für Netzwerk-Checks
        self._last_network_check = 0
        
    def load_known_networks(self):
        """Lade bekannte WLAN-Netzwerke aus der Konfigurationsdatei"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    networks = json.load(f)
                logger.info(f"✅ Lade {len(networks)} bekannte Netzwerke")
                for ssid in networks.keys():
                    logger.info(f"   - {ssid}")
                return networks
            except Exception as e:
                logger.error(f"Fehler beim Laden der Netzwerke: {e}")
                return {}
        else:
            logger.info("Keine bekannten Netzwerke gefunden")
            return {}
    
    def save_known_networks(self):
        """Speichere bekannte Netzwerke"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.known_networks, f, indent=2)
            logger.info(f"Gespeichert: {len(self.known_networks)} bekannte Netzwerke")
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Netzwerke: {e}")
    
    def update_status(self, status, message, ip="", ssid=""):
        """Aktualisiere Status-Datei für Interface"""
        try:
            status_data = {
                'status': status,
                'message': message,
                'ip': ip,
                'ssid': ssid,
                'mode': self.current_mode,
                'hotspot_active': self.hotspot_active,
                'manual_hotspot_requested': self.manual_hotspot_requested,
                'timestamp': time.time()
            }
            
            with open(self.status_file, 'w') as f:
                json.dump(status_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren des Status: {e}")
    
    def scan_networks(self):
        """Scanne verfügbare WLAN-Netzwerke"""
        try:
            logger.info("🔍 Scanne verfügbare WLAN-Netzwerke...")
            result = subprocess.run(['iwlist', 'wlan0', 'scan'], 
                                  capture_output=True, text=True, timeout=15)
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
                        try:
                            quality = line.split('Quality=')[1].split(' ')[0]
                            current_network['quality'] = quality
                        except:
                            current_network['quality'] = 'unknown'
                    elif 'Encryption key:' in line:
                        encrypted = 'on' in line.lower()
                        current_network['encrypted'] = encrypted
                        
                        if 'ssid' in current_network:
                            networks.append(current_network.copy())
                        current_network = {}
                
                logger.info(f"✅ {len(networks)} Netzwerke gefunden")
                return networks
            else:
                logger.error(f"WLAN-Scan fehlgeschlagen: {result.stderr}")
                return []
        except Exception as e:
            logger.error(f"Fehler beim WLAN-Scan: {e}")
            return []
    
    def connect_to_network(self, ssid, password=None):
        """Verbinde mit WLAN-Netzwerk"""
        try:
            logger.info(f"🔗 Versuche Verbindung zu '{ssid}'...")
            
            # Prüfe ob NetworkManager verfügbar ist
            result = subprocess.run(['which', 'nmcli'], capture_output=True)
            if result.returncode == 0:
                return self.connect_to_network_networkmanager(ssid, password)
            else:
                return self.connect_to_network_legacy(ssid, password)
                
        except Exception as e:
            logger.error(f"Fehler bei WLAN-Verbindung zu {ssid}: {e}")
            return False
    
    def connect_to_network_networkmanager(self, ssid, password=None):
        """Verbinde mit WLAN über NetworkManager"""
        try:
            # Lösche existierende Verbindung
            subprocess.run(['sudo', 'nmcli', 'connection', 'delete', ssid], 
                         capture_output=True)
            
            # Erstelle neue Verbindung
            if password:
                cmd = ['sudo', 'nmcli', 'device', 'wifi', 'connect', ssid, 'password', password]
            else:
                cmd = ['sudo', 'nmcli', 'device', 'wifi', 'connect', ssid]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"✅ NetworkManager-Verbindung zu {ssid} erfolgreich")
                time.sleep(5)
                
                if self.check_internet_connection():
                    self.known_networks[ssid] = password
                    self.save_known_networks()
                    return True
                else:
                    logger.warning(f"Verbindung hergestellt, aber kein Internet über {ssid}")
                    return False
            else:
                logger.error(f"NetworkManager-Verbindung zu {ssid} fehlgeschlagen: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Fehler bei NetworkManager-Verbindung zu {ssid}: {e}")
            return False
    
    def connect_to_network_legacy(self, ssid, password=None):
        """Verbinde mit WLAN über wpa_supplicant (Legacy)"""
        try:
            logger.info(f"Legacy-Verbindung zu {ssid}...")
            
            # Stoppe NetworkManager für wlan0
            subprocess.run(['sudo', 'nmcli', 'device', 'set', 'wlan0', 'managed', 'no'], 
                         capture_output=True)
            time.sleep(2)
            
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
            
            with open('/tmp/wpa_supplicant_temp.conf', 'w') as f:
                f.write(wpa_config)
            
            # Stoppe aktuellen wpa_supplicant
            subprocess.run(['sudo', 'killall', 'wpa_supplicant'], capture_output=True)
            time.sleep(2)
            
            # Starte wpa_supplicant
            subprocess.run(['sudo', 'wpa_supplicant', '-B', '-i', 'wlan0', 
                          '-c', '/tmp/wpa_supplicant_temp.conf'], capture_output=True)
            time.sleep(5)
            
            # Fordere IP-Adresse an
            subprocess.run(['sudo', 'dhclient', 'wlan0'], capture_output=True, timeout=30)
            
            if self.check_internet_connection():
                logger.info(f"✅ Legacy-Verbindung zu {ssid} erfolgreich")
                self.known_networks[ssid] = password
                self.save_known_networks()
                return True
            else:
                logger.warning(f"Legacy-Verbindung zu {ssid} fehlgeschlagen")
                return False
                
        except Exception as e:
            logger.error(f"Fehler bei Legacy-Verbindung zu {ssid}: {e}")
            return False
    
    def check_internet_connection(self):
        """Prüfe Internetverbindung mit mehreren Methoden"""
        try:
            # Methode 1: IP-Adresse prüfen
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                ip = result.stdout.strip().split()[0]
                
                # Hotspot-IP = kein Internet
                if ip.startswith('192.168.4.'):
                    return False
                
                # Methode 2: DNS-Test
                try:
                    socket.setdefaulttimeout(3)
                    socket.gethostbyname('google.com')
                    return True
                except:
                    pass
                
                # Methode 3: Socket-Test
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(3)
                    result = sock.connect_ex(('8.8.8.8', 53))
                    sock.close()
                    return result == 0
                except:
                    pass
            
            return False
                
        except Exception as e:
            logger.debug(f"Fehler bei Internetverbindungsprüfung: {e}")
            return False
    
    def try_known_networks(self):
        """Versuche Verbindung zu bekannten Netzwerken mit Priorität"""
        if not self.known_networks:
            logger.info("❌ Keine bekannten Netzwerke gespeichert")
            return False
            
        logger.info(f"🔍 Scanne nach bekannten Netzwerken...")
        available_networks = self.scan_networks()
        available_ssids = [net['ssid'] for net in available_networks]
        
        logger.info(f"Verfügbare Netzwerke: {available_ssids}")
        logger.info(f"Bekannte Netzwerke: {list(self.known_networks.keys())}")
        
        # Versuche jedes bekannte Netzwerk
        for ssid, password in self.known_networks.items():
            if ssid in available_ssids:
                logger.info(f"🔗 Versuche Verbindung zu bekanntem Netzwerk: {ssid}")
                if self.connect_to_network(ssid, password):
                    logger.info(f"✅ Erfolgreich mit {ssid} verbunden")
                    return True
                else:
                    logger.warning(f"❌ Verbindung zu {ssid} fehlgeschlagen")
            else:
                logger.debug(f"Bekanntes Netzwerk '{ssid}' nicht verfügbar")
        
        logger.info("❌ Keine bekannten Netzwerke verfügbar oder alle Verbindungen fehlgeschlagen")
        return False
    
    def start_hotspot(self):
        """Starte WLAN-Hotspot"""
        try:
            logger.info("🔥 Starte Hotspot...")
            
            # Prüfe NetworkManager
            result = subprocess.run(['which', 'nmcli'], capture_output=True)
            if result.returncode == 0:
                if self.start_hotspot_networkmanager():
                    return True
            
            # Fallback zu Legacy
            return self.start_hotspot_legacy()
            
        except Exception as e:
            logger.error(f"Fehler beim Hotspot-Start: {e}")
            return False
    
    def start_hotspot_networkmanager(self):
        """Starte Hotspot mit NetworkManager"""
        try:
            logger.info("Starte NetworkManager Hotspot...")
            
            # Lösche existierende Verbindung
            subprocess.run(['sudo', 'nmcli', 'connection', 'delete', 'Prost-Hotspot'], 
                         capture_output=True)
            
            # Erstelle Hotspot-Verbindung
            cmd = [
                'sudo', 'nmcli', 'connection', 'add',
                'type', 'wifi', 'ifname', 'wlan0',
                'con-name', 'Prost-Hotspot',
                'autoconnect', 'no',
                'ssid', self.hotspot_ssid
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Fehler beim Erstellen: {result.stderr}")
                return False
            
            # Konfiguriere Hotspot
            config_commands = [
                ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 'wifi.mode', 'ap'],
                ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 'wifi.band', 'bg'],
                ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 'wifi.channel', '7'],
                ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 'wifi-sec.key-mgmt', 'wpa-psk'],
                ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 'wifi-sec.psk', self.hotspot_password],
                ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 'ipv4.method', 'shared'],
                ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 'ipv4.addresses', f'{self.hotspot_ip}/24']
            ]
            
            for cmd in config_commands:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"Konfigurationsfehler: {result.stderr}")
                    return False
            
            # Aktiviere Hotspot
            result = subprocess.run(['sudo', 'nmcli', 'connection', 'up', 'Prost-Hotspot'], 
                                  capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Aktivierungsfehler: {result.stderr}")
                return False
            
            time.sleep(5)
            
            self.hotspot_active = True
            self.current_mode = 'hotspot'
            
            logger.info(f"✅ Hotspot '{self.hotspot_ssid}' gestartet")
            logger.info(f"📱 SSID: {self.hotspot_ssid}")
            logger.info(f"🔑 Passwort: {self.hotspot_password}")
            logger.info(f"🌐 IP: {self.hotspot_ip}")
            
            self.update_status('hotspot_active', f"Hotspot aktiv: {self.hotspot_ssid}", 
                             self.hotspot_ip, self.hotspot_ssid)
            
            return True
            
        except Exception as e:
            logger.error(f"NetworkManager Hotspot Fehler: {e}")
            return False
    
    def start_hotspot_legacy(self):
        """Starte Hotspot mit hostapd/dnsmasq"""
        try:
            logger.info("Starte Legacy Hotspot...")
            
            # Stoppe NetworkManager für wlan0
            subprocess.run(['sudo', 'nmcli', 'device', 'set', 'wlan0', 'managed', 'no'], 
                         capture_output=True)
            time.sleep(2)
            
            # Konfiguriere Interface
            subprocess.run(['sudo', 'ip', 'addr', 'flush', 'dev', 'wlan0'], capture_output=True)
            subprocess.run(['sudo', 'ip', 'addr', 'add', f'{self.hotspot_ip}/24', 'dev', 'wlan0'], 
                         capture_output=True)
            subprocess.run(['sudo', 'ip', 'link', 'set', 'wlan0', 'up'], capture_output=True)
            
            # Starte Services
            subprocess.run(['sudo', 'systemctl', 'start', 'hostapd'], capture_output=True)
            subprocess.run(['sudo', 'systemctl', 'start', 'dnsmasq'], capture_output=True)
            
            time.sleep(5)
            
            self.hotspot_active = True
            self.current_mode = 'hotspot'
            
            logger.info(f"✅ Legacy Hotspot '{self.hotspot_ssid}' gestartet")
            self.update_status('hotspot_active', f"Hotspot aktiv: {self.hotspot_ssid}", 
                             self.hotspot_ip, self.hotspot_ssid)
            
            return True
            
        except Exception as e:
            logger.error(f"Legacy Hotspot Fehler: {e}")
            return False
    
    def stop_hotspot(self):
        """Stoppe WLAN-Hotspot"""
        try:
            logger.info("🛑 Stoppe Hotspot...")
            
            # NetworkManager Hotspot stoppen
            subprocess.run(['sudo', 'nmcli', 'connection', 'down', 'Prost-Hotspot'], 
                         capture_output=True)
            subprocess.run(['sudo', 'nmcli', 'connection', 'delete', 'Prost-Hotspot'], 
                         capture_output=True)
            
            # Legacy Services stoppen
            subprocess.run(['sudo', 'killall', 'hostapd'], capture_output=True)
            subprocess.run(['sudo', 'killall', 'dnsmasq'], capture_output=True)
            
            # NetworkManager reaktivieren
            subprocess.run(['sudo', 'nmcli', 'device', 'set', 'wlan0', 'managed', 'yes'], 
                         capture_output=True)
            
            # Web-Server stoppen
            if self.web_server:
                try:
                    self.web_server.shutdown()
                except:
                    pass
            
            self.hotspot_active = False
            self.current_mode = 'client'
            self.web_server_running = False
            
            logger.info("✅ Hotspot gestoppt")
            self.update_status('disconnected', 'Hotspot gestoppt', '', '')
            
            return True
            
        except Exception as e:
            logger.error(f"Fehler beim Stoppen des Hotspots: {e}")
            return False
    
    def start_web_server(self):
        """Starte Web-Server für Hotspot-Konfiguration"""
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import urllib.parse
        
        class ConfigHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                try:
                    if self.path == '/' or self.path == '/index.html':
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.send_header('Cache-Control', 'no-cache')
                        self.end_headers()
                        
                        networks = self.server.wifi_manager.scan_networks()
                        html = self.generate_config_page(networks)
                        self.wfile.write(html.encode('utf-8'))
                        
                    elif self.path == '/status':
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        
                        status = {
                            'mode': self.server.wifi_manager.current_mode,
                            'hotspot_active': self.server.wifi_manager.hotspot_active,
                            'ssid': self.server.wifi_manager.hotspot_ssid
                        }
                        self.wfile.write(json.dumps(status).encode('utf-8'))
                        
                    else:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b'<h1>404 - Seite nicht gefunden</h1>')
                        
                except Exception as e:
                    logger.error(f"Web-Server GET Fehler: {e}")
                    self.send_response(500)
                    self.end_headers()
            
            def do_POST(self):
                try:
                    if self.path == '/connect':
                        content_length = int(self.headers['Content-Length'])
                        post_data = self.rfile.read(content_length)
                        data = urllib.parse.parse_qs(post_data.decode('utf-8'))
                        
                        ssid = data.get('ssid', [''])[0]
                        password = data.get('password', [''])[0]
                        
                        if ssid:
                            logger.info(f"🔗 Web-Interface: Verbindungsversuch zu {ssid}")
                            
                            self.send_response(200)
                            self.send_header('Content-type', 'text/html; charset=utf-8')
                            self.end_headers()
                            
                            html = """
                            <html><head><meta charset="utf-8"><title>Verbindung...</title></head><body>
                            <div style="text-align: center; font-family: Arial; margin-top: 50px;">
                            <h2>🍻 Verbindung wird hergestellt...</h2>
                            <p>Bitte warten Sie einen Moment. Das Gerät versucht sich zu verbinden.</p>
                            <p>Bei erfolgreicher Verbindung wird der Hotspot automatisch deaktiviert.</p>
                            <div style="margin-top: 30px;">
                                <div style="border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 40px; height: 40px; animation: spin 2s linear infinite; margin: 0 auto;"></div>
                            </div>
                            <style>
                            @keyframes spin {
                                0% { transform: rotate(0deg); }
                                100% { transform: rotate(360deg); }
                            }
                            </style>
                            </div></body></html>
                            """
                            self.wfile.write(html.encode('utf-8'))
                            
                            # Verbindung in separatem Thread
                            def connect_thread():
                                try:
                                    time.sleep(2)
                                    if self.server.wifi_manager.connect_to_network(ssid, password):
                                        logger.info("✅ Web-Interface: Verbindung erfolgreich")
                                        
                                        # Starte Watchdog-Service neu bei Netzwerkwechsel
                                        logger.info("🔄 Starte tipsy-watchdog.service neu...")
                                        try:
                                            result = subprocess.run(['sudo', 'systemctl', 'restart', 'tipsy-watchdog.service'], 
                                                                  capture_output=True, text=True, timeout=10)
                                            if result.returncode == 0:
                                                logger.info("✅ tipsy-watchdog.service erfolgreich neu gestartet")
                                            else:
                                                logger.warning(f"⚠️  tipsy-watchdog.service Neustart: {result.stderr}")
                                        except Exception as e:
                                            logger.warning(f"⚠️  Fehler beim Watchdog-Neustart: {e}")
                                        
                                        time.sleep(5)
                                        self.server.wifi_manager.stop_hotspot()
                                    else:
                                        logger.error(f"❌ Web-Interface: Verbindung zu {ssid} fehlgeschlagen")
                                except Exception as e:
                                    logger.error(f"Connect-Thread Fehler: {e}")
                            
                            threading.Thread(target=connect_thread, daemon=True).start()
                        
                except Exception as e:
                    logger.error(f"Web-Server POST Fehler: {e}")
                    self.send_response(500)
                    self.end_headers()
            
            def generate_config_page(self, networks):
                """Generiere HTML-Konfigurationsseite"""
                networks_html = ""
                if not networks:
                    networks_html = "<p>Keine WLAN-Netzwerke gefunden. <a href='/' onclick='location.reload()'>Neu laden</a></p>"
                else:
                    for network in networks:
                        quality = network.get('quality', '0/100')
                        if '/' in quality:
                            quality_num = int(quality.split('/')[0])
                            quality_bar = "🟢" if quality_num > 70 else "🟡" if quality_num > 40 else "🔴"
                        else:
                            quality_bar = "🔴"
                        
                        lock_icon = "🔒" if network.get('encrypted', True) else "🔓"
                        ssid = network['ssid'].replace("'", "\\'")
                        
                        networks_html += f"""
                        <div class="network-item" onclick="selectNetwork('{ssid}', {str(network.get('encrypted', True)).lower()})">
                            <span class="network-name">{lock_icon} {network['ssid']}</span>
                            <span class="signal-strength">{quality_bar}</span>
                        </div>
                        """
                
                return f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Prost WLAN Setup</title>
                    <meta charset="utf-8">
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
                        button:disabled {{ background: #cccccc; cursor: not-allowed; }}
                        .info {{ background: #e7f3ff; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                        .refresh-btn {{ background: #2196f3; margin-bottom: 10px; }}
                        .refresh-btn:hover {{ background: #1976d2; }}
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🍻 Prost WLAN Setup</h1>
                        
                        <div class="info">
                            <strong>🍻 Willkommen beim Prost WLAN-Setup!</strong><br>
                            Sie sind mit dem Hotspot <strong>{self.server.wifi_manager.hotspot_ssid}</strong> verbunden.<br>
                            <strong>Passwort:</strong> {self.server.wifi_manager.hotspot_password}<br>
                            Wählen Sie ein WLAN-Netzwerk aus der Liste und geben Sie das Passwort ein.
                        </div>
                        
                        <button class="refresh-btn" onclick="location.reload()">🔄 Netzwerke neu laden</button>
                        
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
                            document.querySelectorAll('.network-item').forEach(item => {{
                                item.classList.remove('selected');
                            }});
                            
                            event.currentTarget.classList.add('selected');
                            document.getElementById('ssid').value = ssid;
                            
                            const passwordGroup = document.getElementById('passwordGroup');
                            if (encrypted) {{
                                passwordGroup.style.display = 'block';
                                document.getElementById('password').required = true;
                            }} else {{
                                passwordGroup.style.display = 'none';
                                document.getElementById('password').required = false;
                                document.getElementById('password').value = '';
                            }}
                            
                            document.getElementById('connectBtn').disabled = false;
                        }}
                        
                        // Auto-refresh alle 60 Sekunden
                        setTimeout(function() {{
                            location.reload();
                        }}, 60000);
                    </script>
                </body>
                </html>
                """
            
            def log_message(self, format, *args):
                logger.debug(f"HTTP: {format % args}")
        
        try:
            # Versuche verschiedene Ports
            ports_to_try = [80, 8080, 8000]
            server = None
            
            for port in ports_to_try:
                try:
                    server = HTTPServer(('0.0.0.0', port), ConfigHandler)
                    server.wifi_manager = self
                    self.web_server = server
                    logger.info(f"🌐 Web-Server gestartet auf Port {port}")
                    logger.info(f"📱 Setup-URL: http://{self.hotspot_ip}:{port if port != 80 else ''}")
                    break
                except OSError as e:
                    if e.errno in [13, 98]:  # Permission denied oder Address in use
                        logger.warning(f"Port {port} nicht verfügbar, versuche nächsten...")
                        continue
                    else:
                        raise
            
            if server is None:
                logger.error("❌ Konnte keinen verfügbaren Port für Web-Server finden")
                return
            
            # Server starten
            server.serve_forever()
            
        except Exception as e:
            logger.error(f"❌ Web-Server Fehler: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def check_for_commands(self):
        """Prüfe auf Befehle vom Interface"""
        command_file = Path('/tmp/tipsy_wifi_command.json')
        if command_file.exists():
            try:
                with open(command_file, 'r') as f:
                    command = json.load(f)
                
                action = command.get('action')
                if action == 'toggle_hotspot':
                    logger.info("Interface-Befehl: Toggle Hotspot")
                    self.toggle_manual_hotspot()
                
                # Lösche Befehlsdatei
                command_file.unlink()
                
            except Exception as e:
                logger.error(f"Fehler beim Verarbeiten von Befehlen: {e}")
    
    def toggle_manual_hotspot(self):
        """Toggle manueller Hotspot"""
        if self.manual_hotspot_requested:
            self.stop_manual_hotspot()
        else:
            self.request_manual_hotspot()
    
    def request_manual_hotspot(self):
        """Fordere manuellen Hotspot an"""
        self.manual_hotspot_requested = True
        logger.info("Manueller Hotspot angefordert")
    
    def stop_manual_hotspot(self):
        """Stoppe manuellen Hotspot"""
        self.manual_hotspot_requested = False
        if self.hotspot_active:
            self.stop_hotspot()
        logger.info("Manueller Hotspot gestoppt")
    
    def run(self):
        """Hauptschleife des WiFi-Managers mit korrekten Prioritäten"""
        logger.info("🍻 Prost WiFi Manager gestartet")
        
        # Warte beim Start für Netzwerk-Stabilisierung
        logger.info("⏳ Warte 10 Sekunden für Netzwerk-Stabilisierung...")
        time.sleep(10)
        
        # Initialer Check
        logger.info("🔍 Führe initialen Status-Check durch...")
        initial_internet = self.check_internet_connection()
        logger.info(f"Initiale Internet-Verbindung: {'✅ verfügbar' if initial_internet else '❌ nicht verfügbar'}")
        
        # BEIM START: Versuche IMMER zuerst bekannte Netzwerke
        if not initial_internet:
            logger.info("🔍 Keine Internet-Verbindung beim Start - suche bekannte Netzwerke...")
            
            if self.known_networks:
                logger.info(f"📋 Gefunden: {len(self.known_networks)} bekannte Netzwerke")
                if self.try_known_networks():
                    logger.info("✅ Erfolgreich mit bekanntem Netzwerk verbunden beim Start")
                else:
                    logger.info("❌ Keine bekannten Netzwerke verfügbar - starte Hotspot als Fallback")
            else:
                logger.info("❌ Keine bekannten Netzwerke gespeichert - starte Hotspot als Fallback")
        
        while True:
            try:
                # Prüfe Interface-Befehle
                self.check_for_commands()
                
                # Manueller Hotspot hat höchste Priorität
                if self.manual_hotspot_requested:
                    if not self.hotspot_active:
                        logger.info("🔥 Starte manuell angeforderten Hotspot")
                        if self.start_hotspot():
                            if not self.web_server_running:
                                web_thread = threading.Thread(target=self.start_web_server, daemon=False)
                                web_thread.start()
                                self.web_server_running = True
                    else:
                        self.update_status('hotspot_active', 
                                         f"Manueller Hotspot aktiv: {self.hotspot_ssid}", 
                                         self.hotspot_ip, self.hotspot_ssid)
                
                # Normale Automatik
                elif self.check_internet_connection():
                    # Internet verfügbar - stoppe Hotspot falls aktiv
                    if self.hotspot_active:
                        logger.info("✅ Internet verfügbar - stoppe automatischen Hotspot")
                        self.stop_hotspot()
                    
                    # Status aktualisieren
                    result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
                    ip = result.stdout.strip().split()[0] if result.returncode == 0 and result.stdout.strip() else ""
                    
                    result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True)
                    ssid = result.stdout.strip() if result.returncode == 0 else "Unknown"
                    
                    self.update_status('connected', f'Mit {ssid} verbunden', ip, ssid)
                    logger.debug(f"✅ Verbunden mit {ssid}, IP: {ip}")
                    
                else:
                    # Kein Internet - starte Wiederverbindungs-Prozess
                    logger.info("❌ Keine Internetverbindung erkannt")
                    
                    if not self.hotspot_active:
                        logger.info("🔍 Starte Netzwerk-Wiederverbindungs-Prozess...")
                        
                        # ERSTE PRIORITÄT: Bekannte Netzwerke
                        if self.known_networks:
                            logger.info(f"🔍 Scanne nach {len(self.known_networks)} bekannten Netzwerken...")
                            
                            if self.try_known_networks():
                                logger.info("✅ Erfolgreich mit bekanntem Netzwerk wiederverbunden")
                                continue
                            else:
                                logger.info("❌ Keine bekannten Netzwerke verfügbar")
                                
                                # Zweiter Versuch nach kurzer Pause
                                logger.info("⏳ Warte 15 Sekunden und versuche nochmal...")
                                time.sleep(15)
                                
                                if self.try_known_networks():
                                    logger.info("✅ Erfolgreich mit bekanntem Netzwerk verbunden (2. Versuch)")
                                    continue
                                else:
                                    logger.info("❌ Auch 2. Versuch fehlgeschlagen")
                        else:
                            logger.info("❌ Keine bekannten Netzwerke gespeichert")
                        
                        # ZWEITE PRIORITÄT: Hotspot als letzter Ausweg
                        logger.info("🔥 Starte Hotspot als letzten Ausweg...")
                        if self.start_hotspot():
                            logger.info("✅ Automatischer Hotspot gestartet")
                            if not self.web_server_running:
                                logger.info("🌐 Starte Web-Server...")
                                web_thread = threading.Thread(target=self.start_web_server, daemon=False)
                                web_thread.start()
                                self.web_server_running = True
                        else:
                            logger.error("❌ Automatischer Hotspot fehlgeschlagen")
                            self.update_status('error', 'Hotspot-Start fehlgeschlagen', '', '')
                    
                    else:
                        # Hotspot läuft - prüfe regelmäßig ob bekannte Netzwerke verfügbar werden
                        current_time = time.time()
                        if current_time - self._last_network_check > 60:  # Alle 60 Sekunden
                            logger.info("🔍 Prüfe ob bekannte Netzwerke wieder verfügbar sind...")
                            if self.known_networks and self.try_known_networks():
                                logger.info("✅ Bekanntes Netzwerk wieder verfügbar - stoppe Hotspot")
                                self.stop_hotspot()
                                continue
                            self._last_network_check = current_time
                        
                        self.update_status('hotspot_active', 
                                         f"Hotspot aktiv: {self.hotspot_ssid}", 
                                         self.hotspot_ip, self.hotspot_ssid)
                
                # Warte vor nächster Prüfung
                time.sleep(20)  # Weniger aggressive Prüfung
                
            except KeyboardInterrupt:
                logger.info("WiFi Manager wird beendet...")
                break
            except Exception as e:
                logger.error(f"❌ Unerwarteter Fehler: {e}")
                import traceback
                logger.error(traceback.format_exc())
                time.sleep(10)
        
        # Cleanup
        if self.hotspot_active:
            logger.info("🛑 Stoppe Hotspot beim Beenden...")
            self.stop_hotspot()

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
    manager.run()
