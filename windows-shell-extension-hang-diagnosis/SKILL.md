---
name: windows-shell-extension-hang-diagnosis
description: Diagnose and repair Windows explorer.exe hangs, freezes, and slow right-click menus caused by broken or orphaned shell extensions. Use when the file explorer freezes on a specific folder, when right-clicking hangs, when a folder full of one file type (e.g. PDFs) freezes, or after a drive-letter migration / software uninstall left dangling registry references. Covers ContextMenuHandlers, .pdf ShellEx handlers, icon overlay identifiers, orphan CLSIDs, the official HKCU Blocked mitigation, and the process-topology step that decides whether a registry fix ever takes effect (one desktop shell plus per-window explorer.exe host processes). Also covers the SEPARATE, Blocked-immune packaged (MSIX / Store / sparse) context-menu mechanism, whose handlers are instantiated in dllhost.exe / StoreDesktopExtension.exe instead of explorer.exe, and whose typical failure mode is a dead "external content root" left behind by a drive migration.
agent_created: true
---

# Windows Shell Extension Hang Diagnosis

Diagnose why `explorer.exe` hangs — either on a specific folder or on right-click — and
produce a reversible fix. The root cause is almost never "too many files". It is almost
always **a shell extension that fails to load or activate slowly**.

## Golden rule

A frozen explorer is a **hang, not a crash**. A crash leaves an `Application Error`
(Event 1000) log entry; a hang leaves an `Application Hang` (Event 1002) entry. If you
find neither, the process is still *alive and waiting* — so the cause is something it is
**waiting on**, not something that broke.

## Step -1 — Establish WHICH context menu hangs (ask before anything else)

Windows 11 has **two** right-click menus, built by completely different code:

| Menu | Contents | Are legacy shellex handlers loaded? |
|---|---|---|
| modern menu (default) | WinUI/XAML, `IExplorerCommand` verbs only | **NO** |
| classic menu, reached via **"Show more options"** / Shift+F10 | every `IExplorerCommand` **plus** every `shellex\ContextMenuHandlers` COM handler | **YES** |

So "right-click hangs" is ambiguous and the answer changes the whole diagnosis:

- **If the menu appears instantly but "Show more options" hangs**, the fault is in the
  classic menu build — i.e. exactly the `*\shellex\ContextMenuHandlers` set. Ask this
  question explicitly; it halves the search space in one sentence.
- **If the modern menu itself hangs**, the `shellex` handlers are *not involved*. Look at
  `IExplorerCommand` verbs (`ExplorerCommandHandler` values under `shell\verb`), at
  `OpenWithProgids` enumeration for the "Open with" flyout, and at the icon-overlay set.
  Blocking `ContextMenuHandlers` will do nothing.

A folder that used to hang and a right-click that hangs are frequently **one** cause, not
two — the user right-clicks the files in that folder far more often than they do anything
else with them.

**There is a third mechanism, and it is invisible to a classic scan.** Besides the two
menus above, Windows also serves context-menu verbs declared *inside MSIX / Store / sparse
package manifests*. Those handlers are instantiated in a **separate surrogate process**, are
registered under `HKCR\PackagedCom` rather than `HKCR\CLSID`, and are therefore **not
affected by the `Blocked` key at all**. A complete classic-side fix can be applied and the
hang will remain exactly as before. See Step 2d before concluding anything.

## Step 0 — Environment reality check (do this first)

In sandboxed/agent environments the PowerShell tool is often crippled for system queries:

- `Get-WinEvent`, `Get-Volume`, `Get-PhysicalDisk`, `Get-CimInstance Win32_*` may return
  **empty output with exit code 0** — silently. Never read that as "no problems found".
- `New-Object -ComObject` (e.g. `WScript.Shell`) is refused outright.
- Calling `powershell.exe` from bash is refused.

**Working alternatives:**

```bash
# Event log (works from bash; /q: needs MSYS_NO_PATHCONV)
export MSYS_NO_PATHCONV=1
wevtutil qe Application "/q:*[System[Provider[@Name='Application Hang']]]" /c:25 /f:text /rd:true
wevtutil qe Application "/q:*[System[(EventID=1001)]]" /c:10 /f:text /rd:true   # WER / MoAppCrash
wevtutil qe System      "/q:*[System[(EventID=7 or EventID=11 or EventID=51 or EventID=129 or EventID=153)]]" /c:20 /f:text /rd:true   # disk errors
```

Registry and filesystem reads: use Python with `winreg` / `os` — reliable.

### Confirmed program blacklist / hangs (measured on this machine, Windows 11 26100)

Two different failure modes — do not confuse them:

| Symptom when invoked from a script | Programs |
|---|---|
| **Blocked outright** ("Program BLOCKED BY SECURITY POLICY … cannot be approved or bypassed") | `reg.exe`, `sc.exe`, `wmic.exe` |
| **Hangs forever** (no output, no exit — even with a 10 s `subprocess` timeout it is the *outer* `timeout` that has to kill it) | `tasklist` (any form, with or without `/fi`), `driverquery` |

Consequences:

- Enumeration of processes and their loaded modules **must** go through ctypes +
  Toolhelp32; never shell out to `tasklist`:

```python
k32.CreateToolhelp32Snapshot(0x2, 0)                    # TH32CS_SNAPPROCESS
k32.CreateToolhelp32Snapshot(0x8 | 0x10, pid)           # SNAPMODULE | SNAPMODULE32
# PROCESSENTRY32  -> th32ProcessID, th32ParentProcessID, cntThreads, szExeFile  (ANSI)
# MODULEENTRY32   -> szModule, szExePath
```

