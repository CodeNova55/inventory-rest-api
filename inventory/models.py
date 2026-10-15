from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction


class Product(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="products"
    )
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0"))],
    )  # in KES
    quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "sku"], name="unique_sku_per_owner")
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @property
    def is_low_stock(self):
        return self.quantity <= self.reorder_level

    def adjust_stock(self, change, reason=""):
        """Add (positive) or remove (negative) stock and record the movement.

        Raises ValueError if the change is zero or would make stock negative.
        """
        if change == 0:
            raise ValueError("Change must not be zero.")
        with transaction.atomic():
            current = Product.objects.select_for_update().get(pk=self.pk)
            new_quantity = current.quantity + change
            if new_quantity < 0:
                raise ValueError(
                    f"Not enough stock: only {current.quantity} available."
                )
            current.quantity = new_quantity
            current.save(update_fields=["quantity", "updated_at"])
            movement = StockMovement.objects.create(
                product=current,
                change=change,
                reason=reason,
                quantity_after=new_quantity,
            )
        self.quantity = new_quantity
        return movement


class StockMovement(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="movements"
    )
    change = models.IntegerField()
    reason = models.CharField(max_length=200, blank=True)
    quantity_after = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.product.name}: {self.change:+d}"
