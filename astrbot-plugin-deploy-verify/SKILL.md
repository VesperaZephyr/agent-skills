---
name: astrbot-plugin-deploy-verify
description: "Deploy and end-to-end verify a custom AstrBot plugin (Docker + NapCat QQ bot) on the Tencent Lighthouse server, and prove the change actually works rather than merely uploading without error. Use when editing any plugin under E:\\qqbot_cloud_deploy\\, when a Playwright/scraping plugin misbehaves only in production, or when you need to smoke-test screenshot/render output that cannot be produced locally. Captures the local pre-flight checks (py_compile + node --check on inline page JS), scp backup/upload, docker restart, in-container e2e scripts, the JSON-over-scp trick that defeats PowerShell mojibake, and the Playwright-on-Zhihu traps (error pages, lazy images, MathJax timing)."
agent_created: true
---

# Deploy & verify an AstrBot plugin (Windows / WorkBuddy -> remote Docker)

## Environment facts (already established — do not rediscover)

- **Host**: `ssh root@129.211.212.95` (key `C:\Users\asus\.ssh\id_rsa`, passwordless). Containers
  `astrbot` + `napcat` live in `/root/qqbot/docker-compose.yml`.
- **Path mapping**: host `/root/qqbot/data` == container `/AstrBot/data`. Plugins therefore live at
  host `/root/qqbot/data/plugins/<plugin>/` == container `/AstrBot/data/plugins/<plugin>/`.
