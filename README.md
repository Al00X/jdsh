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

*   **Tips:** 
    *   Press `s` to Start/Stop downloads. 
    *   Press `x` to clear the pending queue (after confirmation; files on disk are kept).
    *   Archives being extracted (or waiting for extraction) show up automatically with their progress, also in `jd status`.
    *   Press `l` to turn the download speed limit on/off, `L` to enter a new limit (e.g. `5M`).
    *   Press `Tab` (or `1`/`2`) to switch between the Downloads and LinkGrabber pages.
    *   Press `q` or `Ctrl+C` to quit.

*   **LinkGrabber page:**
    *   `↑`/`↓`/`PgUp`/`PgDn` move, `→`/`←` (or `Enter`) open/close a package to inspect its links.
    *   `Space` selects a link or a whole package, `Shift+↑`/`Shift+↓` extends the selection row by row, `a` selects all/none.
    *   `c` confirms the selection (or the item under the cursor), `C` confirms and starts it right away.
    *   `x`/`Del` removes the selection (or the item under the cursor) from the LinkGrabber after asking for confirmation.

### Commands Overview

```bash
╭─ JDSH        ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│                                                                                                                                                                      │
│    Dashboard                                                                                                                                                         │
│    jd                                                Launch the Interactive TUI                                                                                      │
│    status                                            Show a static snapshot of the queue and extraction                                                              │
│                                                                                                                                                                      │
│    Queue Management                                                                                                                                                  │
│    list (ls)                [-d]                     List active downloads                                                                                           │
│    grabber                  [-d]                     List pending packages inside LinkGrabber                                                                        │
│    add                      <url>...                 Add links to LinkGrabber                                                                                        │
│    confirm                  [pkg...] [-s]            Move packages (all or by ID/name) to Queue, -s starts them                                                      │
│    remove (rm)              <uuid>...                Remove items by ID                                                                                              │
│                                                                                                                                                                      │
│    Controls                                                                                                                                                          │
│    start                    [pkg...]                 Start/Resume downloads, or force-start packages                                                                 │
│    stop                                              Pause/Stop downloads                                                                                            │
│    limit                    [rate]                   Show or set download speed limit (5M, 500K, on, off)                                                            │
│    clear                    [-p]                     Remove finished items from list, -p removes pending ones                                                        │
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

  # Confirm and start a single package by ID or name:
  jd confirm "carrie" -s

  # detailed list view:
  jd ls -d
```

## Config
By default, the application runs with standard settings (`Host: 127.0.0.1, Port: 3128`). You can override these defaults by creating a configuration file.

Create file at `~/.config/jdsh/jdsh.config`, with the contents below.
You may uncomment any line and change when you need.

```ini
[settings]
# HOST = 127.0.0.1
# PORT = 3128

# update interval of interactive mode, in seconds
# REFRESH_RATE = 1.0
```

---
#### Enjoying the tool? Your supports would keep me at it! 💖

[![Donate with Bitcoin](https://img.shields.io/badge/Donate-Bitcoin-orange.svg?logo=bitcoin)](https://blockchain.com/btc/address/bc1qvmv8cnfd0hfc82rm3r9zzq6uheejgw5hfzn426)
[![Donate with Ethereum](https://img.shields.io/badge/Donate-Ethereum-silver.svg?logo=ethereum)](https://etherscan.io/address/0xA25c8eF121ba010d09c6A7E1228be7da523933f8)
[![Donate with Tehter (BEP20)](https://img.shields.io/badge/Donate-Tether%20(BEP20)-blue.svg?logo=tether)](https://bscscan.com/address/0x283857017efb4B1F9fAe57F4599C20FD5bCE1871)
