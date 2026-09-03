import json
import tempfile
from pathlib import Path

import pandas as pd

from decision.report import generate_report


def test_generate_report_basic_and_tradeoffs():
    with tempfile.TemporaryDirectory() as tmpdir:
        study_dir = Path(tmpdir) / "test_study"
        study_dir.mkdir()

        config = {
            "study_name": "Fleet Sizing Test",
            "factors": {"num_robots": [2, 4], "scheduler": ["baseline", "priority"]},
            "base_config": {},
            "cost_config": {},
        }
        with open(study_dir / "study_config.json", "w", encoding="utf-8") as f:
            json.dump(config, f)

        # Notice the tradeoff: 4 robots + priority gives best SLA and throughput, 
        # but 2 robots + baseline gives lowest total cost. 4 robots + priority gives lowest cost per task.
        df = pd.DataFrame(
            [
                {
                    "num_robots": 2,
                    "scheduler": "baseline",
                    "tasks_completed": 10,
                    "total_operating_cost": 50.0,
                    "cost_per_task": 5.0,
                    "sla_compliance_rate": 0.60,
                },
                {
                    "num_robots": 4,
                    "scheduler": "priority",
                    "tasks_completed": 25,
                    "total_operating_cost": 150.0,
                    "cost_per_task": 6.0,
                    "sla_compliance_rate": 0.95,
                },
                {
                    "num_robots": 4,
                    "scheduler": "baseline",
                    "error": "Simulation timed out",
                    "tasks_completed": None,
                    "total_operating_cost": None,
                    "cost_per_task": None,
                    "sla_compliance_rate": None,
                },
            ]
        )
        df.to_csv(study_dir / "results.csv", index=False)

        report_path = generate_report(study_dir)
        assert report_path.exists()

        content = report_path.read_text(encoding="utf-8")
        
        # Structure checks
        assert "# Study Report: Fleet Sizing Test" in content
        assert "## 1. Experiment Design" in content
        assert "## 2. KPI Analysis & Trade-offs" in content
        assert "## 3. Raw Data Summary" in content
        
        # Content checks
        assert "Lowest Cost per Task" in content
        assert "`num_robots=4`, `scheduler=priority`" in content  # Best cost/task
        
        assert "Highest SLA Compliance" in content
        assert "Value: 0.9500" in content
        
        # Error handling check
        assert "Simulation timed out" in content

        # Tradeoff observation check
        assert "Cost vs. Throughput Trade-off" in content
        assert "SLA vs. Cost" in content