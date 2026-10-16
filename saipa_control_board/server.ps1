# =====================================================================
#  Saipa Mashayekh - shared server for the repair-hall control board
#  Uses only Windows PowerShell (built into Windows 10/11): nothing to install.
#  Started by start_server.bat. Other computers open http://<this-pc-ip>:<port>
#
#  Storage : data\board.json (+ data\version.txt), daily copies in
#            data\backups (60 days kept), every save logged in data\changes.log
#  Saving  : a page sends the whole board together with the version it was
#            based on. If someone else saved in between, the server answers
#            "conflict" with the newest data and the page re-applies its change
#            on top of it - so simultaneous users never overwrite each other.
# =====================================================================
param([int]$Port = 8080)

$ErrorActionPreference = 'Stop'
$Base       = Split-Path -Parent $MyInvocation.MyCommand.Path
$DataDir    = Join-Path $Base 'data'
$BackupDir  = Join-Path $DataDir 'backups'
$DataFile   = Join-Path $DataDir 'board.json'
$VerFile    = Join-Path $DataDir 'version.txt'
$LogFile    = Join-Path $DataDir 'changes.log'
$BoardFile  = Join-Path $Base 'board.html'
$Utf8       = New-Object System.Text.UTF8Encoding($false)
$MaxBody    = 20MB

foreach ($d in @($DataDir, $BackupDir)) { if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null } }
if (-not (Test-Path $DataFile)) { [IO.File]::WriteAllText($DataFile, '{"workers":[],"cars":[]}', $Utf8) }
$script:Version = 0
if (Test-Path $VerFile) { $script:Version = [long]([IO.File]::ReadAllText($VerFile).Trim()) }
$script:DataText = [IO.File]::ReadAllText($DataFile, $Utf8)

function Save-Board([string]$text, [string]$ip) {
    $stamp = Get-Date -Format 'yyyyMMdd'
    $daily = Join-Path $BackupDir ("board_$stamp.json")
    if (-not (Test-Path $daily)) {
        Copy-Item $DataFile $daily
        Get-ChildItem $BackupDir -Filter 'board_*.json' | Sort-Object Name -Descending | Select-Object -Skip 60 | Remove-Item -ErrorAction SilentlyContinue
    }
    $tmp = "$DataFile.tmp"
    [IO.File]::WriteAllText($tmp, $text, $Utf8)
    [IO.File]::Copy($tmp, $DataFile, $true)
    Remove-Item $tmp -ErrorAction SilentlyContinue
    $script:Version = $script:Version + 1
    [IO.File]::WriteAllText($VerFile, [string]$script:Version, $Utf8)
    $script:DataText = $text
    $line = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + "`t" + $ip + "`tversion " + $script:Version + "`t" + $text.Length + " bytes`r`n"
    [IO.File]::AppendAllText($LogFile, $line, $Utf8)
}

function Send-Response($stream, [int]$status, [string]$contentType, [byte[]]$body, [string]$extraHeaders) {
    $reason = @{ 200 = 'OK'; 204 = 'No Content'; 400 = 'Bad Request'; 404 = 'Not Found'; 409 = 'Conflict'; 500 = 'Server Error' }[$status]
    $head = "HTTP/1.1 $status $reason`r`n" +
            "Content-Type: $contentType`r`n" +
            "Content-Length: $($body.Length)`r`n" +
            "Cache-Control: no-store`r`n" +
            "Access-Control-Allow-Origin: *`r`n" +
            "Access-Control-Allow-Methods: GET, POST, OPTIONS`r`n" +
            "Access-Control-Allow-Headers: Content-Type`r`n" +
            "Access-Control-Allow-Private-Network: true`r`n" +
            $extraHeaders +
            "Connection: close`r`n`r`n"
    $hb = [Text.Encoding]::ASCII.GetBytes($head)
    $stream.Write($hb, 0, $hb.Length)
    if ($body.Length -gt 0) { $stream.Write($body, 0, $body.Length) }
    $stream.Flush()
}

function Send-Json($stream, [int]$status, [string]$json) {
    Send-Response $stream $status 'application/json; charset=utf-8' ($Utf8.GetBytes($json)) ''
}

function Handle-Client($client) {
    $client.ReceiveTimeout = 10000
    $client.SendTimeout = 10000
    $stream = $client.GetStream()
    $ip = ([Net.IPEndPoint]$client.Client.RemoteEndPoint).Address.ToString()

    # --- read the request head
    $buf = New-Object byte[] 65536
    $ms = New-Object IO.MemoryStream
    $headEnd = -1
    while ($headEnd -lt 0) {
        $n = $stream.Read($buf, 0, $buf.Length)
        if ($n -le 0) { return }
        $ms.Write($buf, 0, $n)
        $all = $ms.ToArray()
        for ($i = [Math]::Max(0, $all.Length - $n - 3); $i -le $all.Length - 4; $i++) {
            if ($all[$i] -eq 13 -and $all[$i + 1] -eq 10 -and $all[$i + 2] -eq 13 -and $all[$i + 3] -eq 10) { $headEnd = $i; break }
        }
        if ($all.Length -gt 65536 -and $headEnd -lt 0) { return }
    }
    $all = $ms.ToArray()
    $headText = [Text.Encoding]::ASCII.GetString($all, 0, $headEnd)
    $lines = $headText -split "`r`n"
    $parts = $lines[0] -split ' '
    $method = $parts[0]
    $target = $parts[1]
    $length = 0
    foreach ($l in $lines) { if ($l -match '^(?i)content-length:\s*(\d+)') { $length = [long]$Matches[1] } }
    if ($length -gt $MaxBody) { Send-Json $stream 400 '{"ok":false,"error":"too large"}'; return }

    # --- read the body
    $bodyStart = $headEnd + 4
    $body = New-Object IO.MemoryStream
    if ($all.Length -gt $bodyStart) { $body.Write($all, $bodyStart, $all.Length - $bodyStart) }
    while ($body.Length -lt $length) {
        $n = $stream.Read($buf, 0, $buf.Length)
        if ($n -le 0) { break }
        $body.Write($buf, 0, $n)
    }
    $bodyText = $Utf8.GetString($body.ToArray())

    $path = $target
    $query = ''
    $q = $target.IndexOf('?')
    if ($q -ge 0) { $path = $target.Substring(0, $q); $query = $target.Substring($q + 1) }

    if ($method -eq 'OPTIONS') { Send-Response $stream 204 'text/plain' (New-Object byte[] 0) ''; return }

    if ($method -eq 'GET' -and ($path -eq '/' -or $path -eq '/index.html' -or $path -eq '/board.html')) {
        Send-Response $stream 200 'text/html; charset=utf-8' ([IO.File]::ReadAllBytes($BoardFile)) ''
        return
    }
    if ($method -eq 'GET' -and $path -eq '/api/version') {
        Send-Json $stream 200 ('{"ok":true,"version":' + $script:Version + '}')
        return
    }
    if ($method -eq 'GET' -and $path -eq '/api/state') {
        Send-Json $stream 200 ('{"ok":true,"version":' + $script:Version + ',"data":' + $script:DataText + '}')
        return
    }
    if ($method -eq 'GET' -and $path -eq '/api/export') {
        $name = 'mashayekh_board_backup_' + (Get-Date -Format 'yyyyMMdd_HHmm') + '.json'
        Send-Response $stream 200 'application/json; charset=utf-8' ($Utf8.GetBytes($script:DataText)) "Content-Disposition: attachment; filename=`"$name`"`r`n"
        return
    }
    if ($method -eq 'POST' -and $path -eq '/api/save') {
        $baseVer = -1
        if ($query -match '(?:^|&)base=(-?\d+)') { $baseVer = [long]$Matches[1] }
        if ($baseVer -ne $script:Version) {
            Send-Json $stream 409 ('{"ok":false,"conflict":true,"version":' + $script:Version + ',"data":' + $script:DataText + '}')
            return
        }
        $t = $bodyText.Trim()
        # Light check only (fast even for years of data): it must be a board object.
        $valid = $t.StartsWith('{') -and $t.EndsWith('}') -and $t.Contains('"cars"') -and $t.Contains('"workers"')
        if (-not $valid) { Send-Json $stream 400 '{"ok":false,"error":"invalid data"}'; return }
        Save-Board $t $ip
        Send-Json $stream 200 ('{"ok":true,"version":' + $script:Version + '}')
        return
    }
    Send-Json $stream 404 '{"ok":false,"error":"not found"}'
}

# ---------------------------------------------------------------- start
$listener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Any, $Port)
try {
    $listener.Start()
} catch {
    Write-Host ''
    Write-Host "  Port $Port is already in use." -ForegroundColor Yellow
    Write-Host '  The server is probably already running in another window.'
    Write-Host "  Opening http://localhost:$Port ..."
    try { Start-Process "http://localhost:$Port" } catch {}
    exit 2
}

$ips = @()
try {
    $ips = [Net.Dns]::GetHostAddresses([Net.Dns]::GetHostName()) |
        Where-Object { $_.AddressFamily -eq 'InterNetwork' -and -not $_.ToString().StartsWith('127.') } |
        ForEach-Object { $_.ToString() }
} catch {}
Write-Host '============================================================' -ForegroundColor Green
Write-Host '  Saipa Mashayekh control board server is RUNNING' -ForegroundColor Green
Write-Host "  This computer   : http://localhost:$Port"
foreach ($a in $ips) { Write-Host "  Other computers : http://${a}:$Port" -ForegroundColor Cyan }
Write-Host "  Data file       : $DataFile"
Write-Host '  Keep this window open (minimize it). Closing it stops the board.'
Write-Host '============================================================' -ForegroundColor Green
if ($env:SAIPA_NO_BROWSER -ne '1') { try { Start-Process "http://localhost:$Port" } catch {} }

while ($true) {
    $client = $listener.AcceptTcpClient()
    try {
        Handle-Client $client
    } catch {
        try { Send-Json $client.GetStream() 500 '{"ok":false,"error":"server error"}' } catch {}
        Write-Host ('  ' + (Get-Date -Format 'HH:mm:ss') + '  error: ' + $_.Exception.Message) -ForegroundColor Red
    } finally {
        $client.Close()
    }
}
