import os
import re
import time
import sys

try:
    # Linux & MacOS
    import select
    import tty
    import termios
except ImportError:
    # Windows
    select = tty = termios = None
    import msvcrt

from rich.live import Live
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.console import Console
from rich.align import Align
from rich.progress_bar import ProgressBar
from rich.text import Text
from rich import box

from . import utils, config

TAB_DOWNLOADS = 0
TAB_LINKGRABBER = 1

MODE_LIST = "list"
MODE_MENU = "menu"
MODE_PROPERTIES = "properties"
MODE_CONFIRM = "confirm"


class KeyboardInput:
    # Cursor keys arrive as an escape sequence: ESC followed by '[' or 'O'
    # (the latter when the terminal is in application cursor mode, which is
    # common on an alternate screen) and a final letter.
    ARROWS = {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}
    ESCAPE_SEQUENCE = re.compile(r"\x1b[\[O]([A-D])")

    def __init__(self):
        self._pending = ""

    def __enter__(self):
        if termios:
            self.old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        return self

    def __exit__(self, type, value, traceback):
        if termios:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)

    def _drain(self):
        """Read straight from the file descriptor.

        Reading through sys.stdin would pull the whole escape sequence into
        Python's own buffer while select() still reports the descriptor as
        empty, leaving the rest of the sequence stranded.
        """
        while select.select([sys.stdin], [], [], 0)[0]:
            data = os.read(sys.stdin.fileno(), 1024)
            if not data:
                break
            self._pending += data.decode("utf-8", errors="ignore")

    def get_key(self):
        if termios:
            self._drain()
            if not self._pending:
                return None

            if not self._pending.startswith("\x1b"):
                key, self._pending = self._pending[0], self._pending[1:]
                return key

            match = self.ESCAPE_SEQUENCE.match(self._pending)
            if match:
                self._pending = self._pending[match.end():]
                return self.ARROWS[match.group(1)]

            # A bare ESC, or a sequence we do not handle: drop one character.
            self._pending = self._pending[1:]
            return "\x1b"

        elif msvcrt:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b"\x00", b"\xe0"):
                    return {b"H": "UP", b"P": "DOWN", b"M": "RIGHT", b"K": "LEFT"}.get(msvcrt.getch())
                try:
                    return ch.decode("utf-8", errors="ignore")
                except Exception:
                    pass
        return None


# --- rows -------------------------------------------------------------------
#
# Packages and their links share one flat list, so the cursor can walk over
# both, the way the tree in the GUI does.

class Row:
    __slots__ = ("kind", "item", "parent")

    def __init__(self, kind, item, parent=None):
        self.kind = kind          # "pkg" or "link"
        self.item = item
        self.parent = parent      # the package a link belongs to

    @property
    def is_package(self):
        return self.kind == "pkg"

    @property
    def uuid(self):
        return self.item.get("uuid")

    @property
    def name(self):
        return self.item.get("name", "?")

    def ids(self):
        """(link_ids, package_ids) as the API expects them."""
        if self.is_package:
            return [], [self.uuid]
        return [self.uuid], []


def build_rows(packages, expanded):
    rows = []
    for pkg in packages:
        rows.append(Row("pkg", pkg))
        if pkg.get("uuid") in expanded:
            for link in pkg.get("_links", []):
                rows.append(Row("link", link, pkg))
    return rows


# --- context menu -----------------------------------------------------------

class MenuEntry:
    def __init__(self, label, action, confirm=False):
        self.label = label
        self.action = action
        self.confirm = confirm


def context_menu(tab, row):
    """The actions the API actually supports for this row."""
    enabled = row.item.get("enabled", True)
    toggle = MenuEntry("Disable" if enabled else "Enable", "toggle_enabled")

    if tab == TAB_LINKGRABBER:
        entries = [
            MenuEntry("Move to download list", "move_to_downloads"),
            toggle,
            MenuEntry("Remove", "remove", confirm=True),
        ]
    else:
        entries = [
            MenuEntry("Force download", "force"),
            toggle,
            MenuEntry("Reset", "reset", confirm=True),
            MenuEntry("Remove", "remove", confirm=True),
        ]
        if row.is_package:
            entries.insert(3, MenuEntry("Delete finished links", "cleanup", confirm=True))

    if row.is_package:
        entries.insert(0, MenuEntry("Collapse / Expand", "expand"))

    entries.append(MenuEntry("Properties", "properties"))
    return entries


