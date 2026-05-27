(function ($) {
    "use strict";

    // 1. Loading Spinner
    var spinner = function () {
        setTimeout(function () {
            if ($('#spinner').length > 0) {
                $('#spinner').removeClass('show');
            }
        }, 1);
    };
    spinner();

    // 2. Khởi tạo hiệu ứng WOW.js
    new WOW().init();

    // 3. Navbar cố định khi cuộn trang (Đã xử lý qua class sticky-top của Bootstrap trên tag <header>)
    // $(window).scroll(function () {
    //     if ($(this).scrollTop() > 45) {
    //         $('.nav-bar').addClass('sticky-top shadow-sm');
    //     } else {
    //         $('.nav-bar').removeClass('sticky-top shadow-sm');
    //     }
    // });

    // 4. Banner Sách Nổi Bật (Header Carousel)
    // Đã gộp và tối ưu hiệu ứng "Center" để cuốn ở giữa to hơn
    $(".header-carousel").owlCarousel({
        autoplay: true,
        smartSpeed: 1500,
        center: true,       // Giúp cuốn sách nằm giữa
        dots: false,
        loop: true,
        margin: 25,
        nav: true,
        navText: [
            '<i class="bi bi-arrow-left"></i>',
            '<i class="bi bi-arrow-right"></i>'
        ],
        responsive: {
            0: { items: 1 },      // Màn hình nhỏ hiện 1 cuốn
            768: { items: 2 },    // Màn hình vừa hiện 2 cuốn
            992: { items: 3 }     // Màn hình lớn hiện 3 cuốn (cuốn giữa sẽ nổi bật nhất)
        }
    });

    // 5. Danh sách Sách (ProductList Carousel)
    $(".productList-carousel, .related-carousel").owlCarousel({
        autoplay: true,
        smartSpeed: 2000,
        dots: false,
        loop: true,
        margin: 25,
        nav: true,
        navText: [
            '<i class="fas fa-chevron-left"></i>',
            '<i class="fas fa-chevron-right"></i>'
        ],
        responsive: {
            0: { items: 1 },
            576: { items: 1 },
            768: { items: 2 },
            992: { items: 3 },
            1200: { items: 4 }
        }
    });

    // 6. Ảnh chi tiết sách (Single Product Carousel)
    $(".single-carousel").owlCarousel({
        autoplay: true,
        smartSpeed: 1500,
        dots: true,
        dotsData: true,
        loop: true,
        items: 1,
        nav: true,
        navText: [
            '<i class="bi bi-arrow-left"></i>',
            '<i class="bi bi-arrow-right"></i>'
        ]
    });

    // 7. Nút tăng giảm số lượng (Nếu dùng cho số lượng mượn)
    $('.quantity button').on('click', function () {
        var button = $(this);
        var oldValue = button.parent().parent().find('input').val();
        var newVal;
        if (button.hasClass('btn-plus')) {
            newVal = parseFloat(oldValue) + 1;
        } else {
            newVal = (oldValue > 0) ? parseFloat(oldValue) - 1 : 0;
        }
        button.parent().parent().find('input').val(newVal);
    });

    // 8. Nút Cuộn lên đầu trang (Back to top)
    $(window).scroll(function () {
        if ($(this).scrollTop() > 300) {
            $('.back-to-top').fadeIn('slow');
        } else {
            $('.back-to-top').fadeOut('slow');
        }
    });
    $('.back-to-top').click(function () {
        $('html, body').animate({ scrollTop: 0 }, 1500, 'easeInOutExpo');
        return false;
    });


})(jQuery);
/* ==========================================
   QUẢN LÝ HỒ SƠ (PROFILE PAGE - FULL: PREVIEW, LOADING, DRAG & DROP)
   ========================================== */
