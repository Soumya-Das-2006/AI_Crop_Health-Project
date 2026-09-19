from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from .models import Category, Order, Product, OrderItem, OrderEvent


def _cart(request):
    return request.session.get('marketplace_cart', {})


def catalog(request, category=None):
    products = Product.objects.filter(is_active=True).select_related('category')
    query = request.GET.get('q', '').strip()
    selected_category = category or request.GET.get('category', '')
    
    if selected_category:
        products = products.filter(category__slug=selected_category)
    if query:
        products = products.filter(name__icontains=query)
        
    return render(request, 'marketplace/catalog.html', {
        'products': products,
        'categories': Category.objects.filter(is_active=True),
        'selected_category': selected_category,
        'query': query,
        'cart_count': sum(_cart(request).values()),
    })


def product_detail(request, slug):
    product = get_object_or_404(Product.objects.select_related('category').prefetch_related('images'), slug=slug, is_active=True)
    return render(request, 'marketplace/product_detail.html', {
        'product': product,
        'cart_count': sum(_cart(request).values()),
    })


def add_to_cart(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    if request.method == 'POST':
        try:
            quantity = max(1, int(request.POST.get('quantity', 1)))
        except (TypeError, ValueError):
            quantity = 1
            
        quantity = min(quantity, product.stock)
        if quantity:
            cart = _cart(request)
            cart[slug] = min(product.stock, int(cart.get(slug, 0)) + quantity)
            request.session['marketplace_cart'] = cart
            request.session.modified = True
            messages.success(request, f'{product.name} added to your cart.')
            if request.POST.get('buy_now'):
                return redirect('marketplace:checkout')
        else:
            messages.error(request, 'This product is currently out of stock.')
    return redirect('marketplace:cart')


def update_cart(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    if request.method == 'POST':
        try:
            quantity = max(0, int(request.POST.get('quantity', 0)))
        except (TypeError, ValueError):
            quantity = 0
            
        cart = _cart(request)
        if quantity and product.stock:
            cart[slug] = min(quantity, product.stock)
        else:
            cart.pop(slug, None)
        request.session['marketplace_cart'] = cart
        request.session.modified = True
    return redirect('marketplace:cart')


def remove_from_cart(request, slug):
    cart_data = _cart(request)
    if request.method == 'POST':
        cart_data.pop(slug, None)
        request.session['marketplace_cart'] = cart_data
        request.session.modified = True
    return redirect('marketplace:cart')


def cart(request):
    cart_data = _cart(request)
    products = Product.objects.filter(slug__in=cart_data, is_active=True).select_related('category')
    lines = []
    item_subtotal = Decimal('0')
    discount_total = Decimal('0')
    
    for product in products:
        quantity = min(int(cart_data.get(product.slug, 0)), product.stock)
        line_price = product.price * quantity
        line_mrp = product.mrp * quantity
        
        lines.append({
            'product': product,
            'quantity': quantity,
            'unit_price': product.price,
            'line_total': line_price
        })
        item_subtotal += line_mrp
        discount_total += (line_mrp - line_price)
        
    grand_total = item_subtotal - discount_total
    
    return render(request, 'marketplace/cart.html', {
        'lines': lines,
        'item_subtotal': item_subtotal,
        'discount': discount_total,
        'grand_total': grand_total,
        'cart_count': sum(cart_data.values()),
    })


@login_required
def checkout(request):
    cart_data = _cart(request)
    if not cart_data:
        messages.info(request, 'Your cart is empty.')
        return redirect('marketplace:catalog')

    products = Product.objects.filter(slug__in=cart_data, is_active=True)
    items = []
    item_subtotal = Decimal('0')
    discount_total = Decimal('0')
    
    for product in products:
        quantity = min(int(cart_data.get(product.slug, 0)), product.stock)
        line_price = product.price * quantity
        line_mrp = product.mrp * quantity
        
        items.append({
            'product': product, 
            'quantity': quantity, 
            'line_total': line_price
        })
        item_subtotal += line_mrp
        discount_total += (line_mrp - line_price)
        
    shipping_cost = Decimal('50.00') if (item_subtotal - discount_total) < 500 else Decimal('0')
    tax = Decimal('0')
    grand_total = item_subtotal - discount_total + shipping_cost + tax

    if request.method == 'POST':
        name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        area = request.POST.get('area', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        pincode = request.POST.get('pincode', '').strip()
        payment_method = request.POST.get('payment_method', 'COD')
        
        if payment_method not in dict(Order.PAYMENT_METHOD_CHOICES).keys():
            messages.error(request, 'Invalid payment method.')
            return redirect('marketplace:checkout')
            
        if payment_method == 'ONLINE':
            messages.error(request, 'Online payment is currently unavailable. Please choose Cash on Delivery.')
            return redirect('marketplace:checkout')

        if not all((name, phone, address, city, state, pincode)):
            messages.error(request, 'Please complete all required delivery address fields.')
        else:
            try:
                with transaction.atomic():
                    # 1. Lock products
                    fresh_products = {
                        p.pk: p for p in Product.objects.select_for_update().filter(
                            pk__in=[item['product'].pk for item in items], is_active=True
                        )
                    }
                    
                    # 2. Check inventory
                    if any(line['quantity'] > fresh_products.get(line['product'].pk, Product(stock=0)).stock for line in items):
                        messages.error(request, 'A product quantity changed or went out of stock. Please review your cart.')
                        return redirect('marketplace:cart')
                        
                    # 3. Create Order
                    order = Order.objects.create(
                        customer=request.user,
                        customer_name=name,
                        phone=phone,
                        address=address,
                        area=area,
                        city=city,
                        state=state,
                        pincode=pincode,
                        payment_method=payment_method,
                        payment_status='PENDING',
                        status='PLACED',
                        item_subtotal=item_subtotal,
                        discount=discount_total,
                        tax=tax,
                        shipping=shipping_cost,
                        grand_total=grand_total
                    )
                    
                    # 4. Create OrderItems & deduct stock
                    for line in items:
                        product = fresh_products[line['product'].pk]
                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            product_name=product.name,
                            sku=product.sku,
                            quantity=line['quantity'],
                            unit_price=product.price,
                            line_total=line['line_total']
                        )
                        product.stock -= line['quantity']
                        product.save(update_fields=['stock'])
                        
                    # 5. Create OrderEvent
                    OrderEvent.objects.create(
                        order=order,
                        status='PLACED',
                        title='Order Placed',
                        description=f'Order received successfully via {payment_method}.'
                    )
                    
                # End Transaction
                request.session['marketplace_cart'] = {}
                messages.success(request, f'Order placed successfully! Your order number is {order.order_number}.')
                return redirect('marketplace:order_detail', order_id=order.pk)
                
            except Exception as e:
                messages.error(request, f'There was an error processing your order: {str(e)}')
                return redirect('marketplace:checkout')

    return render(request, 'marketplace/checkout.html', {
        'lines': items, 
        'item_subtotal': item_subtotal,
        'discount': discount_total,
        'shipping': shipping_cost,
        'tax': tax,
        'grand_total': grand_total,
        'cart_count': sum(cart_data.values()),
    })


@login_required
def my_orders(request):
    orders = Order.objects.filter(customer=request.user).prefetch_related('items')
    return render(request, 'marketplace/orders.html', {'orders': orders})


@login_required
def order_detail(request, order_id):
    qs = Order.objects.prefetch_related('items', 'events')
    if not request.user.is_staff:
        qs = qs.filter(customer=request.user)
        
    order = get_object_or_404(qs, pk=order_id)
    return render(request, 'marketplace/order_detail.html', {'order': order})
