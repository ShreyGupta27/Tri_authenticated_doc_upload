# Document Upload Service

A FastAPI-based document upload service with multi-authentication and Google Cloud Storage integration.

## Features

- **Multi-Authentication**: JWT, API Keys, and Client Certificates
- **Document Validation**: Whitelist-based file format validation (HL7, FHIR, PDF, images, etc.)
- **Cloud Storage**: Google Cloud Storage integration for file persistence
- **Database-Backed Auth**: PostgreSQL for credential management
- **Async/Await**: High-concurrency async request handling

## Quick Start

### Prerequisites
- Python 3.9+
- PostgreSQL
- Google Cloud Storage (optional)

### Installation

1. Clone the repository
```bash
git clone <repo-url>
cd JondaX
```

2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Configure environment
```bash
cp .env.example .env
# Edit .env with your credentials
```

5. Setup database
```bash
python setup_database.py
```

6. Run the server
```bash
python run_server.py
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Upload Document
```
POST /upload
```
Upload a document with authentication.

**Authentication Methods:**
- Bearer token (JWT)
- X-API-Key header
- X-Client-Cert header

**Example:**
```bash
curl -X POST http://localhost:8000/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@document.pdf"
```

### Health Check
```
GET /health
```
Check service and database status.

## Configuration

See [ENVIRONMENT_SETUP.md](ENVIRONMENT_SETUP.md) for detailed configuration instructions.

Key environment variables:
- `JWT_SECRET_KEY` - Secret for JWT validation
- `DATABASE_URL` - PostgreSQL connection string
- `GCS_BUCKET_NAME` - Google Cloud Storage bucket
- `GOOGLE_APPLICATION_CREDENTIALS` - Path to GCS credentials

## Project Structure

```
app/
├── auth/              # Authentication logic
├── storage/           # Cloud storage integration
├── validators/        # File validation
├── main.py           # FastAPI application
├── config.py         # Configuration management
├── database.py       # Database setup
├── exceptions.py     # Error handling
└── models.py         # Data models

tests/                # Test suite
scripts/              # Development utilities
```

## Testing

Run tests with pytest:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=app
```

## Development

Utility scripts are available in the `scripts/` directory:
- `generate_jwt.py` - Generate test JWT tokens
- `add_credentials.py` - Add credentials to database
- `test_api.py` - Test API endpoints

## Security

- Never commit `.env` file (contains real credentials)
- Use strong JWT secrets in production
- Rotate credentials regularly
- Use secrets management for production deployments

## License

Copyright (c) 2026 Shrey Gupta. All rights reserved.

Unauthorized copying, modification, or distribution of this software, via any medium, is strictly prohibited.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.