document.addEventListener('DOMContentLoaded', function () {
    // 1. CHUYỂN ĐỔI GIỮA CHẾ ĐỘ XEM VÀ SỬA
    const btnEditToggle = document.getElementById('btn-edit-toggle');
    const btnCancelEdit = document.getElementById('btn-cancel-edit');
    const viewMode = document.getElementById('profile-view-mode');
    const editMode = document.getElementById('profile-edit-mode');

    if (btnEditToggle && btnCancelEdit && viewMode && editMode) {
        btnEditToggle.addEventListener('click', function () {
            viewMode.classList.add('d-none');
            editMode.classList.remove('d-none');
        });
        btnCancelEdit.addEventListener('click', function () {
            editMode.classList.add('d-none');
            viewMode.classList.remove('d-none');
            // Reset lại ảnh preview về ảnh cũ nếu người dùng hủy bỏ
            const viewImg = document.querySelector('#profile-view-mode img');
            const previewImg = document.getElementById('avatar-preview');
            if (viewImg && previewImg) {
                previewImg.src = viewImg.src;
            }
        });
    }

    // 2. LOGIC XEM TRƯỚC (PREVIEW) AVATAR
    const avatarInput = document.getElementById('avatar-upload');
    const avatarPreview = document.getElementById('avatar-preview');
    const profileForm = document.getElementById('profile-edit-mode');
    const btnSave = document.getElementById('btn-save-profile');
    const profileDragZone = document.getElementById('profile-drag-zone');

    if (avatarInput && avatarPreview) {
        avatarInput.addEventListener('change', function (e) {
            const file = e.target.files[0];

            if (file) {
                // Ràng buộc dung lượng tối đa 2MB
                if (file.size > 2 * 1024 * 1024) {
                    alert('Ảnh hơi nặng! Vui lòng chọn ảnh dưới 2MB nhé.');
                    this.value = '';
                    return;
                }

                // Dùng FileReader để đọc ảnh và gán vào thẻ img
                const reader = new FileReader();
                reader.onload = function (event) {
                    avatarPreview.src = event.target.result;
                }
                reader.readAsDataURL(file);
            }
        });
    }

    // 3. TÍNH NĂNG KÉO THẢ (DRAG & DROP) CHO AVATAR
    if (profileDragZone && avatarInput) {
        // Ngăn chặn hành vi mặc định của trình duyệt
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            profileDragZone.addEventListener(eventName, e => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        // Hiệu ứng đổi màu viền khi kéo ảnh lướt qua
        ['dragenter', 'dragover'].forEach(eventName => {
            profileDragZone.addEventListener(eventName, () => profileDragZone.classList.add('drag-over'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            profileDragZone.addEventListener(eventName, () => profileDragZone.classList.remove('drag-over'), false);
        });

        // Xử lý khi thả file vào vùng chỉ định
        profileDragZone.addEventListener('drop', function (e) {
            const dt = e.dataTransfer;
            const files = dt.files;

            if (files.length > 0) {
                // Gán file đã thả vào thẻ input file
                avatarInput.files = files;
                // Phát lệnh 'change' để kích hoạt logic Xem trước (Mục 2)
                avatarInput.dispatchEvent(new Event('change'));
            }
        }, false);
    }

    // 4. HIỆU ỨNG LOADING KHI BẤM LƯU
    if (profileForm && btnSave) {
        profileForm.addEventListener('submit', function () {
            btnSave.disabled = true;
            const btnText = btnSave.querySelector('.btn-text');
            const spinner = btnSave.querySelector('.spinner-border');

            if (btnText) btnText.textContent = 'Đang tải lên...';
            if (spinner) spinner.classList.remove('d-none');
        });
    }
});
/* ==========================================
   XỬ LÝ ẢNH BÌA SÁCH (BOOK FORM - FULL: UPLOAD, LINK, DRAG & DROP)
   ========================================== */
document.addEventListener('DOMContentLoaded', function () {
    const coverFileInput = document.getElementById('cover-file-upload');
    const coverUrlInput = document.getElementById('cover-url-input');
    const bookCoverPreview = document.getElementById('avatar-preview');
    const dropZone = document.getElementById('drag-drop-area');

    // 1. LOGIC XEM TRƯỚC (PREVIEW) KHI CHỌN FILE
    if (coverFileInput && bookCoverPreview) {
        coverFileInput.addEventListener('change', function (e) {
            const file = e.target.files[0];
            if (file) {
                // Kiểm tra dung lượng (Tối đa 2MB)
                if (file.size > 2 * 1024 * 1024) {
                    alert('Ảnh hơi nặng! Vui lòng chọn ảnh dưới 2MB nhé.');
                    this.value = '';
                    return;
                }

                const reader = new FileReader();
                reader.onload = function (event) {
                    bookCoverPreview.src = event.target.result;
                }
                reader.readAsDataURL(file);
            } else {
                // Nếu người dùng nhấn "Hủy", khôi phục lại ảnh từ link nếu có
                if (coverUrlInput && coverUrlInput.value) {
                    bookCoverPreview.src = coverUrlInput.value;
                } else {
                    bookCoverPreview.src = 'https://placehold.co/150x220?text=Bia+Sach';
                }
            }
        });
    }

    // 2. LOGIC XEM TRƯỚC KHI DÁN LINK MẠNG (URL)
    if (coverUrlInput && bookCoverPreview) {
        coverUrlInput.addEventListener('input', function () {
            // Chỉ cập nhật từ link nếu người dùng CHƯA chọn file vật lý từ máy
            if (!coverFileInput || !coverFileInput.value) {
                if (this.value) {
                    bookCoverPreview.src = this.value;
                } else {
                    bookCoverPreview.src = 'https://placehold.co/150x220?text=Bia+Sach';
                }
            }
        });
    }

    // 3. TÍNH NĂNG KÉO THẢ (DRAG & DROP)
    if (dropZone && coverFileInput) {
        // Ngăn chặn trình duyệt mở file mặc định
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, e => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });

        // Hiệu ứng khi kéo ảnh lướt qua vùng drop
        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.add('drag-over'), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, () => dropZone.classList.remove('drag-over'), false);
        });

        // Xử lý khi thả file vào
        dropZone.addEventListener('drop', function (e) {
            const dt = e.dataTransfer;
            const files = dt.files;

            if (files.length > 0) {
                // Gán file vừa thả vào thẻ input file
                coverFileInput.files = files;

                // Kích hoạt sự kiện 'change' để chạy logic Xem trước (Mục 1)
                coverFileInput.dispatchEvent(new Event('change'));
            }
        }, false);
    }
});

