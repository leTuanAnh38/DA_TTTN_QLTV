# file: core/views/auth_views.py

from django.shortcuts import render, redirect
from django.contrib.auth.forms import PasswordChangeForm, AuthenticationForm
from django.contrib.auth import update_session_auth_hash, authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme


# Import form đăng ký từ thư mục gốc của app core
from core.forms import CustomUserCreationForm

# ==========================================
# NHÓM XÁC THỰC NGƯỜI DÙNG (AUTHENTICATION)
# ==========================================

def user_logout(request):
    logout(request)
   # messages.success(request, 'Bạn đã đăng xuất thành công!')
    return redirect('home')

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Đăng ký tài khoản thành công! Vui lòng đăng nhập.')
            return redirect('login') 
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'core/auth/register.html', {'form': form})

# ==========================================
# HÀM HỖ TRỢ: PHÂN LUỒNG CHUYỂN HƯỚNG THEO VAI TRÒ
# ==========================================
def get_user_redirect_url(user):
    """Xác định URL chuyển hướng phù hợp với vai trò của người dùng"""
    if user.is_superuser or getattr(user, 'role', '') == 'ADMIN':
        return '/admin/'
    elif user.is_staff or getattr(user, 'role', '') == 'STAFF':
        return 'staff_dashboard'
    return 'home'

def user_login(request):
    # 1. Nếu đã đăng nhập, chuyển hướng ngay theo vai trò
    if request.user.is_authenticated:
        return redirect(get_user_redirect_url(request.user))

    # 2. Xử lý khi nhấn nút Đăng nhập (POST)
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user() # AuthenticationForm đã authenticate rồi, chỉ cần lấy user ra
            login(request, user) 
            
            # Xử lý tham số 'next' để quay lại trang cũ nếu có (Tránh Open Redirect)
            next_url = request.GET.get('next')
            if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}):
                return redirect(next_url)
                
            # Nếu không có 'next' hoặc 'next' không an toàn, về dashboard mặc định
            return redirect(get_user_redirect_url(user))
        else:
            messages.error(request, 'Tên đăng nhập hoặc mật khẩu không đúng.')
    else:
        form = AuthenticationForm()
    
    return render(request, 'core/auth/login.html', {'form': form})

@login_required(login_url='login') 
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():  
            user = form.save()
            update_session_auth_hash(request, user) 
            messages.success(request, 'Mật khẩu của bạn đã được cập nhật thành công!')
            return redirect('home')
        else:
            messages.error(request, 'Đổi mật khẩu thất bại. Vui lòng kiểm tra lại thông tin bên dưới.')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'core/auth/change_password.html', {'form': form})
