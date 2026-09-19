from django.contrib import admin
from .models import Category, Product, ProductImage, Order, OrderItem, OrderEvent

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'display_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('display_order', 'is_active')

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'price', 'mrp', 'stock', 'is_featured', 'is_active')
    list_filter = ('category', 'is_featured', 'is_active')
    search_fields = ('name', 'sku', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('price', 'mrp', 'stock', 'is_featured', 'is_active')
    inlines = [ProductImageInline]

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'sku', 'unit_price', 'quantity', 'line_total')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

class OrderEventInline(admin.TabularInline):
    model = OrderEvent
    extra = 1
    readonly_fields = ('created_at', 'created_by')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'customer_name', 'phone', 'grand_total', 'status', 'payment_status', 'created_at')
    list_filter = ('status', 'payment_status', 'payment_method', 'created_at')
    search_fields = ('order_number', 'customer_name', 'phone', 'address', 'tracking_number')
    readonly_fields = ('order_number', 'created_at', 'item_subtotal', 'discount', 'tax', 'shipping', 'grand_total')
    inlines = [OrderItemInline, OrderEventInline]

    fieldsets = (
        ('Order Info', {
            'fields': ('order_number', 'status', 'created_at')
        }),
        ('Customer Details', {
            'fields': ('customer', 'customer_name', 'phone', 'address', 'area', 'city', 'state', 'pincode', 'country')
        }),
        ('Payment', {
            'fields': ('payment_method', 'payment_status', 'transaction_id')
        }),
        ('Totals', {
            'fields': ('item_subtotal', 'discount', 'tax', 'shipping', 'grand_total')
        }),
        ('Fulfilment', {
            'fields': ('delivery_method', 'tracking_number', 'courier')
        }),
    )

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in formset.deleted_objects:
            obj.delete()
        for instance in instances:
            if isinstance(instance, OrderEvent) and not instance.created_by_id:
                instance.created_by = request.user
            instance.save()
        formset.save_m2m()
