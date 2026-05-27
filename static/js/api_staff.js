 /* =================================================================
   10. INFINITE SCROLL - QUẢN LÝ KHO SÁCH (THỦ THƯ)
   ================================================================= */
$(window).scroll(function() {
    var trigger = $('#staff-book-scroll-trigger');
    
    if (trigger.length && trigger.data('has-next') === true) {
        if ($(window).scrollTop() + $(window).height() >= $(document).height() - 50) {
            if (trigger.hasClass('loading')) return;
            trigger.addClass('loading');
            
            $('#staff-book-loading-spinner').show();

            $.ajax({
                url: trigger.data('url'),
                type: 'GET',
                data: { 
                    'page': trigger.data('page'),
                    'q': trigger.data('query')
                },
                success: function(response) {
                    if (response.status === 'success') {
                        var html = '';
                        
                        response.data.forEach(function(book) {
                            var statusClass = book.status === 'AVAILABLE' ? 'bg-success' : 'bg-danger';
                            var progressClass = book.quantity === 0 ? 'bg-danger' : 'bg-success';
                            
                            html += `
                            <tr>
                                <td class="ps-4 py-3">
                                    <div class="d-flex align-items-center">
                                        <img src="${book.cover_image}" style="width: 45px; height: 60px; object-fit: cover;" class="rounded shadow-sm me-3 border">
                                        <div>
                                            <div class="fw-bold text-dark">${book.title}</div>
                                            <small class="text-muted">Tác giả: ${book.author}</small>
                                        </div>
                                    </div>
                                </td>
                                <td>
                                    <span class="badge bg-light text-secondary border px-2 py-1">${book.category_name}</span>
                                </td>
                                <td>
                                    <div class="fw-bold small">${book.quantity} / ${book.initial_quantity}</div>
                                    <div class="progress mt-1" style="height: 5px; width: 80px;">
                                        <div class="progress-bar ${progressClass}" style="width: ${book.percent}%"></div>
                                    </div>
                                </td>
                                <td class="text-center">
                                    <span class="badge ${statusClass} rounded-pill px-3 py-2">
                                        ${book.status_display}
                                    </span>
                                </td>
                                <td class="text-end pe-4">
                                    <div class="btn-group shadow-sm">
                                        <a href="${book.edit_url}" class="btn btn-outline-primary btn-sm" title="Chỉnh sửa">
                                            <i class="fas fa-edit"></i>
                                        </a>
                                        <a href="${book.delete_url}" class="btn btn-outline-danger btn-sm custom-confirm" title="Xóa" data-message="Bạn có chắc chắn muốn xóa cuốn sách này khỏi kho không?">
                                            <i class="fas fa-trash"></i>
                                        </a>
                                    </div>
                                </td>
                            </tr>`;
                        });

                        $('#staff-book-container').append(html);

                        if (response.has_next) {
                            trigger.data('page', trigger.data('page') + 1);
                            trigger.removeClass('loading');
                        } else {
                            trigger.data('has-next', false);
                        }
                        $('#staff-book-loading-spinner').hide();
                    }
                }
            });
        }
    }
});
/* =================================================================
   11. INFINITE SCROLL - QUẢN LÝ MƯỢN TRẢ (THỦ THƯ)
   ================================================================= */
