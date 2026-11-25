import uuid
from decimal import Decimal
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone


def upload_path(instance, filename):
    from pathlib import Path
    return f'{instance._meta.model_name}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Shopkeeper'
        CUSTOMER = 'customer', 'Customer'
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.CUSTOMER)

    @property
    def is_shopkeeper(self):
        return self.is_superuser or self.role == self.Role.ADMIN


class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name='customer')
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    photo = models.ImageField(upload_to=upload_path, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def code(self):
        return f'KH{self.pk:04d}'

    @property
    def balance(self):
        return self.entries.aggregate(total=Sum('signed_amount'))['total'] or Decimal('0.00')

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.code})'


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    class Meta:
        ordering = ['name']
        verbose_name_plural = 'categories'
    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=120)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    image = models.ImageField(upload_to=upload_path, blank=True)
    is_active = models.BooleanField(default=True)
    class Meta:
        ordering = ['name']
        constraints = [models.CheckConstraint(condition=models.Q(price__gt=0), name='positive_product_price')]
    def __str__(self):
        return self.name


class LedgerEntry(models.Model):
    class Kind(models.TextChoices):
        PURCHASE = 'purchase', 'Credit purchase'
        PAYMENT = 'payment', 'Payment received'
        OPENING = 'opening', 'Opening balance owed'
        ADVANCE = 'advance', 'Opening advance credit'
        REVERSAL = 'reversal', 'Reversal'
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='entries')
    kind = models.CharField(max_length=12, choices=Kind.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    signed_amount = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    date = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)
    product = models.ForeignKey(Product, null=True, blank=True, on_delete=models.PROTECT)
    receipt = models.FileField(upload_to=upload_path, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    reversed_entry = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='reversal')
    submission_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    class Meta:
        ordering = ['date', 'id']
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__gt=0), name='positive_entry_amount'),
            models.UniqueConstraint(fields=['customer'], condition=models.Q(kind__in=['opening', 'advance']), name='one_opening_per_customer'),
        ]
    def __str__(self):
        return f'{self.customer.code} • {self.get_kind_display()} • {self.amount}'


class AuditLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    action = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        ordering = ['-created_at']