def run_action(client, tab, row, action):
    """Perform one menu action. Returns the message to show in the footer."""
    link_ids, package_ids = row.ids()
    grabber = tab == TAB_LINKGRABBER
    what = "Package" if row.is_package else "Link"

    if action == "toggle_enabled":
        enable = not row.item.get("enabled", True)
        client.set_enabled(enable, link_ids, package_ids, grabber=grabber)
        return f"{what} {'enabled' if enable else 'disabled'}"

    if action == "force":
        client.force_download(link_ids, package_ids)
        return f"{what} forced to start"

    if action == "reset":
        client.reset_links(link_ids, package_ids)
        return f"{what} reset"

    if action == "remove":
        client.remove(link_ids, package_ids, grabber=grabber)
        return f"{what} removed"

    if action == "cleanup":
        client.cleanup_finished(link_ids, package_ids)
        return "Finished links deleted"

    if action == "move_to_downloads":
        client.move_to_downloadlist(link_ids, package_ids)
        return f"{what} moved to the download list"

    return ""


def properties(row):
    """Key/value pairs worth showing, skipping what the API did not return."""
    item = row.item
    fields = [
        ("Name", item.get("name")),
        ("UUID", item.get("uuid")),
        ("Type", "Package" if row.is_package else "Link"),
        ("Status", item.get("status")),
        ("Extraction", item.get("extractionStatus")),
        ("Size", utils.human_size(item.get("bytesTotal", 0))),
        ("Loaded", utils.human_size(item.get("bytesLoaded", 0)) if "bytesLoaded" in item else None),
        ("Links", item.get("childCount")),
        ("Online / Offline", None if item.get("availableOnlineCount") is None
         else f"{item.get('availableOnlineCount')} / {item.get('availableOfflineCount', 0)}"),
        ("Availability", item.get("availability")),
        ("Host", item.get("host") or (", ".join(item["hosts"]) if item.get("hosts") else None)),
        ("Enabled", "yes" if item.get("enabled", True) else "no"),
        ("Priority", item.get("priority")),
        ("Speed", f"{utils.human_size(item['speed'])}/s" if item.get("speed") else None),
        ("ETA", utils.human_eta(item["eta"]) if item.get("eta") else None),
        ("Save to", item.get("saveTo") or (row.parent.get("saveTo") if row.parent else None)),
        ("URL", item.get("url")),
        ("Comment", item.get("comment")),
    ]
    return [(k, str(v)) for k, v in fields if v not in (None, "", [])]


# --- rendering --------------------------------------------------------------

def _package_progress(pkg):
    total = pkg.get("bytesTotal") or 0
    done = pkg.get("bytesLoaded") or 0
    if pkg.get("finished"):
        return 100.0
    if not total:
        return 0.0
    return min(100.0, (done / total) * 100)


def _package_status(pkg):
    if pkg.get("status"):
        return pkg["status"]
    if pkg.get("finished"):
        return "Finished"
    if pkg.get("running"):
        return "Downloading"
    if not pkg.get("enabled", True):
        return "Disabled"
    return "Queued"


