# GPSS Agent - Automated Builds cu GitHub Actions

## Overview

Acest repository folosește GitHub Actions pentru a compila automat executabilele GPSS Agent pentru toate platformele:
- ✅ Windows 32-bit (.exe)
- ✅ Windows 64-bit (.exe)
- ✅ Linux AMD64 (binary)
- ✅ macOS x64 (binary)

## Cum funcționează

### Build automat

GitHub Actions compilează automat executabilele când:
1. Faci push pe branch-ul `main` sau `master`
2. Creezi un pull request
3. Creezi un tag de versiune (ex: `v1.0.0`)
4. Rulezi manual workflow-ul din GitHub UI

### Descărcarea executabilelor

După ce build-ul se termină cu succes:

1. **Din GitHub Actions UI:**
   - Mergi la tab-ul "Actions" în repository
   - Selectează ultimul workflow run
   - Descarcă artifacts:
     - `windows-executables` - Conține ambele .exe (32 & 64 bit)
     - `linux-executables` - Conține binary Linux
     - `macos-executables` - Conține binary macOS

2. **Din Releases (dacă ai creat un tag):**
   - Mergi la tab-ul "Releases"
   - Găsești toate executabilele atașate la release

## Cum să creezi un build nou

### Metodă 1: Push pe main/master

```bash
cd /Users/toor/Projects/gpss-fix/gpss-vm-standalone/agent
git add .
git commit -m "Update agent code"
git push origin main
```

GitHub Actions va începe automat build-ul.

### Metodă 2: Creare Release cu Tag

```bash
# Creează un tag de versiune
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

Acest lucru va:
1. Compila toate executabilele
2. Crea un GitHub Release
3. Atașa toate executabilele la release

### Metodă 3: Manual Dispatch

1. Mergi la repository pe GitHub
2. Click pe tab-ul "Actions"
3. Selectează "Build GPSS Agent Executables"
4. Click "Run workflow"
5. Selectează branch-ul
6. Click "Run workflow"

## Deploy pe server

După ce ai descărcat executabilele din GitHub Actions:

```bash
# Decomprimă artifacts (dacă e nevoie)
unzip windows-executables.zip
unzip linux-executables.zip
unzip macos-executables.zip

# Upload pe server
scp -P 22 GPSS-Agent-Windows-x64.exe root@vm.gpss.ro:/var/www/vm.gpss.ro/installers/
scp -P 22 GPSS-Agent-Windows-x86.exe root@vm.gpss.ro:/var/www/vm.gpss.ro/installers/
scp -P 22 gpss-agent-linux-amd64 root@vm.gpss.ro:/var/www/vm.gpss.ro/installers/
scp -P 22 gpss-agent-macos-x64 root@vm.gpss.ro:/var/www/vm.gpss.ro/installers/
```

## Actualizare DownloadController.php

După deploy, actualizează paths în `DownloadController.php`:

```php
private function getInstallerPath($osType) {
    $baseDir = '/var/www/vm.gpss.ro/installers';

    $paths = [
        'windows_32' => $baseDir . '/GPSS-Agent-Windows-x86.exe',
        'windows_64' => $baseDir . '/GPSS-Agent-Windows-x64.exe',
        'macos_64' => $baseDir . '/gpss-agent-macos-x64',
        'linux_deb_32' => $baseDir . '/gpss-agent-linux-amd64',
        'linux_deb_64' => $baseDir . '/gpss-agent-linux-amd64',
        'linux_rpm_32' => $baseDir . '/gpss-agent-linux-amd64',
        'linux_rpm_64' => $baseDir . '/gpss-agent-linux-amd64'
    ];

    return $paths[$osType] ?? null;
}
```

## Setup Repository

### Pas 1: Creează repository pe GitHub

```bash
cd /Users/toor/Projects/gpss-fix/gpss-vm-standalone/agent

# Inițializează git (dacă nu e deja)
git init

# Adaugă fișierele
git add .
git commit -m "Initial commit with GitHub Actions workflow"

# Adaugă remote (înlocuiește cu URL-ul tău)
git remote add origin https://github.com/USERNAME/gpss-agent.git

# Push
git push -u origin main
```

### Pas 2: Verifică GitHub Actions

1. Mergi la repository pe GitHub
2. Click pe tab-ul "Actions"
3. Ar trebui să vezi workflow-ul "Build GPSS Agent Executables" rulând

### Pas 3: Așteaptă completion

Build-ul durează aproximativ 5-10 minute pentru toate platformele.

## Troubleshooting

### Build failed pentru Windows

- Verifică că `gpss-agent.spec` este corect configurat
- Verifică că toate dependencies sunt listate în spec file

### Artifacts nu apar

- Verifică că workflow-ul s-a terminat cu succes (✓ verde)
- Artifacts sunt disponibile doar 90 de zile după build

### Nu pot descărca artifacts

- Trebuie să fii autentificat pe GitHub
- Trebuie să ai access la repository

## Beneficii GitHub Actions

✅ **Gratis** - GitHub oferă 2000 minute/lună gratis pentru repositories publice
✅ **Automat** - Build-uri la fiecare push
✅ **Multi-platform** - Compilează pentru Windows, Linux, macOS simultan
✅ **Reproductibil** - Același build environment de fiecare dată
✅ **Sigur** - Environment izolat, fără riscuri pentru server-ul tău
✅ **Versioning** - Păstrează istoricul tuturor build-urilor

## Alternative

Dacă GitHub Actions nu funcționează, alte opțiuni:

1. **GitLab CI/CD** - Similar cu GitHub Actions
2. **Docker multi-stage builds** - Local pe server
3. **Build manual pe Windows** - Dacă ai access la mașină Windows
