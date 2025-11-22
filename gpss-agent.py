#!/usr/bin/env python3
"""
GPSS Vulnerability Management Agent - FULL VERSION
Colectează date complete: CPU, RAM, Disk, IP intern, KB-uri, software, seriale Windows
"""

import os
import sys
import json
import time
import platform
import subprocess
import urllib.request
import urllib.error
import ssl
import hashlib
import socket
import re
from pathlib import Path
from datetime import datetime

# Configuration
SERVER_URL = "https://vm.gpss.ro/api"
CONFIG_FILE = "config.json"
HEARTBEAT_INTERVAL = 60  # seconds

class GPSSAgent:
    def __init__(self):
        self.config = None
        self.platform = platform.system().lower()
        self.config_path = self._get_config_path()

    def _get_config_path(self):
        """Get platform-specific config path"""
        if self.platform == "windows":
            config_dir = os.path.join(os.getenv('PROGRAMDATA', 'C:\\ProgramData'), 'GPSS', 'Agent')
        elif self.platform == "darwin":
            config_dir = "/Library/Application Support/GPSS/Agent"
        else:  # Linux
            config_dir = "/etc/gpss-agent"

        os.makedirs(config_dir, exist_ok=True)
        return os.path.join(config_dir, CONFIG_FILE)

    def _get_windows_version(self):
        """Get detailed Windows version"""
        try:
            result = subprocess.run(['wmic', 'os', 'get', 'Caption,Version,BuildNumber'],
                                  capture_output=True, text=True, timeout=10)
            lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
            if len(lines) > 1:
                return lines[1].strip()
        except:
            pass
        return platform.platform()

    def _get_windows_serial(self):
        """Get Windows product key/serial"""
        try:
            result = subprocess.run(['wmic', 'path', 'softwarelicensingservice', 'get', 'OA3xOriginalProductKey'],
                                  capture_output=True, text=True, timeout=10)
            lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
            if len(lines) > 1 and lines[1]:
                return lines[1].strip()
        except:
            pass
        return None

    def _get_installed_kbs(self):
        """Get installed Windows KB updates"""
        kbs = []
        try:
            result = subprocess.run(['wmic', 'qfe', 'get', 'HotFixID,InstalledOn'],
                                  capture_output=True, text=True, timeout=30)
            lines = result.stdout.strip().split('\n')
            for line in lines[1:]:  # Skip header
                if line.strip() and 'KB' in line:
                    parts = line.strip().split()
                    if parts:
                        kb_id = parts[0]
                        install_date = ' '.join(parts[1:]) if len(parts) > 1 else 'Unknown'
                        kbs.append({'kb_id': kb_id, 'installed_on': install_date})
        except Exception as e:
            print(f"Error getting KBs: {e}")
        return kbs

    def _get_installed_software(self):
        """Get installed software with versions"""
        software = []
        try:
            # Get from registry - 64-bit apps
            result = subprocess.run([
                'reg', 'query',
                'HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall',
                '/s'
            ], capture_output=True, text=True, timeout=60)

            software.extend(self._parse_registry_software(result.stdout))

            # Get from registry - 32-bit apps on 64-bit Windows
            if platform.machine().endswith('64'):
                result = subprocess.run([
                    'reg', 'query',
                    'HKLM\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall',
                    '/s'
                ], capture_output=True, text=True, timeout=60)
                software.extend(self._parse_registry_software(result.stdout))

        except Exception as e:
            print(f"Error getting software: {e}")

        return software[:500]  # Limit to 500 entries

    def _parse_registry_software(self, reg_output):
        """Parse registry output for software"""
        software = []
        current_app = {}

        for line in reg_output.split('\n'):
            line = line.strip()

            if line.startswith('HKEY_'):
                # Save previous app if it has a name
                if current_app.get('name'):
                    software.append(current_app)
                current_app = {}
            elif 'DisplayName' in line and 'REG_SZ' in line:
                name = line.split('REG_SZ')[-1].strip()
                if name:
                    current_app['name'] = name
            elif 'DisplayVersion' in line and 'REG_SZ' in line:
                version = line.split('REG_SZ')[-1].strip()
                if version:
                    current_app['version'] = version
            elif 'Publisher' in line and 'REG_SZ' in line:
                publisher = line.split('REG_SZ')[-1].strip()
                if publisher:
                    current_app['publisher'] = publisher

        # Add last app
        if current_app.get('name'):
            software.append(current_app)

        return software

    def _get_cpu_usage(self):
        """Get current CPU usage"""
        try:
            if self.platform == 'windows':
                result = subprocess.run(['wmic', 'cpu', 'get', 'loadpercentage'],
                                      capture_output=True, text=True, timeout=5)
                lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip() and l.strip().isdigit()]
                if lines:
                    return int(lines[0])
        except:
            pass
        return None

    def _get_ram_info(self):
        """Get RAM information"""
        try:
            if self.platform == 'windows':
                result = subprocess.run(['wmic', 'OS', 'get', 'TotalVisibleMemorySize,FreePhysicalMemory'],
                                      capture_output=True, text=True, timeout=5)
                lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 2:
                        free_kb = int(parts[0])
                        total_kb = int(parts[1])
                        used_kb = total_kb - free_kb
                        return {
                            'total_gb': round(total_kb / 1024 / 1024, 2),
                            'used_gb': round(used_kb / 1024 / 1024, 2),
                            'usage_percent': round((used_kb / total_kb) * 100, 2)
                        }
        except:
            pass
        return {'total_gb': None, 'used_gb': None, 'usage_percent': None}

    def _get_disk_info(self):
        """Get disk information"""
        try:
            if self.platform == 'windows':
                result = subprocess.run(['wmic', 'logicaldisk', 'where', 'drivetype=3',
                                       'get', 'size,freespace'],
                                      capture_output=True, text=True, timeout=5)
                lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
                if len(lines) > 1:
                    parts = lines[1].split()
                    if len(parts) >= 2:
                        free_bytes = int(parts[0])
                        total_bytes = int(parts[1])
                        used_bytes = total_bytes - free_bytes
                        return {
                            'total_gb': round(total_bytes / 1024 / 1024 / 1024, 2),
                            'used_gb': round(used_bytes / 1024 / 1024 / 1024, 2),
                            'usage_percent': round((used_bytes / total_bytes) * 100, 2)
                        }
        except:
            pass
        return {'total_gb': None, 'used_gb': None, 'usage_percent': None}

    def _get_internal_ip(self):
        """Get internal IP address"""
        try:
            # Create a socket to get the actual local IP (not 127.0.0.1)
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            try:
                # Fallback to hostname resolution
                return socket.gethostbyname(socket.gethostname())
            except:
                return None

    def _get_system_info(self):
        """Collect complete system information"""
        info = {
            'hostname': socket.gethostname(),
            'platform': self.platform,
            'os_version': self._get_windows_version() if self.platform == 'windows' else platform.platform(),
            'internal_ip': self._get_internal_ip(),
            'timestamp': datetime.now().isoformat()
        }

        # Get CPU info
        info['cpu_usage'] = self._get_cpu_usage()

        # Get RAM info
        ram_info = self._get_ram_info()
        info['ram_total_gb'] = ram_info['total_gb']
        info['ram_used_gb'] = ram_info['used_gb']
        info['ram_usage_percent'] = ram_info['usage_percent']

        # Get Disk info
        disk_info = self._get_disk_info()
        info['disk_total_gb'] = disk_info['total_gb']
        info['disk_used_gb'] = disk_info['used_gb']
        info['disk_usage_percent'] = disk_info['usage_percent']

        # Windows-specific data
        if self.platform == 'windows':
            info['windows_serial'] = self._get_windows_serial()
            info['installed_kbs'] = self._get_installed_kbs()
            info['installed_software'] = self._get_installed_software()

        return info

    def _send_heartbeat(self):
        """Send heartbeat with complete system info to server"""
        try:
            # Collect complete system info
            system_info = self._get_system_info()

            url = f"{SERVER_URL}/agent/heartbeat"

            # Prepare heartbeat data
            heartbeat_data = {
                'agent_id': self.config['agent_id'],
                'status': 'online',
                'timestamp': int(time.time()),
                'hostname': system_info.get('hostname'),
                'os_version': system_info.get('os_version'),
                'internal_ip': system_info.get('internal_ip'),
                'cpu_usage': system_info.get('cpu_usage'),
                'ram_total_gb': system_info.get('ram_total_gb'),
                'ram_used_gb': system_info.get('ram_used_gb'),
                'ram_usage_percent': system_info.get('ram_usage_percent'),
                'disk_total_gb': system_info.get('disk_total_gb'),
                'disk_used_gb': system_info.get('disk_used_gb'),
                'disk_usage_percent': system_info.get('disk_usage_percent'),
                'platform': system_info.get('platform')
            }

            # Add Windows-specific data
            if self.platform == 'windows':
                heartbeat_data['windows_serial'] = system_info.get('windows_serial')
                heartbeat_data['installed_kbs'] = system_info.get('installed_kbs', [])
                heartbeat_data['installed_software'] = system_info.get('installed_software', [])

            data = json.dumps(heartbeat_data).encode('utf-8')

            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'GPSS-Agent/2.0',
                    'X-Agent-ID': self.config['agent_id'],
                    'X-API-Key': self.config['api_key']
                },
                method='POST'
            )

            context = ssl.create_default_context()

            with urllib.request.urlopen(req, context=context, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))

            return result.get('success', False)

        except Exception as e:
            print(f"Heartbeat error: {e}")
            return False

    def _is_first_run(self):
        """Check if this is first run"""
        return not os.path.exists(self.config_path)

    def _get_token_from_user(self):
        """Prompt user for installation token"""
        print("\n" + "="*60)
        print("GPSS Agent - First Run Setup")
        print("="*60)
        print("\nEnter installation token from GPSS dashboard:\n")

        while True:
            token = input("Token: ").strip()
            if len(token) >= 32:
                return token
            print("Invalid token. Must be at least 32 characters.")

    def _validate_token(self, token):
        """Validate token with server"""
        print("\nValidating token...")
        try:
            url = f"{SERVER_URL}/install-tokens/validate"
            data = json.dumps({"token": token, "action": "install"}).encode('utf-8')

            req = urllib.request.Request(url, data=data,
                headers={'Content-Type': 'application/json', 'User-Agent': 'GPSS-Agent/2.0'},
                method='POST')

            context = ssl.create_default_context()
            with urllib.request.urlopen(req, context=context, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))

            if result.get('success'):
                print("✓ Token valid")
                data = result.get('data', {})
                return {
                    'install_token': token,
                    'server_url': SERVER_URL,
                    'organization_id': data.get('organization_id'),
                    'department_id': data.get('department_id'),
                    'os_type': data.get('os_type'),
                    'hostname': socket.gethostname(),
                    'platform': self.platform
                }
            else:
                print(f"✗ Token invalid: {result.get('error')}")
                return None
        except Exception as e:
            print(f"✗ Error: {e}")
            return None

    def _register_with_server(self):
        """Register agent with server"""
        print("\nRegistering agent...")
        try:
            url = f"{SERVER_URL}/agent/register"
            data = json.dumps({
                'install_token': self.config['install_token'],
                'hostname': self.config['hostname'],
                'os_type': self.config['os_type'],
                'platform': self.config['platform'],
                'organization_id': self.config['organization_id'],
                'department_id': self.config['department_id']
            }).encode('utf-8')

            req = urllib.request.Request(url, data=data,
                headers={'Content-Type': 'application/json', 'User-Agent': 'GPSS-Agent/2.0'},
                method='POST')

            context = ssl.create_default_context()
            with urllib.request.urlopen(req, context=context, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))

            if result.get('success'):
                agent_data = result.get('data', {})
                self.config['agent_id'] = agent_data.get('agent_id')
                self.config['api_key'] = agent_data.get('api_key')
                del self.config['install_token']
                print(f"✓ Registered (ID: {self.config['agent_id'][:8]}...)")
                return True
            else:
                print(f"✗ Registration failed: {result.get('error')}")
                return False
        except Exception as e:
            print(f"✗ Error: {e}")
            return False

    def _save_config(self):
        """Save configuration"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)
            if self.platform != "windows":
                os.chmod(self.config_path, 0o600)
            print(f"✓ Config saved to {self.config_path}")
            return True
        except Exception as e:
            print(f"✗ Save failed: {e}")
            return False

    def _load_config(self):
        """Load configuration"""
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            return True
        except Exception as e:
            print(f"Error loading config: {e}")
            return False

    def first_run_setup(self):
        """Handle first run setup"""
        print("\n" + "="*60)
        print("GPSS AGENT - FIRST RUN SETUP")
        print("="*60)

        token = self._get_token_from_user()
        self.config = self._validate_token(token)
        if not self.config:
            return False

        if not self._register_with_server():
            return False

        if not self._save_config():
            return False

        print("\n✓ Setup complete!")
        return True

    def run(self):
        """Main agent loop"""
        print(f"\nGPSS Agent v2.0 (Platform: {self.platform})")
        print(f"Agent ID: {self.config['agent_id']}")
        print(f"Server: {self.config['server_url']}")
        print(f"Hostname: {socket.gethostname()}")
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                if self._send_heartbeat():
                    print(f"[{time.strftime('%H:%M:%S')}] ✓ Heartbeat sent")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] ✗ Heartbeat failed")

                time.sleep(HEARTBEAT_INTERVAL)

        except KeyboardInterrupt:
            print("\n\nAgent stopped")
        except Exception as e:
            print(f"\n\nAgent error: {e}")

def main():
    """Main entry point"""
    agent = GPSSAgent()

    if agent._is_first_run():
        if not agent.first_run_setup():
            sys.exit(1)

        start_now = input("\nStart agent now? (Y/n): ").strip().lower()
        if start_now == 'n':
            print("\nAgent configured. Run again to start.")
            sys.exit(0)
    else:
        if not agent._load_config():
            print("Failed to load config. Delete config and run setup again.")
            sys.exit(1)

    agent.run()

if __name__ == "__main__":
    main()
