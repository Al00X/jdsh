import sys
from myjdapi import Myjdapi
from . import config

# Fields requested when querying JDownloader. Keep them explicit: the API
# only returns what is asked for.
DOWNLOAD_PACKAGE_FIELDS = {
    "bytesLoaded": True, "bytesTotal": True, "childCount": True,
    "comment": True, "enabled": True, "eta": True, "finished": True,
    "priority": True, "running": True, "saveTo": True, "speed": True,
    "status": True,
}
DOWNLOAD_LINK_FIELDS = {
    "addedDate": True, "bytesLoaded": True, "bytesTotal": True,
    "comment": True, "enabled": True, "eta": True, "extractionStatus": True,
    "finished": True, "finishedDate": True, "host": True, "packageUUID": True,
    "priority": True, "running": True, "speed": True, "status": True,
    "url": True,
}
GRABBER_PACKAGE_FIELDS = {
    "availableOnlineCount": True, "availableOfflineCount": True,
    "bytesTotal": True, "childCount": True, "comment": True, "enabled": True,
    "hosts": True, "priority": True, "saveTo": True, "status": True,
}
GRABBER_LINK_FIELDS = {
    "availability": True, "bytesTotal": True, "comment": True,
    "enabled": True, "host": True, "packageUUID": True, "priority": True,
    "status": True, "url": True,
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

    # --- actions -----------------------------------------------------------
    #
    # Every action takes the ids of the selected links and packages, the way
    # the API expects them, so the caller can act on either kind of row.

    def _list(self, tab_is_grabber):
        return self.device.linkgrabber if tab_is_grabber else self.device.downloads

    def set_enabled(self, enable, link_ids, package_ids, grabber=False):
        self._list(grabber).set_enabled(enable, link_ids, package_ids)

    def force_download(self, link_ids, package_ids):
        self.device.downloadcontroller.force_download(link_ids, package_ids)

    def reset_links(self, link_ids, package_ids):
        self.device.downloads.reset_links(link_ids, package_ids)

    def remove(self, link_ids, package_ids, grabber=False):
        self._list(grabber).remove_links(link_ids, package_ids)

    def cleanup_finished(self, link_ids, package_ids):
        """Delete finished entries, like the GUI's Cleanup submenu."""
        self.device.downloads.cleanup(
            "DELETE_FINISHED", "REMOVE_LINKS_ONLY", "SELECTED",
            link_ids, package_ids,
        )

    def add_links(self, links, package_name=None, destination=None,
                  extract_password=None, download_password=None,
                  priority="DEFAULT", autostart=False):
        """Send links to the LinkGrabber, as the GUI's add dialog does."""
        self.device.linkgrabber.add_links([{
            "links": links,
            "packageName": package_name or None,
            "destinationFolder": destination or None,
            "extractPassword": extract_password or None,
            "downloadPassword": download_password or None,
            "priority": priority,
            "autostart": autostart,
            "overwritePackagizerRules": False,
        }])

    def move_to_downloadlist(self, link_ids, package_ids):
        self.device.linkgrabber.move_to_downloadlist(link_ids, package_ids)

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
