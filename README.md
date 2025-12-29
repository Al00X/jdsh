# 🌐 JDSH - JDownloader Shell

Control and Manage your JDownloader within your terminal with _ease_.

Designed for Linux servers/headless environments where you need full control without a GUI; or if you just love using CLI!

Packed with various **CLI Commands** & **Interactive Mode (TUI)**.

This tool will use your JDownloader local API, which you will need to enable manually. It uses [myjadpi](https://github.com/mmarquezs/My.Jdownloader-API-Python-Library/) package under the hood to work (kudos to the author of this package).

## Setup

1.  Obviously have **JDownloader 2** installed.
2.  Enable JDownloader's Local API:
    *   Edit `<JD_FOLDER>/cfg/org.jdownloader.api.RemoteAPIConfig.json`.
    *   Set: `"deprecatedapienabled": true`
    *   Restart JDownloader.

3.  Clone this repository or download the source code:
    ```bash
    git clone https://github.com/al00x/jdsh.git
    cd jdsh
    ```

4.  Install the package using pip:
    ```bash
    pip install .
    ```
    
    *Note: If you want to modify the code, use `pip install -e .` instead.*

## Usage

You can now use the `jd` command globally from anywhere in your terminal.

### Interactive Mode
Simply run `jd` without arguments to enter the interactive mode.

```bash
jd
```

*   **Tips:** 
    *   Press `s` to Start/Stop downloads. 
    *   Press `Ctrl+C` to quit.

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

Create file at `~/.config/jdsh/jdsh.config`, with content below.
You may uncomment any line and change when you need.

```ini
[settings]
# HOST = 127.0.0.1
# PORT = 3128

# change the rate of interactive mode update interval. Based on seconds
# REFRESH_RATE = 1.0
```

---
#### Enjoying the tool? Your supports would keep me at it! 💖

[![Donate with Bitcoin](https://img.shields.io/badge/Donate-Bitcoin-orange.svg?logo=bitcoin)](bc1qc06cpqe26m6fpf5guw6x5vp3pfwrzavy2yjrh7)
[![Donate with Tehter (BEP20)](https://img.shields.io/badge/Donate-Tether%20(BEP20)-blue.svg?logo=tether)](0x283857017efb4B1F9fAe57F4599C20FD5bCE1871)