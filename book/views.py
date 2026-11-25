import csv
import mimetypes
import uuid
from decimal import Decimal
from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from .forms import CategoryForm, CustomerCreateForm, CustomerEditForm, EntryForm, EntryEditForm, LedgerFilterForm, ProductForm
from .models import AuditLog, Category, Customer, LedgerEntry, Product
from .services import post_entry, reverse_entry, edit_amount, delete_entry, delete_customer


def shopkeeper_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_shopkeeper:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def customers_with_balances():
    return Customer.objects.select_related('user').annotate(
        outstanding=Coalesce(Sum('entries__signed_amount'), Value(Decimal('0.00')), output_field=DecimalField()))


def own_customer(request, pk=None):
    qs = Customer.objects.select_related('user')
    if not request.user.is_shopkeeper:
        qs = qs.filter(user=request.user)
    return get_object_or_404(qs, pk=pk) if pk else get_object_or_404(qs, user=request.user)


def page(request, qs, size=20):
    return Paginator(qs, size).get_page(request.GET.get('page'))


@login_required
def dashboard(request):
    if not request.user.is_shopkeeper:
        return customer_detail(request)
    customers = customers_with_balances()
    entries = LedgerEntry.objects.select_related('customer__user', 'created_by')
    balances = list(customers)
    context = {
        'customer_count': len(balances),
        'total_owed': sum((c.outstanding for c in balances if c.outstanding > 0), Decimal('0')),
        'total_advance': -sum((c.outstanding for c in balances if c.outstanding < 0), Decimal('0')),
        'received_today': entries.filter(kind='payment', date=timezone.localdate(), reversal__isnull=True).aggregate(total=Sum('amount'))['total'] or 0,
        'recent': entries.order_by('-created_at')[:8],
        'top_customers': sorted(balances, key=lambda c: c.outstanding, reverse=True)[:5],
    }
    return render(request, 'book/dashboard.html', context)


@shopkeeper_required
def customer_list(request):
    qs = customers_with_balances()
    q = request.GET.get('q', '').strip()
    if q:
        search = Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) | Q(user__username__icontains=q) | Q(phone__icontains=q)
        code = q.upper().removeprefix('KH')
        if code.isdigit():
            search |= Q(pk=int(code))
        qs = qs.filter(search)
    status = request.GET.get('status')
    if status in {'active', 'inactive'}:
        qs = qs.filter(user__is_active=status == 'active')
    balance = request.GET.get('balance')
    if balance == 'owed':
        qs = qs.filter(outstanding__gt=0)
    elif balance == 'advance':
        qs = qs.filter(outstanding__lt=0)
    elif balance == 'settled':
        qs = qs.filter(outstanding=0)
    order = request.GET.get('sort', 'user__first_name')
    if order not in {'user__first_name', '-outstanding', 'outstanding', '-created_at'}:
        order = 'user__first_name'
    return render(request, 'book/customers.html', {'page_obj': page(request, qs.order_by(order, 'pk'))})


@shopkeeper_required
def customer_create(request):
    form = CustomerCreateForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
            customer = Customer.objects.create(user=user)
            AuditLog.objects.create(actor=request.user, action=f'Created customer {customer.code}')
        messages.success(request, 'Customer account created. Share the login details privately.')
        return redirect('customer_detail', pk=customer.pk)
    return render(request, 'book/form.html', {'form': form, 'title': 'Create a customer', 'subtitle': 'Enter a name and login details.', 'submit_label': 'Create customer'})


@shopkeeper_required
def customer_edit(request, pk):
    customer = own_customer(request, pk)
    form = CustomerEditForm(request.POST or None, request.FILES or None, instance=customer)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            form.save()
            for field in ['first_name', 'last_name', 'email', 'is_active']:
                setattr(customer.user, field, form.cleaned_data[field])
            customer.user.save()
            AuditLog.objects.create(actor=request.user, action=f'Updated customer {customer.code}')
        messages.success(request, 'Customer details saved.')
        return redirect('customer_detail', pk=pk)
    return render(request, 'book/form.html', {'form': form, 'title': f'Edit {customer.code}'})


