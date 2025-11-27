# FusionPBX CDR API

A FastAPI-based REST API for retrieving Call Detail Records (CDRs) from FusionPBX with Keycloak authentication.

## Features

- 🔐 Keycloak JWT authentication
- 📊 CDR retrieval with time period filtering
- 🗄️ PostgreSQL database integration
- 📚 Auto-generated API documentation
- 🏗️ Follows FastAPI best practices

## API Endpoints

### Authentication
All endpoints require Keycloak JWT token in the Authorization header:
```
Authorization: Bearer <your-jwt-token>
```

### Endpoints

#### GET /v1/me
Returns authenticated user information.

**Response:**
```json
{
  "sub": "user123",
  "sip_domain": "example.com",
  "aud": "your-api-identifier",
  "exp": 1640995200
}
```

#### GET /v1/cdr
Retrieves call detail records for the authenticated user's domain.

**Query Parameters:**
- `period` (optional): Time period filter
  - `today` - Today's records
  - `yesterday` - Yesterday's records
  - `last_7_days` - Last 7 days
  - `last_30_days` - Last 30 days
  - `this_week` - Current week
  - `this_month` - Current month
  - `this_year` - Current year
- `start_date` (optional): Custom start date (ISO format)
- `end_date` (optional): Custom end date (ISO format)

**Response:**
```json
{
  "cdrs": [
    {
      "xml_cdr_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "domain_name": "example.com",
      "caller_id_number": "+1234567890",
      "destination_number": "+0987654321",
      "start_stamp": "2024-01-01T10:00:00Z",
      "duration": 300.0,
      "billsec": 300.0,
      "hangup_cause": "NORMAL_CLEARING",
      "recording": "http://localhost:3000/v1/recording/example.com/archive/2024/Jan/01/file.mp3"
    }
  ],
  "total": 1,
  "period": "today"
}
```

#### GET /v1/cdr_compat
Retrieves call detail records in legacy-compatible format for the authenticated user's domain. This endpoint provides a simplified, flat structure suitable for legacy integrations.

**Query Parameters:**
- `period` (optional): Time period filter (same as `/v1/cdr`)
  - `today`, `yesterday`, `last_7_days`, `last_30_days`, `this_week`, `this_month`, `this_year`
- `start_date` (optional): Custom start date (ISO format)
- `end_date` (optional): Custom end date (ISO format)

**Response:**
```json
[
  {
    "date": "01/01/2024 10:00:00",
    "type": "inbound",
    "origin": "+1234567890",
    "destination": "+0987654321",
    "duration": "00:05:00",
    "cost": "R$ 0.00",
    "status": "NORMAL_CLEARING",
    "audio": "http://localhost:3000/v1/recording/example.com/archive/2024/Jan/01/file.mp3"
  }
]
```

#### GET /v1/recording/{file_path:path}
Retrieves audio recording files from the filesystem. This endpoint does not require authentication but includes path traversal protection to ensure files can only be accessed within the configured recording base path.

**Path Parameters:**
- `file_path` (path): Relative path to the recording file from the base recording path
  - Example: `example.com/archive/2025/Nov/24/file.mp3`
  - Full URL: `/v1/recording/example.com/archive/2025/Nov/24/file.mp3`

**Response:**
- Returns the audio file with appropriate `Content-Type` header
- Supported formats: `.wav`, `.mp3`, `.ogg`, `.m4a`, `.flac`
- Default media type: `audio/mpeg` for unknown extensions

**Security:**
- Path traversal protection ensures files can only be accessed within the base recording path
- Returns `403 Forbidden` if the requested path is outside the base directory
- Returns `404 Not Found` if the file doesn't exist

**Example:**
```bash
curl -X GET "http://localhost:3000/v1/recording/example.com/archive/2024/Jan/01/recording.mp3" \
  -H "Accept: audio/mpeg" \
  --output recording.mp3
```

## Examples

### Getting an Access Token and Calling the API

