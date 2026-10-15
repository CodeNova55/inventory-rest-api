from django.db.models import F
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Product
from .serializers import (
    ProductSerializer,
    RegisterSerializer,
    StockAdjustSerializer,
    StockMovementSerializer,
)


class ProductViewSet(viewsets.ModelViewSet):
    """Each user can only see and change their own products."""

    serializer_class = ProductSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "sku"]
    ordering_fields = ["name", "price", "quantity", "created_at"]

    def get_queryset(self):
        queryset = Product.objects.filter(owner=self.request.user)
        low_stock = self.request.query_params.get("low_stock", "").lower()
        if low_stock in {"1", "true", "yes"}:
            queryset = queryset.filter(quantity__lte=F("reorder_level"))
        return queryset

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    @action(
        detail=True,
        methods=["post"],
        url_path="adjust-stock",
        serializer_class=StockAdjustSerializer,
    )
    def adjust(self, request, pk=None):
        product = self.get_object()
        serializer = StockAdjustSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            movement = product.adjust_stock(**serializer.validated_data)
        except ValueError as error:
            return Response({"detail": str(error)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            StockMovementSerializer(movement).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["get"], serializer_class=StockMovementSerializer)
    def history(self, request, pk=None):
        product = self.get_object()
        page = self.paginate_queryset(product.movements.all())
        serializer = StockMovementSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class RegisterView(generics.CreateAPIView):
    """Create an account and get an API token."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
