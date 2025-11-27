# Keycloak Realm Import Instructions

This guide explains how to import the `example-m2m` realm into Keycloak for machine-to-machine authentication.

## Realm Configuration

The realm export file (`keycloak-realm-m2m.json`) contains a minimal realm configuration with:
- Realm name: `example-m2m`
- Access Token Lifespan: 315,360,000 seconds (10 years)
- Access Token Lifespan for Implicit Flow: 315,360,000 seconds (10 years)
- SSL required for external connections
- User registration disabled (M2M only)

## Import Methods

### Method 1: Using Keycloak Admin Console (Recommended)

1. **Log in to Keycloak Admin Console**
   - Navigate to your Keycloak admin interface (e.g., `https://sso.example.com/admin`)
   - Log in with admin credentials

2. **Import the Realm**
   - Click on the realm dropdown (top-left, typically shows "master")
   - Select "Create Realm" or click the "+" button
   - Click "Select file" or "Import" button
   - Upload `keycloak-realm-m2m.json`
   - Click "Create" or "Import"

3. **Verify Realm Settings**
   - Navigate to Realm Settings → Tokens
   - Verify "Access Token Lifespan" is set to `315360000` seconds
   - Verify "Access Token Lifespan For Implicit Flow" is set to `315360000` seconds

### Method 2: Using Keycloak Admin CLI

```bash
# Using kcadm.sh
kcadm.sh config credentials --server https://sso.example.com --realm master --user admin

# Import realm
kcadm.sh create realms -f keycloak-realm-m2m.json
```

### Method 3: Using REST API

```bash
# Get admin access token
TOKEN=$(curl -X POST "https://sso.example.com/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin" \
  -d "password=admin-password" \
  -d "grant_type=password" \
  -d "client_id=admin-cli" | jq -r '.access_token')

# Import realm
curl -X POST "https://sso.example.com/admin/realms" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d @keycloak-realm-m2m.json
```

## Post-Import Configuration

After importing the realm, you need to:

### 1. Create M2M Clients for Each Customer

For each customer, create a client following the steps in the main [README.md](README.md#step-1-create-m2m-client-for-customer):

1. Go to Clients → Create
2. Set Client ID: `customer-{name}-m2m`
3. Set Access Type: `confidential`
4. Enable "Service Accounts Enabled"
5. Set Access Token Lifespan: `315360000` seconds
6. Add `sip_domain` claim via Protocol Mappers
7. Generate and save the Client Secret

### 2. Configure Protocol Mappers

For each client, add the `sip_domain` claim:
- Option A: User Attribute Mapper (recommended)
- Option B: Hardcoded Claim Mapper

See [README.md](README.md#step-3-add-sip_domain-claim-to-service-account) for detailed instructions.

## Minimal Realm vs. Full Export

**Note**: This is a minimal realm configuration that creates the realm with the essential M2M settings. A full realm export would include:
- All authentication flows
- Client scopes
- Default roles
- Authentication configs

However, Keycloak will automatically add the default built-in configurations when you create a minimal realm like this. You can then configure clients and other settings as needed.

## Alternative: Export from Existing Realm

If you prefer a full realm export:

1. Create a realm manually in Keycloak with the desired settings
2. Configure the token lifespans and other settings
3. Export it via:
   - Admin Console: Realm Settings → Export tab → "Partial Export" or "Full Export"
   - CLI: `kcadm.sh get realms/example-m2m -F export`
   - REST API: `GET /admin/realms/example-m2m`

## Troubleshooting

### Realm Already Exists

If the realm already exists:
- Delete it first: Admin Console → Select realm → Delete
- Or use `kcadm.sh delete realms/example-m2m`
- Then import again

### Import Fails with Validation Error

- Ensure the JSON is valid (no syntax errors)
- Check that all required fields are present
- Verify Keycloak version compatibility

### Token Lifespan Not Applied

- After import, manually verify in Realm Settings → Tokens
- If needed, update via Admin Console or CLI
- Token lifespan can be overridden at the client level

## Security Considerations

- This realm is configured for M2M authentication only
- User registration is disabled
- Consider enabling brute force protection for production
- Review and adjust SSL requirements based on your infrastructure
- Regularly audit client secrets and rotate them as needed

## Next Steps

After importing the realm:
1. Create your first M2M client for a customer
2. Test authentication using Client Credentials Grant
3. Verify tokens contain the `sip_domain` claim
4. Configure the application to use this realm

For detailed client configuration instructions, see the [M2M Authentication section](README.md#machine-to-machine-m2m-authentication) in the main README.


