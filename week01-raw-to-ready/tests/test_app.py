import base64

import pytest
from shiny.testserver import TestServerSession

from rtr.sample import sample_export

pytestmark = pytest.mark.parametrize("local_server", ["../app.py"], indirect=True)
BASE = dict(reviewer="Tester", include_gps=False, flag_filter={"check": "all", "severity": "all", "status": "all", "enumerator": "all", "q": ""})


def out(s: TestServerSession, name: str):
    for _ in range(50):
        o = s.get_output(name)
        if o.status == "ok":
            return o.value
        s.flush()
    raise AssertionError(f"{name} never settled: {o.status}")


def test_outputs_render(local_server):
    local_server.set_inputs(**BASE)
    for name in ["meta", "overview", "flag_list", "cleaning_log", "enumerator_board", "dataset"]:
        assert out(local_server, name), name
    assert out(local_server, "overview")["readiness"]["verdict"] == "not ready"


def test_bulk_recommendation_is_logged_with_reviewer(local_server):
    local_server.set_inputs(**BASE)
    open_before = out(local_server, "flag_list")["counts"]["open"]
    local_server.set_inputs(decide={"check": "no_consent", "action": "recommended", "nonce": 1})
    local_server.flush()
    log = out(local_server, "cleaning_log")
    mine = [e for e in log["entries"] if e["changed_by"] == "Tester"]
    assert mine and all(e["action"] == "removed" for e in mine)
    assert out(local_server, "flag_list")["counts"]["open"] == open_before - len(mine)


def test_manual_change_requires_a_reason(local_server):
    local_server.set_inputs(**BASE)
    fid = out(local_server, "flag_list")["items"][0]["flag_id"]
    local_server.set_inputs(decide={"flag_ids": [fid], "action": "set missing", "reason": "", "nonce": 2})
    local_server.flush()
    assert out(local_server, "cleaning_log")["user"] == 0


def test_verification_then_revert(local_server):
    local_server.set_inputs(**{**BASE, "flag_filter": {**BASE["flag_filter"], "check": "short_interview"}})
    fid = out(local_server, "flag_list")["items"][0]["flag_id"]
    local_server.set_inputs(decide={"flag_ids": [fid], "action": "recommended", "nonce": 3})
    local_server.flush()
    item = next(i for i in out(local_server, "flag_list")["items"] if i["flag_id"] == fid)
    assert item["status"] == "awaiting verification"
    local_server.set_inputs(verify={"flag_id": fid, "outcome": "confirmed", "note": "Called household", "nonce": 4})
    local_server.flush()
    item = next(i for i in out(local_server, "flag_list")["items"] if i["flag_id"] == fid)
    assert item["status"] == "resolved"
    entry = item["decision"]["entry"]
    local_server.set_inputs(revert={"entry": entry, "reason": "Wrong household", "nonce": 5})
    local_server.flush()
    log = out(local_server, "cleaning_log")
    assert log["reverted"] == 1 and any(e["entry"] == entry and e["reverted"] for e in log["entries"])


def test_upload_replaces_dataset_and_resets_log(local_server):
    local_server.set_inputs(**BASE)
    csv = sample_export().head(60).to_csv(index=False).encode()
    local_server.set_inputs(upload={"name": "my_export.csv", "b64": base64.b64encode(csv).decode(), "nonce": 6})
    local_server.flush()
    d = out(local_server, "dataset")
    assert d["filename"] == "my_export.csv" and d["rows"] == 60 and d["source"] == "upload"
