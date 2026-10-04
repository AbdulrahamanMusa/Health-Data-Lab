import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


@pytest.fixture(autouse=True)
def no_real_ollama(monkeypatch):
    """Tests never depend on a local Ollama: point at a closed port and drop the cached status."""
    from histo import providers

    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:9")
    providers._local_cache.update(at=0.0, status=None)
