# La naissance d'une IA sur ce PC — la partie Windows.
# À lancer dans PowerShell EN ADMINISTRATEUR (clic droit sur « Windows PowerShell » > « Exécuter en tant qu'administrateur ») :
#   Set-ExecutionPolicy -Scope Process Bypass -Force; .\installer-windows.ps1
# Le script peut être relancé autant de fois qu'il faut : ce qui est fait est sauté. Il :
#   1. active WSL2 (Linux dans Windows) ; un redémarrage du PC peut être demandé, puis on relance le script ;
#   2. installe Ubuntu 24.04 (tu choisis un nom d'utilisateur et un mot de passe Linux) ;
#   3. règle le réseau de WSL (« mirrored » sur Windows 11 22H2 et plus ; le mode normal sinon) et le garde éveillé ;
#   4. crée une tâche planifiée qui démarre Ubuntu (et donc l'IA) à l'ouverture de ta session Windows ;
#   5. propose d'empêcher la mise en veille quand le PC est branché ;
#   6. lance la suite dans Ubuntu : naissance/installer.sh (Node, Python, Claude Code, les clés, son nom…).
#Requires -RunAsAdministrator
param(
  [string]$Distro = "Ubuntu-24.04",
  [string]$Depot = "https://github.com/a2la1213/hakim.git"
)
$ErrorActionPreference = "Stop"
$env:WSL_UTF8 = "1"                                   # les sorties de wsl.exe en UTF-8 (sinon de l'UTF-16 plein de zéros)
function Etape($t) { Write-Host "`n== $t" -ForegroundColor Magenta }
function Dire($t) { Write-Host "   $t" }
function Distros { ((& wsl.exe --list --quiet 2>$null) -join "`n") -replace "`0", "" -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ } }

Etape "0. Vérifications"
$os = Get-CimInstance Win32_OperatingSystem
$build = [int]$os.BuildNumber
Dire "$($os.Caption), build $build"
if ($build -lt 19041) { throw "WSL2 demande Windows 10 version 2004 (build 19041) ou plus récent : fais d'abord les mises à jour de Windows." }
$miroir = $build -ge 22621                             # le réseau « mirrored » n'existe que sur Windows 11 22H2 et plus
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
Dire "Processeur : $($cpu.Name.Trim()) ; mémoire : $([math]::Round($os.TotalVisibleMemorySize / 1MB)) Go"
if ($cpu.VirtualizationFirmwareEnabled -eq $false -and -not (Get-CimInstance Win32_ComputerSystem).HypervisorPresent) {
  Dire "ATTENTION : la virtualisation semble éteinte dans le BIOS (Intel VT-x). Si WSL refuse de démarrer, allume-la dans le BIOS (HP : F10 au démarrage > Advanced > System Options > Virtualization Technology)."
}

Etape "1. WSL2 (Linux dans Windows)"
& wsl.exe --status *> $null
if ($LASTEXITCODE -ne 0) {
  Dire "Installation de WSL…"
  & wsl.exe --install --no-distribution
  if ($LASTEXITCODE -ne 0) {                         # un vieux Windows 10 : les deux fonctions de Windows, à la main
    & dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
    & dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
  }
  Dire "WSL est installé. REDÉMARRE le PC, puis relance ce script : il reprendra ici."
  exit 0
}
& wsl.exe --update *> $null
& wsl.exe --set-default-version 2 *> $null
Dire "WSL2 est prêt."

Etape "2. Ubuntu ($Distro)"
if ((Distros) -notcontains $Distro) {
  Dire "Une fenêtre Ubuntu va s'ouvrir : choisis un nom d'utilisateur (en minuscules, sans espace) et un mot de passe."
  Dire "Note-les bien : le mot de passe te sera demandé par l'installateur (sudo). Puis tape « exit » dans cette fenêtre."
  & wsl.exe --install -d $Distro
  Read-Host "   Appuie sur Entrée ici quand Ubuntu est prêt (utilisateur créé, fenêtre fermée)"
}
if ((Distros) -notcontains $Distro) { throw "Ubuntu n'apparaît pas dans « wsl --list » : relance le script." }
& wsl.exe --set-default $Distro
Dire "Ubuntu est là."