$(window).scroll(function() {
    var trigger = $('#staff-borrow-scroll-trigger');
    
    if (trigger.length && trigger.data('has-next') === true) {
        if ($(window).scrollTop() + $(window).height() >= $(document).height() - 50) {
            if (trigger.hasClass('loading')) return;
            trigger.addClass('loading');
            
            $('#staff-borrow-loading-spinner').show();

            $.ajax({
                url: trigger.data('url'),
                type: 'GET',
                data: { 
                    'page': trigger.data('page'),
                    'q': trigger.data('query')
                },
                success: function(response) {
                    if (response.status === 'success') {
                        var html = '';
                        
                        response.data.forEach(function(t) {
                            
                            // 1. Dựng HTML Trạng thái & Phương thức thanh toán
                            var statusHtml = '';
                            if (t.status === 'BORROWED') {
                                statusHtml = '<span class="badge bg-primary rounded-pill px-3 shadow-sm mb-1">Đang mượn</span>';
                            } else if (t.status === 'OVERDUE') {
                                statusHtml = '<span class="badge bg-dark text-white rounded-pill px-3 shadow-sm mb-1">Quá hạn</span>';
                            } else if (t.status === 'PENDING') {
                                if (t.reason === 'YÊU CẦU TRẢ') {
                                    statusHtml = '<span class="badge bg-warning text-dark rounded-pill px-3 shadow-sm mb-1"><i class="fas fa-undo me-1"></i>Chờ xác nhận trả</span>';
                                } else {
                                    if (t.book_price > 0 && !t.is_paid) {
                                        statusHtml = '<span class="badge bg-danger text-white rounded-pill px-3 shadow-sm mb-1"><i class="fas fa-spinner fa-spin me-1"></i>Chờ duyệt phí</span>';
                                    } else {
                                        statusHtml = '<span class="badge bg-info text-white rounded-pill px-3 shadow-sm mb-1"><i class="fas fa-hourglass-half me-1"></i>Chờ duyệt mượn</span>';
                                    }
                                }
                            } else {
                                statusHtml = '<span class="badge bg-success rounded-pill px-3 shadow-sm mb-1">Đã trả</span>';
                            }

                            var paymentHtml = '';
                            if (t.payment_method !== 'FREE') {
                                var badgeColor = t.payment_method === 'CASH' ? 'bg-success' : 'bg-info';
                                var icon = t.payment_method === 'CASH' ? '<i class="fas fa-money-bill-wave me-1"></i>Tiền mặt' : '<i class="fas fa-qrcode me-1"></i>Chuyển khoản';
                                paymentHtml = `<div class="mt-1"><span class="badge ${badgeColor} rounded-pill shadow-sm" style="font-size: 0.7rem;">${icon}</span></div>`;
                            }

                            // 2. Dựng HTML Nút thao tác
                            var actionHtml = '';
                            if (t.status === 'PENDING') {
                                if (t.reason === 'YÊU CẦU TRẢ') {
                                    actionHtml = `<a href="${t.confirm_return_url}" class="btn btn-sm btn-success rounded-pill px-3 shadow-sm fw-bold" onclick="return confirm('Xác nhận sinh viên đã mang sách ra quầy trả?')"><i class="fas fa-check-circle me-1"></i>Xác nhận thu hồi</a>`;
                                } else {
                                    actionHtml = `<a href="${t.approve_borrow_url}" class="btn btn-sm btn-primary rounded-pill px-3 shadow-sm fw-bold" onclick="return confirm('Xác nhận duyệt và giao sách cho sinh viên này?')"><i class="fas fa-user-check me-1"></i>Duyệt giao sách</a>`;
                                }
                            } else if (t.status === 'BORROWED' || t.status === 'OVERDUE') {
                                actionHtml = `<a href="${t.confirm_return_url}" class="btn btn-sm btn-outline-secondary rounded-pill px-3 shadow-sm" onclick="return confirm('Sinh viên chưa gửi yêu cầu trả trên web. Bạn vẫn muốn thu hồi sách trực tiếp chứ?')">Thu hồi trực tiếp</a>`;
                            } else {
                                actionHtml = `<span class="text-success fw-bold small"><i class="fas fa-check-double me-1"></i>Hoàn tất</span>`;
                            }

                            var dateHtml = t.is_overdue ? `<span class="text-danger fw-bold">${t.due_date}</span>` : `<span>${t.due_date}</span>`;

                            // 3. Ráp vào khung dòng <tr>
                            html += `
                            <tr class="animate__animated animate__fadeInUp">
                                <td class="py-3">
                                    <div class="fw-bold text-dark">${t.user_name}</div>
                                    <small class="text-muted">MSV: ${t.user_msv}</small>
                                </td>
                                <td>
                                    <div class="text-truncate" style="max-width: 200px;" title="${t.book_title}">${t.book_title}</div>
                                </td>
                                <td class="text-center">${dateHtml}</td>
                                <td class="text-center">
                                    ${statusHtml}
                                    ${paymentHtml}
                                </td>
                                <td class="text-end">${actionHtml}</td>
                            </tr>`;
                        });

                        $('#staff-borrow-container').append(html);

                        if (response.has_next) {
                            trigger.data('page', trigger.data('page') + 1);
                            trigger.removeClass('loading');
                        } else {
                            trigger.data('has-next', false);
                        }
                        $('#staff-borrow-loading-spinner').hide();
                    }
                }
            });
        }
    }
});

/* =================================================================
   12. XEM CHI TIẾT ĐÁNH GIÁ (MODAL)
   ================================================================= */