/* ==========================================
   XỬ LÝ CUSTOM CONFIRM MODAL (Thay thế Alert/Confirm)
   ========================================== */
document.addEventListener('DOMContentLoaded', function () {
    const confirmModalElement = document.getElementById('customConfirmModal');
    if (!confirmModalElement) return;

    // Khởi tạo Bootstrap Modal
    const confirmModal = new bootstrap.Modal(confirmModalElement);
    const confirmMessageEl = document.getElementById('customConfirmMessage');
    const confirmBtnEl = document.getElementById('customConfirmBtn');

    // Tìm tất cả các thẻ có class 'custom-confirm'
    const confirmTriggers = document.querySelectorAll('.custom-confirm');

    confirmTriggers.forEach(trigger => {
        trigger.addEventListener('click', function (e) {
            e.preventDefault(); // Chặn hành động chuyển trang hoặc submit mặc định

            // 1. Lấy câu thông báo từ data-message (nếu không có thì dùng câu mặc định)
            const message = this.getAttribute('data-message') || 'Bạn có chắc chắn muốn thực hiện hành động này?';

            // 2. Lấy link thực tế của nút bấm đó
            const targetUrl = this.getAttribute('href');

            // 3. Gắn thông báo và link vào cái Modal màu trắng
            confirmMessageEl.textContent = message;
            confirmBtnEl.href = targetUrl;

            // 4. Bật Modal lên
            confirmModal.show();
        });
    });
    // 4. XỬ LÝ CUSTOM CONFIRM MODAL (DELEGATED)
    document.addEventListener('click', function (e) {
        const trigger = e.target.closest('.custom-confirm');
        if (!trigger) return;

        // Nếu nút này là nút mượn dạng AJAX hoặc đường dẫn chứa 'borrow', bỏ qua để handler AJAX xử lý
        const href = trigger.getAttribute && trigger.getAttribute('href');
        if (trigger.classList.contains('ajax-borrow-btn') || (href && href.includes('borrow'))) {
            return;
        }

        e.preventDefault();
        const message = trigger.getAttribute('data-message') || 'Bạn có chắc chắn muốn thực hiện hành động này?';
        const targetUrl = href || '#';

        confirmMessageEl.textContent = message;
        confirmBtnEl.href = targetUrl;
        confirmModal.show();
    });
});
//THÊM SÁCH VÀO GIỎ (AJAX + LOADING)
// Hàm chuẩn của Django để lấy mã CSRF Token bảo mật từ trình duyệt
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// 2. Hàm tạo Toast Thông báo trượt mượt mà
function showModernToast(message, type = 'success') {
    let container = document.getElementById('modern-toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'modern-toast-container';
        // Vị trí cố định ở góc trên bên phải
        container.style.cssText = 'position: fixed; top: 90px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 12px; pointer-events: none;';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    const isSuccess = type === 'success';
    const icon = isSuccess ? 'fa-check-circle text-success' : 'fa-exclamation-circle text-danger';
    const borderColor = isSuccess ? 'border-success' : 'border-danger';

    // UI của thẻ thông báo
    toast.className = `d-flex align-items-center bg-white shadow-lg rounded-4 p-3 border-start border-4 ${borderColor}`;
    toast.style.cssText = 'min-width: 280px; max-width: 350px; transform: translateX(150%); opacity: 0; transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); pointer-events: auto;';

    toast.innerHTML = `
        <i class="fas ${icon} fs-3 me-3"></i>
        <div class="text-dark lh-sm" style="font-size: 0.95rem;">${message}</div>
    `;

    container.appendChild(toast);

    // Hiệu ứng trượt vào
    requestAnimationFrame(() => {
        toast.style.transform = 'translateX(0)';
        toast.style.opacity = '1';
    });

    // Hiệu ứng trượt ra và tự xóa sau 3 giây
    setTimeout(() => {
        toast.style.transform = 'translateX(150%)';
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 400); // Xóa element khỏi DOM
    }, 3000);
}

