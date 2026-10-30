param(
  [Parameter(Mandatory=$true)][string]$PngDir,
  [Parameter(Mandatory=$true)][string]$OutFile,
  [string]$LangCode = 'zh-Hans-CN',
  [double]$Dpi = 0,
  [double]$Scale = 1.0,
  [switch]$Words
)
# -LangCode : OCR engine language tag. English books often do better with en-US
#             (dot leaders, ligatures, 'of'/'0f'); CJK books need zh-Hans-CN.
# -Dpi      : render dpi used for the PNGs. When > 0 it is written into the dump
#             header so ocr_rows.py cannot silently convert px with a wrong dpi.
# -Scale    : resize factor applied to the rendered image (1.0 = untouched).
#             Effective dpi for px->pt is Dpi*Scale.
# -Words    : emit one line per WORD instead of per OCR line.  Line output keeps
#             only the bbox of the first-to-last word, so the x of an inner token
#             (the folio in a running head, the page column of a TOC) is lost.
#             Word output feeds ocr_rows.py, which re-groups by baseline.
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $OutFile) { throw "Output already exists: $OutFile; choose a new path." }
if ($Dpi -lt 0 -or $Scale -le 0) { throw "Dpi must be >=0 and Scale > 0." }
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
  $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]
function Await($WinRtTask, $ResultType) {
  $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
  $netTask = $asTask.Invoke($null, @($WinRtTask))
  $netTask.Wait(-1) | Out-Null
  $netTask.Result
}
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime]
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime]
$null = [Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime]

$engine = $null
$usedLang = ''
try {
  $lang = New-Object Windows.Globalization.Language($LangCode)
  $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
  if ($null -ne $engine) { $usedLang = $engine.RecognizerLanguage.LanguageTag }
} catch { $engine = $null }
if ($null -eq $engine) {
  $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
  if ($null -ne $engine) { $usedLang = $engine.RecognizerLanguage.LanguageTag }
}
if ($null -eq $engine) { throw "No usable Windows OCR engine is installed." }
if ($usedLang -ne $LangCode) { Write-Warning ("requested language {0} unavailable, using {1}" -f $LangCode, $usedLang) }

$files = @(Get-ChildItem -LiteralPath $PngDir -Filter 'page_*.png' | Sort-Object Name)
if ($files.Count -eq 0) { throw "No page_*.png images in $PngDir" }
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add(("#dpi={0};scale={1};lang={2}" -f $Dpi, $Scale, $usedLang))
$files | ForEach-Object {
  $f = $_.FullName
  $sf = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($f)) ([Windows.Storage.StorageFile])
  $stream = Await ($sf.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
  $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  if ($bitmap.PixelWidth -gt [Windows.Media.Ocr.OcrEngine]::MaxImageDimension -or $bitmap.PixelHeight -gt [Windows.Media.Ocr.OcrEngine]::MaxImageDimension) { throw "Image exceeds OCR size limit: $f ($($bitmap.PixelWidth)x$($bitmap.PixelHeight)); resize and record the scale in -Scale." }
  $lines.Add(("##### " + $_.Name + (" size={0}x{1}" -f $bitmap.PixelWidth, $bitmap.PixelHeight)))
  $res = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
  foreach ($ln in $res.Lines) {
    $ws = @($ln.Words)
    if ($ws.Count -eq 0) { $lines.Add(("0`t0`t0`t0`t" + $ln.Text)); continue }
    if ($Words) {
      foreach ($w in $ws) {
        $r = $w.BoundingRect
        $lines.Add(("{0}`t{1}`t{2}`t{3}`t{4}" -f [int]$r.Y, [int]$r.X, [int]($r.X + $r.Width), [int]$r.Height, $w.Text))
      }
      continue
    }
    $x0 = [int]$ws[0].BoundingRect.X
    $y0 = [int]$ws[0].BoundingRect.Y
    $last = $ws[$ws.Count-1]
    $x1 = [int]($last.BoundingRect.X + $last.BoundingRect.Width)
    $h = [int]$ws[0].BoundingRect.Height
    $lines.Add(("{0}`t{1}`t{2}`t{3}`t{4}" -f $y0, $x0, $x1, $h, $ln.Text))
  }
  $stream.Dispose()
}
Set-Content -Path $OutFile -Value $lines -Encoding UTF8
Write-Output ("ocr done: " + ($lines.Count - 1) + " lines; lang=" + $usedLang + "; dpi=" + $Dpi + "; scale=" + $Scale)
