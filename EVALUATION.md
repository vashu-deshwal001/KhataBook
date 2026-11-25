# Khata Book: evaluation notes

## 1. Project ko 30 seconds mein explain karo

"Khata Book ek Django-based web application hai jo shopkeeper ka udhaar register digital banata hai. Shopkeeper customers bana sakta hai aur credit purchases, payments aur balances manage kar sakta hai. Customer login karke sirf apna balance aur transaction history dekh sakta hai. Ismein role-based access, product catalogue, receipt uploads, search, filtering aur CSV reports bhi hain."

## 2. Apne laptop par run kaise karna hai

PowerShell mein ye do commands:

```powershell
cd "C:\Users\vashu\OneDrive\Desktop\account manager"
python manage.py runserver
```

Browser mein **http://127.0.0.1:8000/** kholo. Terminal open rehna chahiye. Stop karne ke liye **Ctrl+C**.

Alternatively project folder mein **start.bat** double-click karo. Ye automatically correct folder se server chalata hai.

- `manage.py` nahi mil raha: terminal wrong folder mein hai. Upar wala `cd` command chalao.
- Port already in use: pehle se server chal raha ho sakta hai. Uska browser URL kholo, ya `python manage.py runserver 8001` use karo aur browser mein port 8001 kholo.
- `No module named django`: README ke installation steps follow karo.
- Fresh clone par pehle dependencies install karo, `migrate` chalao, phir `setup_shopkeeper`. Setup password tumse poochta hai.
- Existing laptop database mein dobara setup command chalane ki zarurat nahi.

## 3. Django MVT architecture

**Model:** Data ka structure aur relationships. `book/models.py`.

**View:** Request process karta hai, permission check karta hai, models se data leta hai aur response deta hai. `book/views.py`.

**Template:** HTML page jo user ko dikhta hai. `templates/`.

Flow:

```text
Browser request → config/urls.py → book/urls.py → view
                                               ↓
                                       form / service / model
                                               ↓
                                         SQLite database
                                               ↓
                                      template → browser
```

Example: `/ledger/new/` request `entry_create` view par jaati hai. GET request form dikhati hai. POST request mein `EntryForm` input validate karta hai; `post_entry` permission aur transaction rules check karke record save karta hai. Phir customer ledger par redirect hota hai.

## 4. Important files

| File | Kaam |
|---|---|
| `manage.py` | Django commands ka entry point |
| `config/settings.py` | Database, installed apps, middleware, timezone aur auth settings |
| `config/urls.py`, `book/urls.py` | URL ko view se connect karna |
| `book/models.py` | Database models aur relationships |
| `book/forms.py` | Form fields, input validation, uploads aur filters |
| `book/services.py` | Amount posting, edit, deletion aur reversal ke rules |
| `book/views.py` | Permissions, CRUD, dashboards, reports aur file responses |
| `book/admin.py` | Django admin ki columns, filters aur permissions |
| `templates/base.html` | Common navigation aur page layout |
| `templates/book/entry_form.html` | Transaction form aur summary layout |
| `static/book.css` | Red theme aur mobile-friendly layout |
| `static/transaction.js` | Browser mein live balance preview |
| `static/upload.js` | Selected receipt ka filename dikhana |
| `book/tests.py` | Automated tests |

## 5. Database models

| Model | Kya store hota hai |
|---|---|
| `User` | Username, hashed password, role aur active status |
| `Customer` | User profile: phone, address, photo aur notes |
| `Category` | Product category |
| `Product` | Name, category, price, image aur active status |
| `LedgerEntry` | Customer, amount, type, date, notes, receipt aur entry creator |
| `AuditLog` | Kisne kaunsa action kab kiya |

- `User → Customer`: **OneToOneField**, ek customer login ka ek profile.
- `Customer → LedgerEntry`: **ForeignKey**, ek customer ki multiple transactions.
- `Category → Product`: **ForeignKey**, ek category mein multiple products.
- Original entry → reversal: **OneToOneField**, ek entry ka maximum ek reversal.

**ORM** Python code ko database queries mein convert karta hai. Example: `Customer.objects.filter(user__is_active=True)` active customers fetch karta hai. **Migrations** model structure ko database tables aur constraints mein apply karti hain.

## 6. Balance kaise calculate hota hai

```text
Balance = sum of signed_amount for that customer's entries
Credit purchase / opening owed → positive
Payment / opening advance → negative
Reversal → original entry ke sign ka opposite
```

Example explanation: Rs 500 purchase aur Rs 200 payment ke baad customer Rs 300 owe karta hai. Negative balance ka matlab customer ka advance credit hai. Ye sirf explanation hai; application mein preloaded dummy records nahi hain.

`DecimalField` money ko decimal precision mein store karta hai. `Sum` se balance calculate hota hai, isliye amount edit/delete hone par balance bhi update hota hai. JavaScript preview convenience ke liye hai; final save aur validation Django backend karta hai.

