import argparse
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.padding import Padding
from rich import box
from rich.markup import escape

from .client import JDClient, query_grabber_packages, query_grabber_links, query_download_packages, confirm_links, get_speed_limit, set_speed_limit, enable_speed_limit, query_extraction
from . import tui, utils, config

def print_help():
    console = Console()
    
    # Header
    title = Text.assemble(
        ("JDSH ", "bold magenta"), 
        (f"v{config.VERSION}", "dim white"),
    )
    
    # Syntax
    syntax = Text.assemble(
        ("Usage: ", "bold yellow"),
        ("jd ", "bold cyan"),
        ("[COMMAND] ", "bold green"),
        ("[ARGS]...", "dim white")
    )

    # Command Table
    table = Table(box=None, padding=(0, 2), show_header=False, expand=True)
    table.add_column("Command", style="bold cyan", width=5)
    table.add_column("Args", style="cyan", width=5)
    table.add_column("Description", style="white")

    def add_cmd(name, args, desc):
        table.add_row(name, escape(args), desc)
    def add_section(name):
        table.add_row(Text(f"\n{name}", style="bold yellow"))

    add_section("Dashboard")
    add_cmd("jd", "", "Launch the Interactive TUI")
    add_cmd("status", "", "Show a static snapshot of the queue and extraction")

    add_section("Queue Management")
    add_cmd("list (ls)", "[-d]", "List active downloads")
    add_cmd("grabber", "[-d]", "List pending packages inside LinkGrabber")
    add_cmd("add", "<url>...", "Add links to LinkGrabber")
    add_cmd("confirm", "[pkg...] [-s]", "Move packages (all or by ID/name) to Queue, -s starts them")
    add_cmd("remove (rm)", "<uuid>...", "Remove items by ID")

    add_section("Controls")
    add_cmd("start", "[pkg...]", "Start/Resume downloads, or force-start packages")
    add_cmd("stop", "", "Pause/Stop downloads")
    add_cmd("limit", "[rate]", "Show or set download speed limit (5M, 500K, on, off)")
    add_cmd("clear", "[-p]", "Remove finished items from list, -p removes pending ones")
    add_cmd("replace", "<uuid> <url>", "Replace a dead link URL")

    add_section("Utils")
    add_cmd("version", "", "Show shell and core versions")
    add_cmd("help", "", "Show this help message")

    examples = Text.from_markup(
        "[dim]# Run the interactive mode:[/]\n"
        "[bold cyan]jd[/]\n\n"
        "[dim]# Add links, check them, then start:[/]\n"
        "[bold cyan]jd add[/] [green]\"http://site.com/file.exe\"[/]\n"
        "[bold cyan]jd add[/] [green]\"http://site.com/archive1.zip\"[/] [green]\"http://site.com/archive2.zip\"[/]\n"
        "[bold cyan]jd grabber[/]\n"
        "[bold cyan]jd confirm[/]\n\n"
        "[dim]# Confirm and start a single package by ID or name:[/]\n"
        "[bold cyan]jd confirm[/] [green]\"carrie\"[/] [bold cyan]-s[/]\n\n"
        "[dim]# detailed list view:[/]\n"
        "[bold cyan]jd ls -d[/]"
    )

    body = Padding(table, (0, 1))
    
    console.print()
    console.print(Panel(
        body,
        title=title,
        border_style="#333333",
        box=box.ROUNDED,
        title_align="left"
    ))
    console.print(Padding(syntax, (1, 2)))
    console.print(Padding(examples, (0, 2)))
    console.print()


def cmd_status(device, args):
    try:
        state = device.downloadcontroller.get_current_state()
        links = device.downloads.query_links([{
            "name": True, "bytesLoaded": True, "bytesTotal": True, 
            "speed": True, "running": True, "eta": True, "status": True, "advancedStatus": True
        }])
        
        active = [l for l in links if l.get('running')]
        current_speed = sum(l.get('speed', 0) for l in active)

        console = Console()
        console.print(f"[bold]State:[/bold]  {state}")
        console.print(f"[bold]Speed:[/bold]  {utils.human_size(current_speed)}/s")
        console.print(f"[bold]Active:[/bold] {len(active)}")
        
        if active:
            table = Table(box=box.SIMPLE_HEAD, show_edge=False)
            table.add_column("Name")
            table.add_column("%", justify="right")
            table.add_column("Size", justify="right")
            table.add_column("Speed", justify="right", style="cyan")
            table.add_column("ETA", justify="right", style="green")

            for l in active:
                total = l.get('bytesTotal', 1) or 1
                pct = (l.get('bytesLoaded', 0) / total) * 100
                size_str = f"{utils.human_size(l.get('bytesLoaded',0))}/{utils.human_size(total)}"
                
                table.add_row(
                    escape(l['name']), 
                    f"{pct:.1f}%", 
                    size_str, 
                    f"{utils.human_size(l.get('speed',0))}/s", 
                    utils.human_eta(l.get('eta', 0))
                )
            console.print(table)

        extracting = query_extraction(device, links)
        if extracting:
            running = sum(1 for a in extracting if a['status'] == "RUNNING")
            console.print(f"[bold]Extracting:[/bold] {running} running, {len(extracting) - running} queued")

            table = Table(box=box.SIMPLE_HEAD, show_edge=False)
            table.add_column("Archive")
            table.add_column("%", justify="right")
            table.add_column("Size", justify="right")
            table.add_column("Status", justify="right", style="yellow")
            table.add_column("ETA", justify="right", style="green")

            for a in extracting:
                pct = (a['current'] / a['total']) * 100 if a['total'] else 0
                table.add_row(
                    escape(a['name']),
                    f"{pct:.1f}%",
                    f"{utils.human_size(a['current'])}/{utils.human_size(a['total'])}" if a['total'] else "-",
                    escape(a['status'].lower()),
                    utils.human_eta(a['eta'])
                )
            console.print(table)
    except Exception as e:
        print(f"Error fetching status: {e}")