def _visible_window(rows, cursor, height):
    """Scroll the list so the cursor stays inside the viewport."""
    if len(rows) <= height:
        return rows, 0
    start = max(0, min(cursor - height // 2, len(rows) - height))
    return rows[start:start + height], start


def _header(state, downloads, override_status=None):
    speed = sum(p.get("speed", 0) or 0 for p in downloads)
    total_bytes = sum(p.get("bytesTotal", 0) or 0 for p in downloads)
    loaded_bytes = sum(p.get("bytesLoaded", 0) or 0 for p in downloads)
    remaining = max(0, total_bytes - loaded_bytes)
    running = sum(1 for p in downloads if p.get("running"))
    finished = sum(1 for p in downloads if p.get("finished"))

    grid = Table.grid(expand=True)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)

    display_state = override_status if override_status else state

    if override_status:
        st_style, border_color = "bold yellow", "yellow"
    elif state in ["RUNNING", "DOWNLOADING"]:
        st_style, border_color = "bold bright_green", "green"
    elif state in ["STOPPED", "STOPPED_STATE", "IDLE"]:
        st_style, border_color = "bold red", "red"
    else:
        st_style, border_color = "bold yellow", "yellow"

    grid.add_row(
        Text.assemble("State: ", (display_state, st_style)),
        Text.assemble("Speed: ", (f"{utils.human_size(speed)}/s", "bold cyan")),
        f"[dim]Total:[/dim] {utils.human_size(total_bytes)}",
    )
    grid.add_row(
        Text.assemble(
            "Packages: ", (str(len(downloads)), "bold white"),
            "  |  Running: ", (str(running), "bold green"),
            "  |  Done: ", (str(finished), "dim white"),
        ),
        f"[dim]Loaded:[/dim] {utils.human_size(loaded_bytes)}",
        f"[dim]Left: [/dim] [yellow]{utils.human_size(remaining)}[/]",
    )
    return Panel(grid, title="JDownloader Panel", border_style=border_color, box=box.ROUNDED), border_color


def _tab_bar(tab, downloads, grabber):
    def render(label, count, active):
        style = "bold black on bright_cyan" if active else "dim"
        return Text(f" {label} ({count}) ", style=style)

    bar = Table.grid(expand=True)
    bar.add_column(justify="left")
    bar.add_row(Text.assemble(
        render("Downloads", len(downloads), tab == TAB_DOWNLOADS),
        "  ",
        render("Link Grabber", len(grabber), tab == TAB_LINKGRABBER),
        ("   Tab to switch", "dim"),
    ))
    return bar


SELECTED_STYLE = "bold white on blue"


def _downloads_table(rows, cursor, expanded, height):
    t = Table(expand=True, box=box.SIMPLE, show_edge=False, pad_edge=False)
    t.add_column("Name", ratio=3, no_wrap=True)
    t.add_column("Links", width=6, justify="right", style="dim")
    t.add_column("Size", width=20, justify="right", style="dim")
    t.add_column("Status", ratio=1, no_wrap=True, style="yellow")
    t.add_column("Progress", width=18)
    t.add_column("%", width=5, justify="right")
    t.add_column("Speed", width=12, justify="right", style="cyan")
    t.add_column("ETA", width=9, justify="right", style="green")

    if not rows:
        t.add_row("[dim italic]No packages in the download list[/]", "", "", "", "", "", "-", "-")
        return t

    window, offset = _visible_window(rows, cursor, height)
    for i, row in enumerate(window, start=offset):
        style = SELECTED_STYLE if i == cursor else None
        item = row.item
        if row.is_package:
            pct = _package_progress(item)
            marker = "▼" if item.get("uuid") in expanded else "▶"
            bar = ProgressBar(
                total=100, completed=pct, width=None, style="grey23",
                complete_style="bold bright_cyan", finished_style="bold bright_green",
            )
            t.add_row(
                f"{marker} {row.name}",
                f"[{item.get('childCount', 0)}]",
                f"{utils.human_size(item.get('bytesLoaded', 0))}/{utils.human_size(item.get('bytesTotal', 0))}",
                _package_status(item),
                bar,
                f"{pct:.0f}%",
                f"{utils.human_size(item.get('speed', 0))}/s" if item.get("speed") else "-",
                utils.human_eta(item.get("eta", 0)),
                style=style,
            )
        else:
            total = item.get("bytesTotal") or 0
            pct = 100.0 if item.get("finished") else ((item.get("bytesLoaded", 0) / total) * 100 if total else 0.0)
            t.add_row(
                Text(f"    └ {row.name}", style="dim" if style is None else None),
                "",
                f"{utils.human_size(item.get('bytesLoaded', 0))}/{utils.human_size(total)}",
                item.get("status") or ("Finished" if item.get("finished") else "-"),
                "",
                f"{pct:.0f}%",
                f"{utils.human_size(item.get('speed', 0))}/s" if item.get("speed") else "",
                "",
                style=style,
            )
    return t


def _grabber_table(rows, cursor, expanded, height):
    t = Table(expand=True, box=box.SIMPLE, show_edge=False, pad_edge=False)
    t.add_column("Name", ratio=3, no_wrap=True)
    t.add_column("Links", width=6, justify="right", style="dim")
    t.add_column("Size", width=12, justify="right", style="dim")
    t.add_column("Online", width=8, justify="right", style="green")
    t.add_column("Offline", width=8, justify="right", style="red")
    t.add_column("Hoster", ratio=1, no_wrap=True, style="magenta")
    t.add_column("Save to", ratio=2, no_wrap=True, style="dim")

    if not rows:
        t.add_row("[dim italic]LinkGrabber is empty[/]", "", "", "", "", "", "")
        return t

    window, offset = _visible_window(rows, cursor, height)
    for i, row in enumerate(window, start=offset):
        style = SELECTED_STYLE if i == cursor else None
        item = row.item
        if row.is_package:
            marker = "▼" if item.get("uuid") in expanded else "▶"
            hosts = item.get("hosts") or []
            t.add_row(
                f"{marker} {row.name}",
                f"[{item.get('childCount', 0)}]",
                utils.human_size(item.get("bytesTotal", 0)),
                str(item.get("availableOnlineCount", "-")),
                str(item.get("availableOfflineCount", "-")),
                ", ".join(hosts) if hosts else "-",
                item.get("saveTo", "-"),
                style=style,
            )
        else:
            availability = item.get("availability", "-")
            t.add_row(
                Text(f"    └ {row.name}", style="dim" if style is None else None),
                "",
                utils.human_size(item.get("bytesTotal", 0)),
                availability if availability == "ONLINE" else "",
                "" if availability == "ONLINE" else availability,
                item.get("host", "-"),
                item.get("url", "") or "",
                style=style,
            )
    return t


def _menu_panel(entries, index, row):
    t = Table.grid(padding=(0, 1))
    t.add_column()
    for i, entry in enumerate(entries):
        prefix = "›" if i == index else " "
        style = SELECTED_STYLE if i == index else ("red" if entry.confirm else "white")
        t.add_row(Text(f"{prefix} {entry.label}", style=style))
    title = "Package" if row.is_package else "Link"
    return Panel(t, title=title, subtitle="[dim]Enter run · Esc close[/]",
                 border_style="bright_cyan", box=box.ROUNDED)


def _properties_panel(row):
    t = Table.grid(padding=(0, 2))
    t.add_column(style="dim", justify="right")
    t.add_column(overflow="fold")
    for key, value in properties(row):
        t.add_row(key, value)
    return Panel(t, title="Properties", subtitle="[dim]Esc close[/]",
                 border_style="bright_cyan", box=box.ROUNDED)


def generate_layout(state, downloads, grabber, rows=None, tab=TAB_DOWNLOADS, cursor=0,
                    expanded=frozenset(), body_height=20, override_status=None,
                    mode=MODE_LIST, menu=None, menu_index=0, message=""):
    header, border_color = _header(state, downloads, override_status)

    if rows is None:
        rows = build_rows(downloads if tab == TAB_DOWNLOADS else grabber, expanded)

    if tab == TAB_DOWNLOADS:
        table = _downloads_table(rows, cursor, expanded, body_height)
        title = "Downloads"
    else:
        table = _grabber_table(rows, cursor, expanded, body_height)
        title = "Link Grabber"

    body = Panel(table, title=title, border_style=border_color, box=box.ROUNDED)
    row = rows[cursor] if rows and cursor < len(rows) else None

    if mode == MODE_MENU and row is not None:
        side = Layout(_menu_panel(menu or [], menu_index, row), size=32)
        body_layout = Layout(name="body")
        body_layout.split_row(Layout(body), side)
    elif mode == MODE_PROPERTIES and row is not None:
        side = Layout(_properties_panel(row), size=60)
        body_layout = Layout(name="body")
        body_layout.split_row(Layout(body), side)
    else:
        body_layout = Layout(body)

    if mode == MODE_CONFIRM:
        footer = Align.center(Text(message, style="bold yellow"))
    elif message:
        footer = Align.center(Text(message, style="bold green"))
    else:
        footer = Align.center(
            "[dim][bold white]Tab[/] switch  |  [bold white]↑↓[/] move  |  "
            "[bold white]→←[/] expand  |  [bold white]Enter[/] menu  |  "
            "[bold white]p[/] properties  |  [bold white]s[/] start/stop  |  "
            "[bold white]q[/] quit[/]"
        )

    layout = Layout()
    layout.split(
        Layout(header, size=4),
        Layout(_tab_bar(tab, downloads, grabber), size=1),
        body_layout,
        Layout(footer, size=1),
    )
    return layout


def run(client):
    console = Console()
    console.clear()

    state, downloads, grabber = "UNKNOWN", [], []
    tab = TAB_DOWNLOADS
    cursor = 0
    expanded = set()
    mode = MODE_LIST
    menu, menu_index, pending = [], 0, None
    message = ""
    override = None
    rows = []

    def packages():
        return downloads if tab == TAB_DOWNLOADS else grabber

    def rebuild():
        nonlocal rows, cursor
        rows = build_rows(packages(), expanded)
        cursor = min(cursor, max(0, len(rows) - 1))

    def body_height():
        # Panel borders, header, tab bar and footer take a fixed slice.
        return max(3, console.size.height - 12)

    def draw(live):
        live.update(generate_layout(
            state, downloads, grabber, rows, tab, cursor, expanded,
            body_height(), override, mode, menu, menu_index, message,
        ))

    def current_row():
        return rows[cursor] if rows and cursor < len(rows) else None

    def toggle_expand(row):
        if row is not None and row.is_package:
            expanded.symmetric_difference_update({row.uuid})
            rebuild()

    def execute(action):
        nonlocal message, mode, expanded
        row = current_row()
        if row is None:
            return
        if action == "expand":
            toggle_expand(row)
            message = ""
            return
        if action == "properties":
            mode = MODE_PROPERTIES
            return
        try:
            message = run_action(client, tab, row, action)
        except Exception as exc:
            message = f"Failed: {exc}"
        mode = MODE_LIST

    try:
        with KeyboardInput() as kbd, Live(refresh_per_second=4, screen=True) as live:
            live.update(generate_layout("CONNECTING...", [], [], override_status="LOADING..."))
            state, downloads, grabber = client.fetch_overview()
            rebuild()
            draw(live)

            while True:
                start_time = time.time()
                while (time.time() - start_time) < config.REFRESH_RATE:
                    key = kbd.get_key()
                    if not key:
                        time.sleep(0.05)
                        continue

                    if mode == MODE_CONFIRM:
                        if key in ("y", "Y"):
                            execute(pending)
                        else:
                            message = "Cancelled"
                        pending, mode = None, MODE_LIST
                        draw(live)
                        continue

                    if mode == MODE_PROPERTIES:
                        if key in ("\x1b", "q", "Q", "p", "\r", "\n"):
                            mode = MODE_LIST
                        draw(live)
                        continue

                    if mode == MODE_MENU:
                        if key in ("\x1b", "q", "Q", "LEFT"):
                            mode = MODE_LIST
                        elif key in ("UP", "k"):
                            menu_index = max(0, menu_index - 1)
                        elif key in ("DOWN", "j"):
                            menu_index = min(len(menu) - 1, menu_index + 1)
                        elif key in ("\r", "\n", "RIGHT", " "):
                            entry = menu[menu_index]
                            if entry.confirm:
                                pending = entry.action
                                mode = MODE_CONFIRM
                                message = f"{entry.label} '{current_row().name[:40]}'?  [y/N]"
                            else:
                                execute(entry.action)
                        draw(live)
                        continue

                    # --- list mode
                    if key in ("q", "Q"):
                        return

                    message = ""
                    if key == "\t":
                        tab = TAB_LINKGRABBER if tab == TAB_DOWNLOADS else TAB_DOWNLOADS
                        cursor = 0
                        rebuild()
                    elif key in ("UP", "k"):
                        cursor = max(0, cursor - 1)
                    elif key in ("DOWN", "j"):
                        cursor = min(max(0, len(rows) - 1), cursor + 1)
                    elif key in ("RIGHT", " "):
                        toggle_expand(current_row())
                    elif key == "LEFT":
                        row = current_row()
                        if row is not None and not row.is_package:
                            # Step out of an expanded package.
                            cursor = rows.index(next(r for r in rows if r.item is row.parent))
                        elif row is not None:
                            expanded.discard(row.uuid)
                            rebuild()
                    elif key in ("\r", "\n"):
                        row = current_row()
                        if row is not None:
                            menu = context_menu(tab, row)
                            menu_index = 0
                            mode = MODE_MENU
                    elif key in ("p", "P"):
                        if current_row() is not None:
                            mode = MODE_PROPERTIES
                    elif key == "s":
                        is_running = state in ["RUNNING", "DOWNLOADING"]
                        override = "STOPPING..." if is_running else "STARTING..."
                        draw(live)
                        try:
                            client.toggle_state(state)
                        except Exception:
                            pass
                        override = None
                        break
                    elif key == "c" and tab == TAB_LINKGRABBER:
                        override = "CONFIRMING..."
                        draw(live)
                        try:
                            client.move_to_downloads()
                        except Exception:
                            pass
                        override = None
                        break
                    else:
                        continue

                    draw(live)

                state, downloads, grabber = client.fetch_overview()
                rebuild()
                draw(live)

    except KeyboardInterrupt:
        pass