- Services and file-system filter drivers come from `HKLM\SYSTEM\CurrentControlSet\Services`
  (`Type` 1 = kernel driver, 2 = file-system driver, 16 = own-process service; `Group`
  beginning `FSFilter` marks a minifilter; `ImagePath`, `Start`). `fltmc` needs
  administrator and returns `0x80070005` otherwise.
- Working without admin: `wevtutil`, `net use`, `subst`, `fsutil`. **Pass `wevtutil`
  arguments as a list** (`subprocess.run(['wevtutil','qe','Application','/q:…','/c:5','/f:text'])`) —
  with `shell=True` on Git Bash, `/c:5` is rewritten into a path and the call fails with
  "指定的参数太多".
- From Git Bash, prefix external commands with `MSYS_NO_PATHCONV=1` or `/fi`, `/fo` are
  mangled into `C:/…/PortableGit/…/fi`.

### The cheapest high-value artefact: the WER report

When a process hangs, Windows writes
`%ProgramData%\Microsoft\Windows\WER\ReportArchive\AppHang_<Name>_<hash>_…\Report.wer`
(UTF-16LE; `AppHangXProc`/`MoAppHang` variants too). **For a surrogate hang this file
names the package outright** — it is far more informative than the Event Log entry, which
only says "程序 dllhost.exe 停止与 Windows 交互":

```
EventType=MoAppHang
OriginalFilename=dllhost.exe
Sig[0].Name=Package Full Name
Sig[0].Value=FoxitPDFEditorCoreApp_2.0.0.0_x64__p8w8vzan42gcw
AppName=COM Surrogate
AppPath=C:\Windows\System32\dllhost.exe
ConsentKey=AppHangXProcB1
```

The directory *name* (`AppHang_FoxitPDFEditorCo_…`) already carries the culprit. Always
list `ReportArchive` / `ReportQueue` (both `%ProgramData%` and `%LOCALAPPDATA%`), sort by
mtime, and read `Report.wer` for `AppHang*` / `AppCrash*` entries — `AppCrash_<PackageName>_…`
does the same for crashes. Same trick for `Application Error` 1000: the `Faulting 包全名`
field names the package.

## Step 0.5 — Process topology: there is not one explorer, there are many

**This step decides whether your fix will appear to work or appear to do nothing.**

A registry edit only affects processes that **start after** it is written. On both
Windows 10 and 11 there is normally more than one `explorer.exe` running, and the tasks
they own are different:

| Process | Command line | Owns |
|---|---|---|
| the desktop shell | `C:\Windows\Explorer.EXE` | `Shell_TrayWnd`, `Progman`, the taskbar, the desktop |
| a **window host** | `explorer.exe /factory,{75dff2b7-6936-4c06-a8bb-676a7b00b24b} -Embedding` | one File Explorer window (or an idle COM server) |

```
HKCR\CLSID\{75dff2b7-6936-4c06-a8bb-676a7b00b24b}
    FriendlyName  : CLSID_SeparateMultipleProcessExplorerHost
    LocalServer32 : %SystemRoot%\explorer.exe /factory,{75dff2b7-...}
```

Consequences you must design around:

- **"Task Manager → Windows Explorer → Restart" is NOT a reliable way to apply a fix.**
  It may restart only the desktop shell and leave window-host processes alive, still
  running with the old settings. Real case observed: four hosts started 15:39–15:42
  survived while the desktop shell restarted at 15:49, leaving four stale processes with
  ~90 threads each and no window of their own.
- To apply a shell-extension change reliably you must kill **all** of them, then relaunch:

```powershell
Stop-Process -Name explorer -Force
Start-Sleep -Seconds 2
Start-Process (Join-Path $env:WINDIR 'explorer.exe')
```

  Or simply have the user reboot / sign out and back in — usually the cleanest answer.
- When you report a fix, **state explicitly which processes need to die**, and warn that
  every open File Explorer window will close.

### There is another long-lived host: `ShellHost.exe`

From Windows 11 24H2 the shell also keeps a small `C:\Windows\System32\ShellHost.exe`
process alive (tens of threads, a XAML-island window, ~70 modules). It is started via an
AppID, usually very early in the session. Two properties matter:

- **It survives an explorer restart.** Recycling `explorer.exe` does nothing to it. If any
  part of the UI you are fixing is built there, the registry change will not be read.
  Kill it too (`Stop-Process -Name ShellHost -Force` — it respawns on demand), or reboot.
- **No CLSID lists it as `LocalServer32`**, so you cannot confirm from the registry what it
  hosts. Do not assert that it builds the classic menu — **verify empirically** with the
  live tracer: watch both `explorer.exe` and `ShellHost.exe` and see which one loads the
  handler DLLs when the menu is opened.

Practical consequence: when a broad blocking test must be conclusive, prefer **reboot over
shell recycle**, and say so.

### Enumerating processes when WMI/CIM is blocked

`Get-CimInstance Win32_Process` frequently returns empty in sandboxes. Read the command
line straight out of the PEB instead:

```python
# NtQueryInformationProcess(ProcessBasicInformation) -> PEB
#   PEB  + 0x20 -> RTL_USER_PROCESS_PARAMETERS     (x64)
#   RTL..+ 0x70 -> UNICODE_STRING CommandLine      (x64)
```

Then decide "is this a window host?" by matching `/factory,{75dff2b7-...}` in the string.
To find out whether a process actually owns a visible window, run `EnumWindows` and filter
by owning PID, then look for a class of `CabinetWClass` — that is the real File Explorer
window class. A host that owns no `CabinetWClass` is an idle/stale COM server.

**ctypes pitfall:** the default return type is a 32-bit `int`, which **truncates
`HANDLE`s**. Declare `restype`/`argtypes` explicitly, or later calls fail with
`OverflowError: int too long to convert`:

```python
k32.OpenProcess.restype = ctypes.wintypes.HANDLE
k32.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
psapi.GetModuleFileNameExW.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_wchar_p, w.DWORD]
```

