document.addEventListener('DOMContentLoaded', () => {
  const charts = document.querySelectorAll('canvas[data-chart="response"]');

  charts.forEach((canvas) => {
    const rawDataset = canvas.getAttribute('data-response');
    if (!rawDataset) {
      return;
    }

    let points;
    try {
      points = JSON.parse(rawDataset);
    } catch (err) {
      console.error('Failed to parse chart dataset for monitor', canvas.dataset.monitorId, err);
      return;
    }

    const filtered = points.filter((point) => point.y !== null && point.y !== undefined);
    const labels = filtered.map((point) => new Date(point.x));
    const data = filtered.map((point) => point.y);

    if (!labels.length) {
      return;
    }

    const context = canvas.getContext('2d');
    // eslint-disable-next-line no-new
    new Chart(context, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: canvas.getAttribute('data-label') || 'Response Time (ms)',
            data,
            borderColor: '#6366f1',
            backgroundColor: 'rgba(99,102,241,0.1)',
            borderWidth: 2,
            tension: 0.35,
            fill: true,
            pointRadius: 0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => {
                if (!items.length) return '';
                return items[0].parsed.x
                  ? new Date(items[0].parsed.x).toLocaleString()
                  : new Date(labels[items[0].dataIndex]).toLocaleString();
              },
              label: (contextPoint) => `${contextPoint.parsed.y.toFixed(0)} ms`,
            },
          },
        },
        scales: {
          x: {
            type: 'time',
            time: { unit: 'minute' },
            ticks: {
              color: '#94a3b8',
            },
            grid: {
              color: 'rgba(148,163,184,0.08)',
            },
          },
          y: {
            ticks: {
              color: '#94a3b8',
            },
            grid: {
              color: 'rgba(148,163,184,0.08)',
            },
          },
        },
      },
    });
  });
});
