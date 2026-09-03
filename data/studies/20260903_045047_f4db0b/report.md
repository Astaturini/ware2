# Study Report: fleet_sizing_and_scheduling

*Generated on: 2026-09-03 05:14:10*
*Study ID: 20260903_045047_f4db0b*

## 1. Experiment Design
The following factors were varied in this Design of Experiments (DoE):
- **num_robots**: 4, 8, 12
- **scheduler**: baseline, priority, total_cost

Total combinations tested: 9
Successful runs: 9
Failed runs: 0

## 2. KPI Analysis & Trade-offs

### Optimal Configurations
Depending on your operational priority, the following configurations performed best:
- **Lowest Cost per Task**: `num_robots=8`, `scheduler=priority` *(Value: 0.0396)*
- **Highest SLA Compliance**: `num_robots=4`, `scheduler=baseline` *(Value: 1.0000)*
- **Lowest Total Operating Cost**: `num_robots=8`, `scheduler=priority` *(Value: 3.9573)*
- **Highest Throughput**: `num_robots=8`, `scheduler=baseline` *(Value: 101)*

### Trade-off Observations
- **Cost vs. Throughput Trade-off:** The configuration that minimizes cost per task is *different* from the one that maximizes throughput. This indicates diminishing returns on fleet size or scheduling complexity at higher capacities.

## 3. Raw Data Summary

| num_robots | scheduler | tasks_completed | total_operating_cost | cost_per_task | sla_compliance_rate |
|---|---|---|---|---|---|
| 4 | baseline | 100 | 5.259 | 0.053 | 1.000 |
| 4 | priority | 100 | 117.656 | 1.177 | 0.950 |
| 4 | total_cost | 100 | 142.173 | 1.422 | 0.940 |
| 8 | baseline | 101 | 5.077 | 0.050 | 1.000 |
| 8 | priority | 100 | 3.957 | 0.040 | 1.000 |
| 8 | total_cost | 100 | 3.989 | 0.040 | 1.000 |
| 12 | baseline | 100 | 5.217 | 0.052 | 1.000 |
| 12 | priority | 100 | 4.998 | 0.050 | 1.000 |
| 12 | total_cost | 100 | 4.387 | 0.044 | 1.000 |