// 3. Xử lý nút Thêm vào giỏ
document.addEventListener("DOMContentLoaded", function () {
    document.body.addEventListener('click', function (e) {
        let btn = e.target.closest('.btn-add-to-cart');
        if (!btn) return;

        e.preventDefault();
        let url = btn.getAttribute('data-url');

        let originalHTML = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        btn.disabled = true;

        const csrftoken = getCookie('csrftoken');

        fetch(url, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': csrftoken,
                'Content-Type': 'application/json'
            }
        })
            .then(res => res.json())
            .then(data => {
                btn.innerHTML = originalHTML;
                btn.disabled = false;

                if (data.success) {
                    // Gọi Toast xanh báo thành công
                    showModernToast(`<b>${data.message}</b><br><small class="text-muted">Hiện có ${data.cart_count} cuốn trong giỏ.</small>`, 'success');

                    // Cập nhật số vòng tròn đỏ trên Sidebar tự động
                    let badge = document.querySelector('a[href*="/cart/"] .badge');
                    if (badge) {
                        badge.innerText = data.cart_count;
                    } else {
                        let cartLink = document.querySelector('a[href*="/cart/"]');
                        if (cartLink) {
                            cartLink.innerHTML += ` <span class="badge bg-info rounded-pill float-end">${data.cart_count}</span>`;
                        }
                    }
                } else {
                    // Gọi Toast đỏ báo lỗi (ví dụ: chưa đăng nhập hoặc quá 4 cuốn)
                    showModernToast(`<b>Từ chối:</b> ${data.message}`, 'error');
                    
                    // Nếu có yêu cầu chuyển hướng (do chưa đăng nhập)
                    if (data.redirect) {
                        setTimeout(() => {
                            window.location.href = data.redirect;
                        }, 2000);
                    }
                }
            })
            .catch(error => {
                btn.innerHTML = originalHTML;
                btn.disabled = false;
                console.error("Cart Error:", error);
                showModernToast('<b>Lỗi kết nối:</b> Vui lòng thử lại sau!', 'error');
            });
    });
});

/* ==========================================
   GIỚI HẠN CHỌN NGÀY TỐI ĐA 7 NGÀY (FORM MƯỢN SÁCH)
   ========================================== */
document.addEventListener('DOMContentLoaded', function () {
    // Tìm tất cả các ô chọn ngày trên giao diện
    const dateInputs = document.querySelectorAll('input[name="pickup_date"]');

    if (dateInputs.length > 0) {
        // Tính ngày tối đa (Hôm nay + 7 ngày)
        const tzOffset = (new Date()).getTimezoneOffset() * 60000;
        const maxDate = new Date();
        maxDate.setDate(maxDate.getDate() + 7);
        const maxDateString = new Date(maxDate.getTime() - tzOffset).toISOString().split('T')[0];

        // Gắn thuộc tính 'max' vào các ô input
        dateInputs.forEach(input => {
            input.setAttribute('max', maxDateString);
        });
    }
});

// Xử lý xem trước ảnh cực nhanh
document.getElementById('cover-file-upload').addEventListener('change', function (e) {
    var file = e.target.files[0];
    if (file) {
        var reader = new FileReader();
        reader.onload = function (e) {
            document.getElementById('avatar-preview').src = e.target.result;
        }
        reader.readAsDataURL(file);
        document.getElementById('cover-url-input').value = '';
    }
});

document.getElementById('cover-url-input').addEventListener('input', function (e) {
    if (this.value.trim() !== '') {
        document.getElementById('avatar-preview').src = this.value;
    }
});

document.addEventListener("DOMContentLoaded", function () {
    let today = new Date().toISOString().split('T')[0];
    document.querySelectorAll('.date-picker-future').forEach(function (input) {
        input.setAttribute('min', today);
    });
    
    // Fix layout collapse by moving all borrow modals to the body
    // This prevents Bootstrap's modal-open class and CSS transforms from breaking the menu layout
    document.querySelectorAll('.borrow-modal').forEach(function(modal) {
        document.body.appendChild(modal);
    });
});