def cmd_list(device, args):
    query = {"name": True, "status": True, "bytesLoaded": True, "bytesTotal": True, "uuid": True}
    if args.detail: query["url"] = True

    links = device.downloads.query_links([query])
    if not links: return print("Download queue is empty.")

    console = Console()
    if args.detail:
        for l in links:
            total = l.get('bytesTotal', 1) or 1
            pct = (l.get('bytesLoaded', 0) / total) * 100
            
            p = Panel(
                f"[bold]ID:[/bold] {l['uuid']}\n"
                f"[bold]State:[/bold] {escape(str(l.get('status')))} ({pct:.1f}%)\n"
                f"[bold]Size:[/bold] {utils.human_size(l.get('bytesLoaded', 0))} / {utils.human_size(total)}\n"
                f"[bold]URL:[/bold] [blue underline]{escape(l.get('url', 'N/A'))}[/]",
                title=escape(l['name']),
                border_style="dim white",
                expand=False
            )
            console.print(p)
    else:
        table = Table(box=box.SIMPLE_HEAD)
        table.add_column("ID", style="dim", no_wrap=True)
        table.add_column("Done/Total", justify="right")
        table.add_column("Status")
        table.add_column("Name")

        for l in links:
            total = l.get('bytesTotal', 1) or 1
            pct = (l.get('bytesLoaded', 0) / total) * 100
            status = escape((l.get('status') or "N/A")[:15])
            size_fmt = f"{utils.human_size(l.get('bytesLoaded',0))}/{utils.human_size(total)}"
            
            table.add_row(f"{l['uuid']}", size_fmt, status, escape(l['name']))
        console.print(table)

def _select_packages(pkgs, selectors):
    chosen = {}
    for sel in selectors:
        matches = [p for p in pkgs if str(p['uuid']) == sel]
        if not matches:
            matches = [p for p in pkgs if sel.lower() in p['name'].lower()]
        if not matches:
            sys.exit(f"No package matches '{sel}'.")
        if len(matches) > 1:
            names = "\n".join(f"  {p['uuid']}  {p['name']}" for p in matches)
            sys.exit(f"'{sel}' matches multiple packages, use the ID:\n{names}")
        chosen[matches[0]['uuid']] = matches[0]
    return list(chosen.values())

def cmd_grabber(device, args):
    pkgs = query_grabber_packages(device)
    if not pkgs: return print("LinkGrabber is empty.")

    links_by_pkg = {}
    if args.detail:
        for l in query_grabber_links(device):
            links_by_pkg.setdefault(l.get('packageUUID'), []).append(l)

    console = Console()
    table = Table(title=f"Pending Packages ({len(pkgs)})", box=box.SIMPLE)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Name")
    table.add_column("Links", justify="right")
    table.add_column("Online", justify="right", style="green")
    table.add_column("Offline", justify="right", style="red")
    table.add_column("Size", justify="right")
    if args.detail: table.add_column("Save To", style="dim")

    for p in pkgs:
        row = [
            str(p['uuid']), f"[bold]{escape(p['name'])}[/]", str(p.get('childCount', 0)),
            str(p.get('availableOnlineCount', 0)), str(p.get('availableOfflineCount', 0)),
            utils.human_size(p.get('bytesTotal', 0)),
        ]
        if args.detail: row.append(escape(p.get('saveTo', '')))
        table.add_row(*row)
        for l in links_by_pkg.get(p['uuid'], []):
            row = ["", f"  [dim]└[/] {escape(l['name'])}", "", "", "", ""]
            if args.detail: row.append(f"[blue]{escape(l.get('url', ''))}[/]")
            table.add_row(*row)

    console.print(table)
    console.print("\n[green]Run 'jd confirm' (all) or 'jd confirm <ID|name> -s' to start downloading.[/]")

def cmd_add(device, args):
    raw = " ".join(args.urls)
    link_str = ",".join(raw.split())
    device.linkgrabber.add_links([{"links": link_str, "autostart": False, "priority": "DEFAULT"}])
    print(f"Added links to Grabber. Run 'jd confirm' to start.")

