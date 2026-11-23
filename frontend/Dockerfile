# Production build for the hosted POC (deploy/hosted): the built app served by Caddy,
# which also proxies /api to the backend. Local development keeps using the Vite dev server.
FROM node:20-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# Same-origin API (empty base: the app calls /api/... on its own host). The flags match
# docker-compose.demo.yml so testers get the same screens as `make demo`.
ARG VITE_API_BASE=""
ARG VITE_DEMO=1
ARG VITE_DEV_TOOLS=1
ARG VITE_REVIEWER_CONSOLE=1
ARG VITE_CALLCENTRE_CONSOLE=1
ARG VITE_TENANT_PORTAL=1
ENV VITE_API_BASE=$VITE_API_BASE \
    VITE_MOCK=0 \
    VITE_DEMO=$VITE_DEMO \
    VITE_DEV_TOOLS=$VITE_DEV_TOOLS \
    VITE_REVIEWER_CONSOLE=$VITE_REVIEWER_CONSOLE \
    VITE_CALLCENTRE_CONSOLE=$VITE_CALLCENTRE_CONSOLE \
    VITE_TENANT_PORTAL=$VITE_TENANT_PORTAL
RUN npm run build

FROM caddy:2.8-alpine
COPY --from=build /app/dist /srv
