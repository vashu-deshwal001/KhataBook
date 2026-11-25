import csv
import io
import tempfile
import uuid
from datetime import timedelta
from decimal import Decimal
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from .forms import ProductForm, validate_upload
from .models import Category, Customer, LedgerEntry, Product
from .services import post_entry, reverse_entry


class KhataTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser('owner', password='Owner-test-2846', role='admin')
        cls.alice = User.objects.create_user('alice', password='Customer-test-2846', first_name='Alice')
        cls.bob = User.objects.create_user('bob', password='Customer-test-2846', first_name='Bob')
        cls.customer = Customer.objects.create(user=cls.alice)
        cls.other = Customer.objects.create(user=cls.bob)
        cls.category = Category.objects.create(name='Groceries')
        cls.product = Product.objects.create(name='Rice', category=cls.category, price=Decimal('120'))

    def entry(self, **kwargs):
        data = dict(actor=self.admin, customer=self.customer, kind='purchase', amount=Decimal('100'), date=timezone.localdate(), submission_id=uuid.uuid4())
        data.update(kwargs)
        return post_entry(**data)[0]

    def test_balances_and_reversal(self):
        self.entry(kind='opening', amount=Decimal('500'))
        purchase = self.entry(amount=Decimal('300'))
        self.entry(kind='payment', amount=Decimal('600'))
        self.assertEqual(self.customer.balance, Decimal('200'))
        reverse_entry(purchase, self.admin, 'Wrong amount')
        self.assertEqual(self.customer.balance, Decimal('-100'))
        with self.assertRaises(ValidationError):
            reverse_entry(purchase, self.admin, 'Again')

    def test_duplicate_submission_is_idempotent(self):
        token = uuid.uuid4()
        first = self.entry(submission_id=token)
        second = self.entry(submission_id=token)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(self.customer.balance, Decimal('100'))

    def test_opening_must_be_first_and_amount_positive(self):
        self.entry()
        with self.assertRaises(ValidationError):
            self.entry(kind='opening')
        with self.assertRaises(ValidationError):
            self.entry(amount=Decimal('-1'))
        with self.assertRaises(ValidationError):
            self.entry(date=timezone.localdate() + timedelta(days=1))

    def test_opening_advance_and_reverse_payment(self):
        self.entry(kind='advance', amount=Decimal('100'))
        payment = self.entry(kind='payment', amount=Decimal('50'))
        self.assertEqual(self.customer.balance, Decimal('-150'))
        reverse_entry(payment, self.admin, 'Payment entered twice')
        self.assertEqual(self.customer.balance, Decimal('-100'))

    def test_customer_cannot_mutate_or_view_others(self):
        self.client.force_login(self.alice)
        for name in ['customers', 'customer_create', 'entry_create', 'product_create', 'category_create', 'ledger']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
            self.assertEqual(self.client.post(reverse(name), {}).status_code, 403)
        self.assertEqual(self.client.get(reverse('customer_detail', args=[self.other.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('customer_password', args=[self.other.pk]), {}).status_code, 403)
        with self.assertRaises(ValidationError):
            self.entry(actor=self.alice)

    def test_csv_scoped_and_formula_safe(self):
        self.entry(notes='=HYPERLINK("bad")')
        self.entry(customer=self.other, notes='BOB PRIVATE')
        self.client.force_login(self.alice)
        result = self.client.get(reverse('export_ledger'), {'customer': self.other.pk})
        text = result.content.decode('utf-8-sig')
        self.assertNotIn('BOB PRIVATE', text)
        rows = list(csv.reader(io.StringIO(text)))
        self.assertTrue(rows[1][-1].startswith("'="))

    def test_invalid_filters_are_handled(self):
        self.client.force_login(self.admin)
        for query in [{'start': 'oops'}, {'start': '2026-10-10', 'end': '2026-01-01'}, {'sort': 'bad'}, {'customer': 'abc'}]:
            self.assertEqual(self.client.get(reverse('ledger'), query).status_code, 200)
            self.assertEqual(self.client.get(reverse('export_ledger'), query).status_code, 400)

    def test_all_pages_render(self):
        entry = self.entry()
        self.client.force_login(self.admin)
        urls = [reverse(name) for name in ['dashboard', 'customers', 'customer_create', 'ledger', 'entry_create', 'products', 'product_create', 'category_create', 'password_change']]
        urls += [reverse('customer_detail', args=[self.customer.pk]), reverse('customer_edit', args=[self.customer.pk]), reverse('customer_password', args=[self.customer.pk]), reverse('entry_reverse', args=[entry.pk]), reverse('product_edit', args=[self.product.pk]), reverse('product_delete', args=[self.product.pk]), reverse('admin:index')]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.client.get(reverse('products')).status_code, 200)

    def test_http_customer_creation_and_edit(self):
        self.client.force_login(self.admin)
        result = self.client.post(reverse('customer_create'), {'username': 'newcustomer', 'first_name': 'New', 'password1': 'Strong-demo-2846', 'password2': 'Strong-demo-2846', 'role': 'admin', 'is_superuser': 'on'})
        self.assertEqual(result.status_code, 302)
        customer = Customer.objects.get(user__username='newcustomer')
        self.assertFalse(customer.user.is_shopkeeper)
        result = self.client.post(reverse('customer_edit', args=[customer.pk]), {'first_name': 'Updated', 'phone': '111'})
        self.assertEqual(result.status_code, 302)
        customer.user.refresh_from_db()
        self.assertFalse(customer.user.is_active)
        self.assertFalse(self.client.login(username='newcustomer', password='Strong-demo-2846'))

    def test_http_entry_and_duplicate(self):
        self.client.force_login(self.admin)
        data = {'customer': self.customer.pk, 'kind': 'purchase', 'amount': '89.50', 'date': timezone.localdate().isoformat(), 'submission_id': str(uuid.uuid4())}
        for _ in range(2):
            self.assertEqual(self.client.post(reverse('entry_create'), data).status_code, 302)
        self.assertEqual(self.customer.balance, Decimal('89.50'))

    def test_product_crud_and_protected_history(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse('product_create'), {'name': 'Tea', 'category': self.category.pk, 'price': '45.50', 'is_active': 'on'}).status_code, 302)
        tea = Product.objects.get(name='Tea')
        self.assertEqual(self.client.post(reverse('product_delete', args=[tea.pk])).status_code, 302)
        self.assertFalse(Product.objects.filter(pk=tea.pk).exists())
        self.entry(product=self.product)
        self.client.post(reverse('product_delete', args=[self.product.pk]))
        self.product.refresh_from_db()
        self.assertFalse(self.product.is_active)

    def test_receipt_download_is_private(self):
        with tempfile.TemporaryDirectory() as temp, override_settings(MEDIA_ROOT=temp):
            entry = self.entry(receipt=SimpleUploadedFile('receipt.pdf', b'%PDF-1.4\nDemo', content_type='application/pdf'))
            url = reverse('media_file', args=['receipt', entry.pk])
            self.assertEqual(self.client.get(url).status_code, 302)
            self.client.force_login(self.bob)
            self.assertEqual(self.client.get(url).status_code, 404)
            self.client.force_login(self.alice)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn('attachment', response['Content-Disposition'])
            response.close()

    def test_upload_validation(self):
        for name, data in [('bad.html', b'<script>'), ('bad.pdf', b'not a pdf'), ('bad.png', b'not an image')]:
            with self.assertRaises(ValidationError):
                validate_upload(SimpleUploadedFile(name, data))
        with self.assertRaises(ValidationError):
            validate_upload(SimpleUploadedFile('big.pdf', b'%PDF-' + b'a' * (5 * 1024 * 1024)))
        buffer = io.BytesIO()
        Image.new('RGB', (10, 10)).save(buffer, format='PNG')
        form = ProductForm({'name': 'Photo product', 'category': self.category.pk, 'price': '12'}, {'image': SimpleUploadedFile('image.png', buffer.getvalue(), content_type='image/png')})
        self.assertTrue(form.is_valid(), form.errors)

    def test_login_and_csrf(self):
        from django.test import Client
        self.assertEqual(self.client.get('/').status_code, 302)
        self.assertEqual(self.client.get(reverse('login')).status_code, 200)
        self.assertTrue(self.client.login(username='owner', password='Owner-test-2846'))
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.admin)
        self.assertEqual(protected.post(reverse('product_delete', args=[self.product.pk])).status_code, 403)

    def test_running_balance_respects_hidden_earlier_entries(self):
        self.entry(kind='opening', amount=Decimal('500'), date=timezone.localdate() - timedelta(days=5))
        self.entry(kind='payment', amount=Decimal('100'))
        self.client.force_login(self.alice)
        response = self.client.get('/', {'start': timezone.localdate().isoformat()})
        self.assertEqual(list(response.context['page_obj'])[0].running_balance, Decimal('400'))

    def test_only_shopkeeper_can_edit_or_delete(self):
        entry = self.entry()
        self.client.force_login(self.alice)
        urls = [reverse('entry_edit', args=[entry.pk]), reverse('entry_delete', args=[entry.pk]),
                reverse('customer_edit', args=[self.customer.pk]), reverse('customer_delete', args=[self.customer.pk])]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {'amount': '999'}).status_code, 403)
        self.assertEqual(self.customer.balance, Decimal('100'))
        self.assertTrue(Customer.objects.filter(pk=self.customer.pk).exists())

    def test_edit_delete_amount_and_audit(self):
        from .models import AuditLog
        self.entry(amount=Decimal('500'))
        entry = self.entry(kind='payment', amount=Decimal('100'))
        self.client.force_login(self.admin)
        edit_url = reverse('entry_edit', args=[entry.pk])
        self.assertEqual(self.client.get(edit_url).status_code, 200)
        self.assertEqual(self.client.post(edit_url, {'amount': '200', 'notes': 'Corrected'}).status_code, 302)
        self.assertEqual(self.customer.balance, Decimal('300'))
        self.assertEqual(self.client.post(edit_url, {'amount': '-1'}).status_code, 200)
        self.assertEqual(self.customer.balance, Decimal('300'))
        url = reverse('entry_delete', args=[entry.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(LedgerEntry.objects.filter(pk=entry.pk).exists())
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(self.customer.balance, Decimal('500'))
        self.assertTrue(AuditLog.objects.filter(action__startswith='Edited entry').exists())
        self.assertTrue(AuditLog.objects.filter(action__startswith='Deleted entry').exists())

    def test_delete_customer_including_reversed_history(self):
        entry = self.entry()
        reverse_entry(entry, self.admin, 'Mistake')
        self.entry(customer=self.other, amount=Decimal('50'))
        self.client.force_login(self.admin)
        url = reverse('customer_delete', args=[self.customer.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(Customer.objects.filter(pk=self.customer.pk).exists())
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(Customer.objects.filter(pk=self.customer.pk).exists())
        self.assertFalse(get_user_model().objects.filter(pk=self.alice.pk).exists())
        self.assertEqual(self.other.balance, Decimal('50'))
        self.assertFalse(self.client.login(username='alice', password='Customer-test-2846'))

    def test_reversed_entry_edit_blocked_delete_removes_pair(self):
        entry = self.entry()
        reverse_entry(entry, self.admin, 'Mistake')
        self.client.force_login(self.admin)
        response = self.client.post(reverse('entry_edit', args=[entry.pk]), {'amount': '999'})
        self.assertContains(response, 'Reversed entries cannot be edited')
        self.assertEqual(self.customer.balance, 0)
        self.client.post(reverse('entry_delete', args=[entry.pk]))
        self.assertEqual(self.customer.entries.count(), 0)


class SetupTests(TestCase):
    def test_setup_creates_only_one_shopkeeper_without_dummy_data(self):
        from django.core.management import call_command, CommandError
        from unittest.mock import patch
        with patch('book.management.commands.setup_shopkeeper.getpass', return_value='Setup-test-2846'):
            call_command('setup_shopkeeper', stdout=io.StringIO())
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertTrue(self.client.login(username='shopkeeper', password='Setup-test-2846'))
        self.assertEqual(Customer.objects.count(), 0)
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(LedgerEntry.objects.count(), 0)
        with self.assertRaises(CommandError):
            call_command('setup_shopkeeper', stdout=io.StringIO())