**FILETIME pitfall:** `GetProcessTimes` returns FILETIME, which is **UTC**. Converting it
naively gives a naive UTC datetime, and on a UTC+8 machine every start time is reported 8
hours early — which silently turns "this process has been running for 32 minutes" into
"8.5 hours", and can flip the conclusion about whether a fix was applied before or after
the process started. Always go through the local timezone:

```python
utc = datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=ft_value / 10)
local = utc.replace(tzinfo=datetime.timezone.utc).astimezone().replace(tzinfo=None)
```

PowerShell's `Get-Process ... | Select StartTime` is already local, so use it as a
cross-check when the two disagree.

## Step 1 — Measure the folder (kill the "too many files" theory)

Before blaming volume, measure it:

```python
import os, time
D = r"C:\Users\<user>\Downloads"
t = time.time(); top = os.listdir(D); print(len(top), time.time()-t)   # listdir
t = time.time()
for x in top: os.stat(os.path.join(D, x))
print("stat all:", time.time()-t)
```

If `listdir` is ~10 ms for a few dozen files, the folder is **innocent**. Then look at
*what kind of files* dominate. A folder that is 90% PDFs (or 90% videos, or 90% CAD
files) **can** be a folder where a thumbnail/preview handler is invoked once per item —
but verify the mechanism is even live before blaming it, by reading:

```
HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced
    IconsOnly     1 = "always show icons, never thumbnails"  -> thumbnail handler is NOT used
    LaunchTo      1 = opens "This PC", 2 = opens "Quick access"
    SeparateProcess 1 = each folder window in its own process
```

**Do not blame the thumbnail handler if `IconsOnly` is already 1.** That mistake was made
once: the whole diagnosis was built on "41 PDFs generate 41 thumbnails" when thumbnails
had been switched off globally for months. With `IconsOnly=1` the only PDF-specific
mechanism left is the **preview pane** (`IPreviewHandler`), which is unaffected by
`IconsOnly` and only fires when the pane is open.

Also worth checking before blaming the folder: a folder that is dominated by one file type
is a folder the user **right-clicks** a lot — and right-click handlers load on *every*
right-click regardless of view mode. If both "this folder hangs" and "right-clicking
anywhere hangs" are reported, treat it as **one** cause, not two.

## Step 1b — "Explorer freezes when I press **Paste**" is a different disease

Do not re-run the right-click playbook. Copy/paste takes a path of its own:

```
CF_HDROP in the clipboard -> IFileOperation -> CopyHook handlers
   -> destination folder REFRESH: folder-type discovery, re-enumeration
   -> per-item PropertyHandler / PersistentHandler / IFilter
   -> icon-overlay resolution for the items that just appeared
   -> the pasted items become the SELECTION -> command bar / menu for that selection
   -> sync-root (cloud-files) callbacks + AV minifilter on every write
   -> nav pane / "This PC" re-queries EVERY drive, including disconnected ones
```

Rank the suspects in this order; each has a cheap measurement:

1. **A disconnected mapped network drive.** `net use` shows `已断开连接` for a letter whose
   target no longer answers. Every Explorer refresh touches all drives. Check it first —
   it is a one-line fix and a classic cause of "Explorer hangs for tens of seconds".
   Watch for a drive mapped **to the machine's own name** (`\\<this-PC>\share`) — that is a
   stale self-map and is never useful. Measure per-drive cost:

```python
import os, time
for L in 'CDEF...':
    t = time.time();  os.stat(L + ':\\');  a = time.time() - t
    t = time.time()
    try: n = len(os.listdir(L + ':\\'))
    except OSError: n = -1
    b = time.time() - t
    print(L, 'stat=%.3fs listdir=%.3fs items=%d' % (a, b, n))
```

2. **A locked clipboard.** `user32.GetOpenClipboardWindow()` returning a non-zero HWND means
   some window (usually a clipboard viewer / sync client / IME) is holding the clipboard
   open, and Paste blocks until it lets go. Zero HWND plus an empty format list clears this
   line of enquiry outright. Wrap `OpenClipboard` + `EnumClipboardFormats` in a thread with
   a 3 s join — if it does not finish, the clipboard *is* locked.

3. **Packaged (MSIX) verbs whose surrogate is misbehaving.** This is the same third
   mechanism as Step 2d, and it is why "Paste" can hang without any right-click symptom:
   the surrogate lives in `dllhost.exe`, and the WER report names the package (see Step 0).
   Two tells that a package is guilty: `AppCrash_<PackageName>_…` and `AppHang_…` entries in
   `ReportArchive`, and a `Sig[0] Package Full Name` whose `PackageRootFolder` is dead.
4. **`ItemType="*"`** beats `ItemType=".pdf"` in priority — a `*` verb is evaluated no matter
   what was pasted. A `*` verb whose surrogate crashes loses to nothing.
5. **Cloud-sync / AV minifilters** — they get a write notification for the file that just
   landed. `BaiduNetdisk`, `QuarkCloudDrive`, `OneDrive`, McAfee, and any `FSFilter` group
   in `HKLM\SYSTEM\CurrentControlSet\Services` are the ones to look for. A 7-overlay client
   is a 7-overlay cost on every refresh.

### Move the observation from static to live: align "clicked Paste" with "files landed"

Static scans cannot tell you which of the above actually fires. Instrument it. The tracer
below watches, at 4 Hz, **every process that can host a shell extension** (not just
`explorer.exe`) and prints a timestamped timeline of: newly spawned processes **with the
parent resolved to a process name**, newly loaded modules, `IsHungAppWindow` hang/recover
transitions, clipboard-holder changes, per-tick CPU deltas, and **changes in the contents
of the source and destination folders**.