- **Local plugin sources**: `E:\qqbot_cloud_deploy\<plugin_name>\` (git repo, root also holds
  `test_*.py` scratch scripts).
- **Shell choice — verified again 2026-09-22: the `Bash` tool (Git Bash) works well here and is
  now preferred.** `mkdir/cp/rm/ls/sed/grep` all work locally, `ssh`/`scp` work, stdout comes back
  as **clean UTF-8 (no mojibake)**, and remote `grep -a` / `sed -n` over ssh is by far the fastest
  way to read AstrBot logs. The earlier note "bash has no coreutils, use PowerShell only" is
  **superseded**. PowerShell remains a valid fallback (its stdout-swallowing and ACP-mojibake
  problems below still apply), but do not reach for it by default.
- **Uploading a script to the server (bash idiom that works)**:
  `ssh root@HOST "cat > /tmp/x.py" < local/x.py` — note the redirect target is the *remote* path.
  The tempting variant `ssh root@HOST "cat -" < local/x.py > /tmp/x.py` writes to the **local**
  `/tmp` and silently leaves the remote file missing (`docker cp ... lstat: no such file`).
  Then `ssh HOST "docker cp /tmp/x.py astrbot:/tmp/x.py && docker exec astrbot python3 -u /tmp/x.py"`.
- **The PowerShell tool's stdout is frequently swallowed** — `Write-Output` / bare cmdlet results
  come back empty even on exit code 0. **Always** funnel results into a `$env:TEMP\*.txt` file with
  `Set-Content` and read it with the **Read** tool.
- **ssh stdout is UTF-8 but PowerShell decodes it as the console ACP -> Chinese logs arrive as
  mojibake**. Do not fight it: have the in-container script `json.dump(..., ensure_ascii=False)` to a
  file, `scp` the JSON down, and Read it. Mojibake is fine for `grep`-ing on ASCII markers like
  `render`, `DONE`, a version string or an image size.
- Local Python `C:\Users\asus\.workbuddy\binaries\python\versions\3.13.12\python.exe`
  (has **PIL**, **no** playwright / bs4 / mistune — so plugin browser paths can only be tested on the
  server). Local Node `C:\Users\asus\.workbuddy\binaries\node\versions\22.22.2-3\node.exe`.
- One-off `scp` may sporadically fail with
  `Could not stat C:\Users\asus/.ssh: Permission denied` (sandbox). Just **re-run the same command**.

## Phase 1 — local pre-flight (never skip)

1. `py_compile` every changed `.py`; `json.load` every changed `.json` (`_conf_schema.json`).
   - **注意 `_conf_schema.json` 类型约束**：AstrBot 仅支持 `['int', 'float', 'bool', 'string', 'text', 'list', 'file', 'object', 'template_list', 'dict']`，**严禁使用标准 JSON Schema 的 `integer`, `number`, `boolean`**，否则启动时报 `TypeError: 不受支持的配置类型 integer` 导致插件直接被卸载。
2. Plugin renderers embed **large inline JS strings** assigned as
   `_JS_FOO = r"""..."""`. A JS syntax error is invisible to `py_compile` and only explodes at
   runtime. Extract and check them:

   ```python
   blocks = re.findall(r'^(_JS_[A-Z_]+)\s*=\s*r"""(.*?)"""', text, re.S | re.M)
   # write each to <name>.js, then: node.exe --check <file>
   ```
   Use **raw strings** (`r"""`) for these JS blocks so `\s`, `\d` survive verbatim.

## Phase 2 — backup, upload, restart

```powershell
$sshOpts = @("-o","BatchMode=yes","-o","StrictHostKeyChecking=no","-o","ConnectTimeout=15")
# backup once per session dir, e.g. .bak_YYYYMMDD
& ssh $sshOpts $remote "cd $dir && mkdir -p .bak_20260921 && cp -f <files> .bak_20260921/ && rm -rf __pycache__"
foreach ($f in $files) { & scp $sshOpts "$local\$f" "${remote}:${dir}/$f" }
```

- **Always `rm -rf __pycache__`** before restarting, so stale `.pyc` cannot mask the update.
- Restart with `docker restart astrbot` (~30 s). AstrBot has no plugin hot-reload CLI.
  Give it `Start-Sleep -Seconds 32` then confirm
  `docker logs --tail 300 astrbot | grep -a '<plugin> ('` shows the new version.
- Note the handover-doc rule: to edit `data/config/*.json` you must `docker stop astrbot` first,
  otherwise the in-memory config is flushed over your edit. (Not needed for plugin *code*.)

## Phase 3 — in-container end-to-end test

Write the test locally, `scp` it to `/root/qqbot/data/`, run
`docker exec astrbot python /AstrBot/data/<test>.py`.
The container has the real deps (playwright, bs4, mistune, aiohttp) and the real network.

- Read cookies from `/AstrBot/data/config/astrbot_plugin_*_config.json` — **decode with
  `open(cp,"rb").read().decode("utf-8-sig")`**, plain `utf-8` raises `Unexpected UTF-8 BOM`.
- `sys.path.insert(0, "/AstrBot/data/plugins")` then `import <plugin>.renderer` works
  (namespace package, no `__init__.py` needed).
- Import plugin internals directly (`ZhihuRenderer._prepare_page`, `_JS_MARK_TARGET`, ...) to
  reproduce the production path exactly instead of a hand-rolled approximation.

## Phase 4 — visual proof

Numeric success (a file exists, a size is non-trivial) is **not** proof. Crop the produced image with
PIL, `scp` it down, and Read the PNG. (Whether `Read` actually renders it depends on the **running
model**, not the tool — probe once. On a text-only model it answers `Content filtered` /
`当前模型不支持图片`; then fall back to numeric/geometric checks against the expected layout and say
plainly that the visual proof was not obtained.)

- Crop a **targeted region** rather than the whole 15000 px tall slice — e.g. resolve an element's
  `getBoundingClientRect()` against the capture container to locate formulas, then
  `page.screenshot(clip=...)`.
- `page.screenshot(clip=...)` fails with *"Clipped area is either empty or outside the resulting
  image"* when the clip lies below the viewport — raise the viewport height first.
- **Do not chain the download into the same PowerShell command as the run.** A command like
  `scp script; ssh "docker exec ... python script"; scp out.png` can stall indefinitely on the
  Windows side even though the server finished (the PNG was already on disk and SSH answered
  `ALIVE` fine). Split it: run/inspect with one call, download with a fresh `scp` call. If output
  vanishes entirely, the PowerShell tool in this environment sometimes swallows stdout — write to
  a temp file, read it with the Read tool, and check the *artifact* rather than trusting stdout.

### Reusable scripts to keep in `E:\qqbot_cloud_deploy\`

Delete one-off probes after each investigation but keep these; they encode the coordinate math:

- `test_zhihu_regress.py` — production long-image render of a fixed article.
- `test_zhihu_p2035_check.py` — **production render + stage reproduction that tallies
  `{total, svg, chtml, previewOnly, none}` and dumps per-formula CSS boxes**. Adapt `URL` and run
  this first for any "formula not rendered" report.
- `test_zhihu_p2035_crop.py` — crops formulas out of the `partN.png` slices at `cssY * dsf`,
  stitching across slice boundaries. Adapt `UID`/`SAMPLES`.
- `test_zhihu_answer_check.py` — production render of an **answer permalink** (the path that goes
  through the error-page fallback) + stage reproduction + formula crops.
- `test_zhihu_ab_rewait.py` — **deterministic A/B harness**: reproduces the *post-fallback* state
  (question page + located answer) once, then measures the same state under two wait strategies.
  This is the model to copy whenever you must prove a wait-loop fix rather than eyeball it; a
  single page load can't show both behaviours, and question pages are flaky enough that each
  variant needs a navigation-retry loop until `focused.ok && textLen > 500`.

## AstrBot internals cheat-sheet (verified 2026-09-22)

Reconnaissance that took ~20 tool calls to establish. Start here next time.

### Paths & config

| What | Where |
|---|---|
| Host root | `/root/qqbot/` (host `data/` == container `/AstrBot/data`) |
| Core config | container `/AstrBot/data/cmd_config.json` — **UTF-8 WITH BOM → `open(p, encoding="utf-8-sig")`** |
| Core DB (SQLite) | `/AstrBot/data/data_v4.db` |
| Plugin code | `/AstrBot/data/plugins/<plugin>/` |
| Plugin data | `/AstrBot/data/plugin_data/<plugin>/` — note **singular `plugin_data`** |
| Path helpers | `astrbot.core.utils.astrbot_path`: `get_astrbot_data_path()`, `get_astrbot_plugin_data_path()`, `get_astrbot_root()` (honours `$ASTRBOT_ROOT`, else `os.getcwd()`) |

`plugin_set: ["*"]`, providers carry `"modalities": [..., "tool_use"]`, and `platform` is
`{type: aiocqhttp, ws_reverse_host, ws_reverse_port}` — i.e. **AstrBot is the WS server and NapCat
dials into it**; there is no OneBot HTTP endpoint to curl from outside. From a plugin you still get
a live client via `event.bot.call_action("<action>", **params)` (aiocqhttp events set `self.bot`).

### Registering an LLM tool: the schema comes from the DOCSTRING, not the type hints

`register_llm_tool` parses `awaitable.__doc__` with `docstring_parser` and builds the JSON schema
from the **`Args:` block**. Consequences:

- Every documented arg must carry a type, e.g. `group_id(string): ...`, or registration raises
  `ValueError: ... 缺少类型注释`.
- Allowed types (`SUPPORTED_TYPES`): `string`, `number`, `object`, `array`, `boolean`. Python names
  are mapped first (`PY_TO_JSON_TYPE`: `int/float→number`, `bool→boolean`, `str→string`,
  `dict→object`, `list/tuple/set→array`), so writing `limit(int)` or `limit(number)` both work.
- The syntax for generics is `list[string]` (parsed by regex `(\w+)\[(\w+)\]`).
- **A trailing empty `Args:` leaks into the description** — omit the whole `Args:` line for
  zero-argument tools.
- Params appear in the schema as `{"type","name","description"}`; nothing is marked `required`, so
  give every parameter a default and coerce defensively (`int(str(v))` with try/except) — the model
  may send `"60"` for a `number`.
- Global registry: `from astrbot.core.provider.register import llm_tools` (a
  `FunctionToolManager`). Inspect with `llm_tools.func_list` — there is **no `get_tool()`**.
- Hooks: `filter.command(name, alias={...})` (Chinese names/aliases are fine),
  `filter.llm_tool(name=...)`, `filter.on_llm_request()` with signature `(self, event, req)` where
  `req.system_prompt` is writable. `event.is_admin()` exists.
- Command args are **not** parsed into the handler for you unless you declare extra params; the
  parsed dict is stashed at `event.set_extra("parsed_params", ...)`. `event.message_str` is an
  instance attribute that still contains the wake prefix + command name, so strip it yourself.

### Databases worth knowing

- `personas`: `persona_id`, `system_prompt`, **`tools`/`skills`**. In
  `astr_main_agent._ensure_persona_and_skills` a resolved persona **replaces** the built-in default
  prompt, and `tools IS NULL` → inject *all* active tools, `tools = []` → inject **none**
  (foot-gun), `tools = ["a"]` → only those. Always write `NULL`, never `[]`.
- `conversations`: the bot's own session contexts. The `user_id` column holds the **umo key**, e.g.
  `napcat_gandalf:GroupMessage:529535624` / `napcat_gandalf:FriendMessage:247646179`. `content` is a
  JSON list of `{role, content}` (content may be a list of `text`/`think`/`image_url` parts).
  AstrBot already folds long histories into a leading "对话历史全景总结" user message.
- `platform_message_history` exists but was **empty** — don't rely on it.
- `E:\astrbot_data\..\data\plugin_data\astrbot_plugin_self_learning\messages.db` — the richest
  source of *group* chat history:
  - `raw_messages`: **all** group messages including chatter that never addressed the bot
    (columns `sender_name`, `sender_id`=QQ, `message`, `group_id`, `timestamp`, `platform`).
    `sender_qq`, `message_id`, `reply_to` are **NULL**; the bot's own messages are **absent**.
  - `bot_messages`: the bot's own replies, grouped by `group_id`.
  Merge the two to reconstruct a full transcript; OpenAI-style markdown images are embedded in the
  text (`![alt](url)`) so compress them to `[图片]` before feeding a model.
- Reading another plugin's SQLite while it writes: open `file:PATH?mode=ro` with `timeout=3.0` and
  **fall back to copying the db + `-wal` + `-shm` into `tempfile.mkdtemp()` and reading that
  snapshot** — otherwise a WAL writer can hand you `database is locked`.

### Verify a plugin WITHOUT sending any QQ message

Safe, high-fidelity pattern — this exercises the real handler bodies end-to-end while the live bot
keeps running. Do **not** send test messages into real groups.

```python
import importlib.util, os, sys
os.chdir("/AstrBot"); sys.path.insert(0, "/AstrBot")
spec = importlib.util.spec_from_file_location(
    "mod", "/AstrBot/data/plugins/<plugin>/main.py")
m = importlib.util.module_from_spec(spec); sys.modules["mod"] = m
spec.loader.exec_module(m)          # also re-registers tools; harmless, separate process

class StubEvent:                    # only what the handlers touch
    def __init__(self): self.message_str = "/聊天记录 30"; self._extra = {}; self.bot = None
    def get_group_id(self): return "529535624"
    def get_sender_id(self): return "247646179"
    def get_extra(self, k, d=None): return self._extra.get(k, d)
    def set_extra(self, k, v): self._extra[k] = v
    def is_admin(self): return True
    def plain_result(self, t): return t

p = object.__new__(m.MyPlugin)      # bypass Star.__init__() -> no real Context/Config needed
p.config = {...}                    # a dict subclass with .get()
p.store = m.SomeStore("/AstrBot/data")
# then just await p.tool_xxx(StubEvent()) and print the returned string
```

Assert on the **actual returned text** (headings, time range, record count, a known message body),
and also print the tool schema from `llm_tools.func_list` to confirm the model will see sane params.
`object.__new__` is the trick that avoids needing a live `Context`/`AstrBotConfig`.

### Plugin scaffolding files

`main.py` + `metadata.yaml` (`name/desc/version/author/support_platforms/astrbot_version`) +
`_conf_schema.json` (per-key `description/type/default/hint`, `options` for enums) + `README.md`.
`@register(name=..., author=..., desc=..., version=...)` on a `Star` subclass; version must be kept
in sync across `metadata.yaml`, the decorator and the load log — AstrBot prints
`Plugin <name> (<version>) by <author>` at boot, which is your cheapest success signal.

## Phase 5 — verify sync & clean up

- Prove remote == local with `md5sum` on the server vs `Get-FileHash -Algorithm MD5` locally
  (or `md5sum` on both when using bash).
  Do not assume scp delivered the final revision.
- Delete the scratch test scripts / JSON / crops from `/root/qqbot/data/` when done; leave
  `article_screenshot.png`-style pre-existing files alone.
- Also delete the container-side copies (`docker exec astrbot rm -f /tmp/<script>.py`).
- Keep the `.bak_<date>` directory, and archive the verification scripts locally under
  `E:\qqbot_cloud_deploy\_verify_<topic>\` as evidence.
- Before claiming "the bot can now do X", confirm **no command-name collision** (grep all plugins
  for `@filter.command("...")`), that `command_conflicts` has 0 rows, and that the boot log shows
  your tools in `Added llm tool:` **and** that the rest of the tool list is still present (proves
  you didn't accidentally disable anything).

## Playwright scraping traps (Zhihu / WeChat)

- **Error pages are returned to headless browsers.** Zhihu answers the *answer permalink*
  (`/question/{qid}/answer/{aid}`) with a `出了一点问题 / 我们正在解决 / 去往首页` page while the
  question page and `zhuanlan` articles load fine. Detect it (marker text or `.ErrorPage`), retry
  once, then fall back to opening the question page and locating the answer by
  `a[href*="/answer/<aid>"]` -> `closest(".ContentItem")`. On total failure **abort** instead of
  emitting a blank strip, and degrade to plain text rather than sending nothing.
- **Never screenshot on a fixed `wait_for_timeout`.** Lazy images and MathJax/KaTeX settle late.
  Gate on: progressive scroll through the document -> write `data-original`/`data-actualsrc` back
  into `src` -> poll until every `img` is `complete && naturalWidth > 0` -> poll until every
  `.ztext-math` has a MathJax/KaTeX descendant and `MathJax.Hub.queue.pending === 0` -> innerHTML
  fingerprint stable twice. Always keep an overall timeout so a wedged page can't hang the bot.
- **Zhihu renders math server-side as `<img class="ztext-math" ...>` in some views** — skip `IMG`
  nodes in the math-completeness poll and let the image poll own them, otherwise you wait forever.
- **Crop to content by cloning, not by picking the biggest element.** "Largest innerHTML" picks the
  wrapper that carries author cards / vote buttons / copyright, and `document.body` drags in the
  header, sidebar, ads and comments. Instead: pick by an ordered selector list, clone the node into
  an isolated white stage `#zh-capture-stage`, `display:none !important` every other `body > *`, and
  screenshot only the stage.
- Keep the **viewport width at desktop size** and only change its height. Shrinking the viewport to
  the content width trips responsive `@media` rules and re-lays-out the cloned content.
- Do not force `max-width: 100%` / `overflow: visible` onto MathJax or KaTeX subtrees — it reflows
  long formulas. Exclude by class (`MathJax`, `katex`, `mjx`).
- Hide scrollbars (`::-webkit-scrollbar{display:none}`) or their width can push the stage out of view.
- Chromium caps a single capture around 16000 px; clamp the viewport and warn rather than silently
  emitting a blank image.

---

## Stage 4 — Publishing to GitHub (open-sourcing)

Environment facts for this machine (verified 2026-09):

- **No `gh` CLI installed.** `Get-Command gh` is empty. Anything that needs the GitHub API
  (repo description, topics, creating a Release) must be done on the web UI or by installing gh.
  Pushing code + tags works fine over SSH.
- Git: `E:\Git\cmd\git.exe`. SSH key `~/.ssh/id_rsa` is already registered to GitHub account
  `VesperaZephyr`. Verify with `ssh -o BatchMode=yes -T git@github.com`.
- Global identity: `VesperaZephyr` / `204538172+VesperaZephyr@users.noreply.github.com`.

### Pre-publish secret audit (mandatory, do this BEFORE every push)

These plugins handle real site cookies, so scan before publishing:

```powershell
$patterns = @('zse_ck','__zse','d_c0','_zap','z_c0','cookie','token','secret','api_key',
              'password','<server-ip>','root@','BEGIN.*PRIVATE')
Select-String -Path <repo>\*.py,<repo>\*.json,<repo>\*.yaml,<repo>\*.md -Pattern $patterns
```

Read every hit and classify it. A hit on `cookie_str` / `headers["Cookie"]` / a config hint is
**fine** — that's an argument name. A hit that is an actual credential value is a **blocker**:
move it to config, purge it from history, then publish. Also confirm `.gitignore` covers
`__pycache__/`, `*.py[cod]`, `.vscode/`, `.idea/`.

### Push sequence

```powershell
git -C <repo> add -A
git -C <repo> commit -m "<message>"      # UTF-8 is fine
git -C <repo> tag -f -a v<X.Y.Z> -m "..."
git -C <repo> push origin main
git -C <repo> push -f origin refs/tags/v<X.Y.Z>
git -C <repo> rev-list --left-right --count main...origin/main   # expect "0	0"
git -C <repo> ls-tree -r --name-only origin/main                 # confirm file list
```

Then bump `version` in `metadata.yaml` **and** the badge + changelog in `README.md`, and make sure
`metadata.yaml:repo` points at the public URL — AstrBot surfaces that field to users.

### Gotcha: PowerShell mangles UTF-8 output

Console output of Chinese text (commit subjects, YAML, logs) renders as mojibake like
`閲嶅啓娓叉煋鍣`. **The bytes on disk / on GitHub are correct.** Confirm real content with the
Read tool — never "fix" a file because the terminal looked garbled.

---

## Stage 5 — Deciding "are the formulas actually rendered?"

This is the single most error-prone judgement in these plugins. Hard-won rules:

### Never treat a placeholder as proof of completion

`.MathJax_Preview` is inserted by MathJax **before** typesetting and **survives** afterwards
(usually emptied). Any readiness check that counts it as "done" will fire while typesetting is
still in flight. Real incident: a wait loop treated `pendingMath == 0` as ready, so as soon as
MathJax inserted preview placeholders the loop exited ~1.2 s later (DOM length unchanged twice)
and screenshotted formulas that had not been rendered yet — the long image came out with blank
formulas while the surrounding text was fine.

Rule: require a **real output element** (`.MathJax_SVG`, `.MathJax_SVG_Display`, `.MathJax_CHTML`,
`.MathJax_MathML`, `mjx-container`, `.katex`) **and** a non-degenerate bounding box
(`width > 1 && height > 1`). A bare `<svg>` alone is not enough.

### A cloned node will never be typeset afterwards

These plugins screenshot by cloning the content node into an isolated stage. **MathJax does not
walk into that clone.** Whatever was unrendered at clone time stays unrendered forever: any wait
performed only *inside* the stage waits for something that cannot happen. Real incident: after the
error-page fallback navigated the page, the wait was skipped, so all 31 formulas were cloned
un-typeset and the long image came out as raw LaTeX source.

So order the flow as **navigate -> wait/typeset on the original page -> clone -> screenshot**, and
whenever a fallback navigation happens, re-run the readiness step before cloning. Keep a flag
telling the caller "a navigation occurred"; don't assume one readiness pass covers it.

### Reproduce it deterministically

Don't wait for a flaky race. Load a page that already renders, then **mutation-test** it:

```js
const m = document.querySelector(".ztext-math");
(m.querySelector(".MathJax_SVG") || m.querySelector("svg")).remove();  // simulate mid-typeset
// now compare the old predicate vs the new one on the same DOM
```

If old says `pending == 0` and new says `pending >= 1`, the bug is proven. This is far more
convincing than "it looks right now".

### Scope the readiness wait to the target container

If the wait runs *before* the content container is marked, its root degrades to `document.body`.
On a question page that means waiting for **every** answer's images and formulas — it times out
and you screenshot mid-render. Mark/select the container first (a "pre-mark" that doesn't abort
on failure is enough), then wait, then re-confirm the mark.

### Cropping a product to inspect a formula — mind the scale factor

`element.screenshot()` output is multiplied by `device_scale_factor` (commonly 2). Cropping the
product with **CSS-pixel** coordinates yields a wrong region and a misleadingly tiny/blank PNG
(~180 bytes for a blank crop). Multiply coordinates by the scale factor first. A crop of a few
hundred bytes is blank; a real formula crop is 1–10 KB.

### `_MAX_CAPTURE_PX` / 16000 is not what truncates your image

Chromium's `captureBeyondViewport` (used by modern Playwright `element.screenshot()`) handled a
24309 CSS-px stage fine, producing a 1520x48618 product. A short product means the element
itself was short, not that 16000 truncated it. Verify with the real product size before blaming
the clamp.

### Slice the long image; the `_full.png` is gone by then

`_slice_image()` **deletes** `<uid>_full.png` after slicing, so `render_direct_zhihu_page()`
returns only `partN.png`. To crop a formula out of the product, map CSS coordinates onto the
slices yourself:

```
devY      = cssY * dsf                 # dsf = device_scale_factor (2 here)
sliceIdx  = devY // sliceHeight        # sliceHeight is the slice's *pixel* height, 11588 here
offsetIn  = devY %  sliceHeight
```

If a crop straddles a boundary, crop the two overlapping pieces and stitch just those — do
**not** paste all slices into one canvas first. 7 x 1520x11588 in RGBA is ~490 MB and will hurt
a 2 GB container.

### Score the whole product, not one sample

A single sampled formula can look fine while 400 others are blank. Emit a global tally from the
stage and assert on it: `{total, svg, chtml, previewOnly, none}`. A healthy run is
`svg == total` with `previewOnly == 0` and `none == 0`. `previewOnly > 0` means the wait loop
released before typesetting — the exact `MathJax_Preview` bug. Also compare the container's
`textLen` before and after the wait (`18911 -> 21121` here) as a cheap sanity check that lazy
content actually landed.

### Zhihu page-shape notes

- Answers load from the API, so the browser channel is only used for the *screenshot*; the
  screenshot URL is still the raw answer permalink, which Zhihu answers with an error page for
  headless browsers. Fallback: retry, then open the question page and locate the answer via
  `a[href*="/answer/<aid>"]` -> `closest(".ContentItem")`.
- Question and `zhuanlan` pages load fine headlessly. Topic feeds (`/api/v4/topics/{id}/...`) and
  `search_v3` returned 403 / no `ztext-math` content in testing — don't rely on them to find
  formula samples. Ask the user for a concrete failing URL instead of hunting for one.

### Question pages: formulas typeset on visibility, and scrolling is lethal

Two hard facts, both measured on the real server. Getting these wrong costs hours.

1. **A question page only typesets the math that has been in the viewport.** With the target
   answer below the fold, waiting 35 s changes nothing: `scopeMath=31, scopeSvg=0, scopeNone=31`.
   The 19 already-rendered SVGs in the document all belonged to answers that had been on screen.
   Note there wasn't even a `MathJax_Preview` — MathJax had never touched those nodes.
2. **Scrolling a question page to the bottom destroys it.** Immediately after
   `_JS_SCROLL_THROUGH`, `document.title` flips to `出了一点问题`, `bodyLen` collapses
   `17245 -> 18`, `scopeMath` goes to 0. The SPA requested more answers and the anti-bot
   bounced the headless session to the error page. The target answer typically sits at the
   very end of the document (`targetTop=9600`, `docH=11821`, height 2100), so **any
   "scroll it into view" is equivalent to "scroll to the bottom" — scrolling cannot work here.**

Approaches that look clever and do not work:

- `page.route(...)` + `route.abort()` on `/api/v4/questions/*/answers|feeds` before scrolling:
  the page still dies. **The aborted request itself triggers the SPA's error handler**, so you
  land on the same error page.
- Pruning the other answers (`.List-item` removal) with no scroll: the page survives, but the
  target stays at `0/31` because nothing ever brings it into view or asks for a typeset.

**The fix: skip scrolling entirely and ask MathJax to typeset the target container.**

```js
// MathJax v2 (what Zhihu ships); fall back to v3 entry points
MathJax.Hub.Queue(["Typeset", MathJax.Hub, el]);
// v3: await MathJax.typesetPromise([el]);  or  MathJax.typeset(el)
```

Measured on the same answer, same page state, only the wait logic varied:

| variant | page alive | formulas |
|---|---|---|
| old (clone straight into the stage) | yes | **0 / 31** |
| new (force typeset, then clone) | **yes** | **31 / 31** |

Dispatch on page shape rather than always scrolling: treat **only** `/question/<id>` as a
question page and skip the scroll there; `zhuanlan` and `/question/<id>/answer/<aid>` are safe to
scroll (and `zhuanlan` long articles need it for lazy images). Re-push the typeset up to 3 times
at ~5 s intervals in case MathJax wasn't loaded yet at the first attempt.

### Investigate "what is this overlay?" with elementsFromPoint, not by guessing selectors

A translucent `nba shady` was overlapping the first formula in a long image, and I nearly
"fixed" it by adding cleanup selectors. Don't. Walk the three possible carriers instead:

1. Search the whole document by `textContent` for the string — nothing.
2. Scan every element's `::before` / `::after` `content` — only an unrelated `"..."`.
3. Point-cast with `document.elementsFromPoint(x, y)` (converting the product's device
   coordinates back to CSS by dividing by the scale factor). The top of the hit stack was the
   `<img class="origin_image">` itself with **nothing stacked above it**.

Conclusion: it was baked into the image pixels. Downloading the source file
(`https://picx.zhimg.com/v2-....jpg`) confirmed it — Zhihu watermarks user-uploaded images with
a random word pair to trace leaks. Worse, the "formula" I had assumed was MathJax output was
**part of that exam-paper screenshot all along**. So: when the DOM and pseudo-elements both come
up empty, suspect image pixels, and download the image before touching any cleanup rule.

The transferable rule for anti-bot pages: **avoid triggering the action at the source rather
than adding post-hoc fallbacks**. Here the trigger was scrolling — and aborting the request was
an equally good trigger.
