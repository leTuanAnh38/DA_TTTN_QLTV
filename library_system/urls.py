"""
URL configuration for library_system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings # THÊM DÒNG NÀY
from django.conf.urls.static import static

admin.site.site_header = 'Hệ Thống Quản Lý Thư Viện'  # Thay đổi chữ ở thanh bar xanh
admin.site.site_title = 'Allovu Admin'             # Thay đổi chữ trên tab trình duyệt
admin.site.index_title = 'Bảng điều khiển'          # Tiêu đề bên trong trang chủ

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')), 
]

# Chỉ thêm static media khi ở chế độ DEBUG
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)