$(document).on('click', '.btn-view-reviews', function() {
    var btn = $(this);
    var url = btn.data('url');
    var modal = $('#reviewDetailModal');
    var container = $('#modal-reviews-container');
    
    // Reset modal
    container.html(`
        <div class="p-5 text-center text-muted">
            <div class="spinner-border spinner-border-sm me-2" role="status"></div>
            Đang tải dữ liệu...
        </div>
    `);
    modal.modal('show');
    
    $.ajax({
        url: url,
        type: 'GET',
        success: function(response) {
            if (response.status === 'success') {
                $('#modal-book-title').text('Đánh giá: ' + response.book_title);
                $('#modal-total-reviewers').text(response.total_reviewers);
                
                var html = '';
                if (response.reviews.length > 0) {
                    response.reviews.forEach(function(r) {
                        var stars = '';
                        for (var i = 1; i <= 5; i++) {
                            if (i <= r.rating) {
                                stars += '<i class="fas fa-star text-warning small"></i>';
                            } else {
                                stars += '<i class="far fa-star text-muted small"></i>';
                            }
                        }
                        
                        html += `
                            <div class="p-4 border-bottom transition-hover bg-white">
                                <div class="d-flex justify-content-between align-items-start mb-2">
                                    <div class="d-flex align-items-center">
                                        <img src="${r.user_avatar}" 
                                             class="rounded-circle border border-2 border-primary-soft me-3 shadow-sm object-fit-cover" 
                                             style="width: 42px; height: 42px;" 
                                             onerror="this.src='/static/img/avatar.png'">
                                        <div>
                                            <div class="fw-bold text-dark mb-0" style="font-size: 0.9rem;">${r.user_name}</div>
                                            <div class="stars-group">${stars}</div>
                                        </div>
                                    </div>
                                    <div class="text-muted small" style="font-size: 0.75rem;">
                                        <i class="far fa-clock me-1"></i>${r.created_at}
                                    </div>
                                </div>
                                <div class="ps-5">
                                    <p class="text-dark mb-0 lh-base" style="font-size: 0.9rem;">${r.comment}</p>
                                </div>
                            </div>
                        `;
                    });
                } else {
                    html = '<div class="p-5 text-center text-muted">Chưa có đánh giá nào cho sách này.</div>';
                }
                container.html(html);
            } else {
                container.html('<div class="p-5 text-center text-danger">Có lỗi xảy ra khi tải dữ liệu.</div>');
            }
        },
        error: function() {
            container.html('<div class="p-5 text-center text-danger">Không thể kết nối đến máy chủ.</div>');
        }
    });
});

/* =================================================================
   13. TÍNH PHÍ PHẠT KHI THU HỒI SÁCH (BORROW MANAGEMENT)
   ================================================================= */
document.addEventListener('DOMContentLoaded', function() {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const conditionSelectors = document.querySelectorAll('.condition-selector');
    
    conditionSelectors.forEach(select => {
        const updateFines = () => {
            const transId = select.dataset.transactionId;
            const originalPrice = parseFloat(select.dataset.originalPrice) || 0;
            const dueDate = new Date(select.dataset.dueDate);
            const condition = select.value;

            // 1. Tính phí trễ hạn (5000đ/ngày)
            let lateFine = 0;
            if (today > dueDate) {
                const diffTime = Math.abs(today - dueDate);
                const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
                lateFine = diffDays * 5000;
            }

            // 2. Tính phí hư hỏng
            let damageFine = 0;
            if (condition === 'LIGHT_DAMAGE') {
                damageFine = Math.floor(originalPrice * 0.10);
            } else if (condition === 'LOST_OR_DESTROYED') {
                damageFine = Math.floor(originalPrice);
            }

            const totalFine = lateFine + damageFine;

            // 3. Cập nhật giao diện
            const lateFineElem = document.getElementById(`lateFine${transId}`);
            const damageFineElem = document.getElementById(`damageFine${transId}`);
            const totalFineElem = document.getElementById(`totalFine${transId}`);

            if (lateFineElem) lateFineElem.innerText = lateFine.toLocaleString('vi-VN') + ' VNĐ';
            if (damageFineElem) damageFineElem.innerText = damageFine.toLocaleString('vi-VN') + ' VNĐ';
            if (totalFineElem) totalFineElem.innerText = totalFine.toLocaleString('vi-VN') + ' VNĐ';

            // 4. Hiển thị checkbox "Đã nộp tiền" nếu có phí phạt
            const payNowContainer = document.getElementById(`payNowContainer${transId}`);
            const summaryBox = document.getElementById(`penaltySummary${transId}`);
            
            if (totalFine > 0) {
                if (payNowContainer) payNowContainer.style.display = 'block';
                if (summaryBox) {
                    summaryBox.classList.add('bg-warning-subtle', 'border-warning');
                    summaryBox.classList.remove('bg-light');
                }
            } else {
                if (payNowContainer) payNowContainer.style.display = 'none';
                if (summaryBox) {
                    summaryBox.classList.remove('bg-warning-subtle', 'border-warning');
                    summaryBox.classList.add('bg-light');
                }
            }
        };

        select.addEventListener('change', updateFines);
        // Chạy lần đầu (trong trường hợp quá hạn sẵn)
        updateFines();
    });
});