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
COMMAND_CHECK_INTERVAL = 30  # seconds

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

    def _check_pending_commands(self):
        """Check for pending commands from server"""
        try:
            url = f"{SERVER_URL}/agent/commands/pending"

            req = urllib.request.Request(
                url,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'GPSS-Agent/2.0',
                    'X-Agent-ID': self.config['agent_id'],
                    'X-API-Key': self.config['api_key']
                },
                method='GET'
            )

            context = ssl.create_default_context()

            with urllib.request.urlopen(req, context=context, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))

            if result.get('success'):
                return result.get('data', {}).get('commands', [])

            return []

        except Exception as e:
            print(f"Command check error: {e}")
            return []

    def _execute_command(self, command):
        """Execute a command and return result"""
        command_id = command.get('id')
        command_type = command.get('command_type')
        params = command.get('parameters', {})

        print(f"\n[{time.strftime('%H:%M:%S')}] Executing command: {command_type}")

        try:
            if command_type == 'uninstall_software':
                result = self._uninstall_software(params.get('software_name'), params.get('uninstall_string'))
            elif command_type == 'update_agent':
                result = self._update_agent(params.get('download_url'))
            elif command_type == 'restart_agent':
                result = self._restart_agent()
            elif command_type == 'uninstall_agent':
                result = self._uninstall_agent()
            else:
                result = {'success': False, 'error': f'Unknown command type: {command_type}'}

            # Report command result
            self._report_command_result(command_id, result)

            return result

        except Exception as e:
            error_result = {'success': False, 'error': str(e)}
            self._report_command_result(command_id, error_result)
            return error_result

    def _uninstall_software(self, software_name, uninstall_string):
        """Uninstall software on Windows"""
        try:
            if not software_name or not uninstall_string:
                return {'success': False, 'error': 'Missing software name or uninstall string'}

            print(f"  Uninstalling: {software_name}")

            # Execute uninstall command silently
            if self.platform == 'windows':
                # Add silent flags if not present
                if '/quiet' not in uninstall_string.lower() and '/silent' not in uninstall_string.lower():
                    uninstall_string += ' /quiet /norestart'

                result = subprocess.run(
                    uninstall_string,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minutes max
                )

                if result.returncode == 0:
                    return {
                        'success': True,
                        'message': f'Successfully uninstalled {software_name}',
                        'output': result.stdout
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Uninstall failed with code {result.returncode}',
                        'output': result.stderr
                    }
            else:
                return {'success': False, 'error': 'Uninstall only supported on Windows'}

        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Uninstall timeout (5 minutes)'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _update_agent(self, download_url):
        """Update agent to new version"""
        try:
            if not download_url:
                return {'success': False, 'error': 'Missing download URL'}

            print(f"  Downloading update from: {download_url}")

            # Download new version
            temp_file = os.path.join(os.path.dirname(sys.executable), 'GPSS-Agent-Update.exe')

            req = urllib.request.Request(download_url, headers={'User-Agent': 'GPSS-Agent/2.0'})
            context = ssl.create_default_context()

            with urllib.request.urlopen(req, context=context, timeout=300) as response:
                with open(temp_file, 'wb') as f:
                    f.write(response.read())

            print(f"  Downloaded to: {temp_file}")

            # Replace current executable
            current_exe = sys.executable
            backup_exe = current_exe + '.bak'

            # Backup current version
            if os.path.exists(current_exe):
                if os.path.exists(backup_exe):
                    os.remove(backup_exe)
                os.rename(current_exe, backup_exe)

            # Move new version
            os.rename(temp_file, current_exe)

            print("  Update installed. Restarting...")

            # Restart agent
            if self.platform == 'windows':
                subprocess.Popen([current_exe], creationflags=subprocess.DETACHED_PROCESS)
            else:
                subprocess.Popen([current_exe])

            # Exit current process
            sys.exit(0)

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _restart_agent(self):
        """Restart the agent"""
        try:
            print("  Restarting agent...")

            current_exe = sys.executable

            if self.platform == 'windows':
                subprocess.Popen([current_exe], creationflags=subprocess.DETACHED_PROCESS)
            else:
                subprocess.Popen([current_exe])

            # Exit current process
            sys.exit(0)

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _uninstall_agent(self):
        """Uninstall the agent"""
        try:
            print("  Uninstalling agent...")

            # Remove config file
            if os.path.exists(self.config_path):
                os.remove(self.config_path)

            # Remove service/daemon
            if self.platform == 'windows':
                try:
                    subprocess.run(['sc', 'stop', 'GPSSAgent'], capture_output=True)
                    subprocess.run(['sc', 'delete', 'GPSSAgent'], capture_output=True)
                except:
                    pass
            elif self.platform == 'linux':
                try:
                    subprocess.run(['systemctl', 'stop', 'gpss-agent'], capture_output=True)
                    subprocess.run(['systemctl', 'disable', 'gpss-agent'], capture_output=True)
                    if os.path.exists('/etc/systemd/system/gpss-agent.service'):
                        os.remove('/etc/systemd/system/gpss-agent.service')
                except:
                    pass
            elif self.platform == 'darwin':
                try:
                    subprocess.run(['launchctl', 'unload', '/Library/LaunchDaemons/ro.gpss.agent.plist'], capture_output=True)
                    if os.path.exists('/Library/LaunchDaemons/ro.gpss.agent.plist'):
                        os.remove('/Library/LaunchDaemons/ro.gpss.agent.plist')
                except:
                    pass

            # Remove executable
            current_exe = sys.executable
            if os.path.exists(current_exe):
                # On Windows, we need to delete after exit
                if self.platform == 'windows':
                    bat_file = os.path.join(os.getenv('TEMP'), 'gpss-uninstall.bat')
                    with open(bat_file, 'w') as f:
                        f.write(f'@echo off\n')
                        f.write(f'timeout /t 2 /nobreak >nul\n')
                        f.write(f'del /f /q "{current_exe}"\n')
                        f.write(f'del /f /q "%~f0"\n')
                    subprocess.Popen([bat_file], shell=True, creationflags=subprocess.DETACHED_PROCESS)
                else:
                    os.remove(current_exe)

            print("  Agent uninstalled")
            sys.exit(0)

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _report_command_result(self, command_id, result):
        """Report command execution result to server"""
        try:
            url = f"{SERVER_URL}/agent/commands/result"

            data = json.dumps({
                'command_id': command_id,
                'result': result,
                'timestamp': int(time.time())
            }).encode('utf-8')

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

            with urllib.request.urlopen(req, context=context, timeout=30) as response:
                response_data = json.loads(response.read().decode('utf-8'))

            if result.get('success'):
                print(f"  ✓ Command completed successfully")
            else:
                print(f"  ✗ Command failed: {result.get('error')}")

        except Exception as e:
            print(f"  Error reporting result: {e}")

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

        last_heartbeat = 0
        last_command_check = 0

        try:
            while True:
                current_time = time.time()

                # Send heartbeat
                if current_time - last_heartbeat >= HEARTBEAT_INTERVAL:
                    if self._send_heartbeat():
                        print(f"[{time.strftime('%H:%M:%S')}] ✓ Heartbeat sent")
                    else:
                        print(f"[{time.strftime('%H:%M:%S')}] ✗ Heartbeat failed")
                    last_heartbeat = current_time

                # Check for pending commands
                if current_time - last_command_check >= COMMAND_CHECK_INTERVAL:
                    commands = self._check_pending_commands()
                    if commands:
                        print(f"[{time.strftime('%H:%M:%S')}] Found {len(commands)} pending command(s)")
                        for command in commands:
                            self._execute_command(command)
                    last_command_check = current_time

                # Sleep for a short time
                time.sleep(5)

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
