from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import AuditLog, Category, Customer, LedgerEntry, Product, User
from .forms import ProductForm

admin.site.site_header = 'Khata Book · Shop administration'
admin.site.site_title = 'Khata Book'
admin.site.index_title = 'Manage your shop'

@admin.register(User)
class KhataUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('Khata access', {'fields': ('role',)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (('Khata access', {'fields': ('role',)}),)
    list_display = ['username', 'first_name', 'last_name', 'role', 'is_active']
    list_filter = ['role', 'is_active', 'is_staff']
    def has_module_permission(self, request):
        return request.user.is_superuser
    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    def has_add_permission(self, request):
        return request.user.is_superuser
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ['code', 'user', 'phone', 'balance', 'created_at']
    search_fields = ['user__username', 'user__first_name', 'phone']
    list_filter = ['user__is_active']
    readonly_fields = ['user', 'phone', 'address', 'notes', 'photo', 'created_at']
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductForm
    list_display = ['name', 'category', 'price', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'description']

admin.site.register(Category)

@admin.register(LedgerEntry)
class LedgerAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'kind', 'amount', 'signed_amount', 'date', 'created_by']
    search_fields = ['customer__user__username', 'notes']
    list_filter = ['kind', 'date']
    readonly_fields = [f.name for f in LedgerEntry._meta.fields]
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(AuditLog)
class AuditAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'actor', 'action']
    readonly_fields = ['created_at', 'actor', 'action']
    def has_add_permission(self, request):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