That last channel is the key trick: it puts "user pressed Paste" (`FS CHANGE … +['file.pdf']`)
on the same timeline as "window stopped responding", so you can tell a **pre-operation**
hang (nothing landed — the verb/menu path is at fault) from a **post-operation** hang (files
landed, then the refresh/property/overlay/sync path is at fault). Without it you are guessing
which half of the pipeline stalled.

Ask the user for the source and destination paths *before* they run it, take them as
arguments, and have the launcher `set /p` for them. Give a 5 s countdown and a 120 s window,
and echo the timeline to the console as well as to a file. Report `parent=svchost.exe` on a
burst of new processes as package activation, and any module appearing in `dllhost.exe`
immediately before the stall as the culprit.

## Step 2 — Find the broken handlers

Three registry locations matter. Scan all of them.

### 2a. Per-extension property handlers (the PDF case)

```
HKLM\SOFTWARE\Classes\<.ext>\ShellEx\{E357FCCD-A995-4576-B01F-234630154E96}   # IThumbnailProvider
HKLM\SOFTWARE\Classes\<.ext>\ShellEx\{8895b1c6-b41f-4c1c-a562-0d564250836f}   # IPreviewHandler
HKLM\SOFTWARE\Classes\SystemFileAssociations\<.ext>\ShellEx\...
```

Two failure modes:

1. **Orphan CLSID** — the referenced CLSID key does not exist at all.
   `CoCreateInstance` cannot resolve it; the shell walks the whole failure path.
2. **Stranded DLL** — the CLSID resolves, but points at a DLL whose host app is gone,
   or which lives on a slow/removable volume.

### 2b. Right-click (context menu) handlers — loaded on EVERY right-click

```
HKLM\SOFTWARE\Classes\*\shellex\ContextMenuHandlers
HKLM\SOFTWARE\Classes\AllFilesystemObjects\shellex\ContextMenuHandlers
HKLM\SOFTWARE\Classes\Directory\shellex\ContextMenuHandlers
HKLM\SOFTWARE\Classes\Directory\Background\shellex\ContextMenuHandlers
HKLM\SOFTWARE\Classes\Folder\shellex\ContextMenuHandlers
```
Also `PropertySheetHandlers`, `CopyHookHandlers`, `DragDropHandlers`, `IconHandler`.

The value of each subkey is either a CLSID `{...}` or a ProgID alias that itself has a
`CLSID` value.

### 2c. Icon overlay identifiers — Windows loads only ~15

```
HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\ShellIconOverlayIdentifiers
```
Cloud drives (OneDrive, Baidu, Dropbox) and AV products each register several. When the
total exceeds 15 the extras are silently dropped and the whole set costs time on every
folder refresh. Count and report the total.

### Detection script skeleton

```python
import os, winreg
HKLM = winreg.HKEY_LOCAL_MACHINE
CL = "SOFTWARE\\Classes"

def q(path, name=""):
    try: return winreg.QueryValueEx(winreg.OpenKey(HKLM, path), name)[0]
    except Exception: return None

def alive(dll):
    if not dll or not isinstance(dll, str): return False
    p = dll.strip().strip('"').split(' /')[0].split(' -')[0].strip().strip('"')
    p = os.path.expandvars(p)          # expand %SystemRoot% etc.
    return os.path.exists(p)
```

**Critical correctness note — path liveness has three false-positive traps:**

1. Values often carry **arguments**: `C:\X\App.exe /Automation`, `"E:\App.exe" /Phantom.Embed`
   → `os.path.exists()` on the whole string returns False even though the exe exists.
2. Values often use **environment variables**: `%SystemRoot%\system32\shell32.dll`
   → must `os.path.expandvars()` first.
3. Values may be **quoted**: `"C:\Program Files\...\app.exe"`

Failing to handle all three will make you report dozens of healthy system entries as
"missing" and bury the real one. **Only a CLSID key that does not exist at all is
unambiguously broken.**

### 2d — Packaged (MSIX / Store / sparse) handlers: the layer `Blocked` cannot touch

This is the mechanism that makes a well-executed classic fix look like it did nothing.

A package declares its context-menu verbs in its own `AppxManifest.xml`:

```xml
<desktop4:Extension Category="windows.fileExplorerContextMenus">
  <desktop4:FileExplorerContextMenus>
    <desktop5:ItemType Type=".pdf">
      <desktop5:Verb Id="file2" Clsid="DBDED57A-CA8E-4C07-8691-3F66147DB794" />
    </desktop5:ItemType>
    <desktop5:ItemType Type="*">            <!-- runs on EVERY file -->
      <desktop5:Verb Id="ATopItem" Clsid="..." />
    </desktop5:ItemType>
  </desktop4:FileExplorerContextMenus>
</desktop4:Extension>

<com:Extension Category="windows.comServer"><com:ComServer>
  <com:SurrogateServer DisplayName="...">
    <com:Class Id="DBDED57A-..." Path="Foo.ShellExtension.dll" ThreadingModel="STA" />
  </com:SurrogateServer>
</com:ComServer></com:Extension>
```

The CLSID is materialised at

```
HKLM\SOFTWARE\Classes\PackagedCom\Package\<PackageFullName>\Class\{...}
```

Properties that change the whole diagnosis:

- The handler DLL **never loads into `explorer.exe`**. `ThreadingModel="STA"` plus
  `com:SurrogateServer` means it is instantiated out-of-process in **`dllhost.exe`**. The
  packaged host is **`C:\Windows\System32\StoreDesktopExtension.exe`**.
- Activation routes through the COM SCM (`svchost.exe -k DcomLaunch`) and the package
  infrastructure, so a right-click produces a *burst of helper processes*:
  `StoreDesktopExtension.exe`, `backgroundTaskHost.exe`, `RuntimeBroker.exe`,
  `dllhost.exe` (often several), `smartshellhost`. Seeing that burst is the fingerprint.
