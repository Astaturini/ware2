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

// Resize charts when browser window changes.
window.addEventListener("resize", () => {
    if (visualizationChart) visualizationChart.resize();
    if (compareChart) compareChart.resize();

    analysisCharts.forEach(chart => {
        if (chart) chart.resize();
    });
});