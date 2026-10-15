# Inventory REST API

A stock-tracking API built with Django and Django REST Framework. Each user registers, gets a token, and manages their own products: they can adjust stock up or down, and every change is recorded in a history.

## Features
- Register and log in with a token (session login also works for the browsable API)
- Products with name, SKU, price in KES, quantity, and a reorder level
- Each user only sees and changes their own products
- Stock changes only through a dedicated endpoint, which refuses a zero change or one that would make stock negative, and records every movement
- Stock history per product, newest first
- Low-stock filter, search by name or SKU, ordering, and pagination (10 per page)
- SKUs are trimmed and uppercased, and unique per user
- Browsable API in the browser, plus the Django admin
- 26 automated tests

## Tech Stack
- Python 3
- Django
- Django REST Framework (token authentication)
- SQLite (default database)

## Getting Started

```bash
git clone https://github.com/CodeNova55/inventory-rest-api.git
cd inventory-rest-api
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open http://127.0.0.1:8000/api-auth/login/ to log in, then http://127.0.0.1:8000/api/products/ to use the browsable API.

## Using the API

Register and call the API from PowerShell:

```powershell
$reg = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/register/ -ContentType "application/json" -Body '{"username":"demo","password":"Str0ng-pass-99"}'
$headers = @{ Authorization = "Token $($reg.token)" }

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/products/ -Headers $headers -ContentType "application/json" -Body '{"name":"Unga 2kg","sku":"unga-2kg","price":"220.00","initial_quantity":20,"reorder_level":5}'

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/products/1/adjust-stock/ -Headers $headers -ContentType "application/json" -Body '{"change":-17,"reason":"Sold"}'

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/products/?low_stock=true" -Headers $headers
```

Or with curl:

```bash
curl -H "Authorization: Token YOUR_TOKEN" http://127.0.0.1:8000/api/products/
```

## Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /api/auth/register/` | create an account and get a token |
| `POST /api/auth/token/` | get a token for an existing account |
| `GET /api/products/` | list your products (`?search=`, `?ordering=`, `?low_stock=true`, `?page=`) |
| `POST /api/products/` | create a product (optional `initial_quantity`) |
| `GET/PATCH/DELETE /api/products/{id}/` | read, update, or delete a product |
| `POST /api/products/{id}/adjust-stock/` | add (positive) or remove (negative) stock |
| `GET /api/products/{id}/history/` | stock movements for a product |

Quantity cannot be set directly on a product. It only changes through `adjust-stock`, so the history is always complete.

## Running Tests

```bash
python manage.py test
```

## Project Structure

```
config/                    project settings and root URLs
inventory/models.py        Product and StockMovement, with the stock adjustment logic
inventory/serializers.py   validation and registration
inventory/views.py         products API, stock adjustment, history, registration
inventory/urls.py          API routes
inventory/tests.py         automated tests
```

## Limitations
- Development settings only: the secret key and debug flag are not set up for production yet, so it is not ready to host as is
- SQLite is used. Row locking during stock changes has no effect on SQLite, so use Postgres in production
- Tokens do not expire, and there is no rate limiting or password reset
- Single currency (KES) and no multiple warehouses

## Git Workflow
- One feature branch per piece of work
- Feature branch -> PR into `develop`
- `develop` -> PR into `main` (after approval)
- No direct pushes to `develop` or `main`

## Roadmap
- Production settings and deployment
- Token expiry and rate limiting
- Multiple locations and low-stock email alerts
- CSV import and export