- **`HKCU\...\Shell Extensions\Blocked` does not apply.** These CLSIDs are not in
  `HKCR\CLSID`, so the official block silently misses them. Step 4 alone cannot fix this.
- **There is usually more than one**, and several use `ItemType="*"` (every file) or
  `Directory`. Counting them is part of the job.

Enumerate them (this works in a non-elevated shell):

```powershell
Get-AppxPackage | ForEach-Object {
  $x = ($_ | Get-AppxPackageManifest).OuterXml
  if ($x -match 'windows.fileExplorerContextMenus') {
    '{0,-46} {1,-10} {2}' -f $_.Name, $_.SignatureKind,
      (([regex]::Matches($x,'<desktop[45]:ItemType Type="([^"]+)"') |
        ForEach-Object { $_.Groups[1].Value } | Sort-Object -Unique) -join ',')
  }
}
```

#### The killer failure mode: a dead "external content root"

A sparse package may set `<uap10:AllowExternalContent>true</uap10:AllowExternalContent>`
and keep its real binaries **outside** the package. The authoritative path is

```
HKCU\Software\Classes\Local Settings\Software\Microsoft\Windows
    \CurrentVersion\AppModel\Repository\Packages\<PackageFullName>\PackageRootFolder
```

- `InstallLocation` is only the folder holding `AppxManifest.xml`.
- `PackageRootFolder` is where the DLL actually has to be. **They differ for external-
  content packages — always test `PackageRootFolder`, not `InstallLocation`.**

**Reading the manifest when there is no readable `AppxManifest.xml`.** For exactly these
`AllowExternalContent` packages `InstallLocation` is frequently **empty** in
`…\AppModel\Repository\Packages\<full>` (only `PackageRootFolder` is populated), and
`C:\Program Files\WindowsApps` is ACL-blocked from a normal shell (`WinError 5`). So walk
the two registry sources and, if the on-disk manifest cannot be read, **open the `.appx`
shipped next to the binaries — an `.appx` is just a zip**:

```python
import zipfile
z = zipfile.ZipFile(r'C:\Program Files\Tencent\QQNT\extension\QQExtension.appx')
manifest = z.read('AppxManifest.xml').decode('utf-8-sig')
```

That is how the real verb list is recovered (measured example: `ItemType Type="*"` plus
`<com:SurrogateServer><com:Class Id="CC19E147-…" Path="qq_explorer_command.dll"
ThreadingModel="STA"/>` — i.e. every file, out-of-process, `dllhost.exe`). Enumerate
candidates from **both** `HKLM\SOFTWARE\Classes\PackagedCom\Package` and
`HKCU\Software\Classes\Local Settings\…\AppModel\Repository\Packages`, and read
`PackageRootFolder` from the latter to resolve `Path="…"` from the former.

Real case: an Acrobat sparse package declared a `.pdf` verb (`Id="EditCommand"`) backed by
`Acrobat Elements\ContextMenuIExplorerCommandShim.dll`, with
`PackageRootFolder = D:\Adobe Acrobat Pro DC2022\Acrobat DC`. After a D:→E: migration that
directory no longer existed, while the registration did. Result: **every** right-click on a
.pdf walked a doomed package activation — a repeatable multi-second stall that no
`HKCR\CLSID` scan can see, because there is no such CLSID.

Also fragile: a root that embeds a **build hash**, e.g.
`E:\Microsoft VS Code\04c0d99f4f\appx`. The next update creates a new hash directory and
deletes the old one, silently breaking the verb.

#### Fix: remove the package (there is nothing to "block")

```powershell
Get-AppxPackage -Name <PackageName> | Remove-AppxPackage     # per-user, no admin needed
```

- Check `NonRemovable` first; `False` means a plain user may remove it.
- Export the manifest first (`(Get-AppxPackage ... | Get-AppxPackageManifest).OuterXml`);
  the reliable route back is reinstalling the parent application, and `Add-AppxPackage
  -Register <manifest>` only works if the content is still on disk.
- Rank candidates by: **dead root** > `ItemType="*"` > hooks the exact extension under
  debug > `SignatureKind = Developer` (sideloaded) with an unknown vendor.
- `SignatureKind = Developer` together with `Publisher = CN=Microsoft Corporation` is
  **not** automatically a forgery. Check the DLL:
  `Get-AuthenticodeSignature <dll>`. A valid chain to `Microsoft Code Signing PCA 2011`
  with subject `CN=Microsoft 3rd Party Application Component` means Microsoft signed a
  genuine third-party add-on — removable junk, not malware. Say it that way.
- `NonRemovable: False` + `SignatureKind: Developer` + `Publisher: Microsoft` is exactly
  what a bundled Chinese "PDF tool" add-on looks like. Report the facts, not the verdict.

#### Removal is not the end of the job — check the PackagedCom orphan

`Remove-AppxPackage` clears the **per-user** record under
`AppModel\Repository\Packages`, but the **machine-wide** key

```
HKLM\SOFTWARE\Classes\PackagedCom\Package\<PackageFullName>
```

is frequently **left behind**. Either:

- reboot (the AppX maintenance pass at logon normally clears it), or
- delete it explicitly (admin, after `reg export`).

Severity is **lower** than a dead content root: with the package manifest gone Windows
no longer enumerates the verb, and any stray activation fails **fast**
(`REGDB_E_CLASSNOTREG`-style), exactly like a classic orphan CLSID. So do not promise a
second performance win from cleaning it — the win already happened at removal. The real
reasons to clean are hygiene and avoiding a **collision on a future reinstall at a
different version**.

