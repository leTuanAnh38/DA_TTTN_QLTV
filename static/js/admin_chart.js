// admin_chart.js - Biểu đồ Dashboard Thủ thư
(function() {
    var ctx1 = document.getElementById('statusChart');
    var ctx2 = document.getElementById('topBooksChart');

    // Chỉ chạy khi trang có chứa canvas biểu đồ
    if (!ctx1 && !ctx2) return;

    fetch('/api/admin-chart/')
        .then(function(res) { return res.json(); })
        .then(function(data) {
            // Biểu đồ trạng thái mượn sách (Doughnut)
            if (ctx1 && data.status_labels) {
                new Chart(ctx1, {
                    type: 'doughnut',
                    data: {
                        labels: data.status_labels,
                        datasets: [{
                            data: data.status_data,
                            backgroundColor: ['#4e73df', '#f6c23e', '#1cc88a', '#e74a3b'],
                            hoverBackgroundColor: ['#2e59d9', '#dda20a', '#17a673', '#be2617'],
                            borderWidth: 2,
                            borderColor: '#fff'
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: '65%',
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: { padding: 15, usePointStyle: true, font: { size: 12 } }
                            }
                        }
                    }
                });
            }

            // Biểu đồ Top sách mượn nhiều nhất (Bar ngang)
            if (ctx2 && data.top_labels) {
                new Chart(ctx2, {
                    type: 'bar',
                    data: {
                        labels: data.top_labels,
                        datasets: [{
                            label: 'Lượt mượn',
                            data: data.top_data,
                            backgroundColor: '#4e73df',
                            hoverBackgroundColor: '#2e59d9',
                            borderRadius: 6,
                            barThickness: 22
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: {
                            x: {
                                beginAtZero: true,
                                grid: { display: false },
                                ticks: { stepSize: 1 }
                            },
                            y: {
                                grid: { display: false },
                                ticks: { font: { size: 11 } }
                            }
                        }
                    }
                });
            }
        })
        .catch(function(err) { console.error('Lỗi biểu đồ:', err); });
})();