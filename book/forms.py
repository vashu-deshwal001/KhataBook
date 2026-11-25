from pathlib import Path
from decimal import Decimal
from PIL import Image, UnidentifiedImageError
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from .models import Category, Customer, LedgerEntry, Product, User
from .widgets import ReceiptUpload


def validate_upload(file, images_only=False):
    if not file or not hasattr(file, 'content_type'):
        return file
    if file.size > 5 * 1024 * 1024:
        raise forms.ValidationError('Upload a file smaller than 5 MB.')
    extension = Path(file.name).suffix.lower()
    if extension == '.pdf' and not images_only:
        if file.read(5) != b'%PDF-':
            raise forms.ValidationError('Upload a valid PDF receipt.')
        file.seek(0)
        return file
    if extension not in {'.jpg', '.jpeg', '.png', '.webp'}:
        raise forms.ValidationError('Use a JPG, PNG or WebP image' + ('.' if images_only else ', or a PDF.'))
    try:
        image = Image.open(file)
        if image.width * image.height > 20_000_000:
            raise forms.ValidationError('Image must be smaller than 20 megapixels.')
        image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise forms.ValidationError('This image could not be read.')
    finally:
        file.seek(0)
    return file


class CustomerCreateForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, label='Customer name')
    class Meta:
        model = User
        fields = ['first_name', 'username']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].help_text = ''
        self.fields['password1'].help_text = 'Use at least 8 characters; avoid common or all-number passwords.'
        self.fields['password2'].label = 'Confirm password'
        self.fields['password2'].help_text = ''


class CustomerEditForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    is_active = forms.BooleanField(required=False, label='Account is active')
    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'email', 'phone', 'address', 'notes', 'photo', 'is_active']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in ['first_name', 'last_name', 'email', 'is_active']:
            self.fields[field].initial = getattr(self.instance.user, field)
    def clean_photo(self):
        return validate_upload(self.cleaned_data.get('photo'), True)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'category', 'description', 'price', 'image', 'is_active']
    def clean_image(self):
        return validate_upload(self.cleaned_data.get('image'), True)


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']


class EntryForm(forms.ModelForm):
    submission_id = forms.UUIDField(widget=forms.HiddenInput)
    class Meta:
        model = LedgerEntry
        fields = ['customer', 'kind', 'amount', 'date', 'product', 'notes', 'receipt']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'}), 'receipt': ReceiptUpload()}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['kind'].choices = [c for c in LedgerEntry.Kind.choices if c[0] != 'reversal']
        self.fields['customer'].queryset = Customer.objects.filter(user__is_active=True).select_related('user')
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
        self.fields['product'].help_text = 'Optional reference. Enter the total amount manually.'
    def clean_date(self):
        date = self.cleaned_data['date']
        if date > timezone.localdate():
            raise forms.ValidationError('The transaction date cannot be in the future.')
        return date
    def clean_receipt(self):
        return validate_upload(self.cleaned_data.get('receipt'))


class EntryEditForm(forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    notes = forms.CharField(required=False, widget=forms.Textarea)


class LedgerFilterForm(forms.Form):
    q = forms.CharField(required=False, label='Search notes or customer')
    customer = forms.ModelChoiceField(queryset=Customer.objects.select_related('user'), required=False)
    kind = forms.ChoiceField(choices=[('', 'All types')] + LedgerEntry.Kind.choices, required=False)
    start = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    sort = forms.ChoiceField(required=False, choices=[('-date', 'Newest first'), ('date', 'Oldest first'), ('amount', 'Amount: low to high'), ('-amount', 'Amount: high to low')])
    def clean(self):
        data = super().clean()
        if data.get('start') and data.get('end') and data['start'] > data['end']:
            raise forms.ValidationError('Start date must be before end date.')
        return data
