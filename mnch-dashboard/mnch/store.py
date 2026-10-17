"""One shared copy of the data, for every session in this process.

On start-up the bundled snapshot is served at once; a live pull from DHIS2 runs
in the background and replaces it when it lands (like Power BI's scheduled
refresh, but on demand). Every replacement bumps `version`, which sessions watch.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from . import dhis2, metrics, predict

log = logging.getLogger("mnch")
DATA = Path(__file__).resolve().parents[1] / "data"
SNAPSHOT = DATA / "snapshot.json.gz"  # committed: the app works even when DHIS2 is down
CACHE = DATA / "cache.json.gz"  # the latest live pull (not committed)


@dataclass
class State:
    model: metrics.Model
    facilities: predict.FacilityData
    risk: dict  # outcome -> predict.OutcomeModel
    districts: list  # district polygons for the map
    version: int


class Store:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.state = self._build(dhis2.load(CACHE if CACHE.exists() else SNAPSHOT), 1)
        self.refreshing = False
        self.last_error: str | None = None

    @staticmethod
    def _build(snap: dict, version: int) -> State:
        fd = predict.FacilityData.from_snapshot(snap)
        return State(
            model=metrics.Model.from_snapshot(snap),
            facilities=fd,
            risk={o: predict.build(fd, o) for o in predict.OUTCOMES},
            districts=snap.get("districts", []),
            version=version,
        )

    @property
    def version(self) -> int:
        return self.state.version

    def refresh(self) -> tuple[bool, str]:
        """Pull live from DHIS2 and swap it in. Safe to call from a worker thread."""
        with self._lock:
            if self.refreshing:
                return False, "A refresh is already running."
            self.refreshing = True
        started = time.monotonic()
        try:
            snap = dhis2.fetch()
            state = self._build(snap, self.state.version + 1)
            self.state = state
            self.last_error = None
            try:
                dhis2.save(snap, CACHE)  # the next start-up begins from fresher data
            except OSError:
                pass  # read-only disk (some hosts): keep serving from memory
            return True, f"Loaded {len(snap['values']) + len(snap['populations']):,} rows from {snap['source']['host']} in {time.monotonic() - started:.0f} s."
        except Exception as e:  # noqa: BLE001 - a failed refresh keeps the current data
            self.last_error = str(e) if isinstance(e, dhis2.DHIS2Error) else f"Refresh failed ({type(e).__name__})."
            log.warning("DHIS2 refresh failed: %s", e)
            return False, self.last_error
        finally:
            self.refreshing = False


STORE = Store()


def refresh_in_background() -> None:
    threading.Thread(target=STORE.refresh, name="dhis2-refresh", daemon=True).start()


# Once per server process (Shiny Express re-runs app.py for every session, this module only once):
# serve the snapshot now and swap in live data when it lands.
if os.environ.get("DHIS2_LIVE_ON_START", "1") == "1":
    refresh_in_background()
