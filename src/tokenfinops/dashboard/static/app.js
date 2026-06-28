document.addEventListener("DOMContentLoaded", () => {
    setupTabNavigation();
    loadDashboardData();
    // Refresh overview data every 10 seconds
    setInterval(loadDashboardData, 10000);
});

let spendChart = null;
let modelsChart = null;

function setupTabNavigation() {
    const navItems = document.querySelectorAll(".nav-item");
    const tabPanes = document.querySelectorAll(".tab-pane");

    navItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const targetTab = item.getAttribute("data-tab");

            // Deactivate all
            navItems.forEach(i => i.classList.remove("active"));
            tabPanes.forEach(p => p.classList.remove("active"));

            // Activate target
            item.classList.add("active");
            document.getElementById(`tab-${targetTab}`).classList.add("active");
            
            // Load specific tab data if required
            if (targetTab === "requests") {
                loadRequestsLog();
            } else if (targetTab === "budgets") {
                loadBudgets();
            } else if (targetTab === "recommendations") {
                loadRecommendations();
            }
        });
    });
}

async function fetch_json(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return await response.json();
    } catch (e) {
        console.error(`Failed to fetch from ${url}:`, e);
        return null;
    }
}

async function loadDashboardData() {
    // 1. Overview KPIs
    const overview = await fetch_json("/api/dashboard/overview");
    if (overview) {
        document.getElementById("kpi-spend").textContent = `$${overview.total_spent.toFixed(2)}`;
        document.getElementById("kpi-savings").textContent = `$${overview.estimated_savings.toFixed(2)}`;
        document.getElementById("kpi-cache-rate").textContent = `${(overview.cache_hit_rate * 100).toFixed(1)}%`;
        document.getElementById("kpi-latency").textContent = `${Math.round(overview.avg_latency_ms)}ms`;
    }

    // 2. Load and render charts
    const spendSeries = await fetch_json("/api/dashboard/spend");
    if (spendSeries) {
        renderSpendChart(spendSeries);
    }

    const modelBreakdown = await fetch_json("/api/dashboard/models");
    if (modelBreakdown) {
        renderModelsChart(modelBreakdown);
    }
}

function renderSpendChart(data) {
    const ctx = document.getElementById("chart-spend").getContext("2d");
    const labels = data.map(d => d.date);
    const spentValues = data.map(d => d.spent);

    if (spendChart) {
        spendChart.destroy();
    }

    spendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Spend ($)',
                data: spentValues,
                borderColor: '#8b5cf6',
                backgroundColor: 'rgba(139, 92, 246, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#9ca3af' } },
                x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#9ca3af' } }
            },
            plugins: {
                legend: { labels: { color: '#f3f4f6' } }
            }
        }
    });
}

function renderModelsChart(data) {
    const ctx = document.getElementById("chart-models").getContext("2d");
    const labels = data.map(d => d.model);
    const spentValues = data.map(d => d.spent);

    if (modelsChart) {
        modelsChart.destroy();
    }

    modelsChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: spentValues,
                backgroundColor: [
                    '#8b5cf6',
                    '#10b981',
                    '#3b82f6',
                    '#f59e0b',
                    '#ef4444'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#f3f4f6' }
                }
            }
        }
    });
}

async function loadRequestsLog() {
    const requests = await fetch_json("/api/dashboard/requests");
    const tbody = document.getElementById("requests-table-body");
    tbody.innerHTML = "";

    if (!requests || requests.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align: center;">No requests recorded yet.</td></tr>`;
        return;
    }

    requests.forEach(r => {
        const time = new Date(r.timestamp).toLocaleTimeString();
        const cacheBadge = r.cache_hit ? `<span class="cache-badge">HIT</span>` : `<span class="kpi-subtext">MISS</span>`;
        const statusBadge = `<span class="status-badge ${r.status}">${r.status.toUpperCase()}</span>`;
        
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${time}</td>
            <td>${r.requested_model}</td>
            <td>${r.routed_model || '—'}</td>
            <td>${r.provider || '—'}</td>
            <td>${r.input_tokens + r.output_tokens}</td>
            <td>$${r.cost.toFixed(4)}</td>
            <td>${Math.round(r.latency_ms)}ms</td>
            <td>${cacheBadge}</td>
            <td>${statusBadge}</td>
        `;
        tbody.appendChild(row);
    });
}

async function loadBudgets() {
    const teams = await fetch_json("/api/dashboard/teams");
    const container = document.getElementById("budget-list-container");
    container.innerHTML = "";

    if (!teams || teams.length === 0) {
        container.innerHTML = `<p style="text-align: center; color: var(--text-secondary);">No budgets configured. Set them up in the budgets database table.</p>`;
        return;
    }

    teams.forEach(t => {
        const barColor = t.utilization_pct >= 95 ? "var(--danger)" : t.utilization_pct >= 70 ? "var(--warning)" : "var(--primary)";
        
        const item = document.createElement("div");
        item.className = "budget-item";
        item.innerHTML = `
            <div class="budget-header">
                <strong>Team: ${t.team_id}</strong>
                <span>$${t.spent.toFixed(2)} / $${t.amount.toFixed(2)} (${t.utilization_pct.toFixed(1)}%)</span>
            </div>
            <div class="progress-bar-bg">
                <div class="progress-bar-fill" style="width: ${Math.min(t.utilization_pct, 100)}%; background-color: ${barColor}"></div>
            </div>
            <div style="margin-top: 0.5rem; font-size: 0.85rem; color: var(--text-secondary)">
                Fallback Downgrade Model: ${t.downgrade_model || 'None'}
            </div>
        `;
        container.appendChild(item);
    });
}

async function loadRecommendations() {
    const recs = await fetch_json("/api/dashboard/recommendations");
    const container = document.getElementById("rec-list-container");
    container.innerHTML = "";

    if (!recs || recs.length === 0) {
        container.innerHTML = `<p style="text-align: center; color: var(--text-secondary);">Your AI configuration is fully optimized. Check back later!</p>`;
        return;
    }

    recs.forEach(r => {
        const item = document.createElement("div");
        item.className = "rec-card";
        item.innerHTML = `
            <div class="rec-title-row">
                <strong>${r.title}</strong>
                <span class="rec-savings">Est. Savings: $${Number(r.estimated_savings || 0).toFixed(2)}/mo</span>
            </div>
            <p style="font-size: 0.95rem; color: var(--text-secondary); margin-bottom: 0.5rem;">${r.description}</p>
            <span class="status-badge" style="background: rgba(139, 92, 246, 0.1); color: var(--primary)">Priority: ${r.priority.toUpperCase()}</span>
        `;
        container.appendChild(item);
    });
}
