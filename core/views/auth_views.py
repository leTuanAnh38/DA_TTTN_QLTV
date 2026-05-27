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


