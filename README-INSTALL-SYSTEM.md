# GPSS Agent Installer Distribution System

## Overview

This document describes the simplified, NIS2-compliant agent installer distribution system.

## System Architecture

### Flow

1. **Admin** generates installation token in web UI (Settings → Agent Installers)
2. **Admin** shares download link with user: `https://vm.gpss.ro/download/{TOKEN}`
3. **User** downloads agent executable (generic, works for all installs)
4. **User** runs agent executable
5. **Agent** detects first run (no config.json)
6. **Agent** prompts user to enter installation token
7. **Agent** validates token with server via `POST /api/install-tokens/validate`
8. **Server** validates token and returns:
   - organization_id
   - department_id
   - os_type
9. **Agent** saves configuration locally
10. **Agent** installs itself as system service
11. **Agent** starts and sends heartbeats to server

## Security Model

✅ **NO embedded tokens** - Agent is generic for everyone
✅ **Runtime token validation** - Token entered manually at first run
✅ **Organization/Department from token** - Stored in database, returned during validation
✅ **Token becomes invalid after use** - Single-use tokens by default
✅ **100% NIS2 compliant** - Full audit trail

## Files

### Frontend

- **AgentInstallers.jsx** - Token management UI
  - Create tokens with org/dept assignment
  - View token status (Active/Expired/Revoked/Used Up)
  - Copy download URLs
  - Revoke/Delete tokens

### Backend

- **InstallTokenController.php** - Token management
  - `create()` - Generate new install token (Super Admin only)
  - `getAll()` - List all tokens (Super Admin only)
  - `validateToken()` - **PUBLIC** endpoint for token validation
  - `revoke()` - Revoke a token (Super Admin only)
  - `delete()` - Delete a token (Super Admin only)

- **DownloadController.php** - Secure downloads
  - Validates token before serving installer
  - Tracks download count
  - Returns proper error pages

### Agent

- **gpss-agent.py** - Main agent with first-run setup
  - Detects first run (no config.json)
  - Prompts for installation token
  - Validates with server
  - Saves config (org_id + dept_id from server)
  - Self-installs as service
  - Sends heartbeats

## Database Schema

### install_tokens table

```sql
CREATE TABLE install_tokens (
    id SERIAL PRIMARY KEY,
    token VARCHAR(255) UNIQUE NOT NULL,
    created_by INTEGER REFERENCES users(id),
    organization_id INTEGER REFERENCES organizations(id),
    department_id INTEGER REFERENCES departments(id),
    description TEXT,
    os_type VARCHAR(50) NOT NULL,
    max_uses INTEGER DEFAULT 1,
    used_count INTEGER DEFAULT 0,
    download_count INTEGER DEFAULT 0,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    last_used_at TIMESTAMP,
    last_used_ip INET,
    revoked BOOLEAN DEFAULT FALSE,
    revoked_at TIMESTAMP,
    revoked_by INTEGER REFERENCES users(id),
    revocation_reason TEXT,
    ip_whitelist TEXT[],
    installer_checksum VARCHAR(64),
    installer_size_bytes BIGINT,
    metadata JSONB
);
```

## API Endpoints

### Token Validation (PUBLIC - NO AUTH)

```
POST /api/install-tokens/validate
Content-Type: application/json

{
  "token": "128-char-hex-token",
  "action": "install"
}
```

**Response (Success):**
```json
{
  "success": true,
  "valid": true,
  "os_type": "windows_64",
  "organization_id": 1,
  "department_id": 5,
  "data": {
    "os_type": "windows_64",
    "organization_id": 1,
    "department_id": 5
  },
  "message": "Token validated successfully"
}
```

**Response (Failed):**
```json
{
  "error": "Token validation failed",
  "details": [
    "Token has expired",
    "Token has reached maximum number of uses"
  ]
}
```

### Download Installer (PUBLIC - NO AUTH)

```
GET /download/{TOKEN}
```

Downloads the appropriate installer based on token's `os_type`.

## Building Executables

### Requirements

