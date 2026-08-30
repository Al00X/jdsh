# 🟠 JDSH - JDownloader Shell 🔵

![preview](.github/preview-v1.0.1.webp)

Control and Manage your JDownloader within your terminal with _ease_.

Designed for Linux servers/headless environments where you need full control without a GUI; or if you just love using CLI!

Packed with various **Commands** & **Interactive Mode (TUI)**.

This tool will use your JDownloader local API, which you will need to enable manually. It uses [myjadpi](https://github.com/mmarquezs/My.Jdownloader-API-Python-Library/) package under the hood to work (kudos to the author of this package).

## Installation
```bash
pip install jdsh
```

## Setup

0.  Obviously have **JDownloader 2** installed.
1.  Enable JDownloader's Local API:
    *   Edit `<JD_FOLDER>/cfg/org.jdownloader.api.RemoteAPIConfig.json`.
    *   Set `"deprecatedapienabled": true`
    *   _(Optional)_ you may also need to set `deprecatedapilocalhostonly` to `false` if you want to access it from remote. 
    *   Restart JDownloader.

## Usage

You can now use the `jd` command globally from anywhere in your terminal.

### Interactive Mode
Simply run `jd` without arguments to enter the interactive mode.

```bash
jd
```

The interactive mode shows the same tree as the JDownloader GUI: packages
with their links, split across a **Downloads** and a **Link Grabber** tab.

| Key | Action |
| --- | --- |
| `Tab` | Switch between Downloads and Link Grabber |
| `↑` `↓` (or `k` `j`) | Move the cursor |
| `→` `←` | Expand / collapse a package |
| `Space` | Mark the row under the cursor |
| `a` | Mark every row, or clear the marks |
| `Esc` | Clear the selection |
| `Enter` | Open the context menu on the selection |
| `p` | Show the properties of the selected row |
| `s` | Start / stop downloads |
| `c` | Move the whole Link Grabber to the download list |
| `q` (or `Ctrl+C`) | Quit |

The context menu acts on every marked row at once, so a dozen links can be
forced, reset, disabled or removed in a single action. Destructive entries
ask for confirmation first.

### Commands Overview

```bash
╭─ JDSH        ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│                                                                                                                                                                      │
│    Dashboard                                                                                                                                                         │
│    jd                                                Launch the Interactive TUI                                                                                      │
│    status                                            Show a static snapshot of the queue                                                                             │
│                                                                                                                                                                      │
│    Queue Management                                                                                                                                                  │
│    list (ls)                [-d]                     List active downloads                                                                                           │
│    grabber                  [-d]                     List pending links inside LinkGrabber                                                                           │
│    add                      <url>...                 Add links to LinkGrabber                                                                                        │
│    confirm                                           Move all pending links to Queue                                                                                 │
│    remove (rm)              <uuid>...                Remove items by ID                                                                                              │
│                                                                                                                                                                      │
│    Controls                                                                                                                                                          │
│    start                                             Start/Resume downloads                                                                                          │
│    stop                                              Pause/Stop downloads                                                                                            │
│    clear                                             Remove finished items from list                                                                                 │
│    replace                  <uuid> <url>             Replace a dead link URL                                                                                         │
│                                                                                                                                                                      │
│    Utils                                                                                                                                                             │
│    version                                           Show shell and core versions                                                                                    │
│    help                                              Show this help message                                                                                          │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯

  Usage: jd [COMMAND] [ARGS]...

  # Run the interactive mode:
  jd

  # Add links, check them, then start:
  jd add "http://site.com/file.exe"
  jd add "http://site.com/archive1.zip" "http://site.com/archive2.zip"
  jd grabber
  jd confirm

  # detailed list view:
  jd ls -d
```

## Config
By default, the application runs with standard settings (`Host: 127.0.0.1, Port: 3128`). You can override these defaults by creating a configuration file.

Create file at `~/.config/jdsh/jdsh.conf`, with the contents below.
You may uncomment any line and change when you need.

```ini
[settings]
# HOST = 127.0.0.1
# PORT = 3128

# update interval of interactive mode, in seconds
# REFRESH_RATE = 1.0

# colours of the selected and of the marked rows, for themes the
# defaults do not suit
# SELECTION_STYLE = bold #ffffff on #1c3f6e
# MARK_STYLE = #ffffff on #16293f
```

---
#### Enjoying the tool? Your supports would keep me at it! 💖

[![Donate with Bitcoin](https://img.shields.io/badge/Donate-Bitcoin-orange.svg?logo=bitcoin)](https://blockchain.com/btc/address/bc1qvmv8cnfd0hfc82rm3r9zzq6uheejgw5hfzn426)
[![Donate with Ethereum](https://img.shields.io/badge/Donate-Ethereum-silver.svg?logo=ethereum)](https://etherscan.io/address/0xA25c8eF121ba010d09c6A7E1228be7da523933f8)
[![Donate with Tehter (BEP20)](https://img.shields.io/badge/Donate-Tether%20(BEP20)-blue.svg?logo=tether)](https://bscscan.com/address/0x283857017efb4B1F9fAe57F4599C20FD5bCE1871)