## 7. Authentication aur authorization

- **Authentication:** User kaun hai? Username/password login se verify hota hai.
- **Authorization:** User kya kar sakta hai? Role aur ownership se decide hota hai.
- `login_required`: Login ke bina protected page nahi milega.
- `shopkeeper_required`: Customer management aur amount changes sirf shopkeeper kar sakta hai.
- Customer queries logged-in user tak restricted hain. Sirf buttons hide nahi kiye; backend bhi access block karta hai.
- Password plain text mein save nahi hota; Django password hashing karta hai.
- Form POST requests par CSRF token check hota hai.
- Receipt download par bhi login aur customer ownership check hota hai.

## 8. CRUD aur extra features

**CRUD = Create, Read, Update, Delete.** Customers aur products par demonstrate karo. Shopkeeper transaction amount bhi edit/delete kar sakta hai.

Customer deletion uska login aur ledger remove karti hai. Used product ko delete karne par archive kiya jaata hai taaki transaction reference safe rahe. Reversed entries ko edit nahi kar sakte. Original entry delete karne par linked reversal bhi remove hota hai.

**Duplicate submission:** Har new transaction ko unique UUID milta hai; same form dobara submit hone par double entry nahi banti.

**File upload:** Images Pillow se verify hoti hain; receipt PDF ya image ho sakti hai; limit 5 MB hai. PDF signature check basic hai, full malware scan nahi.

**Search/filter/sort:** Text search, date/type/customer filters aur allowed sorting fields use hote hain. Pagination ek page par limited records dikhati hai.

**CSV report:** Selected filters ke matching records download hote hain. Customer export mein sirf uske records milte hain.

## 9. Evaluation demonstration order

1. Shopkeeper login aur dashboard dikhao.
2. Evaluation ke liye customer manually create karo; name, username aur password fields explain karo.
3. Credit purchase record karo, phir payment. Resulting balance explain karo.
4. Amount edit karke balance update dikhao.
5. Receipt upload aur protected download dikhao.
6. Search, date/type filters, sorting aur CSV export dikhao.
7. Category/product add karke catalogue aur product CRUD dikhao.
8. Logout karke customer login karo. Customer ka own balance aur read-only history dikhao.
9. Customer session se `/customers/` kholkar access restriction demonstrate karo.
10. Shopkeeper se Django admin kholo: `/admin/`. Customized lists aur filters explain karo.

Ye steps manually evaluation ke time perform karne hain; setup dummy data generate nahi karta.

## 10. Topics covered

| Assignment | Project feature |
|---|---|
| A4 Dynamic information page | Customer profile aur live database balance |
| A5 Catalogue | Product catalogue |
| A6 ORM SQLite | Models, migrations aur SQLite |
| A7 ORM and templates | QuerySets, aggregation aur template inheritance |
| A8 Login and admin | Django authentication aur customized admin |
| A9 Search/filter | Customer name, phone, code, status aur balance filters |
| A10 Search/sort/filter | Ledger aur catalogue filters, sort, pagination |
| A11 Protected CRUD | Login/role-protected customer/product operations |
| A12 Role-based access | Shopkeeper aur customer permissions |
| A13 Upload/images | Customer/product photos aur receipt uploads |

## 11. Common viva questions

**SQLite kyun?** Local single-shop project ke liye lightweight hai, separate database server ki zarurat nahi. Busy production environment mein PostgreSQL configure kar sakte hain.

**GET aur POST mein difference?** GET page/data read karne ke liye. POST form submit karke data create/update/delete karne ke liye. Delete confirmation GET se dikhata hai; actual delete POST par hota hai.

**ModelForm kyun?** Model fields se form banta hai aur Django validation reuse hoti hai.

**Business logic services mein kyun?** Balance rules ek jagah rehte hain; views readable rehte hain aur rules independently test ho sakte hain.

**transaction.atomic kya karta hai?** Related database operations ek unit mein run hoti hain. Failure par partial changes rollback ho jaate hain.

**ForeignKey ka PROTECT?** Referenced record ko accidentally delete hone se rokta hai. Customer delete service pehle dependent ledger explicitly remove karti hai.

**JavaScript off ho toh?** Forms aur core server operations work karte hain. Live preview aur enhanced upload display available nahi honge.

**Testing kaise?** `python manage.py test`. Balance calculations, login, role restrictions, uploads, edit/delete aur duplicate submissions cover kiye hain.

**GitHub par push karne se website live?** Nahi. GitHub repository code store karti hai. Is Django server ko live karne ke liye separate hosting chahiye.

**Limitations?** Single shop, manually entered transactions, no online payment gateway, no inventory counting, no email password reset. Public deployment ke liye HTTPS, login rate limiting, proper server setup aur backups chahiye.
