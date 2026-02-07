# Why Devhost?

Devhost eliminates "port salad" and brings production-like routing to your local development environment.

## The Problem: Port Salad

Without Devhost, your development environment looks like this:
- Frontend: `http://localhost:3000`
- API: `http://localhost:8080`
- Auth: `http://localhost:5001`
- Admin: `http://localhost:4200`

This approach has several drawbacks:
1. **Cognitive Load**: Remembering which port goes to which service.
2. **OAuth Friction**: OAuth providers (Google, GitHub, etc.) require exact redirect URLs. If you change a port, you must update your OAuth app settings.
3. **Cookie Leakage**: Cookies set on `localhost:3000` are sent to `localhost:8080`, leading to subtle authentication bugs.
4. **CORS Complexity**: Browsers don't always trigger CORS preflights between different ports on `localhost`, hiding potential production issues.
5. **Mobile Testing**: It's hard to hit `localhost:3000` from a physical mobile device on the same network.

## The Solution: Memorable Subdomains

Devhost gives your apps semantic, memorable URLs:
- Frontend: `http://web.localhost:7777`
- API: `http://api.localhost:7777`
- Auth: `http://auth.localhost:7777`
- Admin: `http://admin.localhost:7777`

## Core Benefits

### 1. OAuth/OIDC Stability
Use stable subdomain URLs in your provider settings. `http://auth.localhost:7777/callback` never changes, even if you move your service to a different internal port.

### 2. Domain Isolation
`web.localhost` and `api.localhost` are treated as different domains by browsers. This provides:
- **Cookie Isolation**: No more leaked session tokens between apps.
- **Realistic CORS**: Catch CORS configuration issues during development.
- **Service Worker Scope**: Each subdomain has its own clean PWA/Service Worker scope.

### 3. Production Parity
By upgrading to **System Mode**, you get portless URLs (e.g., `http://api.localhost`). This forces you to handle hardcoded URLs and configuration correctly, exactly as you would in production.

### 4. Zero-Friction Setup
The default **Gateway Mode** requires no administrator permissions and works out of the box.

### 5. Multi-Tenant Testing
Easily test multi-tenant applications by creating sub-subdomains: `tenant1.app.localhost:7777`, `tenant2.app.localhost:7777`.

### 6. IoT & Home Lab
Map memorable names to devices on your LAN. Use `http://nas.home` instead of `http://192.168.1.100:5000`. Set `DEVHOST_DOMAIN=home` and you are good to go.

---

Ready to start? [Go to Getting Started](getting-started.md).
