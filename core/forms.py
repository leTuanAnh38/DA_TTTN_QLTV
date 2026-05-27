from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User
from .models import User, Book,Category, Publisher # Thêm Book vào đây
from .models import Event

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Địa chỉ Email")
    last_name = forms.CharField(required=True, label="Tên") 
    first_name = forms.CharField(required=True, label="Họ và chữ lót")          
    msv = forms.CharField(max_length=20, required=False, label="Mã sinh viên")
    lop = forms.CharField(max_length=50, required=False, label="Lớp học")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('last_name', 'first_name','username', 'email', 'msv', 'lop')

    # Hàm ma thuật: Tự động gắn class CSS bo tròn của bạn vào TẤT CẢ các ô nhập liệu của Django
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                'class': 'form-control rounded-pill border-secondary-subtle ps-4',
                'placeholder': field.label
            })

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email này đã được sử dụng. Vui lòng chọn Email khác!")
        return email
# --- 2. FORM QUẢN LÝ DANH MỤC (MỚI) ---
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên danh mục'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Mô tả danh mục...'}),
        }

# --- 3. FORM QUẢN LÝ NHÀ XUẤT BẢN (ĐÃ SỬA LỖI EMAIL) ---
class PublisherForm(forms.ModelForm):
    class Meta:
        model = Publisher
        # Chỉ dùng name và address theo đúng Model của bạn
        fields = ['name', 'address'] 
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên nhà xuất bản'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Địa chỉ trụ sở'}),
        }
# --- THÊM PHẦN NÀY ĐỂ QUẢN LÝ SÁCH ---
class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        # 1. THÊM các trường mới (floor, shelf, area, original_price) vào danh sách fields
        fields = [
            'title', 'category', 'publisher', 'author', 'cover_image', 'cover_file',
            'price', 'original_price', 'initial_quantity', 'quantity', 'published_year', 
            'floor', 'shelf', 'area', 'location', 'description', 'status'
        ]
        
        # 2. Cấu hình Widgets để giao diện có class Bootstrap đẹp như Admin
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nhập tên sách'}),
            'author': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tên tác giả'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'publisher': forms.Select(attrs={'class': 'form-select'}),
            'cover_image': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Dán link ảnh bìa'}),
            
            # --- TRƯỜNG GIÁ CHO MƯỢN VÀ GIÁ GỐC ---
            'price': forms.NumberInput(attrs={'class': 'form-control text-danger fw-bold', 'placeholder': 'VD: 50000 (Để trống nếu sách Free)'}),
            'original_price': forms.NumberInput(attrs={'class': 'form-control text-primary fw-bold', 'placeholder': 'Giá mua bìa sách (Dùng tính phí phạt)'}),
            
            'initial_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'published_year': forms.NumberInput(attrs={'class': 'form-control'}),
            
            # --- BA TRƯỜNG VỊ TRÍ ---
            'floor': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Tầng'}),
            'shelf': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Kệ sách'}),
            'area': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Khu vực/Phòng'}),
            
            # Giữ lại location (nó sẽ bị ẩn ở giao diện HTML đã sửa trước đó)
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

        # 3. Chuyển đổi nhãn (Label) sang tiếng Việt cho thân thiện
        labels = {
            'title': 'Tên cuốn sách',
            'category': 'Danh mục',
            'publisher': 'Nhà xuất bản',
            'author': 'Tác giả',
            'price': 'Giá cho mượn (VNĐ)',
            'original_price': 'Giá gốc cuốn sách (VNĐ)',
            'initial_quantity': 'Tổng số lượng ban đầu',
            'quantity': 'Số lượng còn trong kho',
            'published_year': 'Năm xuất bản',
            'description': 'Tóm tắt nội dung',
            'floor': 'Tầng số',
            'shelf': 'Kệ số / Ngăn số',
            'area': 'Khu vực / Phòng',
            'status': 'Trạng thái hiện tại'
        }
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['avatar', 'msv', 'lop', 'dia_chi', 'first_name', 'last_name', 'email']
        widgets = {
            'dia_chi': forms.Textarea(attrs={'rows': 3}),
        }

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'cover_image', 'content', 'start_date', 'end_date', 'location', 'max_participants', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            # Gắn ID "cover-file-upload" để tái sử dụng JS xem trước ảnh trong main.js
            'cover_image': forms.FileInput(attrs={'class': 'form-control', 'id': 'cover-file-upload'}),
            'content': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            # Gắn class bỏ viền trái cho đẹp
            'location': forms.TextInput(attrs={'class': 'form-control border-start-0'}),
            'max_participants': forms.NumberInput(attrs={'class': 'form-control border-start-0'}),
            # Gắn class nút gạt Switch của Bootstrap
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }