// =====================================================================
// ECharts wrappers
// =====================================================================

function ensureECharts(el) {
    if (typeof echarts !== "undefined") {
        return true;
    }

    if (el) {
        el.innerHTML = `
            <div style="
                padding: 12px;
                border-radius: 6px;
                border: 1px solid rgba(239, 68, 68, 0.45);
                background: rgba(239, 68, 68, 0.12);
                color: #fecaca;
            ">
                ECharts library failed to load.
                Check your internet connection or vendor ECharts locally at
                /static/vendor/echarts.min.js.
            </div>
        `;
    }

    console.error("ECharts is not loaded. Charts cannot render.");
    return false;
}

function getBaseChartOption() {
    return {
        backgroundColor: "transparent",
        textStyle: { color: "#eaeaea" },
        tooltip: {
            trigger: "axis",
            backgroundColor: "#16213e",
            borderColor: "#2d3748",
            textStyle: { color: "#eaeaea" }
        },
        legend: {
            top: 0,
            textStyle: { color: "#eaeaea" }
        },
        grid: {
            left: 60,
            right: 30,
            top: 50,
            bottom: 80
        },
        xAxis: {
            type: "value",
            name: "Tick",
            axisLine: { lineStyle: { color: "#2d3748" } },
            axisLabel: { color: "#a8a8a8" }
        },
        yAxis: {
            type: "value",
            axisLine: { lineStyle: { color: "#2d3748" } },
            axisLabel: { color: "#a8a8a8" },
            splitLine: { lineStyle: { color: "#2d3748" } }
        },
        dataZoom: [
            { type: "inside" },
            {
                type: "slider",
                height: 20,
                bottom: 10,
                borderColor: "#2d3748",
                fillerColor: "rgba(245,158,11,0.2)"
            }
        ],
        color: CHART_COLORS
    };
}

function renderLineChart(containerId, series, options = {}) {
    const el = document.getElementById(containerId);
    if (!el) return null;

    if (!ensureECharts(el)) return null;

    if (options.existingChart) {
        options.existingChart.dispose();
    }

    const chart = echarts.init(el, "dark");
    const opt = getBaseChartOption();

    opt.series = series.map(item => ({
        name: item.name,
        type: "line",
        showSymbol: false,
        data: item.points,
        smooth: options.smooth !== false,
        lineStyle: item.lineStyle || { width: 2 }
    }));

    chart.setOption(opt);
    return chart;
}

function renderStackedAreaChart(containerId, series) {
    const el = document.getElementById(containerId);
    if (!el) return null;

    if (!ensureECharts(el)) return null;

    if (visualizationChart) visualizationChart.dispose();

    const chart = echarts.init(el, "dark");
    const opt = getBaseChartOption();

    opt.series = series.map(item => ({
        name: item.name,
        type: "line",
        stack: "total",
        areaStyle: { opacity: 0.6 },
        showSymbol: false,
        data: item.points,
        smooth: true,
        emphasis: { focus: "series" }
    }));

    chart.setOption(opt);
    return chart;
}

function renderBarChart(containerId, categories, values, title) {
    const el = document.getElementById(containerId);
    if (!el) return null;

    if (!ensureECharts(el)) return null;

    if (compareChart) compareChart.dispose();

    const chart = echarts.init(el, "dark");
    const opt = getBaseChartOption();

    opt.xAxis = {
        type: "category",
        data: categories,
        axisLabel: {
            color: "#a8a8a8",
            rotate: 30
        }
    };

    opt.yAxis = {
        type: "value",
        axisLine: { lineStyle: { color: "#2d3748" } },
        splitLine: { lineStyle: { color: "#2d3748" } }
    };

    opt.dataZoom = [];

    opt.series = [{
        name: title,
        type: "bar",
        data: values,
        itemStyle: { borderRadius: [4, 4, 0, 0] }
    }];

    chart.setOption(opt);
    return chart;
}

function renderHistogramChart(containerEl, histogram) {
    if (!containerEl) return;

    if (!ensureECharts(containerEl)) return;

    const chart = echarts.init(containerEl, "dark");
    const opt = getBaseChartOption();

    opt.xAxis = {
        type: "category",
        data: (histogram.bin_centers || []).map(v => Number(v).toFixed(1)),
        axisLabel: { color: "#a8a8a8" }
    };

    opt.yAxis = {
        type: "value",
        axisLine: { lineStyle: { color: "#2d3748" } },
        splitLine: { lineStyle: { color: "#2d3748" } }
    };

    opt.dataZoom = [];

    opt.series = [{
        type: "bar",
        data: histogram.counts || [],
        itemStyle: { color: "#E69F00" }
    }];

    chart.setOption(opt);
    analysisCharts.push(chart);
}

function renderProbabilityBarChart(containerEl, payload) {
    if (!containerEl || !ensureECharts(containerEl)) return null;
    const candidates = payload.candidates || [];
    if (!candidates.length) return null;
    const chart = echarts.init(containerEl, "dark");
    chart.setOption({
        backgroundColor: "transparent",
        tooltip: { trigger: "axis" },
        grid: { left: 60, right: 30, top: 55, bottom: 55 },
        xAxis: { type: "category", data: candidates.map(item => item.label || "Candidate") },
        yAxis: { type: "value", min: 0, max: 1, axisLabel: { formatter: value => `${Math.round(value * 100)}%` } },
        graphic: [{ type: "text", left: 60, top: 12, style: { text: `Minimum pass probability: ${Math.round(Number(payload.min_pass_probability || 0) * 100)}%`, fill: "#fef3c7" } }],
        series: [{
            type: "bar",
            data: candidates.map(item => ({ value: item.constraint_pass_probability, itemStyle: { color: item.robust_pass ? "#10b981" : "#ef4444" } })),
            markLine: { symbol: "none", data: [{ yAxis: payload.min_pass_probability, label: { formatter: "threshold" }, lineStyle: { color: "#f59e0b", type: "dashed" } }] }
        }]
    });
    return chart;
}

function renderParetoScatterChart(containerEl, payload) {
    const points = payload.points || [];
    return renderScatterChart(containerEl, [
        { name: "Other feasible trials", type: "scatter", data: points.filter(item => !item.pareto).map(item => [item.x, item.y]), itemStyle: { color: "#56B4E9" } },
        { name: "Pareto candidates", type: "scatter", data: points.filter(item => item.pareto).map(item => [item.x, item.y]), symbolSize: 14, itemStyle: { color: "#f59e0b" } }
    ], payload.x_metric, payload.y_metric);
}

function renderRobustnessChart(containerEl, candidates, threshold) {
    if (!containerEl || !ensureECharts(containerEl)) return null;
    const chart = echarts.init(containerEl, "dark");
    chart.setOption({
        backgroundColor: "transparent",
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        grid: { left: 60, right: 30, top: 50, bottom: 55 },
        xAxis: { type: "category", data: candidates.map(item => item.label || "Candidate"), axisLabel: { color: "#a8a8a8" } },
        yAxis: { type: "value", min: 0, max: 1, axisLabel: { formatter: value => `${Math.round(value * 100)}%` } },
        graphic: [{ type: "text", left: 60, top: 12, style: { text: `Minimum pass probability: ${Math.round(Number(threshold || 0) * 100)}%`, fill: "#fef3c7", fontSize: 12 } }],
        series: [{
            type: "bar",
            data: candidates.map(item => ({ value: Number(item.constraint_pass_probability), itemStyle: { color: item.robust_pass ? "#10b981" : "#ef4444" } })),
            markLine: { symbol: "none", data: [{ yAxis: Number(threshold || 0), label: { formatter: "threshold" }, lineStyle: { color: "#f59e0b", type: "dashed" } }] }
        }]
    });
    return chart;
}

function renderScatterChart(containerEl, series, xName, yName) {
    if (!containerEl || !ensureECharts(containerEl)) return null;
    const chart = echarts.init(containerEl, "dark");
    chart.setOption({
        backgroundColor: "transparent",
        tooltip: { trigger: "item" },
        legend: { top: 0, textStyle: { color: "#eaeaea" } },
        grid: { left: 65, right: 30, top: 45, bottom: 60 },
        xAxis: { type: "value", name: xName },
        yAxis: { type: "value", name: yName },
        series
    });
    return chart;
}

function renderObjectiveTrialChart(containerEl, trials, objective, bestTrial) {
    if (!containerEl || !ensureECharts(containerEl)) return null;
    const chart = echarts.init(containerEl, "dark");
    chart.setOption({
        backgroundColor: "transparent",
        tooltip: { trigger: "axis" },
        grid: { left: 65, right: 30, top: 45, bottom: 60 },
        xAxis: { type: "category", name: "Trial", data: trials.map(item => item.number ?? item.trial_number) },
        yAxis: { type: "value", name: objective },
        series: [{
            type: "bar",
            data: trials.map(item => ({ value: Number(item.value ?? item[objective]), itemStyle: { color: item.feasible ? "#10b981" : "#ef4444" } }))
        }, ...(bestTrial ? [{ type: "scatter", name: "Best feasible", data: [[String(bestTrial.number), Number(bestTrial.value ?? bestTrial[objective])]], symbolSize: 14, itemStyle: { color: "#f59e0b" } }] : [])]
    });
    return chart;
}

function renderTornadoChart(containerEl, rows) {
    if (!containerEl || !ensureECharts(containerEl)) return null;
    const chart = echarts.init(containerEl, "dark");
    const ordered = [...rows].sort((a, b) => Math.abs(Number(b.delta ?? b.delta_percent ?? 0)) - Math.abs(Number(a.delta ?? a.delta_percent ?? 0)));
    chart.setOption({
        backgroundColor: "transparent",
        tooltip: { trigger: "axis" },
        grid: { left: 120, right: 30, top: 25, bottom: 35 },
        xAxis: { type: "value" },
        yAxis: { type: "category", data: ordered.map(item => item.factor || item.name || "factor") },
        series: [{ type: "bar", data: ordered.map(item => Number(item.delta ?? item.delta_percent ?? 0)), itemStyle: { color: "#56B4E9" } }]
    });
    return chart;
}

// Resize charts when browser window changes.
window.addEventListener("resize", () => {
    if (visualizationChart) visualizationChart.resize();
    if (compareChart) compareChart.resize();

    analysisCharts.forEach(chart => {
        if (chart) chart.resize();
    });
});