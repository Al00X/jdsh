import os
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
from rich.markup import escape

from . import utils, config

KEYS = {
    "\x1b[A": "up", "\x1b[B": "down", "\x1b[C": "right", "\x1b[D": "left",
    "\x1b[1;2A": "shift-up", "\x1b[1;2B": "shift-down", "\x1b[a": "shift-up", "\x1b[b": "shift-down",
    "\x1bOA": "up", "\x1bOB": "down", "\x1bOC": "right", "\x1bOD": "left",
    "\x1b[5~": "pgup", "\x1b[6~": "pgdn", "\x1b[3~": "delete",
    "\r": "enter", "\n": "enter", "\t": "tab", " ": "space",
    "\x7f": "backspace", "\x08": "backspace", "\x1b": "esc",
}
ESC_SEQS = sorted((k for k in KEYS if k.startswith("\x1b")), key=len, reverse=True)
WIN_KEYS = {"H": "up", "P": "down", "K": "left", "M": "right", "I": "pgup", "Q": "pgdn", "S": "delete"}

class KeyboardInput:
    def __enter__(self):
        self.pending = []
        if termios:
            self.old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        return self

    def __exit__(self, type, value, traceback):
        if termios:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)

    @staticmethod
    def parse(data):
        keys, i = [], 0
        while i < len(data):
            if data[i] == "\x1b":
                seq = next((s for s in ESC_SEQS if data.startswith(s, i)), "\x1b")
                keys.append(KEYS.get(seq, "esc"))
                i += len(seq)
            else:
                keys.append(KEYS.get(data[i], data[i]))
                i += 1
        return keys
        
    def get_key(self):
        if not self.pending:
            if termios:
                fd = sys.stdin.fileno()
                if select.select([fd], [], [], 0)[0]:
                    # Read all available bytes so escape sequences stay together
                    self.pending = self.parse(os.read(fd, 64).decode("utf-8", errors="ignore"))
            elif msvcrt:
                while msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    if ch in ("\x00", "\xe0"):
                        key = WIN_KEYS.get(msvcrt.getwch())
                        if key: self.pending.append(key)
                    else:
                        self.pending.append(KEYS.get(ch, ch))
        return self.pending.pop(0) if self.pending else None

def generate_layout(state, active_links, pending_links, limit=None, extracting=(), override_status=None):
    current_speed = sum(l.get('speed', 0) for l in active_links)
    
    total_bytes = sum(l.get('bytesTotal', 0) for l in active_links)
    loaded_bytes = sum(l.get('bytesLoaded', 0) for l in active_links)
    remaining_bytes = total_bytes - loaded_bytes
    
    # Header
    grid = Table.grid(expand=True)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)

    display_state = override_status if override_status else state
    
    # Colors
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
        Text.assemble("Speed: ", (f"{utils.human_size(current_speed)}/s", "bold cyan")),
        f"[dim]Total:[/dim] {utils.human_size(total_bytes)}",
    )
    grid.add_row(
        Text.assemble("Active: ", (str(len(active_links)), "bold white"), "  |  ", "Pending: ", (str(len(pending_links)), "dim white")),
        f"[dim]Done: [/dim] {utils.human_size(loaded_bytes)}",
        f"[dim]Left: [/dim] [yellow]{utils.human_size(remaining_bytes)}[/]"
    )
    grid.add_row(
        Text.assemble("Limit: ", (f"{utils.human_size(limit)}/s", "bold yellow") if limit else ("off", "dim")),
        "", "",
    )

    header = Panel(grid, title="JDownloader Panel", border_style=border_color, box=box.ROUNDED)

    # Active Queue
    t_active = Table(expand=True, box=box.SIMPLE, show_edge=False, pad_edge=False)
    t_active.add_column("Name", ratio=3, no_wrap=True)
    t_active.add_column("Progress", ratio=2) 
    t_active.add_column("%", width=5, justify="right")
    t_active.add_column("Size (Done/Total)", width=20, justify="right", style="dim")
    t_active.add_column("Speed", width=12, justify="right", style="cyan")
    t_active.add_column("ETA", width=10, justify="right", style="green")

    if not active_links:
        t_active.add_row("[dim italic]No active downloads[/]", "", "", "", "-", "-")
    else:
        for l in active_links:
            total = l.get('bytesTotal', 1) or 1
            done = l.get('bytesLoaded', 0)
            pct = (done / total) * 100
            
            bar = ProgressBar(
                total=100, completed=pct, width=None, style="grey23", 
                complete_style="bold bright_cyan", finished_style="bold bright_green"
            )
            
            size_str = f"{utils.human_size(done)}/{utils.human_size(total)}"
            
            t_active.add_row(
                escape(l['name']), 
                bar, 
                f"{pct:.0f}%", 
                size_str,
                f"{utils.human_size(l.get('speed', 0))}/s", 
                utils.human_eta(l.get('eta', 0))
            )

    panel_active = Panel(t_active, title="Active Queue", border_style="white", box=box.ROUNDED)

    # Pending Queue
    t_pending = Table(expand=True, box=box.SIMPLE, show_edge=False, pad_edge=False)
    t_pending.add_column("Name", ratio=1, no_wrap=True)
    t_pending.add_column("Status", ratio=1, style="yellow")
    t_pending.add_column("Total Size", width=24, justify="right", style="dim")

    if not pending_links:
        t_pending.add_row("[dim italic]No pending items[/]", "-", "-")
    else:
        limit = 10
        for l in pending_links[:limit]:
            t_pending.add_row(
                escape(l['name']),
                escape(l.get('status', 'Pending')),
                utils.human_size(l.get('bytesTotal', 0))
            )
        if len(pending_links) > limit:
            t_pending.add_row(f"[italic]...and {len(pending_links)-limit} more[/]", "", "")

    panel_pending = Panel(t_pending, title="Pending Queue", border_style="dim white", box=box.ROUNDED)

    # Extraction
    t_extract = Table(expand=True, box=box.SIMPLE, show_edge=False, pad_edge=False)
    t_extract.add_column("Archive", ratio=3, no_wrap=True)
    t_extract.add_column("Progress", ratio=2)
    t_extract.add_column("%", width=5, justify="right")
    t_extract.add_column("Size (Done/Total)", width=20, justify="right", style="dim")
    t_extract.add_column("Status", width=12, justify="right", style="yellow")
    t_extract.add_column("ETA", width=10, justify="right", style="green")

    for a in extracting:
        pct = (a['current'] / a['total']) * 100 if a['total'] else 0
        bar = ProgressBar(
            total=100, completed=pct, width=None, style="grey23",
            complete_style="bold bright_magenta", finished_style="bold bright_green"
        )
        t_extract.add_row(
            escape(a['name']),
            bar if a['total'] else "",
            f"{pct:.0f}%",
            f"{utils.human_size(a['current'])}/{utils.human_size(a['total'])}" if a['total'] else "-",
            escape(a['status'].lower()),
            utils.human_eta(a['eta'])
        )

    running = sum(1 for a in extracting if a['status'] == "RUNNING")
    panel_extract = Panel(t_extract, title=f"Extracting ({running} running, {len(extracting) - running} queued)", border_style="magenta", box=box.ROUNDED)

    layout = Layout()
    layout.split(
        Layout(header, size=5),
        Layout(panel_active, ratio=2), # Active takes more space
        *([Layout(panel_extract, size=min(len(extracting), 6) + 4)] if extracting else []),
        Layout(panel_pending, ratio=1),
    )
    return layout

AVAILABILITY_STYLES = {"ONLINE": "green", "OFFLINE": "red"}

class GrabberView:
    def __init__(self):
        self.packages = []
        self.links = {}
        self.expanded = set()
        self.selected = set()
        self.cursor = None
        self.offset = 0
        self.page_size = 10

    def update(self, packages, links):
        self.packages = packages
        self.links = {}
        for l in links:
            self.links.setdefault(l.get('packageUUID'), []).append(l)
        link_ids = {l['uuid'] for l in links}
        self.selected &= link_ids
        self.expanded &= {p['uuid'] for p in packages}

    def rows(self):
        rows = []
        for p in self.packages:
            rows.append(("pkg", p))
            if p['uuid'] in self.expanded:
                rows.extend(("link", l) for l in self.links.get(p['uuid'], []))
        return rows

    def cursor_index(self, rows):
        for i, (kind, item) in enumerate(rows):
            if (kind, item['uuid']) == self.cursor:
                return i
        return 0

    def current(self):
        rows = self.rows()
        if not rows:
            return None, None
        kind, item = rows[min(self.cursor_index(rows), len(rows) - 1)]
        self.cursor = (kind, item['uuid'])
        return kind, item

    def move(self, delta):
        rows = self.rows()
        if not rows: return
        i = max(0, min(len(rows) - 1, self.cursor_index(rows) + delta))
        self.cursor = (rows[i][0], rows[i][1]['uuid'])

    def package_of(self, link):
        return next((p for p in self.packages if p['uuid'] == link.get('packageUUID')), None)

    def expand(self):
        kind, item = self.current()
        if kind == "pkg":
            self.expanded.add(item['uuid'])

    def collapse(self):
        kind, item = self.current()
        if kind == "link":
            item = self.package_of(item)
            if not item: return
        if item:
            self.expanded.discard(item['uuid'])
            self.cursor = ("pkg", item['uuid'])

    def toggle_expand(self):
        kind, item = self.current()
        if kind == "pkg":
            self.expanded ^= {item['uuid']}

    def pkg_link_ids(self, pkg):
        return {l['uuid'] for l in self.links.get(pkg['uuid'], [])}

    def toggle_select(self):
        kind, item = self.current()
        if kind == "pkg":
            ids = self.pkg_link_ids(item)
            if ids <= self.selected: self.selected -= ids
            else: self.selected |= ids
        elif kind == "link":
            self.selected ^= {item['uuid']}

    def select_current(self):
        kind, item = self.current()
        if kind == "pkg": self.selected |= self.pkg_link_ids(item)
        elif kind == "link": self.selected.add(item['uuid'])

    def extend_selection(self, delta):
        self.select_current()
        self.move(delta)
        self.select_current()

    def toggle_all(self):
        all_ids = {l['uuid'] for links in self.links.values() for l in links}
        self.selected = set() if all_ids <= self.selected else all_ids

    def count_links(self, link_ids, pkg_ids):
        return len(link_ids) + sum(len(self.pkg_link_ids(p)) for p in self.packages if p['uuid'] in pkg_ids)

    def selection(self):
        if self.selected:
            link_ids, pkg_ids, names = [], [], []
            for p in self.packages:
                ids = self.pkg_link_ids(p)
                chosen = ids & self.selected
                if not chosen: continue
                names.append(p['name'])
                if chosen == ids: pkg_ids.append(p['uuid'])
                else: link_ids.extend(chosen)
            return link_ids, pkg_ids, names
        kind, item = self.current()
        if kind == "pkg":
            return [], [item['uuid']], [item['name']]
        if kind == "link":
            pkg = self.package_of(item)
            return [item['uuid']], [], [pkg['name']] if pkg else []
        return [], [], []

def check_mark(selected, total):
    if total and selected == total: return Text("[x]", style="bold green")
    if selected: return Text("[-]", style="yellow")
    return Text("[ ]", style="dim")

def generate_grabber_layout(view, height):
    rows = view.rows()
    t = Table(expand=True, box=box.SIMPLE, show_edge=False, pad_edge=False)
    t.add_column("", width=3, no_wrap=True)
    t.add_column("Name", ratio=3, no_wrap=True)
    t.add_column("Links / Host", ratio=1, no_wrap=True)
    t.add_column("Status", width=12, no_wrap=True)
    t.add_column("Size", width=11, justify="right", style="dim")

    # Scroll
    visible = max(1, height - 11)
    view.page_size = visible
    cur = view.cursor_index(rows) if rows else 0
    if cur < view.offset: view.offset = cur
    if cur >= view.offset + visible: view.offset = cur - visible + 1
    view.offset = max(0, min(view.offset, max(0, len(rows) - visible)))

    if not rows:
        t.add_row("", Text("LinkGrabber is empty", style="dim italic"), "", "", "")

    for i, (kind, item) in enumerate(rows[view.offset:view.offset + visible], start=view.offset):
        style = "reverse" if i == cur else None
        if kind == "pkg":
            links = view.links.get(item['uuid'], [])
            ids = {l['uuid'] for l in links}
            online = sum(1 for l in links if l.get('availability') == "ONLINE")
            offline = sum(1 for l in links if l.get('availability') == "OFFLINE")
            arrow = "▾ " if item['uuid'] in view.expanded else "▸ "
            status = Text.assemble((f"{online}✓", "green"), " ", (f"{offline}✗", "red" if offline else "dim"))
            t.add_row(
                check_mark(len(ids & view.selected), len(ids)),
                Text.assemble(arrow, (item['name'], "bold")),
                Text(f"{item.get('childCount', len(links))} links"),
                status,
                utils.human_size(item.get('bytesTotal', 0)),
                style=style,
            )
        else:
            avail = item.get('availability', 'UNKNOWN')
            t.add_row(
                check_mark(int(item['uuid'] in view.selected), 1),
                Text("    " + item['name']),
                Text(item.get('host', ''), style="dim"),
                Text(avail.lower(), style=AVAILABILITY_STYLES.get(avail, "yellow")),
                utils.human_size(item.get('bytesTotal', 0)),
                style=style,
            )

    title = f"LinkGrabber ({len(view.packages)} packages, {len(view.selected)} links selected)"
    if len(rows) > visible:
        title += f"  [{view.offset + 1}-{min(len(rows), view.offset + visible)}/{len(rows)}]"
    panel_list = Panel(t, title=escape(title), border_style="white", box=box.ROUNDED)

    # Details
    kind, item = view.current()
    details = Table.grid(padding=(0, 2))
    details.add_column(style="dim", no_wrap=True)
    details.add_column(overflow="fold")
    if kind == "pkg":
        details.add_row("Package", Text(item['name']))
        details.add_row("Save To", Text(item.get('saveTo', '')))
        details.add_row("Links", f"{item.get('childCount', 0)}  ({item.get('availableOnlineCount', 0)} online, {item.get('availableOfflineCount', 0)} offline)")
    elif kind == "link":
        details.add_row("Link", Text(item['name']))
        details.add_row("URL", Text(item.get('url', ''), style="blue"))
        details.add_row("Host", Text(f"{item.get('host', '')}   {utils.human_size(item.get('bytesTotal', 0))}   {item.get('availability', 'UNKNOWN').lower()}"))
    panel_details = Panel(details, title="Details", border_style="dim white", box=box.ROUNDED)

    layout = Layout()
    layout.split(
        Layout(panel_list, ratio=1),
        Layout(panel_details, size=5),
    )
    return layout

PAGES = ["downloads", "grabber"]
FOOTERS = {
    "downloads": "[bold white]s[/] Start/Stop  [bold white]l[/] Limit on/off  [bold white]L[/] Set Limit  [bold white]x[/] Clear Pending  "
                 "[bold white]Tab[/] LinkGrabber  [bold white]q[/]/[bold white]Ctrl+C[/] Quit",
    "grabber": "[bold white]↑↓ PgUp PgDn[/] Move  [bold white]→←[/] Open  [bold white]Space[/] Select  [bold white]Shift+↑↓[/] Range  [bold white]a[/] All  "
               "[bold white]c[/] Confirm  [bold white]C[/] +Start  [bold white]x[/] Remove  [bold white]q[/] Quit",
}

def generate_screen(page, body, message=None):
    tabs = Text.assemble(
        (" 1 Downloads ", "bold black on bright_cyan" if page == "downloads" else "dim"), " ",
        (" 2 LinkGrabber ", "bold black on bright_cyan" if page == "grabber" else "dim"),
    )
    footer = Text.from_markup(f"[dim]{FOOTERS[page]}[/]")
    if message:
        footer = Text(message, style="bold yellow")

    layout = Layout()
    layout.split(
        Layout(tabs, size=1),
        Layout(body),
        Layout(Align.center(footer), size=1),
    )
    return layout

