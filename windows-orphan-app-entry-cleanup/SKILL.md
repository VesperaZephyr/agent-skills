---
name: windows-orphan-app-entry-cleanup
description: Find and remove orphaned rows in Windows Settings -> Installed apps — duplicate or "ghost" entries left behind when an app was uninstalled incompletely, or after a drive-letter migration. Use when the user shows two entries with the same DisplayName, when an uninstalled program still appears in Apps and features, when an uninstall left a dead Start Menu shortcut / dead firewall rule behind, or when a program must be purged from the app list while its uninstaller no longer exists. Covers the Uninstall registry hives (HKLM 64-bit, WOW6432Node, HKCU), the three-path dead test, cross-checking a screenshot row against EstimatedSize, and backup-first reversible removal of a protected HKLM key.
agent_created: true
---

# Windows Orphaned "Installed apps" Entry Cleanup

Removing a leftover row from **Settings -> Apps -> Installed apps** is a registry job, not a
file job. The row is drawn from an `Uninstall` key; the program it names is already gone.

## Golden rule

Do **not** delete an entry because its name looks wrong. Delete it only when

1. **every path inside the key is dead** (installation dir, uninstaller, display icon), and
2. the entry that stays is **verified alive**, and
3. the key's `DisplayVersion` matches the ghost version you identified.

Add the version guard in code, not just in your head. Two rows sharing a `DisplayName` is the
normal shape of this bug, and a name-only match will eventually delete the wrong one.

## Step 1 — Enumerate every possible source

Settings merges several hives. Collect all of them before concluding anything:

| Hive | Notes |
|---|---|
| `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall` | 64-bit view |
| `HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall` | 32-bit view |
| `HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall` | per-user installers |
| `HKLM\SOFTWARE\WOW6432Node\...\Uninstall` read via `KEY_WOW64_32KEY` | **same key as row 2** |

**WOW64 duplication trap.** Reading the plain path with `KEY_WOW64_32KEY`, and reading the
explicit `WOW6432Node` path with `KEY_WOW64_64KEY`, return *the same physical key*. A scan
that reports "found it in 2 places" is usually reporting one key twice. Say so explicitly —
otherwise the user believes there are two keys to clean, and a script that "removes both"
looks like it half-failed when the second path is simply absent.

Also check `WindowsInstaller` / `ParentKeyName` / `SystemComponent`: an MSI-backed entry needs
`msiexec` product cleanup instead of a key delete, and `SystemComponent=1` entries are
deliberately hidden (they are not what the user is seeing).

## Step 2 — The three-path dead test

For each candidate read and probe:

```
InstallLocation     -> directory must exist
UninstallString     -> executable must exist
DisplayIcon         -> file must exist
```

Report each independently. **One dead path is not a ghost** — vendors ship broken
`DisplayIcon` values constantly. It is a ghost when the *install location* and the
*uninstaller* are both gone.

Two parsing rules that otherwise produce false "MISSING" verdicts:

- **Strip embedded quotes.** `InstallLocation = "C:\Program Files\Tencent\Weixin"` (quotes
  inside the value) is a common installer quirk, not damage. `Test-Path` on the raw string
  fails. Trim `"` and spaces before probing, and never report that as a missing directory.
- **Pull the exe out of a command line.** `UninstallString` may be
  `"C:\...\Uninstall.exe" /S` or include `%SystemRoot%`. Take the quoted first token when
  present, else cut at the first `*.exe|*.ico|*.dll`, then expand environment variables.
  For the backup/compare raw value, read with `DoNotExpandEnvironmentNames` so you keep what
  is actually stored.

## Step 3 — Prove the key you found is the row the user saw

Before deleting, tie the registry facts to the user's own evidence:

- **`EstimatedSize` matches the size column.** The value is in **KB**. 821290 KB = 802 MB,
  which is exactly what Settings displayed. A match to the megabyte confirms you are looking
  at the same key the screenshot shows — and that the screenshot is not a Store/MSIX entry.
- **Icon state.** The ghost row usually shows the generic default icon, which is consistent
  with a `DisplayIcon` pointing at a deleted `.exe`.
- **Install date ordering.** The ghost's install date predates the live one.

Say which of these you used. It converts "I found a dead key" into "this is your row".

## Step 4 — Audit the residue the uninstaller forgot

An incomplete uninstall leaves several kinds of debris. Enumerate all of them, but classify
them by risk before offering to clean:

