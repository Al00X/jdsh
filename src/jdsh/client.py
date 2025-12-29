import sys
from myjdapi import Myjdapi
from . import config

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

    def fetch_stats(self):
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

    def toggle_state(self, current_state):
        if current_state in ["RUNNING", "DOWNLOADING"]:
            self.device.downloadcontroller.stop_downloads()
        else:
            self.device.downloadcontroller.start_downloads()
