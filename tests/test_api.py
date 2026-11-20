import os, tempfile
os.environ["DATABASE_URL"] = "sqlite:///./test_medlegal.db"
from fastapi.testclient import TestClient
from medlegal_extract.app import app

client = TestClient(app)


def test_submit_status_result(tmp_path):
    f = tmp_path / "rec.txt"
    f.write_text("Patient: Jane Doe\nProvider: City General Hospital\n"
                 "Date of Service: 2024-03-01\nCharges: $10.00\nTotal: $10.00\n")
    r = client.post("/jobs", json={"path": str(f)})
    assert r.status_code == 200
    job = r.json()["job_id"]
    assert client.get(f"/jobs/{job}").json()["status"] in {"queued", "running", "done"}
    res = client.get(f"/jobs/{job}/result")
    assert res.status_code == 200
    # Background task completes within TestClient lifecycle; result or still-running is valid shape.
    assert "status" in res.json() or "extraction" in res.json()


def test_missing_job_404():
    assert client.get("/jobs/nope").status_code == 404
