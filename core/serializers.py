from django.contrib.auth import get_user_model
User = get_user_model()
from rest_framework import serializers

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('username', 'email', 'password')

    def create(self, validated_data):
        # Hàm create_user sẽ tự động mã hóa (hash) mật khẩu cực kỳ an toàn
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password']
        )
        return user