def run(client):
    console = Console()
    console.clear()
    page = "downloads"
    view = GrabberView()
    downloads = ("UNKNOWN", [], [], None, [])
    override = None
    message, message_until = None, 0
    pending_remove = None
    pending_clear = None
    prompt = None

    def render():
        if page == "downloads":
            body = generate_layout(*downloads, override_status=override)
        else:
            body = generate_grabber_layout(view, console.size.height)
        if prompt is not None:
            return generate_screen(page, body, f"Speed limit (e.g. 5M, 500K): {prompt}_   Enter apply, Esc cancel")
        return generate_screen(page, body, message if time.time() < message_until else None)

    try:
        with KeyboardInput() as kbd, Live(refresh_per_second=4, screen=True) as live:
            live.update(generate_screen(page, generate_layout("CONNECTING...", [], [], override_status="LOADING...")))
            
            next_fetch = 0
            while True:
                dirty = False
                if time.time() >= next_fetch:
                    if page == "downloads":
                        downloads = client.fetch_stats()
                    else:
                        grabber = client.fetch_grabber()
                        if grabber is not None:
                            view.update(*grabber)
                    override = None
                    next_fetch = time.time() + config.REFRESH_RATE
                    dirty = True
                        
                key = kbd.get_key()
                if key is None:
                    if dirty: live.update(render())
                    time.sleep(0.05)
                    continue
                        
                if pending_remove is not None:
                    link_ids, pkg_ids, count = pending_remove
                    pending_remove = None
                    if key == "y":
                        try:
                            client.remove_from_grabber(link_ids, pkg_ids)
                            message = f"Removed {count} links"
                        except Exception as e:
                            message = f"Remove failed: {e}"
                        view.selected.clear()
                        next_fetch = 0
                    else:
                        message = "Remove cancelled"
                    message_until = time.time() + 3
                    live.update(render())
                    continue

                if pending_clear is not None:
                    if key == "y":
                        try:
                            client.clear_pending(pending_clear)
                            message = f"Removed {len(pending_clear)} pending links"
                        except Exception as e:
                            message = f"Clear failed: {e}"
                        next_fetch = 0
                    else:
                        message = "Clear cancelled"
                    pending_clear = None
                    message_until = time.time() + 3
                    live.update(render())
                    continue

                if prompt is not None:
                    if key == "enter":
                        try:
                            limit = utils.parse_size(prompt)
                            client.set_limit(limit)
                            message = f"Speed limit set to {utils.human_size(limit)}/s"
                        except ValueError:
                            message = f"Invalid rate '{prompt}', use e.g. 5M or 500K"
                        except Exception as e:
                            message = f"Setting limit failed: {e}"
                        message_until = time.time() + 3
                        prompt = None
                        next_fetch = 0
                    elif key == "esc": prompt = None
                    elif key == "backspace": prompt = prompt[:-1]
                    elif len(key) == 1: prompt += key
                elif key == "q":
                    break
                elif key in ("tab", "1", "2"):
                    page = {"1": "downloads", "2": "grabber"}.get(key) or PAGES[(PAGES.index(page) + 1) % len(PAGES)]
                    next_fetch = 0
                elif key == "s" and page == "downloads":
                    is_running = downloads[0] in ["RUNNING", "DOWNLOADING"]
                    override = "STOPPING..." if is_running else "STARTING..."
                    live.update(render())
                    try: client.toggle_state(downloads[0])
                    except: pass
                    next_fetch = 0
                    continue
                elif key == "l" and page == "downloads":
                    try: client.toggle_limit(downloads[3])
                    except: pass
                    next_fetch = 0
                elif key == "L" and page == "downloads":
                    prompt = ""
                elif key == "x" and page == "downloads":
                    if downloads[2]:
                        pending_clear = [l['uuid'] for l in downloads[2]]
                        message = f"Remove {len(pending_clear)} pending links from the download list (files stay)? y = yes, any other key = cancel"
                        message_until = time.time() + 3600
                elif page == "grabber":
                    if key == "up": view.move(-1)
                    elif key == "down": view.move(1)
                    elif key == "pgup": view.move(-view.page_size)
                    elif key == "pgdn": view.move(view.page_size)
                    elif key == "shift-up": view.extend_selection(-1)
                    elif key == "shift-down": view.extend_selection(1)
                    elif key == "right": view.expand()
                    elif key == "left": view.collapse()
                    elif key == "enter": view.toggle_expand()
                    elif key == "space": view.toggle_select()
                    elif key == "a": view.toggle_all()
                    elif key in ("c", "C"):
                        link_ids, pkg_ids, names = view.selection()
                        if link_ids or pkg_ids:
                            message = "Confirming..."
                            message_until = time.time() + 10
                            live.update(render())
                            try:
                                started = client.confirm(link_ids, pkg_ids, names, start=(key == "C"))
                                count = view.count_links(link_ids, pkg_ids)
                                message = f"Confirmed {count} links" + (f", started {len(started)} packages" if key == "C" else "")
                            except Exception as e:
                                message = f"Confirm failed: {e}"
                            message_until = time.time() + 4
                            view.selected.clear()
                            next_fetch = 0
                    elif key in ("x", "delete"):
                        link_ids, pkg_ids, _ = view.selection()
                        if link_ids or pkg_ids:
                            count = view.count_links(link_ids, pkg_ids)
                            pending_remove = (link_ids, pkg_ids, count)
                            message = f"Remove {count} links from LinkGrabber? y = yes, any other key = cancel"
                            message_until = time.time() + 3600
                live.update(render())

    except KeyboardInterrupt:
        pass
