# Khata Book

A simple digital khata for shopkeepers to keep track of customer balances, credit purchases, and payments. Customers can log in to view their own accounts.

For a walkthrough, viva questions, and demonstration steps, see [EVALUATION.md](EVALUATION.md). On an already configured Windows machine, double-click `start.bat` to launch the app.

## Quick start (Windows PowerShell)

Requires Python 3.11 or later.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py setup_shopkeeper
.\.venv\Scripts\python.exe manage.py runserver
```

Open http://127.0.0.1:8000/ and sign in with username `shopkeeper` and the password you chose during setup. Only this initial account is created; the database starts without customers, products or transactions. Create customer accounts from **Customers → Add customer**. There is no public registration. The setup command refuses to change an existing database or reset existing passwords.

For this workspace, Django is already installed and Pillow is installed in the ignored `.vendor` directory, so `python manage.py runserver` also works. A fresh environment should use the requirements file above.

## Access

Only the shopkeeper can create, edit or delete customer accounts and record, edit or delete transaction amounts. Customers can view their own balance/history and change their password. Deleting a customer removes their login and all their transactions after a confirmation page. Editing or deleting a transaction automatically recalculates the balance; audit events record these actions. Reversed entries cannot be edited; deleting an original entry also removes its linked reversal.

## Features

- Custom user model with shopkeeper and customer roles; secure Django password hashing and session authentication.
- Admin-created customer accounts, protected profile edits, activation/deactivation, password reset and password change.
- Customer photos, product images and downloadable PDF/image receipts, with upload size and image checks.
- Categories and products with create/read/update/delete operations; referenced products are archived instead of deleted.
- Decimal-based ledger, opening amount owed or advance credit, credit purchases, payments and reversals.
- Duplicate transaction submission protection using unique submission IDs.
- Customer dashboard and shopkeeper dashboard, recent activity, outstanding totals and advance balances.
- Search by customer name, phone or code; filter account status and balance; sort customers.
- Transaction text/date/type/customer filters and amount/date sorting, pagination and CSV exports.
- Running balances remain accurate when earlier transactions are hidden by filters.
- Private file views check authentication and record ownership. No public media directory route is configured.
- Customized Django administration, read-only admin ledger and audit records.
- Responsive interface with local CSS, usable without JavaScript. Optional web fonts fall back to system fonts offline.

## Accounting rules

Positive balance = customer owes the shop. Negative balance = customer has advance credit. A purchase increases the balance; a payment decreases it. Opening balances must be the customer's first entry. The shopkeeper can edit an amount or delete a transaction through the application. Changes are recorded in the audit log. Alternatively, reverse an entry with a reason and record a replacement. The Django admin ledger remains read-only. Reversals use today's date and preserve the original date and amount. An entry can be reversed only once; reversals cannot themselves be reversed.

Products are optional references on purchase entries, not a stock or automatic invoice system. The shopkeeper enters the full transaction amount. Reports show **net change for matching entries**, while customer account balances always reflect the whole ledger. “Received today” counts today's payment entries that have not been reversed. Deactivated accounts retain history and cannot sign in.

## Structure

```text
config/                Project settings, URL routing and WSGI entry point
book/models.py         Users, customers, categories, products, ledger, audit log
book/forms.py          Validated forms, uploads and report filters
book/services.py       Transaction posting and reversal rules
book/views.py          Role checks, dashboards, CRUD, reports and private files
book/admin.py          Customized Django admin
book/tests.py          Financial, authorization, upload and workflow tests
book/management/       Initial shopkeeper setup command
book/migrations/       Versioned database schema
templates/             Reusable Django templates and auth/error pages
static/book.css        Responsive application styling
```

This is a modular Django application in one `book` app, keeping related account and ledger logic easy to follow for a student project.

## Assignment coverage and demonstration

| Topic | Implementation | Demonstration |
|---|---|---|
| A4: Dynamic information webpage | Customer profile and dashboard templates; `customer_detail` view | Open a customer account and show their current balance and history |
| A5: Catalogue | `Category`, `Product`, `products` view and catalogue template | Add categories/products and search the catalogue |
| A6: ORM SQLite | Models, migrations and SQLite configuration | Run migrations; inspect records through Django ORM or admin |
| A7: ORM and templates | QuerySets, aggregation, reusable base/partial templates | Explain `Sum`, `Coalesce`, filters, loops and template inheritance |
| A8: Login and admin customization | Custom `User`, Django auth views and `admin.py` | Sign in as shopkeeper, inspect admin columns and filters |
| A9: Search/filter records | `customer_list` | Search name/phone/KH code and filter active/outstanding accounts |
| A10: Search/sort/filter | `LedgerFilterForm`, catalogue filters and pagination | Filter by dates/type/customer; sort amounts; export matching CSV |
| A11: Authentication and protected CRUD | Auth decorators, product CRUD and customer edits | Create/edit/delete an unused product; show customer access is denied |
| A12: Role-based access | `shopkeeper_required`, ownership-scoped queries | Sign in as a customer and attempt another customer's URL |
| A13: Upload and image handling | Image fields, upload validation, `media_file` | Upload a photo, product image and receipt; show private receipt access |

The assignment screenshot truncates A11 after “Protected CRUD O…”. This implementation covers the visible authentication and CRUD requirements. Student/course record examples are adapted to customer/product records; there is no unrelated school module.

## Testing

```powershell
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
```

Tests cover balances, opening advances, reversals, duplicate submissions, role/ownership restrictions, private downloads, invalid uploads, customer creation/deactivation, product deletion/archiving, filtered running balances, CSV isolation/formula escaping, rendered pages, login and CSRF.

## Configuration and deployment

`.env.example` documents environment variables; it is a reference file and is not loaded automatically. Set variables in PowerShell or your hosting platform. Local development defaults to SQLite, India time and debug mode. A random development secret is generated into ignored `.secret-key`.

For production set `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY` to a strong secret and `DJANGO_ALLOWED_HOSTS` to the exact hostnames. HTTPS redirects and secure cookies are enabled when debug is off. Use a production WSGI server and web server, run migrations and `collectstatic`, and serve `staticfiles` publicly. **Do not serve `media` publicly**: keep private file downloads behind Django. Configure your reverse proxy for HTTPS and request-size limits. The application does not include login throttling; add proxy/application rate limiting before public deployment. Email delivery and self-service email password recovery are not configured; the shopkeeper resets customer passwords.

SQLite is suitable for this local, single-shop project. For a busy multi-user production installation, configure PostgreSQL with its driver and repeat concurrency/load tests; the repository does not include a PostgreSQL deployment. Back up both the database and uploaded media regularly. Do not commit real data, credentials or uploads.

The project is built locally; no public hosting has been provisioned.
