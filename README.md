# Django Google Sign-In & Paystack Payment API

## Overview
A secure Django backend API that implements Google OAuth 2.0 authentication and Paystack payment processing. This project demonstrates integration with third-party services, proper authentication flows, and transaction management with comprehensive logging.

## Features
- Google OAuth 2.0 authentication with server-side flow
- Paystack payment initialization and verification
- Webhook handling for real-time transaction updates
- Comprehensive logging system
- RESTful API endpoints with proper error handling
- Transaction status tracking and idempotency
- Admin interface for data management
- API documentation with Swagger/OpenAPI

## Tech Stack
- **Backend**: Django 4.2.7, Django REST Framework
- **Database**: SQLite (can be configured for PostgreSQL)
- **Authentication**: Google OAuth 2.0
- **Payment**: Paystack API
- **Documentation**: Swagger/OpenAPI with drf-yasg
- **Environment**: python-dotenv for configuration management

## Prerequisites
- Python 3.8+
- Google Cloud Console account
- Paystack account (test mode available)
- Basic knowledge of Django and REST APIs

## Quick Start

### 1. Clone and Setup
```bash
# Clone the repository
git clone <repository-url>
cd payment_auth_project

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Environment Configuration
Copy the `.env.example` file to `.env`:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```env
# Django Settings
SECRET_KEY=your-django-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Google OAuth 2.0
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8001/api/v1/auth/google/callback

# Paystack
PAYSTACK_SECRET_KEY=sk_test_your_paystack_secret_key
PAYSTACK_PUBLIC_KEY=pk_test_your_paystack_public_key
PAYSTACK_WEBHOOK_SECRET=whsec_your_webhook_secret

# Server
BASE_URL=http://localhost:8001
```

### 3. Google OAuth Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Navigate to "APIs & Services" → "Credentials"
4. Click "Create Credentials" → "OAuth 2.0 Client ID"
5. Configure consent screen if prompted
6. Application type: "Web application"
7. Add authorized redirect URI: `http://localhost:8001/api/v1/auth/google/callback`
8. Copy Client ID and Client Secret to `.env` file

