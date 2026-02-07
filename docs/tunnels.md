# Tunnels

Devhost can expose a route publicly using an external tunnel provider.

Supported providers:
- `cloudflared` (Cloudflare Tunnel)
- `ngrok`
- `localtunnel` (`lt`)

## Install a provider CLI

Devhost shells out to these CLIs. Install at least one provider:

- `cloudflared`: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
- `ngrok`: https://ngrok.com/download
- `localtunnel`: `npm i -g localtunnel`

## Start a tunnel

```bash
devhost tunnel start api --provider cloudflared
devhost tunnel start api --provider ngrok
devhost tunnel start api --provider localtunnel
```

## Status / stop

```bash
devhost tunnel status
devhost tunnel stop api
```

## Security notes

- Tunnels are opt-in and can expose local services to the public internet.
- Prefer least-privilege routes, and avoid tunneling admin panels unless protected.
- Treat tunnel URLs as secrets if they grant access.