@shopkeeper_required
def customer_password(request, pk):
    customer = own_customer(request, pk)
    form = SetPasswordForm(customer.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        AuditLog.objects.create(actor=request.user, action=f'Reset password for {customer.code}')
        messages.success(request, 'Customer password reset.')
        return redirect('customer_detail', pk=pk)
    return render(request, 'book/form.html', {'form': form, 'title': f'Reset password · {customer.code}'})


@shopkeeper_required
def customer_delete(request, pk):
    customer = own_customer(request, pk)
    if request.method == 'POST':
        delete_customer(customer, request.user)
        messages.success(request, 'Customer account and its transactions deleted.')
        return redirect('customers')
    return render(request, 'book/confirm.html', {
        'title': 'Delete customer account', 'cancel_url': reverse('customer_detail', args=[customer.pk]),
        'description': f'Delete {customer}? This permanently removes their login and all {customer.entries.count()} transactions.'})


@shopkeeper_required
def entry_edit(request, pk):
    entry = get_object_or_404(LedgerEntry, pk=pk)
    form = EntryEditForm(request.POST or None, initial={'amount': entry.amount, 'notes': entry.notes})
    if request.method == 'POST' and form.is_valid():
        try:
            edit_amount(entry, request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
        else:
            messages.success(request, 'Amount updated. The customer balance has been recalculated.')
            return redirect('customer_detail', pk=entry.customer_id)
    return render(request, 'book/form.html', {'form': form, 'title': f'Edit transaction #{entry.pk}', 'subtitle': f'{entry.customer} · {entry.get_kind_display()}'})


@shopkeeper_required
def entry_delete(request, pk):
    entry = get_object_or_404(LedgerEntry, pk=pk)
    if request.method == 'POST':
        customer_id = entry.customer_id
        try:
            delete_entry(entry, request.user)
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        else:
            messages.success(request, 'Transaction deleted. The customer balance has been recalculated.')
        return redirect('customer_detail', pk=customer_id)
    return render(request, 'book/confirm.html', {'title': 'Delete transaction', 'cancel_url': reverse('customer_detail', args=[entry.customer_id]),
        'description': f'Permanently delete transaction #{entry.pk} ({entry.get_kind_display()}, ₹{entry.amount})? Any linked reversal will also be removed.'})


def filtered_entries(request, qs, fixed_customer=None):
    form = LedgerFilterForm(request.GET)
    if fixed_customer or not request.user.is_shopkeeper:
        form.fields.pop('customer')
    if form.is_valid():
        data = form.cleaned_data
        if data.get('q'):
            q = data['q']
            qs = qs.filter(Q(notes__icontains=q) | Q(customer__user__first_name__icontains=q) | Q(customer__user__username__icontains=q))
        if data.get('customer'):
            qs = qs.filter(customer=data['customer'])
        if data.get('kind'):
            qs = qs.filter(kind=data['kind'])
        if data.get('start'):
            qs = qs.filter(date__gte=data['start'])
        if data.get('end'):
            qs = qs.filter(date__lte=data['end'])
        order = data.get('sort') or '-date'
        qs = qs.order_by(order, '-id' if order.startswith('-') else 'id')
    else:
        qs = qs.none()
    return form, qs


@login_required
def customer_detail(request, pk=None):
    customer = own_customer(request, pk)
    all_entries = customer.entries.select_related('created_by', 'reversal', 'reversed_entry', 'product')
    running = Decimal('0')
    balances = {}
    for entry in all_entries.order_by('date', 'id'):
        running += entry.signed_amount
        balances[entry.pk] = running
    form, qs = filtered_entries(request, all_entries, customer)
    current_page = page(request, qs)
    for entry in current_page:
        entry.running_balance = balances[entry.pk]
    return render(request, 'book/customer_detail.html', {'customer': customer, 'balance': running, 'form': form, 'page_obj': current_page})


@shopkeeper_required
def ledger(request):
    qs = LedgerEntry.objects.select_related('customer__user', 'created_by', 'reversal')
    form, qs = filtered_entries(request, qs)
    return render(request, 'book/ledger.html', {'form': form, 'page_obj': page(request, qs), 'net_change': qs.aggregate(total=Sum('signed_amount'))['total'] or 0})


@shopkeeper_required
def entry_create(request):
    initial = {'submission_id': uuid.uuid4()}
    if request.GET.get('customer', '').isdigit():
        initial['customer'] = request.GET['customer']
    form = EntryForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            entry, created = post_entry(actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, '; '.join(exc.messages))
        except IntegrityError:
            form.add_error(None, 'This transaction conflicts with an existing entry. Refresh and check the ledger.')
        else:
            messages.success(request, 'Transaction recorded.' if created else 'This transaction was already recorded; no duplicate was added.')
            return redirect('customer_detail', pk=entry.customer_id)
    customer_balances = {
        str(customer.pk): {
            'name': customer.user.get_full_name() or customer.user.username,
            'code': customer.code,
            'balance': str(customer.outstanding),
        }
        for customer in customers_with_balances().filter(user__is_active=True)
    }
    return render(request, 'book/entry_form.html', {'form': form, 'customer_balances': customer_balances})


@shopkeeper_required
def entry_reverse(request, pk):
    entry = get_object_or_404(LedgerEntry, pk=pk)
    from django import forms
    class ReasonForm(forms.Form):
        reason = forms.CharField(max_length=500, widget=forms.Textarea)
    form = ReasonForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            reverse_entry(entry, request.user, form.cleaned_data['reason'])
        except (ValidationError, IntegrityError) as exc:
            form.add_error(None, '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'This entry has already been reversed.')
        else:
            messages.success(request, 'Reversal recorded. The original entry remains in the ledger.')
            return redirect('customer_detail', pk=entry.customer_id)
    return render(request, 'book/form.html', {'form': form, 'title': f'Reverse transaction #{entry.pk}', 'subtitle': f'{entry.get_kind_display()} · ₹{entry.amount} · {entry.customer}'})


@login_required
def products(request):
    qs = Product.objects.select_related('category')
    if not request.user.is_shopkeeper:
        qs = qs.filter(is_active=True)
    if request.GET.get('q'):
        qs = qs.filter(Q(name__icontains=request.GET['q']) | Q(description__icontains=request.GET['q']))
    category = request.GET.get('category', '')
    if category.isdigit():
        qs = qs.filter(category_id=category)
    order = request.GET.get('sort', 'name')
    if order not in ['name', 'price', '-price']:
        order = 'name'
    return render(request, 'book/products.html', {'page_obj': page(request, qs.order_by(order, 'pk'), 12), 'categories': Category.objects.all()})


@shopkeeper_required
def product_edit(request, pk=None):
    product = get_object_or_404(Product, pk=pk) if pk else None
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            saved = form.save()
            AuditLog.objects.create(actor=request.user, action=f'Saved product #{saved.pk}: {saved.name}')
        messages.success(request, 'Product saved.')
        return redirect('products')
    return render(request, 'book/form.html', {'form': form, 'title': 'Edit product' if pk else 'Add a product', 'category_hint': True})


@shopkeeper_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        with transaction.atomic():
            if product.ledgerentry_set.exists():
                product.is_active = False
                product.save(update_fields=['is_active'])
                messages.info(request, 'This product has ledger history and was archived instead.')
            else:
                product.delete()
                messages.success(request, 'Product deleted.')
            AuditLog.objects.create(actor=request.user, action=f'Removed product: {product.name}')
        return redirect('products')
    return render(request, 'book/confirm.html', {'title': 'Remove product', 'description': f'Remove {product.name}? Products with ledger history will be archived.'})


@shopkeeper_required
def category_create(request):
    form = CategoryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Category created. You can now use it for products.')
        return redirect('product_create')
    return render(request, 'book/form.html', {'form': form, 'title': 'Add a category'})


def safe_csv(value):
    value = str(value)
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@')) else value


@login_required
def export_ledger(request):
    qs = LedgerEntry.objects.select_related('customer__user')
    if not request.user.is_shopkeeper:
        qs = qs.filter(customer=own_customer(request))
    form, qs = filtered_entries(request, qs)
    if not form.is_valid():
        return HttpResponse('Invalid filters. Check the start/end dates and filter values.', status=400)
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="khata-ledger.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow(['Entry', 'Date', 'Customer code', 'Customer', 'Type', 'Amount INR', 'Balance change INR', 'Notes'])
    for entry in qs:
        writer.writerow([entry.pk, entry.date, entry.customer.code, safe_csv(entry.customer.user.get_full_name() or entry.customer.user.username), entry.get_kind_display(), entry.amount, entry.signed_amount, safe_csv(entry.notes)])
    return response


@login_required
def media_file(request, kind, pk):
    if kind == 'receipt':
        qs = LedgerEntry.objects.all()
        if not request.user.is_shopkeeper:
            qs = qs.filter(customer__user=request.user)
        field = get_object_or_404(qs, pk=pk).receipt
    elif kind == 'photo':
        field = own_customer(request, pk).photo
    elif kind == 'product':
        qs = Product.objects.all()
        if not request.user.is_shopkeeper:
            qs = qs.filter(is_active=True)
        field = get_object_or_404(qs, pk=pk).image
    else:
        raise Http404
    if not field:
        raise Http404
    try:
        response = FileResponse(field.open('rb'), as_attachment=kind == 'receipt', filename=field.name.rsplit('/', 1)[-1], content_type=mimetypes.guess_type(field.name)[0] or 'application/octet-stream')
    except FileNotFoundError:
        raise Http404
    response['Cache-Control'] = 'private, no-store'
    return response