### 4. Paystack Setup
1. Sign up at [Paystack Dashboard](https://dashboard.paystack.com/)
2. Navigate to "Settings" → "API Keys & Webhooks"
3. Get your Test Secret Key and Public Key
4. Configure webhook URL: `http://localhost:8001/api/v1/payments/paystack/webhook`
5. Copy keys and webhook secret to `.env` file

### 5. Database Setup
```bash
# Run migrations
python manage.py makemigrations auth_payment
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser
```

### 6. Run Development Server
```bash
# Run server on port 8001
python manage.py runserver 8001
```

The server will be available at: `http://localhost:8001`

## API Documentation

### Swagger UI
Access interactive API documentation at:
```
http://localhost:8001/swagger/
```

### ReDoc Alternative Documentation
```
http://localhost:8001/redoc/
```

## API Endpoints

### Authentication Endpoints

#### GET /api/v1/auth/google
Initiate Google Sign-In flow
- **Response**: Returns Google OAuth URL
- **Example Response**:
```json
{
  "success": true,
  "message": "Google authentication URL generated",
  "data": {
    "google_auth_url": "https://accounts.google.com/o/oauth2/v2/auth?..."
  }
}
```

#### GET /api/v1/auth/google/callback
Google OAuth callback endpoint
- **Parameters**: `code` (authorization code from Google)
- **Response**: User information and authentication tokens
- **Example Response**:
```json
{
  "success": true,
  "message": "User authentication successful",
  "data": {
    "id": "uuid-here",
    "email": "user@example.com",
    "name": "John Doe",
    "picture": "https://lh3.googleusercontent.com/...",
    "created_at": "2024-01-15T10:30:45Z"
  }
}
```

### Payment Endpoints

#### POST /api/v1/payments/paystack/initiate
Initialize a Paystack payment
- **Request Body**:
```json
{
  "amount": 5000,
  "user_id": "uuid-of-existing-user"
}
```
- **Response**: Payment reference and authorization URL
- **Example Response**:
```json
{
  "success": true,
  "message": "Payment initialized successfully",
  "data": {
    "reference": "TXN_uuid_timestamp",
    "authorization_url": "https://checkout.paystack.com/...",
    "amount": 5000,
    "currency": "NGN"
  }
}
```

#### POST /api/v1/payments/paystack/webhook
Paystack webhook endpoint (called by Paystack)
- **Headers**: `x-paystack-signature` (signature verification)
- **Response**: Confirmation of webhook processing

#### GET /api/v1/payments/{reference}/status
Check transaction status
- **Parameters**: 
  - `reference`: Transaction reference
  - `refresh` (optional): Set to `true` to verify with Paystack
- **Response**: Transaction details and status
- **Example Response**:
```json
{
  "success": true,
  "message": "Transaction status retrieved",
  "data": {
    "id": "uuid-here",
    "reference": "TXN_uuid_timestamp",
    "user": {
      "id": "user-uuid",
      "email": "user@example.com",
      "name": "John Doe"
    },
    "amount": "50.00",
    "status": "success",
    "authorization_url": "https://checkout.paystack.com/...",
    "paid_at": "2024-01-15T10:35:22Z",
    "currency": "NGN",
    "created_at": "2024-01-15T10:30:45Z"
  }
}
```

#### GET /api/v1/payments
List transactions for a user
- **Query Parameters**: `user_id` (required)
- **Response**: List of user's transactions
- **Example Response**:
```json
{
  "success": true,
  "message": "Transactions retrieved successfully",
  "data": {
    "transactions": [
      {
        "id": "uuid-here",
        "reference": "TXN_uuid_timestamp",
        "amount": "50.00",
        "status": "success",
        "created_at": "2024-01-15T10:30:45Z"
      }
    ]
  }
}
```

## Database Models

### User Model
- `id`: UUID primary key
- `google_id`: Google OAuth user ID
- `email`: User email (unique)
- `name`: User's full name
- `picture`: Profile picture URL
- `is_active`: Account status
- `created_at`, `updated_at`: Timestamps

### Transaction Model
- `id`: UUID primary key
- `reference`: Unique transaction reference
- `user`: Foreign key to User
- `amount`: Transaction amount
- `status`: pending/success/failed/abandoned
- `paystack_reference`: Paystack transaction reference
- `authorization_url`: Paystack checkout URL
- `paid_at`: Payment completion timestamp
- `currency`: Transaction currency (default: NGN)
- `metadata`: JSON field for additional data
- `created_at`, `updated_at`: Timestamps

## Testing the API

### 1. Google Authentication Test
```bash
# Get Google auth URL
curl -X GET "http://localhost:8001/api/v1/auth/google"

# After obtaining authorization code from browser redirect
curl -X GET "http://localhost:8001/api/v1/auth/google/callback?code=authorization_code_here"
```

### 2. Payment Flow Test
```bash
# Create a user first (or use existing user ID)
# Initialize payment (5000 Kobo = 50 NGN)
curl -X POST "http://localhost:8001/api/v1/payments/paystack/initiate" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 5000,
    "user_id": "existing-user-uuid-here"
  }'

# Check transaction status
curl -X GET "http://localhost:8001/api/v1/payments/TXN_uuid_timestamp/status"

# Check with refresh
curl -X GET "http://localhost:8001/api/v1/payments/TXN_uuid_timestamp/status?refresh=true"
```

## Admin Interface
Access the Django admin interface at:
```
http://localhost:8001/admin/
```

Use the superuser credentials created during setup to:
- View and manage users
- Monitor transactions
- Check payment statuses

## Logging
The application logs to both console and file (`app.log`):
- **Console**: Real-time development logs
- **File**: Persistent logs for debugging and monitoring

Log levels:
- INFO: Successful operations, user actions
- WARNING: Non-critical issues
- ERROR: Failed operations, exceptions
- DEBUG: Detailed debugging information (when DEBUG=True)

## Error Handling
The API uses standardized error responses:
```json
{
  "success": false,
  "message": "Error description",
  "errors": {
    "field_name": ["Error details"]
  }
}
```

Common HTTP status codes:
- 200: Success
- 201: Resource created
- 400: Bad request (validation errors)
- 401: Unauthorized (authentication failed)
- 402: Payment required (Paystack error)
- 404: Resource not found
- 500: Internal server error

## Security Features

### Implemented
1. **Environment-based configuration**: No hardcoded secrets
2. **Input validation**: All endpoints validate input data
3. **Webhook signature verification**: Paystack webhook authenticity
4. **Idempotent transactions**: Prevent duplicate payments
5. **CORS configuration**: Configured for development
6. **CSRF protection**: Enabled for relevant endpoints
7. **Secure headers**: Django security middleware

### Recommended for Production
1. Use HTTPS for all endpoints
2. Configure proper CORS origins
3. Use PostgreSQL or MySQL instead of SQLite
4. Implement rate limiting
5. Set up monitoring and alerting
6. Regular dependency updates
7. Database backups

## Project Structure
```
payment_auth_project/
├── auth_payment/          # Main application
│   ├── models.py         # Database models
│   ├── views.py          # API views
│   ├── serializers.py    # Request/response serializers
│   ├── utils.py          # Helper functions
│   ├── urls.py           # Application URLs
│   └── admin.py          # Admin configurations
├── payment_auth_project/  # Project configuration
│   ├── settings.py       # Django settings
│   ├── urls.py           # Project URLs
│   └── wsgi.py           # WSGI configuration
├── manage.py             # Django management script
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables (create from .env.example)
├── .env.example          # Example environment configuration
└── README.md             # This file
```

## Troubleshooting

### Common Issues

#### 1. Google OAuth Redirect URI Mismatch
**Error**: `redirect_uri_mismatch`
**Solution**: Ensure the redirect URI in Google Cloud Console exactly matches the one in `.env`

#### 2. Paystack Invalid Key
**Error**: `Invalid key`
**Solution**: Verify Paystack API keys in `.env` and ensure you're using test keys for development

#### 3. Migration Errors
**Error**: `Table already exists` or migration conflicts
**Solution**: 
```bash
# Reset migrations (development only)
python manage.py migrate auth_payment zero
python manage.py migrate
```

#### 4. Port Already in Use
**Error**: `Address already in use`
**Solution**: 
```bash
# Kill process on port 8001
sudo lsof -t -i tcp:8001 | xargs kill -9
# Or use different port
python manage.py runserver 8002
```

#### 5. Module Not Found
**Error**: `ModuleNotFoundError`
**Solution**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Reinstall dependencies
pip install -r requirements.txt
```

## Development

### Running Tests
```bash
# Create test database and run tests
python manage.py test auth_payment
```

### Code Style
The project follows PEP 8 conventions. Use the following tools:
```bash
# Check code style
flake8 .

# Auto-format code
black .
```

### Adding New Features
1. Create migrations for model changes
2. Add serializers for new endpoints
3. Implement views with proper error handling
4. Update URLs configuration
5. Add tests for new functionality
6. Update API documentation

## Deployment Considerations

### Production Settings
Update `settings.py` for production:
```python
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com']
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

### Database
Switch to production database:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'your_db_name',
        'USER': 'your_db_user',
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### Web Server
Recommended production setup:
- **Web Server**: Nginx or Apache
- **WSGI Server**: Gunicorn or uWSGI
- **Process Manager**: Systemd or Supervisor

## Support

### Getting Help
1. Check the troubleshooting section
2. Review API documentation at `/swagger/`
3. Check application logs in `app.log`
4. Verify environment variables are set correctly

### Reporting Issues
When reporting issues, include:
1. Steps to reproduce
2. Expected vs actual behavior
3. Error messages from logs
4. Environment details (OS, Python version, etc.)

## License
This project is for demonstration purposes. Adapt and modify as needed for your requirements.

## Contributing
1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Submit a pull request with description

## Acknowledgements
- [Django](https://www.djangoproject.com/) - Web framework
- [Django REST Framework](https://www.django-rest-framework.org/) - API toolkit
- [Paystack](https://paystack.com/) - Payment processing
- [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2) - Authentication

---

*This project demonstrates backend integration patterns and is suitable for learning and prototyping. For production use, ensure additional security measures and thorough testing.*