**Never identify orphans by full package name.** A version upgrade leaves the same
pattern, and deleting those is wrong:

```
PackageFullName = Name_Version_Arch__PublisherHash    # Name contains no '_'
base = full.Split('_')[0]                             # take everything before the 1st '_'
orphan  <=>  base NOT present in the current user's Repository
```

Measured on the case machine: matching by **full name** flagged 5 entries, but 2 of them
(`Microsoft.OneDriveSync_26119…`, `OpenAI.Codex_26.915…`) were **stale versions of apps
still installed** — only 3 were true orphans. Add one more guard: if
`C:\Program Files\WindowsApps\<PackageFullName>` still exists, **skip** — the package may
belong to another user account, and only `-AllUsers` (admin) could tell you.

#### Case outcome (proof the diagnosis was right)

Removing the single dead-root Adobe package, then recycling the shell, **fixed the hang**.
Everything else on the machine stayed in place. When a one-line removal reproduces the
fix, do not keep removing further candidates "to be safe" — say the root cause is
confirmed and put the remaining ones on a watch list instead.

## Step 3 — Look for the working provider that is already installed

Do not assume the only fix is "disable". Very often a **healthy provider is already on
the machine and simply unused**. Scan all CLSIDs for the relevant friendly-name keyword
and check which ones resolve to a live DLL:

- For PDF preview on modern Windows: `{3A84F9C2-6164-485C-A7D9-4B27F8AC009E}`
  ("PDF Preview Handler", ships with Microsoft Edge at
  `...\Edge\Application\<ver>\PdfPreview\PdfPreviewHandler.dll`).
- Check both `HKLM\SOFTWARE\Classes\CLSID` and its `WOW6432Node` twin — the same vendor
  often registers different CLSIDs in 32- and 64-bit views.

Repointing the interface GUID at the working CLSID restores functionality instead of
only removing it. Reference the **CLSID**, never the DLL path — Edge rewrites the path
on every update but keeps the CLSID stable.

## Step 4 — Apply a reversible fix
### Preferred: the official Blocked list (no admin needed)

```
HKCU\Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Blocked
   "{CLSID}" = ""        (REG_SZ, empty data)
```

This is Microsoft's supported mechanism. It is user-scoped, needs no administrator
rights, and is undone by simply deleting the value. Prefer it over deleting or renaming
HKLM keys.

Blocking is keyed on **CLSID**, so one entry neutralises that handler everywhere it is
registered — `*`, `Folder`, `Directory`, `Directory\Background`, `Drive`, and any
per-extension `shellex` registration. Enumerate those locations anyway, so you can tell the
user exactly which menu items will disappear.

**Writing the value changes nothing on its own.** See Step 0.5 — every process that already
exists keeps the extension until it dies. Always pair the registry change with an explicit
shell recycle, and say so in the instructions you hand over.

**And it does not cover Step 2d.** The `Blocked` list is keyed on *classic* CLSIDs living in
`HKCR\CLSID`. Packaged (MSIX) verbs are registered under `HKCR\PackagedCom` and are
completely unaffected — you can block every classic handler on the machine and the packaged
ones still run on every right-click. A full classic block-plus-reboot that changes nothing
is the diagnostic signal to go back to Step 2d, not a reason to keep tuning the classic set.

When only some entries should be reverted, support a **selective restore** in the script
(`-Only <name>`): useful handlers get caught in a broad sweep, and re-enabling them one at
a time through a GUI is painful. A 99 KB, well-behaved archive tool sitting on a secondary
drive is not the same risk class as a dismembered portable install — rank by "does this DLL
have to scan a plugin system / find a missing host / sit on a slow volume", not merely by
"is it third-party".

### When Blocked is not enough: rename the key (admin needed)

Renaming preserves the original data for instant rollback:

```powershell
Rename-Item -Path 'HKLM:\SOFTWARE\Classes\<...>\ContextMenuHandlers\<name>' `
            -NewName '<name>_disabled_by_diag' -Force