def cmd_confirm(device, args):
    pkgs = query_grabber_packages(device)
    if not pkgs: return print("No pending packages.")
    if args.packages:
        pkgs = _select_packages(pkgs, args.packages)

    started = confirm_links(device, [], [p['uuid'] for p in pkgs], [p['name'] for p in pkgs], args.start)
    print(f"Confirmed {len(pkgs)} packages.")
    if args.start and not started:
        return print("Could not find the confirmed packages in the download list, run 'jd start' manually.")
    for name in started:
        print(f"Started: {name}")

def cmd_start(device, args):
    if not args.packages:
        device.downloadcontroller.start_downloads()
        return print("Command executed: start")
    pkgs = _select_packages(query_download_packages(device), args.packages)
    device.downloads.force_download([], [p['uuid'] for p in pkgs])
    for p in pkgs:
        print(f"Started: {p['name']}")

def cmd_remove(device, args):
    device.downloads.remove_links(args.uuids, [])
    print(f"Removed {len(args.uuids)} items.")

def cmd_replace(device, args):
    try: device.downloads.remove_links([args.uuid], [])
    except: pass
    device.linkgrabber.add_links([{"links": args.url, "autostart": True, "packageName": f"Rep_{args.uuid}"}])
    print("Link replaced and restarted.")

def cmd_simple(device, args):
    cmds = {
        'stop': device.downloadcontroller.stop_downloads,
        'clear': lambda: device.downloads.cleanup("DELETE_FINISHED", "REMOVE_LINKS_ONLY", "ALL", [], [])
    }
    cmds[args.command]()
    print(f"Command executed: {args.command}")

def cmd_clear(device, args):
    if not args.pending:
        return cmd_simple(device, args)
    links = device.downloads.query_links([{"finished": True, "running": True, "enabled": True, "maxResults": -1, "startAt": 0}])
    pending = [l['uuid'] for l in links if not l.get('finished') and not l.get('running') and l.get('enabled')]
    if pending:
        device.downloads.remove_links(pending, [])
    print(f"Removed {len(pending)} pending links.")

def cmd_limit(device, args):
    if args.rate is None:
        limit = get_speed_limit(device)
    elif args.rate.lower() in ("on", "off"):
        enable_speed_limit(device, args.rate.lower() == "on")
        limit = get_speed_limit(device)
    else:
        try: limit = utils.parse_size(args.rate)
        except ValueError: sys.exit(f"Invalid rate '{args.rate}', use e.g. 5M or 500K.")
        set_speed_limit(device, limit)
    print(f"Speed limit: {utils.human_size(limit)}/s" if limit else "Speed limit: off")

def cmd_version(device, args):
    print(f"JDSH v{config.VERSION}")
    try: print(f"JD Core: {device.action('/jd/getCoreRevision', [])}")
    except: print("JD Core: Unknown")


def main():
    client = JDClient()
    
    # Interactive Mode
    if len(sys.argv) == 1:
        client.connect()
        tui.run(client)
        sys.exit(0)

    if "-h" in sys.argv or "--help" in sys.argv:
        print_help()
        sys.exit(0)

    parser = argparse.ArgumentParser(prog="jd", add_help=False)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status")

    p_ls = sub.add_parser("list", aliases=["ls"])
    p_ls.add_argument("-d", "--detail", action="store_true")
    
    p_gr = sub.add_parser("grabber")
    p_gr.add_argument("-d", "--detail", action="store_true")

    p_conf = sub.add_parser("confirm")
    p_conf.add_argument("packages", nargs="*")
    p_conf.add_argument("-s", "--start", action="store_true")

    p_start = sub.add_parser("start")
    p_start.add_argument("packages", nargs="*")

    sub.add_parser("stop")
    p_limit = sub.add_parser("limit")
    p_limit.add_argument("rate", nargs="?")
    p_clear = sub.add_parser("clear")
    p_clear.add_argument("-p", "--pending", action="store_true")
    sub.add_parser("version")
    sub.add_parser("help")

    p_add = sub.add_parser("add")
    p_add.add_argument("urls", nargs="+")
    
    p_rm = sub.add_parser("remove", aliases=["rm"])
    p_rm.add_argument("uuids", nargs="+")

    p_rep = sub.add_parser("replace")
    p_rep.add_argument("uuid")
    p_rep.add_argument("url")

    try:
        args, unknown = parser.parse_known_args()
    except:
        print_help()
        sys.exit(1)
    
    if args.command in ["help", None]:
        print_help()
        sys.exit(0)

    device = client.connect()
    actions = {
        'status': cmd_status,
        'list': cmd_list, 'ls': cmd_list,
        'grabber': cmd_grabber, 'confirm': cmd_confirm,
        'add': cmd_add, 'remove': cmd_remove, 'rm': cmd_remove,
        'replace': cmd_replace, 'start': cmd_start, 
        'stop': cmd_simple, 'clear': cmd_clear, 'limit': cmd_limit,
        'version': cmd_version,
    }
    
    if args.command in actions:
        actions[args.command](device, args)

if __name__ == "__main__":
    main()