> **Note**: For production use, we recommend [Machine-to-Machine (M2M) Authentication](#machine-to-machine-m2m-authentication) using Client Credentials Grant. The password grant flow shown below is primarily for testing purposes.

#### Password Grant (Testing Only)

1. **Get an access token from Keycloak:**

```bash
# Replace {REALM} and {CLIENT_ID} with your actual Keycloak realm and client ID
curl -X POST "https://sso.example.com/realms/{REALM}/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id={CLIENT_ID}" \
  -d "username=test_user" \
  -d "password=test_pass"
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJ...",
  "expires_in": 300,
  "refresh_expires_in": 1800,
  "token_type": "Bearer",
  ...
}
```

2. **Use the access token to call the API:**

```bash
# Extract the access_token from the response above and use it
curl -X GET "http://localhost:3000/v1/me" \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJ..."
```

**Or in a single command (using jq to extract the token):**

```bash
# Get token and call API in one command
TOKEN=$(curl -s -X POST "https://sso.example.com/realms/{REALM}/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id={CLIENT_ID}" \
  -d "client_secret={CLIENT_SECRET}"
  -d "username=test_user" \
  -d "password=test_pass" | jq -r '.access_token')

curl -X GET "http://localhost:3000/v1/me" \
  -H "Authorization: Bearer $TOKEN"
```

## Machine-to-Machine (M2M) Authentication

> **Recommended for Production**: M2M authentication is the recommended approach for production deployments, automated systems, and integrations.

This API supports machine-to-machine authentication using Keycloak's Client Credentials Grant flow with long-lived tokens (10 years). This is ideal for automated systems, monitoring tools, and applications running on remote machines without user interaction.

### Architecture: Single Application, Multiple Keycloak Clients

**One shared application instance serves all customers. Each customer gets their own Keycloak client for authentication with their unique `sip_domain`.**

#### How It Works

1. **Single Application Deployment**: One application instance validates tokens from all customers
2. **Per-Customer Keycloak Clients**: Each customer has a dedicated Keycloak client with:
   - Unique `client_id` and `client_secret`
   - Service account with `sip_domain` attribute matching their domain
   - Long-lived tokens (10 years = 315,360,000 seconds)
3. **Token-Based Isolation**: Application extracts `sip_domain` from each token and filters data accordingly

#### Flow Diagram

```
Customer A Machine → Keycloak (Client A) → Token with sip_domain: "customer-a.example.com"
                                              ↓
                                    Single Application Instance
                                              ↓
                                    Filters CDRs by sip_domain
                                              ↓
                                    Returns only customer-a.example.com CDRs

Customer B Machine → Keycloak (Client B) → Token with sip_domain: "customer-b.example.com"
                                              ↓
                                    Same Application Instance
                                              ↓
                                    Filters CDRs by sip_domain
                                              ↓
                                    Returns only customer-b.example.com CDRs
```

#### Benefits

- ✅ **Single Deployment**: One application instance for all customers
- ✅ **Perfect Isolation**: Each customer has independent credentials
- ✅ **Easy Revocation**: Disable/delete client to revoke specific customer access
- ✅ **Security**: Compromised credentials only affect one customer
- ✅ **Scalable**: Easy to add new customers (just create new Keycloak client)
- ✅ **Clear Audit Trail**: Each client ID maps directly to a customer
- ✅ **Automatic Data Filtering**: Existing code automatically filters by `sip_domain` from token

### Keycloak Configuration for M2M Authentication

#### Realm-Level Configuration (One-Time Setup)

1. **Configure Realm Token Lifetimes**:
   - Go to Realm Settings → Tokens
   - Set "Access Token Lifespan" to `315360000` seconds (10 years)
   - Note: This is the default; individual clients can override

#### Per-Customer Configuration (Repeat for Each Customer)

For each customer, create a dedicated Keycloak client following these steps:

##### Step 1: Create M2M Client for Customer

1. Go to Clients → Create
2. Configure basic settings:
   - **Client ID**: `customer-{name}-m2m` (e.g., `customer-acme-m2m`)
   - **Client Protocol**: `openid-connect`
   - **Access Type**: `confidential`
   - Click "Save"

3. Enable Service Account:
   - In the client settings, find "Service Accounts Enabled"
   - Toggle to **ON**
   - This automatically creates a service account user for this client

4. Enable Client Credentials Grant:
   - Go to "Settings" tab
   - In "Valid Grant Types", ensure "Client credentials" is enabled
   - If not visible, it's enabled by default for confidential clients

5. Generate/Configure Client Secret:
   - Go to "Credentials" tab
   - Copy the "Client Secret" (you'll provide this to the customer)
   - Or generate a new one if needed

##### Step 2: Configure Token Lifetime for This Client

1. Go to "Advanced Settings" tab (or "Settings" → scroll to Advanced)
2. Set "Access Token Lifespan" to `315360000` seconds (10 years)
3. Click "Save"

##### Step 3: Add `sip_domain` Claim to Service Account

**Option A: Using User Attributes (Recommended - More Flexible)**

a. **Add Attribute to Service Account User**:
   - Go to Clients → [Customer's Client] → "Service Account Roles" tab
   - Click the "Service Account User" link at the bottom
   - Go to "Attributes" tab
   - Click "Add"
   - Key: `sip_domain`
   - Value: `customer.example.com` (the customer's actual SIP domain)
   - Click "Add", then "Save"

b. **Create User Attribute Protocol Mapper**:
   - Go back to Clients → [Customer's Client] → "Mappers" tab
   - Click "Create"
   - Select "By configuration" → "User Attribute"
   - Configure:
     - Name: `sip_domain`
     - User Attribute: `sip_domain`
     - Token Claim Name: `sip_domain`
     - Claim JSON Type: `String`
     - Add to access token: `ON`
     - Add to ID token: `OFF`
   - Click "Save"

**Option B: Using Hardcoded Claim (Simpler, but less flexible)**

- Go to Clients → [Customer's Client] → "Mappers" tab
- Click "Create" → "By configuration" → "Hardcoded claim"
- Configure:
  - Name: `sip_domain`
  - Token Claim Name: `sip_domain`
  - Claim value: `customer.example.com` (hardcoded)
  - Claim JSON Type: `String`
  - Add to access token: `ON`
- Click "Save"

##### Step 4: Provide Credentials to Customer

Provide the customer with:
- **Client ID**: `customer-{name}-m2m`
- **Client Secret**: The secret from the Credentials tab
- **Token Endpoint**: `https://{keycloak-server}/realms/{realm}/protocol/openid-connect/token`
- **API Endpoint**: `https://api.example.com/v1/*`

### M2M Authentication Examples

#### Getting a Token (Client Credentials Grant)

```bash
curl -X POST "https://sso.example.com/realms/{REALM}/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=customer-acme-m2m" \
  -d "client_secret={CLIENT_SECRET}"
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICJ...",
  "expires_in": 315360000,
  "token_type": "Bearer",
  "scope": "profile email"
}
```

#### Using the Token with API

```bash
# Get token first
TOKEN=$(curl -s -X POST "https://sso.example.com/realms/{REALM}/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=customer-acme-m2m" \
  -d "client_secret={CLIENT_SECRET}" | jq -r '.access_token')

# Use token to call API
curl -X GET "http://localhost:3000/v1/cdr?period=today" \
  -H "Authorization: Bearer $TOKEN"
```

#### Verifying Token Contains sip_domain

You can decode the token at [jwt.io](https://jwt.io) or use a JWT decoder. The token should contain:

```json
{
  "sub": "service-account-customer-acme-m2m",
  "sip_domain": "example.com",
  "aud": "...",
  "exp": 1735689600,
  ...
}
```

#### Python Example (Using the M2M Service Utility)

```python
import asyncio
from app.services.keycloak_m2m import KeycloakM2MService

async def main():
    service = KeycloakM2MService(
        server_url="https://sso.example.com",
        realm="your-realm",
        client_id="customer-acme-m2m",
        client_secret="your-client-secret"
    )
    
    token = await service.get_service_account_token()
    print(f"Token: {token}")

asyncio.run(main())
```

### Adding New Customers

To add a new customer, simply repeat the "Per-Customer Configuration" steps above. **No application changes or restarts are needed** - the application automatically accepts tokens from any valid Keycloak client in the realm.

### Troubleshooting M2M Authentication

#### Token Request Fails

**Problem**: `401 Unauthorized` when requesting token

**Solutions**:
- Verify `client_id` and `client_secret` are correct
- Ensure "Service Accounts Enabled" is ON for the client
- Check that "Client credentials" grant type is enabled
- Verify the realm name is correct in the token endpoint URL

#### Token Valid but API Returns 403

**Problem**: Token is valid but API returns `403 Forbidden: SIP domain attribute not found in token`

**Solutions**:
- Verify the `sip_domain` Protocol Mapper is configured correctly
- Check that the mapper has "Add to access token" set to ON
- Ensure the service account user has the `sip_domain` attribute set (if using User Attribute mapper)
- Decode the token at jwt.io to verify the `sip_domain` claim is present

#### Token Expires Too Quickly

**Problem**: Token expires before the expected 10 years

**Solutions**:
- Verify the client's "Access Token Lifespan" is set to `315360000` seconds
- Check that realm-level token lifespan isn't overriding client settings
- Ensure the token is actually a service account token (not a user token)

#### Multiple Customers See Each Other's Data

**Problem**: One customer can see another customer's CDR data

**Solutions**:
- Verify each customer has a unique `sip_domain` in their token
- Check that the `sip_domain` claim matches the actual domain in the database
- Ensure the application is correctly filtering by `sip_domain` (this should be automatic)

## Setup

### 1. Install Dependencies
```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

### 2. Environment Configuration
Copy the example environment file and configure your settings:
```bash
cp env.example .env
```

Edit `.env` with your configuration:
```env
# Keycloak Configuration
KEYCLOAK_SERVER_URL=https://sso.example.com
KEYCLOAK_REALM=your-realm-name
KEYCLOAK_AUDIENCE=your-client-id-or-resource
KEYCLOAK_ALGORITHMS=RS256

# Database Configuration (FusionPBX)
FUSIONPBX_DB_HOST=localhost
FUSIONPBX_DB_PORT=5432
FUSIONPBX_DB_NAME=fusionpbx
FUSIONPBX_DB_USER=fusionpbx
FUSIONPBX_DB_PASSWORD=your_password
FUSIONPBX_DB_SCHEMA=public

# Application Configuration
APP_DEBUG=False
APP_LOG_LEVEL=INFO
APP_PORT=3001

# CORS Configuration
ALLOWED_ORIGINS=["http://localhost:3000", "https://example.com"]
```

### 3. Keycloak Setup

**For Machine-to-Machine (M2M) authentication** (recommended for production), see the [Machine-to-Machine Authentication](#machine-to-machine-m2m-authentication) section above for detailed configuration steps.

**For user-based authentication (password grant - testing only)**, follow these steps:
1. Create a Keycloak client in your realm
2. Configure JWT settings
3. Add custom claims for `sip_domain` attribute:
   - Create a **User Attribute Protocol Mapper** on the client (or client scope)
   - Mapper name: `sip_domain`
   - User Attribute: `sip_domain`
   - Token Claim Name: `sip_domain`
   - Claim JSON Type: `String`
   - Add to access token: `ON`
4. Set up API permissions
5. Enable "Direct Access Grants" flow for password grant testing

### 4. Run the Application

#### Option A: Using Docker Compose (Recommended)

##### Prerequisites

- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher (or Docker Compose V2 plugin)
- **Access to FusionPBX database**: The API needs network access to your FusionPBX PostgreSQL database
- **Recordings directory**: Access to FusionPBX call recordings directory (if using recordings feature)

##### Step 1: Configure Environment Variables

1. **Copy the example environment file:**
   ```bash
   cp env.example .env
   ```

2. **Edit `.env` with your configuration:**
   ```env
   # Keycloak Configuration
   KEYCLOAK_SERVER_URL=https://sso.example.com
   KEYCLOAK_REALM=your-realm-name
   KEYCLOAK_AUDIENCE=your-client-id-or-resource
   KEYCLOAK_ALGORITHMS=RS256

   # Database Configuration (FusionPBX)
   # For external database, use the hostname/IP of your FusionPBX server
   FUSIONPBX_DB_HOST=your-fusionpbx-server-ip
   FUSIONPBX_DB_PORT=5432
   FUSIONPBX_DB_NAME=fusionpbx
   FUSIONPBX_DB_USER=fusionpbx
   FUSIONPBX_DB_PASSWORD=your_database_password
   FUSIONPBX_DB_SCHEMA=public

   # Application Configuration
   APP_DEBUG=False
   APP_LOG_LEVEL=INFO
   APP_PORT=3001
   # Optional: Set explicit server URI for recording URLs (auto-detected if not set)
   # APP_SERVER_URI=http://your-domain.com
   APP_RECORDING_PATH=/var/lib/freeswitch/recordings
   FUSIONPBX_RECORDING_PATH=/var/lib/freeswitch/recordings

   # CORS Configuration
   ALLOWED_ORIGINS=["http://localhost:3000", "https://example.com"]
   ```

   **Important Notes:**
   - `FUSIONPBX_DB_HOST`: Use the IP address or hostname of your FusionPBX server. If running on the same host, use `host.docker.internal` (Docker Desktop) or the host's IP address.
   - `FUSIONPBX_DB_PASSWORD`: Use the actual database password from your FusionPBX installation.
   - `APP_SERVER_URI`: Optional. If not set, the API will auto-detect from request headers. Set this if you're behind a reverse proxy or need specific URLs in responses.

##### Step 2: Configure Recordings Volume

The Docker Compose setup uses a named volume by default. For production, you'll want to mount your actual FusionPBX recordings directory.

**Option A: Bind Mount (Recommended for Production)**

Edit `docker-compose.yml` and replace the recordings volume section:

```yaml
services:
  api:
    volumes:
      # Mount your FusionPBX recordings directory
      - /path/to/fusionpbx/recordings:/var/lib/freeswitch/recordings:ro
```

**Option B: Named Volume (Default - for testing)**

The default configuration uses a named volume. This is fine for testing but won't contain your actual recordings:

```yaml
volumes:
  recordings:
    driver: local
```

**Security Note:** The recordings volume is mounted as read-only (`:ro`) for security. The API only needs to read recording files, not write them.

##### Step 3: Database Network Access

If your FusionPBX database is on a different host, ensure:

1. **PostgreSQL is accessible from Docker network:**
   - Check PostgreSQL `postgresql.conf`: `listen_addresses = '*'` or specific IP
   - Check `pg_hba.conf`: Allow connections from Docker network IP range (typically `172.x.x.x/16`)

2. **Firewall rules:**
   - Allow connections from Docker host to FusionPBX database port (default: 5432)

3. **For same-host database:**
   - Use `host.docker.internal` as `FUSIONPBX_DB_HOST` (Docker Desktop)
   - Or use the host's actual IP address
   - Or use `network_mode: "host"` in docker-compose.yml (Linux only, less secure)

##### Step 4: Build and Start the Stack

1. **Build the Docker image:**
   ```bash
   docker-compose build
   ```

2. **Start the services:**
   ```bash
   docker-compose up -d
   ```

   This will:
   - Build the API service image
   - Pull the Caddy reverse proxy image
   - Start both services in detached mode
   - Create necessary networks and volumes

3. **Verify services are running:**
   ```bash
   docker-compose ps
   ```

   You should see both `fusionpbx-cdr-api` and `fusionpbx-cdr-caddy` services with status "Up".

##### Step 5: View Logs

**View all logs:**
```bash
docker-compose logs -f
```

**View specific service logs:**
```bash
# API service logs
docker-compose logs -f api

# Caddy proxy logs
docker-compose logs -f caddy
```

**View last 100 lines:**
```bash
docker-compose logs --tail=100 api
```

##### Step 6: Access the Application

Once running, the application is available at:
- **API Base URL**: http://localhost:3000
- **Swagger UI**: http://localhost:3000/docs
- **ReDoc**: http://localhost:3000/redoc
- **Health Check**: http://localhost:3000/ (returns API information)

##### Step 7: Stop and Cleanup

**Stop services (keeps containers):**
```bash
docker-compose stop
```

**Stop and remove containers:**
```bash
docker-compose down
```

**Stop, remove containers, and volumes:**
```bash
docker-compose down -v
```

**Stop, remove containers, volumes, and images:**
```bash
docker-compose down -v --rmi all
```

##### Architecture Overview

The Docker Compose setup consists of two services:

1. **API Service** (`fusionpbx-cdr-api`):
   - Built from the project's Dockerfile
   - Runs FastAPI application on port 3001 (internal)
   - Not exposed directly to host (only accessible via Caddy)
   - Includes health checks
   - Mounts recordings directory (read-only)

2. **Caddy Service** (`fusionpbx-cdr-caddy`):
   - Official Caddy 2 Alpine image
   - Reverse proxy listening on host port 3000
   - Proxies all requests to API service
   - Handles SSL/TLS termination (if configured)
   - Preserves request headers for proper forwarding

**Network Architecture:**
```
Internet → Host:3000 (Caddy) → Docker Network → API:3001
```

**Benefits:**
- API service is not directly exposed (security)
- Easy SSL/TLS configuration via Caddy
- Request header preservation
- Health checks for both services
- Automatic restart on failure

##### Port Configuration

- **Caddy Proxy Port**: Configured in `docker-compose.yml` ports section (default: `3000:3000`)
  - Change host port: `"8080:3000"` to use port 8080 on host
- **API Internal Port**: Configured via `APP_PORT` environment variable (default: 3001)
  - Only accessible within Docker network
  - Do not expose this port to host for security

##### Health Checks

Both services include health checks:

- **API Service**: Checks `http://localhost:3001/` every 30 seconds
- **Caddy Service**: Checks `http://localhost:3000/` every 30 seconds

If a service fails its health check, Docker will restart it automatically.

##### Updating the Application

1. **Pull latest code:**
   ```bash
   git pull
   ```

2. **Rebuild and restart:**
   ```bash
   docker-compose up -d --build
   ```

   Or rebuild specific service:
   ```bash
   docker-compose up -d --build api
   ```

##### Troubleshooting

**Service won't start:**
```bash
# Check logs for errors
docker-compose logs api

# Check if port is already in use
netstat -tulpn | grep 3000
```

**Database connection errors:**
- Verify `FUSIONPBX_DB_HOST` is correct and reachable
- Check PostgreSQL is listening on the expected port
- Verify firewall rules allow connections
- Test connection from Docker host: `psql -h <host> -U <user> -d <database>`

**Recordings not found:**
- Verify recordings volume is mounted correctly
- Check `APP_RECORDING_PATH` matches the mount point in container
- Verify file permissions on host recordings directory
- Check API logs for path resolution issues

**CORS errors:**
- Update `ALLOWED_ORIGINS` in `.env` to include your frontend domain
- Restart services after changing environment variables

**View service status:**
```bash
# Check service status
docker-compose ps

# Check resource usage
docker stats

# Inspect service configuration
docker-compose config
```

#### Option B: Local Development

```bash
# Using uv
uv run python run.py

# Or directly with uvicorn
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 3001
```

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:3000/docs (Docker) or http://localhost:3001/docs (local)
- ReDoc: http://localhost:3000/redoc (Docker) or http://localhost:3001/redoc (local)

## Project Structure

```
fusionpbx-cdr-api/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── auth.py
│   │       │   ├── me.py
│   │       │   ├── cdr.py
│   │       │   └── recording.py
│   │       └── api.py
│   ├── core/
│   │   ├── config.py
│   │   └── security.py
│   ├── database/
│   │   └── session.py
│   ├── models/
│   │   └── cdr.py
│   ├── schemas/
│   │   ├── user.py
│   │   └── cdr.py
│   ├── services/
│   │   ├── cdr_service.py
│   │   └── keycloak_m2m.py
│   └── main.py
├── pyproject.toml
├── uv.lock
├── env.example
└── README.md
```

## Development

### Code Style
This project follows PEP 8 and FastAPI best practices:
- Type hints throughout
- Pydantic models for validation
- Dependency injection
- Proper error handling
- Comprehensive documentation

### Testing
```bash
# Run tests (when implemented)
uv run pytest

# Run with coverage
uv run pytest --cov=app

# Run linting
uv run black .
uv run isort .
uv run flake8 .
uv run mypy .
```

## License

MIT License
