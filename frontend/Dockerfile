# Phase 18b: build the React app, then serve the static files with nginx.

# 1) Build (Debian-based Node: the TypeScript 7 and oxlint native binaries need glibc)
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# The backend address is baked into the built files, so it is set at build time
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# 2) Serve: only the built files end up in the final image, no Node and no source code
FROM nginx:1.29-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
