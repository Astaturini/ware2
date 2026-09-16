from app import app


client = app.test_client()


def test_chart_endpoints_return_404_for_missing_artifacts():
    routes = [
        "/api/decision/monte-carlo/missing/charts/histograms",
        "/api/decision/optimizations/missing/charts/objective",
        "/api/decision/multiobjective/missing/charts/pareto",
        "/api/decision/robustness/missing/charts/pass-probability",
        "/api/decision/sensitivity/missing/tornado",
    ]

    assert all(client.get(route).status_code == 404 for route in routes)


def test_monte_carlo_histogram_query_validation():
    response = client.get(
        "/api/decision/monte-carlo/missing/charts/histograms?metrics=unknown"
    )

    assert response.status_code == 404


def test_pareto_chart_requires_two_objectives_for_unknown_artifact():
    response = client.get("/api/decision/multiobjective/missing/charts/pareto")

    assert response.status_code == 404
