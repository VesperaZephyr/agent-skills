param(
  [Parameter(Mandatory=$true)][string]$PngDir,
  [Parameter(Mandatory=$true)][string]$OutFile
)
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
$lang = New-Object Windows.Globalization.Language("zh-Hans-CN")
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
if ($null -eq $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if ($null -eq $engine) { Set-Content -Path $OutFile -Value "NO_ENGINE" -Encoding UTF8; exit 1 }

$lines = New-Object System.Collections.Generic.List[string]
Get-ChildItem -Path $PngDir -Filter "page_*.png" | Sort-Object Name | ForEach-Object {
  $f = $_.FullName
  $sf = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($f)) ([Windows.Storage.StorageFile])
  $stream = Await ($sf.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
  $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
  $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
  $res = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
  $lines.Add("##### " + $_.Name)
  foreach ($ln in $res.Lines) {
    $ws = @($ln.Words)
    if ($ws.Count -eq 0) { $lines.Add(("0`t0`t0`t0`t" + $ln.Text)); continue }
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
Write-Output ("ocr done: " + $lines.Count + " lines")
