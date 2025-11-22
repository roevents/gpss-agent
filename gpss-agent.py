#!/usr/bin/env python3
"""
GPSS Vulnerability Management Agent
Simplified version with first-run token setup
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
from pathlib import Path

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

    def _is_first_run(self):
        """Check if this is first run (no config file)"""
        return not os.path.exists(self.config_path)

    def _get_token_from_user(self):
        """Prompt user for installation token"""
        print("\n" + "="*60)
        print("GPSS Vulnerability Management Agent - First Run Setup")
        print("="*60)
        print("\nThis agent requires an installation token to register.")
        print("Please obtain a token from your administrator.\n")

        while True:
            token = input("Enter installation token: ").strip()
            if len(token) >= 32:  # Basic validation
                return token
            print("Invalid token. Token must be at least 32 characters.")

    def _validate_token(self, token):
        """Validate token with server and get configuration"""
        print("\nValidating token with server...")

        try:
            # Prepare request
            url = f"{SERVER_URL}/install-tokens/validate"
            data = json.dumps({
                "token": token,
                "action": "install"
            }).encode('utf-8')

            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'GPSS-Agent/1.0'
                },
                method='POST'
            )

            # Create SSL context
            context = ssl.create_default_context()

            # Make request
            with urllib.request.urlopen(req, context=context, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))

            if result.get('success'):
                print("✓ Token validated successfully")

                # Extract configuration from response data
                data = result.get('data', {})
                config = {
                    'install_token': token,
                    'server_url': SERVER_URL,
                    'organization_id': data.get('organization_id'),
                    'department_id': data.get('department_id'),
                    'os_type': data.get('os_type'),
                    'hostname': socket.gethostname(),
                    'platform': self.platform
                }

                return config
            else:
                error = result.get('error', 'Unknown error')
                print(f"✗ Token validation failed: {error}")
                return None

        except urllib.error.HTTPError as e:
            error_msg = e.read().decode('utf-8') if e.fp else str(e)
            try:
                error_data = json.loads(error_msg)
                print(f"✗ Server error: {error_data.get('error', error_msg)}")
            except:
                print(f"✗ HTTP error {e.code}: {error_msg}")
            return None

        except Exception as e:
            print(f"✗ Connection error: {e}")
            return None

    def _register_with_server(self):
        """Register agent with server using install token"""
        print("\nRegistering agent with server...")

        try:
            # Prepare registration data
            url = f"{SERVER_URL}/agent/register"
            data = json.dumps({
                'install_token': self.config['install_token'],
                'hostname': self.config['hostname'],
                'os_type': self.config['os_type'],
                'platform': self.config['platform'],
                'organization_id': self.config['organization_id'],
                'department_id': self.config['department_id']
            }).encode('utf-8')

            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'GPSS-Agent/1.0'
                },
                method='POST'
            )

            context = ssl.create_default_context()

            with urllib.request.urlopen(req, context=context, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))

            if result.get('success'):
                agent_data = result.get('data', {})

                # Update config with permanent credentials
                self.config['agent_id'] = agent_data.get('id')
                self.config['api_key'] = agent_data.get('api_key')

                # Remove install token (no longer needed)
                del self.config['install_token']

                print(f"✓ Agent registered successfully (ID: {self.config['agent_id']})")
                return True
            else:
                print(f"✗ Registration failed: {result.get('error', 'Unknown error')}")
                return False

        except Exception as e:
            print(f"✗ Registration error: {e}")
            return False

    def _save_config(self):
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=2)

            # Set secure permissions
            if self.platform != "windows":
                os.chmod(self.config_path, 0o600)

            print(f"✓ Configuration saved to {self.config_path}")
            return True
        except Exception as e:
            print(f"✗ Failed to save configuration: {e}")
            return False

    def _load_config(self):
        """Load configuration from file"""
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
            return True
        except Exception as e:
            print(f"Error loading configuration: {e}")
            return False

    def _install_as_service(self):
        """Install agent as system service"""
        print("\nInstalling agent as system service...")

        try:
            if self.platform == "windows":
                return self._install_windows_service()
            elif self.platform == "darwin":
                return self._install_macos_service()
            else:  # Linux
                return self._install_linux_service()
        except Exception as e:
            print(f"✗ Service installation failed: {e}")
            return False

    def _install_windows_service(self):
        """Install as Windows service using NSSM or sc.exe"""
        try:
            # Get current executable path
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.abspath(__file__)

            # Try to use NSSM if available
            nssm_path = self._find_nssm()

            if nssm_path:
                # Install using NSSM
                subprocess.run([
                    nssm_path, 'install', 'GPSSAgent',
                    exe_path
                ], check=True)

                subprocess.run([
                    nssm_path, 'set', 'GPSSAgent',
                    'DisplayName', 'GPSS Vulnerability Management Agent'
                ], check=True)

                subprocess.run([
                    nssm_path, 'set', 'GPSSAgent',
                    'Description', 'Monitors and reports system vulnerabilities to GPSS server'
                ], check=True)

                subprocess.run([
                    nssm_path, 'start', 'GPSSAgent'
                ], check=True)

                print("✓ Installed as Windows service using NSSM")
                return True
            else:
                print("⚠ NSSM not found. Please install manually or run agent with --service flag")
                print(f"  Executable: {exe_path}")
                return False

        except subprocess.CalledProcessError as e:
            print(f"✗ Service installation failed: {e}")
            return False

    def _find_nssm(self):
        """Find NSSM executable"""
        # Check common locations
        locations = [
            "C:\\Program Files\\NSSM\\nssm.exe",
            "C:\\Program Files (x86)\\NSSM\\nssm.exe",
            "nssm.exe"  # In PATH
        ]

        for loc in locations:
            if os.path.exists(loc):
                return loc

        # Try to find in PATH
        try:
            result = subprocess.run(['where', 'nssm'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip().split('\n')[0]
        except:
            pass

        return None

    def _install_linux_service(self):
        """Install as Linux systemd service"""
        try:
            # Get current executable path
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.abspath(__file__)

            service_content = f"""[Unit]
