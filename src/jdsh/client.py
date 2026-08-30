import sys
from myjdapi import Myjdapi
from . import config

# Fields requested when querying JDownloader. Keep them explicit: the API
# only returns what is asked for.
DOWNLOAD_PACKAGE_FIELDS = {
    "bytesLoaded": True, "bytesTotal": True, "childCount": True,
    "enabled": True, "eta": True, "finished": True, "running": True,
    "saveTo": True, "speed": True, "status": True,
}
DOWNLOAD_LINK_FIELDS = {
    "bytesLoaded": True, "bytesTotal": True, "enabled": True, "eta": True,
    "finished": True, "host": True, "packageUUID": True, "running": True,
    "speed": True, "status": True, "url": True,
}
GRABBER_PACKAGE_FIELDS = {
    "availableOnlineCount": True, "availableOfflineCount": True,
    "bytesTotal": True, "childCount": True, "enabled": True,
    "hosts": True, "saveTo": True, "status": True,
}
GRABBER_LINK_FIELDS = {
    "availability": True, "bytesTotal": True, "enabled": True,
    "host": True, "packageUUID": True, "status": True, "url": True,
}


def _group_by_package(packages, links):
    """Attach every link to its package, mirroring the JDownloader GUI tree."""
    children = {}
    for link in links:
        children.setdefault(link.get("packageUUID"), []).append(link)
    for pkg in packages:
        pkg["_links"] = children.get(pkg.get("uuid"), [])
    return packages


class JDClient:
    def __init__(self):
        self.api = Myjdapi()
        self.api.set_app_key(config.APP_KEY)
        self.device = None

    def connect(self):
        try:
            if not self.api.direct_connect(config.HOST, config.PORT):
                raise ConnectionError(f"Failed to connect to {config.HOST}:{config.PORT}")
            self.device = self.api.get_device()
            return self.device
        except Exception as e:
            print(f"Connection Error: {e}", file=sys.stderr)
            sys.exit(1)

    def fetch_downloads(self):
        """Packages of the download list, each with its links attached."""
        try:
            packages = self.device.downloads.query_packages([DOWNLOAD_PACKAGE_FIELDS])
            links = self.device.downloads.query_links([DOWNLOAD_LINK_FIELDS])
            return _group_by_package(packages, links)
        except Exception:
            return []

    def fetch_linkgrabber(self):
        """Packages sitting in the LinkGrabber, each with its links attached."""
        try:
            packages = self.device.linkgrabber.query_packages([GRABBER_PACKAGE_FIELDS])
            links = self.device.linkgrabber.query_links([GRABBER_LINK_FIELDS])
            return _group_by_package(packages, links)
        except Exception:
            return []

    def fetch_overview(self):
        """State plus both lists, as displayed by the TUI."""
        try:
            state = self.device.downloadcontroller.get_current_state()
        except Exception:
            return "ERROR", [], []
        return state, self.fetch_downloads(), self.fetch_linkgrabber()

    def fetch_stats(self):
        """Legacy view used by the CLI: running links and pending ones."""
        try:
            state = self.device.downloadcontroller.get_current_state()

            links = self.device.downloads.query_links([{
                "name": True, "bytesLoaded": True, "bytesTotal": True,
                "speed": True, "running": True, "eta": True, "status": True,
                "finished": True, "enabled": True, "uuid": True
            }])

            active = []
            pending = []

            for l in links:
                if l.get('finished'):
                    continue

                # Active
                if l.get('running'):
                    active.append(l)
                # Pending
                elif l.get('enabled'):
                    pending.append(l)

            return state, active, pending
        except Exception:
            return "ERROR", [], []

    def move_to_downloads(self):
        """Confirm every LinkGrabber package, like the GUI's 'Continue' button."""
        packages = self.device.linkgrabber.query_packages([{"maxResults": -1}])
        if not packages:
            return 0
        ids = [p["uuid"] for p in packages]
        self.device.linkgrabber.move_to_downloadlist([], ids)
        return len(ids)

    def toggle_state(self, current_state):
        if current_state in ["RUNNING", "DOWNLOADING"]:
            self.device.downloadcontroller.stop_downloads()
        else:
            self.device.downloadcontroller.start_downloads()