```

Always `reg export` the parent key first. **Never delete.**

### Rebuilding a stuck icon/thumbnail cache

`iconcache_*.db` files of ~24 bytes are stubs left behind when explorer was force-killed;
they force constant regeneration. Stop explorer, rename the cache files to `*.old`, restart
explorer. Rename, do not delete.

## Step 4.5 — When static analysis is inconclusive, trace it live

Ranking suspects by DLL size and path is guesswork. If the user can reproduce the hang on
demand, **measure it instead**. Context-menu handler DLLs are loaded lazily, so the DLLs
that appear in the process *during* the hang are the participants — and the one that
appears immediately before the stall is the culprit.

Build a poller (about 4 Hz) that watches **every process that can host a handler**, not just
the shell — `explorer.exe`, `ShellHost.exe`, and the packaged hosts `StoreDesktopExtension.exe`,
`dllhost.exe`, `RuntimeBroker.exe`, `backgroundTaskHost.exe` — and records:

- **newly appeared modules** — module set diff against the previous tick,
- **`user32.IsHungAppWindow(hwnd)`** on the process's top-level windows — this is the only
  cheap way to get an exact "stopped responding / recovered" transition and time it,
- **newly spawned processes**, with the parent PID **resolved to a process name** — a shell
  extension may delegate to a helper process, and *that* is where the time goes. Printing a
  bare parent PID is a real usability loss: a burst whose parent is `svchost.exe` is package
  activation of a packaged verb, while the same burst from `explorer.exe` means something
  else entirely,
- **kernel+user CPU delta per tick** — shows the process is actually spinning rather than
  blocked on I/O. Note: `GetProcessTimes` kernel/user values are **durations**, not
  timestamps; never run them through a timezone conversion. Only `CreationTime` is a real
  timestamp.

Then read the timeline:

```
+3.2s  PID 97916 加载 C:\...\biz_shellext64.dll   <<== Sogou Input
+3.4s  *** PID 97916 停止响应 (IsHungAppWindow=True)
+11.8s --- PID 97916 恢复响应
```
→ that DLL is the culprit.

```
+2.1s  新进程: PID 78928  biz_helper.exe  (父 97916)
```
→ the extension spawned a helper from the shell process itself; suspect that path.

If **nothing** loads before the stall, the culprit is either already resident from shell
startup (cloud-drive clients and input-method extensions are, because they also register
icon overlays) or it is not a shell extension at all.

## Step 5 — Verify, do not assume

Verification has **two levels**, and skipping the first is how a fix gets reported as
working when it is not.

### 5a. Immediate proof: is the change live in the running processes?

Context-menu handler DLLs are **loaded lazily** — a handler appears in the process's module
list only after a context menu has actually been built. So:

1. Enumerate loaded modules of every `explorer.exe` (`EnumProcessModulesEx` +
   `GetModuleFileNameExW`); match module paths against the handler DLLs by path fragment.
2. Record that as the baseline.
3. Have the user right-click a file in the folder that used to hang.
4. Re-enumerate. **A blocked DLL that now appears was not actually blocked** — the process
   predates the change, so the shell still needs recycling.

Separate the matches into two groups before drawing a verdict:

- **handlers you blocked** → these decide pass/fail
- **handlers deliberately left alone** → context only

Getting this wrong produces a false alarm: handlers that are *supposed* to stay active
(OneDrive, cloud-drive clients, input-method extensions, Adobe CoreSync) are **resident
from shell startup** because they also register icon-overlay and drag-drop handlers,
whereas the ones you blocked are absent until a menu opens. A naive "count of loaded
third-party DLLs" therefore reports failure every single time.

### 5b. Long-run proof: the hang log

```bash
wevtutil qe Application "/q:*[System[Provider[@Name='Application Hang']]]" /c:10 /f:text /rd:true
```

No new `explorer.exe 停止与 Windows 交互` entries = closed loop. Note that a *manual*
shell restart produces no hang event at all, so a missing event is not by itself proof that
nothing happened — pair it with a fresh `explorer.exe` start time.

## Step 6 — Look for the systemic cause

Isolated breakage is rare. If you find one orphan reference, **assume there are more**.
Common systemic triggers:

- **A drive-letter migration** (D: → E:) that copied files but not registry references.
- A **portable/green software install** unpacked into a drive root instead of
  `Program Files`, later moved or partially deleted.
- An **uninstall that left its shell extension registration behind** — produces a value
  pointing at a CLSID that no longer exists anywhere.

When you find one, scan the whole `HKLM\SOFTWARE\Classes\CLSID` tree for entries whose
`InprocServer32`/`LocalServer32` DLL is missing, and report the lot as one job.

## Pitfalls learned the hard way

- **Do not claim an orphan CLSID "causes a long delay" without care.** A truly
  unregistered CLSID makes `CoCreateInstance` fail *fast* (`REGDB_E_CLASSNOTREG`). The
  genuinely slow cases are DLLs that *do* load but then block on I/O, licensing, a
  missing host process, or a slow volume. Rank E:-drive / network / removable-volume
  DLLs above pure orphans. An orphan is still worth cleaning up — just do not present it
  as the cause of the delay while a loadable-but-blocking DLL is in the same list.
- **Check the view-mode settings before blaming a thumbnail handler** (`IconsOnly`), and
  check whether the user actually hit the *main* menu or the *Open with* submenu.
- **`HKCU\Software\Classes` overrides `HKLM\SOFTWARE\Classes`.** A per-user copy of the
  same broken value silently defeats an HKLM-only repair — the fix looks applied and the
  symptom never changes. Always walk **both** hives for `.ext\ShellEx\{iface-guid}` keys
  (and for ProgIDs), and back each one up separately. Found in the wild: the orphan PDF
  preview CLSID was registered in **both** hives, while the thumbnail one existed only in
  HKLM — so a script that handled one hive looked correct on inspection yet changed
  nothing.
- **Uninstalling a package is not the last step.** `Remove-AppxPackage` leaves the
  machine-wide `HKCR\PackagedCom\Package\<full name>` key behind. Verify the removal, and
  judge orphans by **base package name**, never by full name (version upgrades otherwise
  look identical to orphans). See Step 2d. Cleaning it is hygiene, not a second
  performance win — do not oversell it.
- **A registry fix with no shell recycle is indistinguishable from a fix that failed.**
  Always report the running processes and their start times alongside the change.
- **Do not stop at the "obviously broken" handlers.** The genuinely broken ones are the
  cheap win, but the classic menu also initialises every well-behaved third-party handler,
  and on a machine with an input-method extension, a cloud-drive client, a sync client and
  a vendor "suite" that is easily 10 MB of code. Provide a "block everything" switch so the
  user can run one conclusive test, plus a selective restore so they can bisect back to the
  exact offender and keep the rest.
- **Enumerate the whole class chain, not just `*`.** For a specific file the menu is
  assembled from `*`, `AllFilesystemObjects`, the extension key itself,
  `SystemFileAssociations\<.ext>`, and the extension's ProgID (plus anything in its
  `OpenWithProgids`). The ProgID is where the app's own verbs (`open`/`print`/`printto`)
  live, and those are exactly the entries that point at an app path that a migration broke.
- **Icon resolution is a legitimate suspect but check it before blaming it.** Every classic
  menu item's icon must resolve; a dead icon path or a dead-app path can stall the draw.
  Scan `Icon` / `DefaultIcon` values with the same path-parsing rules as Step 2c. If the
  scan comes back clean, say so and move on rather than speculating about it.
- **Do not call an unusual association "corruption"** without checking whether it is
  actually broken. Verify versioned `@{Package_<ver>?ms-resource://...}` references
  against the installed package before declaring them stale.
- **Windows deliberately does not auto-execute `.ps1`.** An association to a text editor
  is by design, not damage.
- Windows 11's "Open with" submenu is built lazily. A slow *main* context menu and a slow
  *Open with* submenu have different causes — establish which one the user actually hit
  before fixing.
- **An empty dynamic trace is not evidence of innocence.** A poller that watches only
  `explorer.exe` for newly loaded modules is *structurally blind* to packaged handlers
  (Step 2d), which load in `dllhost.exe` / `StoreDesktopExtension.exe`. A run that reports
  "nothing was loaded and nothing stopped responding" while the timeline is full of **new
  surrogate processes** is reporting a blind spot, not a clean machine. Before trusting a
  negative result, state explicitly which processes and which mechanism the probe can see.
- **"The scan found no broken references" only means that scan's mechanism is clean.** A
  `HKCR\CLSID` sweep for orphans and missing DLLs is silent about `HKCR\PackagedCom`, about
  package manifests, and about dead `PackageRootFolder` paths. When an extension-specific
  hang survives a clean classic sweep, change mechanism rather than tuning severity.
- **Watch out for a burst of helper processes whose parent is `svchost.exe`.** That parent is
  the COM/package activation host, so the burst is packaged-verb activation — a classic-CLSID
  problem cannot produce it.
- **Precautionary blocks must be reverted once the real cause is found.** A broad sweep
  (e.g. `-Aggressive` / `-All`) disables handlers that were never guilty, and those users
  silently lose working right-click entries. When the user confirms the hang is gone,
  explicitly walk back every entry you only blocked "just in case" and left a note in the
  hand-over — do not close the ticket with the sweep still in place. Reverting one value
  needs its own shell recycle, so say when the menu item will actually reappear.
- **`Explorer hangs when I click Paste` is not the right-click bug wearing a hat.** The two
  share only the *vocabulary* (shell extensions, `dllhost.exe`). Different trigger, different
  handler set, different cheap fixes — start from Step 1b, not from Step 2.
- **A `PackageRootFolder` that still exists does not mean the package is healthy.** The
  proven-killer case was a *dead root*; the next one is a **live root with a DLL that crashes
  or blocks** (`qq_explorer_command.dll` loaded fine and still brought `combase.dll` down
  inside `dllhost.exe`, twice in an hour). Look for `AppCrash_<PackageName>_…` /
  `AppHang_…` in WER before concluding the package is innocent just because its files exist.
- **Read `Report.wer`, not just the Event Log.** The Event Log entry for a surrogate hang
  only says "程序 dllhost.exe 停止与 Windows 交互"; the WER report carries
  `Sig[0].Name=Package Full Name` and names the guilty package. The report *directory name*
  often does too. See Step 0.
- **Prefer the paste-tracer over another round of registry archaeology** when the user can
  reproduce on demand. Rank by measurement, not by how suspicious a DLL name looks.
- **The regression test is the user's own scenario, not the absence of hangs.** Ask the
  user to state whether a specific folder/action still stutters, or whether it is simply
  fine. "Seems to open normally now" is a confirmation, and it is what turns a strong
  static inference into a closed loop — say which of the two you got, rather than
  reporting the fix as proven.

## Deliverable shape

Prefer producing a small toolkit rather than one script:

1. an inspector/patcher with `Status` / `Fix` / `Restore` actions (and a selective
   `-Only` restore),
2. a **shell recyler** that kills every `explorer.exe` and relaunches the shell, since no
   registry change takes effect without it,
3. a module-level verifier for the closed-loop right-click test,
4. for the **packaged** layer, a separate remover with the same `Status` / `Remove` /
   `Restore` / `CleanStale` shape. It must back up the manifest (`Get-AppxPackageManifest`
   → `OuterXml`) and `reg export` the `HKLM\SOFTWARE\Classes\PackagedCom\Package\<full>`
   key *before* touching anything, record each package's restore command in a printed
   table (`Add-AppxPackage <the .appx>` for a shipped bundle, `Add-AppxPackage -Register
   <WindowsApps>\…\AppxManifest.xml -DisableDevelopmentMode` otherwise), and report
   `NonRemovable` so the user knows whether a plain user may remove it at all,
5. for a hang the user can reproduce, a **live tracer** (Step 1b) rather than more scans.

Script-writing rules:

- ASCII-only content: avoids the PowerShell 5.1 UTF-8 BOM trap on non-English locales.
  Verify with a byte scan that every byte is < 0x80 and that no BOM is present.
- `reg export` backup before any HKLM change; hard bias toward rename-over-delete.
- **Model the registry targets as a list of hives, not a single path.** A constant such as
  `HKLM:\SOFTWARE\Classes\.pdf\ShellEx` invites exactly the bug described in Pitfalls —
  build a `$roots` array of `{ Name; PsPath; RegPath }` and drive Status / Fix / Disable /
  Restore / backup from it, so HKCU cannot be forgotten.
- **PowerShell 5.1 does not support `if` as an expression.** Write
  `$x = 'a'; if ($c) { $x = 'b' }` — never `($c ? 'a' : 'b')` and never
  `(... (if ($c) {'a'} else {'b'}) ...)` inside a `-f` argument list. No `??`, no `?.`,
  no `&&`/`||`. `Get-CimInstance` hands back a `[datetime]` for `CreationDate`, while
  older CIM paths hand back a DMTF string — accept both.
- Validate syntax before handing the script over, and capture the result to a file —
  PowerShell output is sometimes swallowed by the sandbox:

```powershell
$e = $null
[System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$null, [ref]$e)
```

Then give the user the manual GUI fallback for anything requiring admin rights.
