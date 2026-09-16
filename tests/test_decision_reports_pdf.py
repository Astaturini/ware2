from pathlib import Path

from app import app
from decision.jobs import DecisionJob, DecisionJobManager


def test_report_pdf_download_returns_pdf():
    client = app.test_client()
    response = client.get(
        "/api/decision/reports/20260905_113629_48895a_report/download.pdf"
    )

    assert response.status_code == 200
    assert response.content_type == "application/pdf"
    assert response.data.startswith(b"%PDF")


def test_report_pdf_download_rejects_missing_report():
    response = app.test_client().get(
        "/api/decision/reports/missing/download.pdf"
    )
    assert response.status_code == 404


def test_job_manager_persists_and_recovers_interrupted_jobs(tmp_path: Path):
    manager = DecisionJobManager(tmp_path / "data", tmp_path / "data" / "runs")
    job = DecisionJob(
        job_id="job_test_recovery",
        module="report",
        config={"run_id": "valid_run"},
        status="running",
        created_at="2026-01-01T00:00:00",
    )
    manager._jobs[job.job_id] = job
    manager._save_jobs_locked()

    recovered = DecisionJobManager(tmp_path / "data", tmp_path / "data" / "runs")
    recovered_job = recovered.get_job(job.job_id)

    assert recovered_job.status == "failed"
    assert "Flask restart" in (recovered_job.error or "")
