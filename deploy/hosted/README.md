# Hosted POC (MS5): one VM for the developers and QA

This runs the POC at one HTTPS address with one shared login, so Cenomi's developers and QA can try it without a laptop. It has the same screens and mock integrations as `make demo`: the chat, `/dev` (inbox, reset), the reviewer console, the call centre and the tenant portal.

```
browser ──HTTPS──▶ web (Caddy: password, the built app, /api → backend)
                         └──▶ backend (FastAPI, mocks, Azure OpenAI) ──▶ postgres
```

Files: [`docker-compose.yml`](docker-compose.yml), [`Caddyfile`](Caddyfile), [`.env.example`](.env.example), `backend/Dockerfile`, `frontend/Dockerfile`. On every PR, CI builds this exact stack and smoke-tests it (`ci.yml`, job `hosted`, with [`smoke.py`](smoke.py)): the password covers everything, the app and `/api` are served, a chat turn streams through Caddy, and a session survives a backend restart.

## 1. Create the VM (once, about 15 minutes)

Any Linux VM with Docker works. On Azure, next to the Azure OpenAI resource:

```bash
az group create -n cenomi-inquiry-poc -l uaenorth
az vm create -g cenomi-inquiry-poc -n inquiry-poc \
  --image Ubuntu2404 --size Standard_B2s \
  --admin-username azureuser --generate-ssh-keys \
  --public-ip-address-dns-name cenomi-inquiry-poc
az vm open-port -g cenomi-inquiry-poc -n inquiry-poc --port 80,443 --priority 900
```

- The address is `cenomi-inquiry-poc.uaenorth.cloudapp.azure.com`; use it as `DOMAIN`.
- Pick the region you use; the DNS label must be unique in it.
- `Standard_B2s` (2 vCPU, 4 GB) is enough for a handful of testers.
- Leave port 22 open only to your own IP. In the portal: Networking → the SSH rule → Source → My IP address.

Then on the VM (`ssh azureuser@<DOMAIN>`):

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && exit   # log in again so the group applies
git clone https://github.com/swa01wk/send-inquiry-agent.git && cd send-inquiry-agent
```

The repo is private, so use a deploy key or a fine-grained read-only token for the clone.

## 2. Configure (once)

```bash
cp deploy/hosted/.env.example deploy/hosted/.env
nano deploy/hosted/.env
```

Set these:
- `DOMAIN`.
- `BASIC_AUTH_USER`, and `BASIC_AUTH_HASH` in single quotes. Make the hash with `docker run --rm caddy:2.8-alpine caddy hash-password --plaintext '<password>'`.
- `POSTGRES_PASSWORD` and `RESUME_TOKEN_SECRET`, from `openssl rand -hex 32` each.
- The Azure OpenAI endpoint, key and deployment.

## 3. Run and update

From the repo root on the VM:

| Command | Does |
| --- | --- |
| `make hosted-up` | Builds the images and starts everything in the background. The first HTTPS certificate takes a minute. |
| `make hosted-update` | `git pull`, rebuild and restart. Data in Postgres is kept. |
| `make hosted-logs` | Follows the logs (`ARGS=backend` for one service). |
| `make hosted-down` | Stops it. Data is kept in the Docker volumes. |

Check it: open `https://<DOMAIN>`, log in, then `https://<DOMAIN>/api/health`.

**Reset the demo data:** `/dev` → Reset demo (the same as on a laptop).

## 4. Hand it to the developers and QA

Send them:
- the address and the shared login, through a separate channel from the address;
- the flow page link;
- the testers' note below.

> The POC runs on mock systems: nothing reaches Tenant Central, Yardi, SMS or email. The SMS code is always 1234. Emails, including the verification and tracking links, land in `/dev/inbox`. `/dev` → Reset demo puts the seeded cases back. The reviewer console is at `/review`. It's a test system, so please use made-up details.

## 5. Keep it safe

- **One shared password covers everything**, `/api` included, because `/dev` shows every code and link. Change it by updating `BASIC_AUTH_HASH`, then `make hosted-update`.
- **Mock data only:** `INTEGRATIONS=mock` is fixed in the compose file.
- **The Azure OpenAI key lives only in `deploy/hosted/.env` on the VM.** It's never in the image or the repo, and the browser never sees it.
- **Rate limits** are 30 a minute per session and 60 a minute per IP (`RATE_LIMIT_*`). Set a budget alert on the Azure OpenAI resource too.
- **Stop it when nobody needs it:** `make hosted-down` stops the containers, and `az vm deallocate` stops the VM's billing.