Description=GPSS Vulnerability Management Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={exe_path}
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
"""

            service_path = "/etc/systemd/system/gpss-agent.service"

            with open(service_path, 'w') as f:
                f.write(service_content)

            # Reload systemd
            subprocess.run(['systemctl', 'daemon-reload'], check=True)

            # Enable and start service
            subprocess.run(['systemctl', 'enable', 'gpss-agent'], check=True)
            subprocess.run(['systemctl', 'start', 'gpss-agent'], check=True)

            print("✓ Installed as Linux systemd service")
            return True

        except Exception as e:
            print(f"✗ Service installation failed: {e}")
            return False

    def _install_macos_service(self):
        """Install as macOS LaunchDaemon"""
        try:
            # Get current executable path
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.abspath(__file__)

            plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>ro.gpss.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>{exe_path}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/var/log/gpss-agent.log</string>
    <key>StandardOutPath</key>
    <string>/var/log/gpss-agent.log</string>
</dict>
</plist>
"""

            plist_path = "/Library/LaunchDaemons/ro.gpss.agent.plist"

            with open(plist_path, 'w') as f:
                f.write(plist_content)

            # Load service
            subprocess.run(['launchctl', 'load', plist_path], check=True)

            print("✓ Installed as macOS LaunchDaemon")
            return True

        except Exception as e:
            print(f"✗ Service installation failed: {e}")
            return False

    def _send_heartbeat(self):
        """Send heartbeat to server"""
        try:
            url = f"{SERVER_URL}/agent/heartbeat"
            data = json.dumps({
                'agent_id': self.config['agent_id'],
                'status': 'online',
                'timestamp': int(time.time())
            }).encode('utf-8')

            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'GPSS-Agent/1.0'
                },
                method='POST'
            )

            context = ssl.create_default_context()

            with urllib.request.urlopen(req, context=context, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))

            return result.get('success', False)

        except Exception as e:
            print(f"Heartbeat error: {e}")
            return False

    def first_run_setup(self):
        """Handle first run setup"""
        print("\n" + "="*60)
        print("GPSS AGENT - FIRST RUN SETUP")
        print("="*60)

        # Get token from user
        token = self._get_token_from_user()

        # Validate token
        self.config = self._validate_token(token)
        if not self.config:
            print("\n✗ Setup failed. Please check your token and try again.")
            return False

        # Register with server
        if not self._register_with_server():
            print("\n✗ Setup failed. Could not register with server.")
            return False

        # Save configuration
        if not self._save_config():
            print("\n✗ Setup failed. Could not save configuration.")
            return False

        # Install as service
        print("\n" + "-"*60)
        print("INSTALLATION COMPLETE")
        print("-"*60)
        print(f"Agent ID: {self.config['agent_id']}")
        print(f"Organization ID: {self.config['organization_id']}")
        print(f"Department ID: {self.config['department_id']}")
        print(f"Config saved to: {self.config_path}")

        install_service = input("\nInstall as system service? (Y/n): ").strip().lower()
        if install_service != 'n':
            self._install_as_service()
        else:
            print("\nSkipping service installation.")
            print("You can run the agent manually or install as service later.")

        print("\n✓ Setup completed successfully!")
        return True

    def run(self):
        """Main agent loop"""
        print(f"GPSS Agent starting (Platform: {self.platform})")
        print(f"Agent ID: {self.config['agent_id']}")
        print(f"Server: {self.config['server_url']}")
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                # Send heartbeat
                if self._send_heartbeat():
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Heartbeat sent")
                else:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Heartbeat failed")

                # Wait for next heartbeat
                time.sleep(HEARTBEAT_INTERVAL)

        except KeyboardInterrupt:
            print("\n\nAgent stopped by user")
        except Exception as e:
            print(f"\n\nAgent error: {e}")

def main():
    """Main entry point"""
    agent = GPSSAgent()

    # Check if first run
    if agent._is_first_run():
        if not agent.first_run_setup():
            sys.exit(1)

        # Ask if user wants to start agent now
        start_now = input("\nStart agent now? (Y/n): ").strip().lower()
        if start_now == 'n':
            print("\nAgent configured but not started.")
            print("Run this executable again to start the agent.")
            sys.exit(0)
    else:
        # Load existing configuration
        if not agent._load_config():
            print("Failed to load configuration. Please delete config and run setup again.")
            sys.exit(1)

    # Run agent
    agent.run()

if __name__ == "__main__":
    main()
