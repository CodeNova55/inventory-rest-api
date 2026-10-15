from django.contrib.auth import get_user_model, password_validation
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from .models import Product, StockMovement

User = get_user_model()


class ProductSerializer(serializers.ModelSerializer):
    is_low_stock = serializers.BooleanField(read_only=True)
    initial_quantity = serializers.IntegerField(
        write_only=True,
        required=False,
        min_value=0,
        max_value=1_000_000,
        help_text="Starting stock when creating a product",
    )

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "price",
            "quantity",
            "reorder_level",
            "is_low_stock",
            "initial_quantity",
            "created_at",
            "updated_at",
        ]
        # Stock changes only through the adjust-stock endpoint, so history stays complete
        read_only_fields = ["quantity", "created_at", "updated_at"]

    def validate_sku(self, value):
        value = value.strip().upper()
        owner = self.context["request"].user
        queryset = Product.objects.filter(owner=owner, sku=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("You already have a product with this SKU.")
        return value

    def create(self, validated_data):
        initial = validated_data.pop("initial_quantity", 0)
        product = Product.objects.create(**validated_data)
        if initial:
            product.adjust_stock(initial, "Initial stock")
        return product

    def update(self, instance, validated_data):
        validated_data.pop("initial_quantity", None)
        return super().update(instance, validated_data)


class StockAdjustSerializer(serializers.Serializer):
    change = serializers.IntegerField(
        min_value=-1_000_000,
        max_value=1_000_000,
        help_text="Positive to add stock, negative to remove it",
    )
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")

    def validate_change(self, value):
        if value == 0:
            raise serializers.ValidationError("Change must not be zero.")
        return value


class StockMovementSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = ["id", "change", "reason", "quantity_after", "created_at"]


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is taken.")
        return value

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

    def to_representation(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        return {"username": user.username, "token": token.key}
