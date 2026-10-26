# Pix2Poly - 공식 COLMAP(사진측량, BSD) 릴리스를 내려받아 colmap\ 에 설치
# NVIDIA GPU 가 있으면 CUDA판(정밀 복원), 없으면 일반판(대략적인 형태). 출처: github.com/colmap/colmap/releases
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$ver = '4.2.1'
$kind = if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) { 'cuda' } else { 'nocuda' }
$url = "https://github.com/colmap/colmap/releases/download/$ver/colmap-x64-windows-$kind.zip"
try {
    Write-Host "COLMAP $ver ($kind) 내려받는 중... (CUDA판 약 400MB, 일반판 약 120MB)"
    Write-Host "  $url"
    Invoke-WebRequest -Uri $url -OutFile 'colmap-download.zip'
    if (Test-Path 'colmap-tmp') { Remove-Item -Recurse -Force 'colmap-tmp' }
    Expand-Archive -Force 'colmap-download.zip' 'colmap-tmp'
    $bat = Get-ChildItem -Recurse -Filter 'COLMAP.bat' 'colmap-tmp' | Select-Object -First 1
    if (-not $bat) { throw '압축 안에서 COLMAP.bat 을 찾지 못했습니다.' }
    if (Test-Path 'colmap') { Remove-Item -Recurse -Force 'colmap' }
    Move-Item $bat.DirectoryName 'colmap'
    Remove-Item -Recurse -Force 'colmap-tmp', 'colmap-download.zip' -ErrorAction SilentlyContinue
    & .\colmap\COLMAP.bat -h | Select-Object -First 2
    Write-Host ''
    Write-Host "설치 완료. run.bat 으로 Pix2Poly 를 실행하고 '여러 장'에 같은 물체 사진을 5장 이상 넣으세요."
} catch {
    Write-Host "실패: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host '인터넷 연결을 확인하고 다시 실행하세요.'
    exit 1
}