| Residue | Where | Verdict |
|---|---|---|
| Dead Start Menu / Desktop shortcut | `.lnk` whose target is the removed exe | safe to remove (move, don't delete) |
| `App Paths` entry | `HKLM\...\App Paths\<name>` | safe if target is gone |
| `Run` autostart | `HKCU`/`HKLM` `...\CurrentVersion\Run` | safe if target is gone |
| Service | `HKLM\SYSTEM\CurrentControlSet\Services\<name>` | report; deleting needs care |
| Firewall rules | `...\FirewallPolicy\FirewallRules` | **report only** — security-relevant |
| **User data directory** | `%APPDATA%\<vendor>\<app>` | **do not touch** |
| Vendor software tree | `HKLM\SOFTWARE\<vendor>` | report only |

Two hard limits worth stating out loud to the user:

- **A data directory is not "junk".** Deleting `%APPDATA%\...` is data loss, not cleanup.
  Its size is worth *reporting*, never acting on.
- **Firewall rules are security configuration.** List the dead ones, let the user decide.

Resolving a shortcut without COM: `WScript.Shell` may be unavailable (restricted shell,
sandbox). Read the `.lnk` bytes and search for the target fragment in **both** ASCII and
UTF-16LE decodings — enough to answer "does this shortcut point at the deleted exe?" without
a full LNK parser.

## Step 5 — Remove it safely

1. **Back up first, in a format that does not depend on `reg.exe`.** `reg export` is the
   best-fidelity backup, but `reg.exe` is blacklisted in some agent sandboxes. Write a JSON
   dump of the key path + every value name/value as well, and let `-Action Restore` rebuild
   the key from the JSON. Then a blocked `reg.exe` costs you nothing.
2. **Expect HKLM to need elevation.** `Uninstall` keys are Administrators-only. A
   non-elevated process gets `PermissionError` / `WinError 5` on `KEY_SET_VALUE` even when
   the *parent* key looked readable — probe the leaf key, not the parent, before promising
   the user you can do it.
3. **Hand over a self-elevating launcher.** A `.cmd` that tests elevation with
   `fsutil dirty query %SystemDrive%` and re-launches itself via
   `Start-Process -FilePath '%~f0' -Verb RunAs` turns a multi-step instruction into one
   double-click. Print the exact list of removals before writing, and ask for a typed `YES`.
4. **Move, do not delete, the files.** Dead shortcuts go into a backup folder next to the
   script; the `Restore` action moves them back.
5. **Guard the survivor.** After removal, assert that the live sibling key still exists and
   its directory is intact. Report it as a first-class check, not an afterthought.

## Step 6 — Verify

- Re-read both candidate paths: they must be gone.
- The live entry must still be present, with its install directory intact.
- Tell the user no restart is required for Settings to refresh, and where the backup is.

## Pitfalls

- **In PowerShell, `,` binds TIGHTER than `+`.** `@('a\' + $x, 'b\' + $x)` silently builds a
  **one-element** array whose only string is `"a\$x b\$x"` — the two paths joined by a space.
  A loop over it then probes one nonsense path and reports "nothing found", with no error.
  Always parenthesise: `@( ('a\' + $x), ('b\' + $x) )`. Verify with `.Count`.
- **`$env:AppData` already ends in `\Roaming`.** `Join-Path $env:AppData 'Roaming\...'`
  produces `...\Roaming\Roaming\...` and every probe silently reports "absent".
- **PowerShell 5.1 does not support `if` as an expression**, and `-f` with a bare comma list
  is another precedence trap. Prefer intermediate variables and plain string concatenation
  over `-f` plus inline `if`.
- **Keep `.ps1` ASCII-only** (PS 5.1 mis-decodes non-ASCII `.ps1` without a UTF-8 BOM on
  Chinese-locale systems). Chinese only ever appears in *paths at runtime* — build those
  from `Join-Path`/`Get-ChildItem`, never as a literal in the source.
- **`.cmd` should be CRLF, not LF.** cmd.exe has known failures with LF-only batch files
  (label scanning, parenthesised blocks). Byte-check both files: `nonASCII=0` and, for
  `.cmd`, a non-zero `\r\n` count.
- **Never identify the ghost by `DisplayName` alone.** Same name, two versions, one live —
  that is the whole bug. Require the dead-path test plus a version match.
- **A hanging/slow shell and an orphaned app-list row are different bugs with the same
  origin** (an incomplete uninstall or a drive migration). Fixing one does not fix the other;
  say which one you are addressing.
- **The exit criterion is the user's own screen.** Ask them to reopen Settings and confirm
  one row remains — do not declare success from the registry alone.

## Deliverable shape

A small, self-describing toolkit rather than a one-off command:

1. `*-ghost.ps1` with `Status` (default, read-only) / `Apply` (backup then remove) /
   `Restore` actions, a `-Force` to skip the prompt, and a `-KeepShortcut` escape hatch.
2. `*-ghost.cmd` — the double-click, self-elevating launcher, echoing exactly what it removes.
3. A read-only audit script per residue class (uninstall keys, shortcuts, autostart, firewall)
   so the user can re-run the survey after a future uninstall.

Prints to guarantee in `Status`: the ghost key with each dead path labelled, the live sibling
key with its directory existence, the dead shortcuts, and the "reported but not touched"
list with sizes.