Etape "3. Le réseau de WSL et son sommeil (fichier $env:USERPROFILE\.wslconfig)"
$conf = Join-Path $env:USERPROFILE ".wslconfig"
if ((Test-Path $conf) -and -not (Select-String -Path $conf -Pattern "naissance" -Quiet)) {
  Copy-Item $conf "$conf.avant-naissance" -Force
  Dire "ton ancien .wslconfig est gardé : $conf.avant-naissance"
}
$lignes = @("# ecrit par naissance/installer-windows.ps1", "[wsl2]", "vmIdleTimeout=-1", "localhostForwarding=true")
if ($miroir) { $lignes += "networkingMode=mirrored" }
Set-Content -Path $conf -Value $lignes -Encoding ASCII
if ($miroir) { Dire "réseau « mirrored » : Linux partage les adresses de Windows (le téléphone joint le PC par Tailscale)." }
else { Dire "Windows 10 : pas de réseau « mirrored » ; le mode normal suffit (le téléphone passe par Tailscale, dans Ubuntu)." }

Etape "4. systemd dans Ubuntu (les services de l'IA redémarrent seuls)"
& wsl.exe -d $Distro -u root -- bash -c "grep -q '^systemd *= *true' /etc/wsl.conf 2>/dev/null || printf '[boot]\nsystemd=true\n\n[interop]\nappendWindowsPath=false\n' >> /etc/wsl.conf"
& wsl.exe --shutdown
Start-Sleep -Seconds 3
Dire "WSL redémarré avec systemd."

Etape "5. Démarrer Ubuntu (et l'IA) à l'ouverture de ta session Windows"
$dossier = Join-Path $env:LOCALAPPDATA "Naissance"
New-Item -ItemType Directory -Force -Path $dossier | Out-Null
$vbs = Join-Path $dossier "garder-wsl.vbs"
# wscript lance wsl.exe SANS fenêtre ; « sleep infinity » garde Ubuntu vivant (ses services tournent tant qu'il vit)
Set-Content -Path $vbs -Encoding ASCII -Value @(
  'Set s = CreateObject("Wscript.Shell")',
  ('s.Run "wsl.exe -d ' + $Distro + ' --exec /bin/sleep infinity", 0, False')
)
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$vbs`""
$declencheur = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$reglages = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$qui = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName "Naissance - garder WSL" -Action $action -Trigger $declencheur -Settings $reglages -Principal $qui -Force | Out-Null
Start-ScheduledTask -TaskName "Naissance - garder WSL"
Dire "tâche planifiée « Naissance - garder WSL » créée et lancée (à chaque ouverture de session)."
Dire "Pour que l'IA revienne seule après un redémarrage (mises à jour), active l'ouverture de session automatique (netplwiz)."

Etape "6. La mise en veille"
$r = Read-Host "   Empêcher la mise en veille quand le PC est branché (l'IA reste joignable) ? [O/n]"
if ($r -notmatch '^[nN]') { & powercfg /change standby-timeout-ac 0; Dire "veille sur secteur : jamais." }

Etape "7. La suite, dans Ubuntu (ton mot de passe Linux sera demandé)"
$suite = "set -e; sudo apt-get update -qq; sudo apt-get install -y -qq git >/dev/null; " +
         "if [ -d ~/.naissance/hakim/.git ]; then git -C ~/.naissance/hakim pull --ff-only; else git clone --depth 1 $Depot ~/.naissance/hakim; fi; " +
         "bash ~/.naissance/hakim/anamnese/naissance/installer.sh"
& wsl.exe -d $Distro -- bash -lc $suite
if ($LASTEXITCODE -ne 0) { Dire "L'installation dans Ubuntu s'est arrêtée : lis le message au-dessus, puis relance ce script." ; exit 1 }

Etape "C'est fini"
Dire "Le cockpit : http://localhost:4317 dans ton navigateur Windows."
Dire "Sur ton téléphone : Tailscale (même compte), puis l'appli « Hakim libre » avec l'adresse donnée à l'étape Tailscale."
