import os
import sys
from pathlib import Path

os.environ["DHIS2_LIVE_ON_START"] = "0"  # tests never call the DHIS2 server
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
