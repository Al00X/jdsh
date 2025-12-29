import time
import sys
import select
import tty
import termios
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

class KeyboardInput:
    def __enter__(self):
        self.old_settings = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())
        return self

    def __exit__(self, type, value, traceback):
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)

    def get_key(self):
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
        return None

def generate_layout(state, active_links, pending_links, override_status=None):
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
                l['name'], 
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
                l['name'],
                l.get('status', 'Pending'),
                utils.human_size(l.get('bytesTotal', 0))
            )
        if len(pending_links) > limit:
            t_pending.add_row(f"[italic]...and {len(pending_links)-limit} more[/]", "", "")

    panel_pending = Panel(t_pending, title="Pending Queue", border_style="dim white", box=box.ROUNDED)

    # Footer
    footer = Align.center("[dim]Press [bold white]s[/] to Start/Stop  |  [bold white]Ctrl+C[/] to Quit[/]")

    layout = Layout()
    layout.split(
        Layout(header, size=4),
        Layout(panel_active, ratio=2), # Active takes more space
        Layout(panel_pending, ratio=1),
        Layout(footer, size=1)
    )
    return layout

def run(client):
    console = Console()
    console.clear()
    last_state, last_active, last_pending = "UNKNOWN", [], []

    try:
        with KeyboardInput() as kbd, Live(refresh_per_second=4, screen=True) as live:
            live.update(generate_layout("CONNECTING...", [], [], override_status="LOADING..."))
            
            last_state, last_active, last_pending = client.fetch_stats()
            live.update(generate_layout(last_state, last_active, last_pending))

            while True:
                start_time = time.time()
                while (time.time() - start_time) < config.REFRESH_RATE:
                    key = kbd.get_key()
                    if key == 's':
                        is_running = last_state in ["RUNNING", "DOWNLOADING"]
                        fb_status = "STOPPING..." if is_running else "STARTING..."
                        
                        live.update(generate_layout(last_state, last_active, last_pending, override_status=fb_status))
                        
                        try: client.toggle_state(last_state)
                        except: pass
                        
                        break
                    
                    if key: pass 
                    time.sleep(0.1)

                state, active, pending = client.fetch_stats()
                last_state, last_active, last_pending = state, active, pending
                
                live.update(generate_layout(state, active, pending))

    except KeyboardInterrupt:
        pass
