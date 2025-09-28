#!/usr/bin/env python3
import subprocess
import time
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class ConfigHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            html = '''<!DOCTYPE html>
<html><head>
<title>Prost WLAN Setup</title>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { font-family: Arial, sans-serif; margin: 20px; background: #f0f0f0; }
.container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 600px; margin: 0 auto; }
h1 { color: #2c3e50; text-align: center; }
.info { background: #e8f5e8; padding: 15px; border-radius: 5px; margin: 20px 0; }
.status { background: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; }
.network-list { background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0; }
.network-item { padding: 10px; margin: 5px 0; background: white; border-radius: 5px; cursor: pointer; border: 1px solid #ddd; }
.network-item:hover { background: #e9ecef; }
.network-item.selected { background: #007bff; color: white; }
.form-group { margin: 15px 0; }
label { display: block; margin-bottom: 5px; font-weight: bold; }
input[type="text"], input[type="password"] { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; box-sizing: border-box; }
button { background: #007bff; color: white; padding: 12px 24px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; width: 100%; margin: 10px 0; }
button:hover { background: #0056b3; }
button:disabled { background: #6c757d; cursor: not-allowed; }
.loading { text-align: center; color: #007bff; }
.error { background: #f8d7da; color: #721c24; padding: 10px; border-radius: 5px; margin: 10px 0; }
.success { background: #d4edda; color: #155724; padding: 10px; border-radius: 5px; margin: 10px 0; }
</style>
</head>
<body>
<div class="container">
<h1>🍻 Prost WLAN Setup</h1>
<div class="info">
<h3>📡 Hotspot-Informationen:</h3>
<p><strong>SSID:</strong> Prost-Setup</p>
<p><strong>Passwort:</strong> prost123</p>
<p><strong>IP-Adresse:</strong> 192.168.4.1</p>
</div>

<div id="status" class="status">
<h3>✅ Status:</h3>
<p>Hotspot ist aktiv und bereit für WLAN-Konfiguration!</p>
</div>

<div class="network-list">
<h3>📶 Verfügbare WLAN-Netzwerke:</h3>
<button onclick="scanNetworks()" id="scanBtn">Netzwerke scannen</button>
<div id="networks"></div>
</div>

<div id="connectForm" style="display: none;">
<h3>🔗 WLAN-Verbindung:</h3>
<div class="form-group">
<label>Netzwerk:</label>
<input type="text" id="selectedSSID" readonly>
</div>
<div class="form-group">
<label>Passwort:</label>
<input type="password" id="wifiPassword" placeholder="WLAN-Passwort eingeben">
</div>
<button onclick="connectToNetwork()" id="connectBtn">Verbinden</button>
<button onclick="cancelConnect()">Abbrechen</button>
</div>

<div id="messages"></div>
</div>

<script>
let selectedNetwork = null;

function showMessage(message, type = 'info') {
    const messagesDiv = document.getElementById('messages');
    const messageClass = type === 'error' ? 'error' : type === 'success' ? 'success' : 'status';
    messagesDiv.innerHTML = `<div class="${messageClass}">${message}</div>`;
}

function scanNetworks() {
    const scanBtn = document.getElementById('scanBtn');
    const networksDiv = document.getElementById('networks');
    
    scanBtn.disabled = true;
    scanBtn.textContent = 'Scanne...';
    networksDiv.innerHTML = '<div class="loading">Suche nach WLAN-Netzwerken...</div>';
    
    fetch('/scan')
        .then(response => response.json())
        .then(data => {
            scanBtn.disabled = false;
            scanBtn.textContent = 'Netzwerke scannen';
            
            if (data.success && data.networks.length > 0) {
                networksDiv.innerHTML = '';
                data.networks.forEach(network => {
                    const div = document.createElement('div');
                    div.className = 'network-item';
                    div.innerHTML = `<strong>${network.ssid}</strong><br><small>Signal: ${network.signal}%</small>`;
                    div.onclick = () => selectNetwork(network);
                    networksDiv.appendChild(div);
                });
                showMessage(`${data.networks.length} Netzwerke gefunden`, 'success');
            } else {
                networksDiv.innerHTML = '<div class="error">Keine Netzwerke gefunden. Bitte erneut scannen.</div>';
                showMessage('Keine WLAN-Netzwerke gefunden', 'error');
            }
        })
        .catch(error => {
            scanBtn.disabled = false;
            scanBtn.textContent = 'Netzwerke scannen';
            networksDiv.innerHTML = '<div class="error">Fehler beim Scannen der Netzwerke.</div>';
            showMessage('Fehler beim Netzwerk-Scan', 'error');
        });
}

function selectNetwork(network) {
    selectedNetwork = network;
    
    // Entferne vorherige Auswahl
    document.querySelectorAll('.network-item').forEach(item => {
        item.classList.remove('selected');
    });
    
    // Markiere ausgewähltes Netzwerk
    event.target.classList.add('selected');
    
    // Zeige Verbindungsformular
    document.getElementById('selectedSSID').value = network.ssid;
    document.getElementById('connectForm').style.display = 'block';
    document.getElementById('wifiPassword').focus();
}

function connectToNetwork() {
    const password = document.getElementById('wifiPassword').value;
    const connectBtn = document.getElementById('connectBtn');
    
    if (!password) {
        showMessage('Bitte Passwort eingeben', 'error');
        return;
    }
    
    connectBtn.disabled = true;
    connectBtn.textContent = 'Verbinde...';
    
    fetch('/connect', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            ssid: selectedNetwork.ssid,
            password: password
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showMessage('Verbindung erfolgreich! Hotspot wird gestoppt...', 'success');
            setTimeout(() => {
                showMessage('Verbindung hergestellt! Du kannst diese Seite jetzt schließen.', 'success');
            }, 3000);
        } else {
            showMessage(`Verbindung fehlgeschlagen: ${data.error}`, 'error');
            connectBtn.disabled = false;
            connectBtn.textContent = 'Verbinden';
        }
    })
    .catch(error => {
        showMessage('Fehler bei der Verbindung', 'error');
        connectBtn.disabled = false;
        connectBtn.textContent = 'Verbinden';
    });
}

function cancelConnect() {
    selectedNetwork = null;
    document.getElementById('connectForm').style.display = 'none';
    document.getElementById('wifiPassword').value = '';
    document.querySelectorAll('.network-item').forEach(item => {
        item.classList.remove('selected');
    });
}

// Automatisch Netzwerke scannen beim Laden
window.onload = function() {
    setTimeout(scanNetworks, 1000);
};
</script>
</body></html>'''
            self.wfile.write(html.encode('utf-8'))
        elif self.path == '/scan':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            networks = self.scan_wifi_networks()
            response = {'success': True, 'networks': networks}
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == '/connect':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            success = self.connect_to_wifi(data['ssid'], data['password'])
            response = {'success': success}
            if not success:
                response['error'] = 'Verbindung fehlgeschlagen'
            
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
    def scan_wifi_networks(self):
        """Scanne verfügbare WLAN-Netzwerke"""
        try:
            result = subprocess.run(['sudo', 'iwlist', 'wlan0', 'scan'], 
                                 capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                return []
            
            networks = []
            lines = result.stdout.split('\n')
            current_ssid = None
            current_signal = 0
            
            for line in lines:
                line = line.strip()
                if 'ESSID:' in line:
                    ssid = line.split('ESSID:')[1].strip().strip('"')
                    if ssid and ssid != '':
                        current_ssid = ssid
                elif 'Signal level=' in line:
                    signal_str = line.split('Signal level=')[1].split()[0]
                    try:
                        signal_db = int(signal_str)
                        # Konvertiere dBm zu Prozent (ungefähr)
                        signal_percent = max(0, min(100, (signal_db + 100) * 2))
                        current_signal = signal_percent
                    except:
                        current_signal = 50
                
                if current_ssid and current_ssid not in [n['ssid'] for n in networks]:
                    networks.append({
                        'ssid': current_ssid,
                        'signal': current_signal
                    })
            
            # Sortiere nach Signalstärke
            networks.sort(key=lambda x: x['signal'], reverse=True)
            return networks[:10]  # Top 10 Netzwerke
            
        except Exception as e:
            logger.error(f"Fehler beim Netzwerk-Scan: {e}")
            return []
    
    def connect_to_wifi(self, ssid, password):
        """Verbinde mit WLAN-Netzwerk"""
        try:
            logger.info(f"Verbinde mit WLAN: {ssid}")
            
            # Lösche alte Verbindung
            subprocess.run(['sudo', 'nmcli', 'connection', 'delete', ssid], 
                         capture_output=True)
            
            # Erstelle neue Verbindung
            cmd = ['sudo', 'nmcli', 'connection', 'add', 'type', 'wifi', 
                   'ifname', 'wlan0', 'con-name', ssid, 'ssid', ssid]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Fehler beim Erstellen der Verbindung: {result.stderr}")
                return False
            
            # Setze Passwort
            if password:
                cmd = ['sudo', 'nmcli', 'connection', 'modify', ssid, 
                       'wifi-sec.key-mgmt', 'wpa-psk', 'wifi-sec.psk', password]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.error(f"Fehler beim Setzen des Passworts: {result.stderr}")
                    return False
            
            # Aktiviere Verbindung
            cmd = ['sudo', 'nmcli', 'connection', 'up', ssid]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.error(f"Fehler beim Aktivieren der Verbindung: {result.stderr}")
                return False
            
            # Warte auf Verbindung
            time.sleep(5)
            
            # Prüfe Internet-Verbindung
            if self.check_internet_connection():
                logger.info(f"✅ Erfolgreich mit {ssid} verbunden")
                
                # Stoppe Hotspot
                subprocess.run(['sudo', 'nmcli', 'connection', 'down', 'Prost-Hotspot'], 
                             capture_output=True)
                
                # Starte Watchdog-Service neu
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
                
                return True
            else:
                logger.error("Verbindung hergestellt, aber kein Internet")
                return False
                
        except Exception as e:
            logger.error(f"Fehler bei WLAN-Verbindung: {e}")
            return False
    
    def check_internet_connection(self):
        """Prüfe Internet-Verbindung"""
        try:
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                ip = result.stdout.strip().split()[0]
                if not ip.startswith('192.168.4.'):
                    import socket
                    socket.setdefaulttimeout(3)
                    socket.gethostbyname('google.com')
                    return True
            return False
        except:
            return False

class WiFiManager:
    def __init__(self):
        self.hotspot_active = False
        self.hotspot_ssid = "Prost-Setup"
        self.hotspot_password = "prost123"
        self.hotspot_ip = "192.168.4.1"
        self.web_server_running = False
        
    def check_internet(self):
        try:
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                ip = result.stdout.strip().split()[0]
                if not ip.startswith('192.168.4.'):
                    import socket
                    socket.setdefaulttimeout(3)
                    socket.gethostbyname('google.com')
                    return True
            return False
        except:
            return False
    
    def start_web_server(self):
        if self.web_server_running:
            return
            
        def run_server():
            try:
                server = HTTPServer(('192.168.4.1', 8080), ConfigHandler)
                logger.info("🌐 Web-Server gestartet auf http://192.168.4.1:8080")
                self.web_server_running = True
                server.serve_forever()
            except Exception as e:
                logger.error(f"❌ Web-Server Fehler: {e}")
                self.web_server_running = False
        
        thread = threading.Thread(target=run_server, daemon=False)
        thread.start()
        time.sleep(2)  # Warte bis Server startet
    
    def start_hotspot(self):
        try:
            logger.info("🔥 Starte Hotspot...")
            
            # Lösche alte Verbindung
            subprocess.run(['sudo', 'nmcli', 'connection', 'delete', 'Prost-Hotspot'], 
                         capture_output=True)
            
            # Erstelle neue Verbindung
            cmd = ['sudo', 'nmcli', 'connection', 'add', 'type', 'wifi', 'ifname', 'wlan0',
                   'con-name', 'Prost-Hotspot', 'autoconnect', 'no', 'ssid', self.hotspot_ssid]
            subprocess.run(cmd, capture_output=True)
            
            # Konfiguriere
            configs = [
                ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 'wifi.mode', 'ap'],
                ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 'wifi-sec.key-mgmt', 'wpa-psk'],
                ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 'wifi-sec.psk', self.hotspot_password],
                ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 'ipv4.method', 'shared'],
                ['sudo', 'nmcli', 'connection', 'modify', 'Prost-Hotspot', 'ipv4.addresses', f'{self.hotspot_ip}/24']
            ]
            
            for cmd in configs:
                subprocess.run(cmd, capture_output=True)
            
            # Aktiviere
            subprocess.run(['sudo', 'nmcli', 'connection', 'up', 'Prost-Hotspot'], 
                         capture_output=True)
            
            time.sleep(5)
            self.hotspot_active = True
            
            # Starte Web-Server
            self.start_web_server()
            
            logger.info(f"✅ Hotspot {self.hotspot_ssid} gestartet")
            logger.info(f"📱 SSID: {self.hotspot_ssid}")
            logger.info(f"🔑 Passwort: {self.hotspot_password}")
            logger.info(f"🌐 IP: {self.hotspot_ip}")
            logger.info(f"🌐 Web-Server: http://{self.hotspot_ip}:8080")
            return True
            
        except Exception as e:
            logger.error(f"❌ Hotspot-Fehler: {e}")
            return False
    
    def run(self):
        logger.info("🍻 WiFi Manager mit vollständigem Web-Setup gestartet")
        time.sleep(10)
        
        if not self.check_internet():
            logger.info("❌ Kein Internet - starte Hotspot")
            self.start_hotspot()
        else:
            logger.info("✅ Internet verfügbar")
        
        while True:
            try:
                if self.check_internet():
                    if self.hotspot_active:
                        logger.info("✅ Internet verfügbar - stoppe Hotspot")
                        subprocess.run(['sudo', 'nmcli', 'connection', 'down', 'Prost-Hotspot'], 
                                     capture_output=True)
                        self.hotspot_active = False
                        self.web_server_running = False
                else:
                    if not self.hotspot_active:
                        logger.info("❌ Kein Internet - starte Hotspot")
                        self.start_hotspot()
                
                time.sleep(20)
                
            except KeyboardInterrupt:
                logger.info("🛑 WiFi Manager wird beendet...")
                break
            except Exception as e:
                logger.error(f"❌ Fehler: {e}")
                time.sleep(10)

if __name__ == "__main__":
    manager = WiFiManager()
    manager.run()