- Python 3.8+
- PyInstaller: `pip install pyinstaller`

### Build Commands

#### Linux
```bash
pyinstaller --onefile --name gpss-agent gpss-agent.py
```

#### Windows
```powershell
pyinstaller --onefile --name GPSS-Agent gpss-agent.py
```

#### macOS
```bash
pyinstaller --onefile --name GPSS-Agent gpss-agent.py
```

### Output

Executables are created in `dist/` directory:
- Linux: `gpss-agent`
- Windows: `GPSS-Agent.exe`
- macOS: `GPSS-Agent`

## Installation Process

### User Experience

1. User receives link: `https://vm.gpss.ro/download/abc123...`
2. User clicks link → Downloads agent executable
3. User runs executable:
   ```
   ============================================================
   GPSS Vulnerability Management Agent - First Run Setup
   ============================================================

   This agent requires an installation token to register.
   Please obtain a token from your administrator.

   Enter installation token: _
   ```
4. User enters token
5. Agent validates:
   ```
   Validating token with server...
   ✓ Token validated successfully

   Registering agent with server...
   ✓ Agent registered successfully (ID: abc123)
   ✓ Configuration saved to /etc/gpss-agent/config.json

   ------------------------------------------------------------
   INSTALLATION COMPLETE
   ------------------------------------------------------------
   Agent ID: abc123
   Organization ID: 1
   Department ID: 5
   Config saved to: /etc/gpss-agent/config.json

   Install as system service? (Y/n): _
   ```
6. Agent installs as service and starts

## Configuration Storage

### Linux
```
/etc/gpss-agent/config.json
```

### Windows
```
C:\ProgramData\GPSS\Agent\config.json
```

### macOS
```
/Library/Application Support/GPSS/Agent/config.json
```

### Config Format

```json
{
  "agent_id": "abc123...",
  "api_key": "def456...",
  "server_url": "https://vm.gpss.ro/api",
  "organization_id": 1,
  "department_id": 5,
  "os_type": "linux_deb_64",
  "hostname": "webserver-01",
  "platform": "linux"
}
```

**Note:** `install_token` is removed after registration for security.

## Service Installation

### Linux (systemd)

Created at: `/etc/systemd/system/gpss-agent.service`

```ini
[Unit]
Description=GPSS Vulnerability Management Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/gpss-agent
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
```

### Windows (NSSM)

Requires NSSM (Non-Sucking Service Manager):
```powershell
nssm install GPSSAgent "C:\Program Files\GPSS\gpss-agent.exe"
nssm set GPSSAgent DisplayName "GPSS Vulnerability Management Agent"
nssm set GPSSAgent Description "Monitors and reports system vulnerabilities to GPSS server"
nssm start GPSSAgent
```

### macOS (LaunchDaemon)

Created at: `/Library/LaunchDaemons/ro.gpss.agent.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>ro.gpss.agent</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/GPSS-Agent</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

## Status

### Completed

✅ Database schema (install_tokens table)
✅ Backend token controller with NIS2 compliance
✅ Frontend token management UI
✅ Token validation endpoint
✅ Download controller with security
✅ Agent with first-run setup
✅ Organization/Department assignment

### Pending

⏳ Agent registration endpoint (needs modification to use install_tokens)
⏳ Build PyInstaller specs for all platforms
⏳ Build executables (Windows, macOS, Linux)
⏳ End-to-end testing

## Next Steps

1. Modify agent registration to work with install_tokens instead of agent_tokens
2. Create PyInstaller spec files for each platform
3. Build executables on respective platforms
4. Test complete flow: download → install → register → heartbeat
5. Code sign executables (recommended for production)

## Security Notes

- Tokens are 128-character hex strings (64 random bytes)
- Default expiry: 7 days (configurable)
- Default max uses: 1 (single-use, configurable)
- All token operations logged with full audit trail
- IP whitelist support (optional)
- Config files have restrictive permissions (0600 on Linux/macOS)
- HTTPS required for all communication
- HMAC-based authentication after registration
