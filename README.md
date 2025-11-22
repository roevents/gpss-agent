# GPSS Vulnerability Management Agent

Agent Python pentru monitorizarea vulnerabilităților pe sisteme client, compatibil cu platformele Windows, Linux și macOS.

## Overview

GPSS Agent este un agent lightweight care:
- 🔍 Scanează sistemul pentru vulnerabilități
- 📊 Raportează rezultatele către server-ul central GPSS
- 🔄 Trimite heartbeat-uri regulate pentru monitoring
- 🔐 Se autentifică securizat folosind token-uri de instalare
- 🏢 Se asociază automat cu organizația și departamentul corect

## Platforme Suportate

- ✅ **Windows** (32-bit & 64-bit)
- ✅ **Linux** (DEB & RPM, 32-bit & 64-bit)
- ✅ **macOS** (64-bit, Intel & Apple Silicon)

## Instalare

### 1. Obține Token de Instalare

Administratorul sistemului trebuie să genereze un token de instalare din panoul web GPSS:
- Navighează la **Settings → Agent Installers**
- Click **Generate New Token**
- Selectează organizația, departamentul și tipul de OS
- Copiază link-ul de download

### 2. Descarcă Agent-ul

```bash
# Link-ul arată astfel:
https://vm.gpss.ro/download/{TOKEN}
```

Click pe link sau descarcă folosind curl:
```bash
curl -O https://vm.gpss.ro/download/{TOKEN}
```

### 3. Rulează Agent-ul

#### Windows

```powershell
# Rulează executabilul
.\GPSS-Agent.exe

# La prima rulare, vei fi întrebat pentru token-ul de instalare
```

#### Linux

```bash
# Fă fișierul executabil
chmod +x gpss-agent

# Rulează
sudo ./gpss-agent

# Introdu token-ul când ești întrebat
```

#### macOS

```bash
# Fă fișierul executabil
chmod +x GPSS-Agent

# Rulează
sudo ./GPSS-Agent

# Introdu token-ul când ești întrebat
```

### 4. Instalare ca Serviciu

După prima rulare reușită, agent-ul va întreba dacă dorești să îl instalezi ca serviciu de sistem:

```
Install as system service? (Y/n):
```

Răspunde `Y` pentru instalare automată ca:
- **Windows**: Windows Service (via NSSM)
- **Linux**: systemd service
- **macOS**: LaunchDaemon

## Configurare

După instalare, configurația este salvată în:

- **Windows**: `C:\ProgramData\GPSS\Agent\config.json`
- **Linux**: `/etc/gpss-agent/config.json`
- **macOS**: `/Library/Application Support/GPSS/Agent/config.json`

### Exemplu config.json

```json
{
  "agent_id": "abc123...",
  "api_key": "def456...",
  "server_url": "https://vm.gpss.ro/api",
  "organization_id": 1,
  "department_id": 5,
  "os_type": "windows_64",
  "hostname": "workstation-01",
  "platform": "windows"
}
```

## Dezvoltare

### Requirements

- Python 3.8+
- PyInstaller (pentru building executables)

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Build Executables

#### Opțiune 1: Build Local

```bash
# Linux/macOS
./build-all.sh

# Windows
python -m PyInstaller gpss-agent.spec
```

#### Opțiune 2: GitHub Actions (Recomandat)

Vezi [README-GITHUB-ACTIONS.md](README-GITHUB-ACTIONS.md) pentru detalii complete.

**Avantaje GitHub Actions:**
- ✅ Build automat pentru toate platformele simultan
- ✅ Gratis (2000 minute/lună)
- ✅ Environment consistent și reproductibil
- ✅ Fără configurare Wine sau cross-compilation

### Repository Structure

```
agent/
├── .github/
│   └── workflows/
│       └── build-agents.yml       # GitHub Actions workflow
├── gpss-agent.py                  # Main agent code
├── gpss-agent.spec                # PyInstaller spec file
├── build-all.sh                   # Local build script
├── .gitignore                     # Git ignore rules
├── README.md                      # Acest fișier
├── README-GITHUB-ACTIONS.md       # GitHub Actions guide
└── README-INSTALL-SYSTEM.md       # System documentation
```

## Securitate

- 🔐 Token-uri de instalare single-use (default)
- 🔑 HMAC-based authentication după înregistrare
- 🔒 HTTPS required pentru toate comunicațiile
- 📝 Full audit trail pentru compliance NIS2
- 🚫 Token-ul de instalare este șters după înregistrare

## Troubleshooting

### Agent nu se poate conecta la server

```bash
# Verifică conectivitatea
curl https://vm.gpss.ro/api/health

# Verifică configurația
cat /etc/gpss-agent/config.json  # Linux/macOS
type C:\ProgramData\GPSS\Agent\config.json  # Windows
```

### Token invalid

- Verifică că token-ul nu a expirat
- Verifică că token-ul nu a fost deja folosit (dacă max_uses=1)
- Contactează administratorul pentru un token nou

### Serviciul nu pornește

```bash
# Linux
sudo systemctl status gpss-agent
sudo journalctl -u gpss-agent -f

# macOS
sudo launchctl list | grep gpss
tail -f /var/log/system.log | grep GPSS

# Windows
Get-Service GPSSAgent
Get-EventLog -LogName Application -Source GPSSAgent -Newest 20
```

## Monitorizare

Agent-ul trimite:
- ✅ Heartbeat la fiecare 60 secunde
- ✅ Scan complet la fiecare 24 ore
- ✅ Rapoarte instant la detectarea vulnerabilităților noi

Statusul poate fi monitorizat în panoul web GPSS sub **Dashboard → Agents**.

## License

Proprietary - GPSS Vulnerability Manager

## Support

Pentru suport tehnic, contactează echipa GPSS la:
- Email: support@gpss.ro
- Website: https://vm.gpss.ro

---

**NIS2 Compliant** | **Production Ready** | **Multi-Platform**
