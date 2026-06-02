// Dashboard charts (Chart.js). Sidebar toggle, dropdowns and alert dismissal
// are handled declaratively by Alpine.js in the templates.
function initDashboardCharts(data) {
  if (typeof Chart === 'undefined') return;
  Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', sans-serif";
  Chart.defaults.color = '#64748b';

  const movement = document.getElementById('movementChart');
  if (movement) {
    new Chart(movement, {
      type: 'bar',
      data: {
        labels: data.stock_in.labels.length ? data.stock_in.labels : data.stock_out.labels,
        datasets: [
          { label: 'Stock In', data: data.stock_in.values, backgroundColor: '#10b981' },
          { label: 'Stock Out', data: data.stock_out.values, backgroundColor: '#ef4444' },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false,
        scales: { y: { beginAtZero: true } } },
    });
  }

  const trend = document.getElementById('valueTrendChart');
  if (trend) {
    new Chart(trend, {
      type: 'line',
      data: {
        labels: data.value_trend.labels,
        datasets: [{
          label: 'Inventory Value (Stock In)', data: data.value_trend.values,
          borderColor: '#4f46e5', backgroundColor: 'rgba(79,70,229,.12)',
          fill: true, tension: .35,
        }],
      },
      options: { responsive: true, maintainAspectRatio: false,
        scales: { y: { beginAtZero: true } } },
    });
  }

  const topMoving = document.getElementById('topMovingChart');
  if (topMoving) {
    new Chart(topMoving, {
      type: 'doughnut',
      data: {
        labels: data.top_moving.labels,
        datasets: [{
          data: data.top_moving.values,
          backgroundColor: ['#4f46e5', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'],
        }],
      },
      options: { responsive: true, maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } } },
    });
  }
}
