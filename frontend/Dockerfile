# Etapa de construcción
FROM node:16-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./

RUN npm install

COPY . .

RUN npm run build --prod

# Etapa de producción - Usando nginx
FROM nginx:alpine

# Add curl for exec probes
RUN apk add --no-cache curl

# Copiar archivos de construcción
COPY --from=build /app/dist/cuenlyapp-frontend /usr/share/nginx/html

# Error page
RUN echo '<html><body><h1>CuenlyApp Temporalmente No Disponible</h1><p>El servicio se está reiniciando...</p></body></html>' > /usr/share/nginx/html/50x.html

# Configurar nginx para SPA con headers de caché apropiados
RUN echo 'server { \
    listen 80; \
    server_name localhost; \
    root /usr/share/nginx/html; \
    index index.html; \
    client_max_body_size 100M; \
    \
    # Health check \
    location /health { \
        access_log off; \
        add_header Content-Type text/plain; \
        return 200 "healthy\\n"; \
    } \
    \
    # Static SPA \
    location / { \
        try_files $uri $uri/ /index.html; \
        \
        # Cache for hashed assets \
        location ~* \\.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot|webp)$ { \
            expires 1y; \
            add_header Cache-Control "public, immutable"; \
        } \
        \
        # No cache for index.html \
        location = /index.html { \
            add_header Cache-Control "no-cache, no-store, must-revalidate"; \
            add_header Pragma "no-cache"; \
            add_header Expires "0"; \
        } \
    } \
    \
    # API proxy - process-direct (timeouts largos para procesamiento manual) \
    location /process-direct { \
        proxy_pass http://cuenly-backend-service.cuenly-backend.svc.cluster.local:8000; \
        proxy_http_version 1.1; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; \
        proxy_set_header X-Forwarded-Proto $scheme; \
        proxy_set_header Authorization $http_authorization; \
        proxy_connect_timeout 600s; \
        proxy_send_timeout 600s; \
        proxy_read_timeout 600s; \
        proxy_cache_bypass $http_upgrade; \
        client_max_body_size 50M; \
    } \
    \
    # API proxy - otros endpoints del backend con timeouts moderados \
    location /process { \
        proxy_pass http://cuenly-backend-service.cuenly-backend.svc.cluster.local:8000; \
        proxy_http_version 1.1; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; \
        proxy_set_header X-Forwarded-Proto $scheme; \
        proxy_set_header Authorization $http_authorization; \
        proxy_connect_timeout 300s; \
        proxy_send_timeout 300s; \
        proxy_read_timeout 300s; \
        proxy_cache_bypass $http_upgrade; \
        client_max_body_size 50M; \
    } \
    \
    # API proxy (in-cluster) - otros endpoints del backend \
    location ~ ^/(user|admin|v2|status|upload|upload-xml|job|tasks|prefs|email-config|email-configs|invoices|export-templates|export|health|cache|imap|docs|openapi.json|system|debug|email-processing|api)(/|$) { \
        proxy_pass http://cuenly-backend-service.cuenly-backend.svc.cluster.local:8000; \
        proxy_http_version 1.1; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; \
        proxy_set_header X-Forwarded-Proto $scheme; \
        proxy_set_header Authorization $http_authorization; \
        proxy_set_header Upgrade $http_upgrade; \
        proxy_set_header Connection "upgrade"; \
        proxy_cache_bypass $http_upgrade; \
        proxy_connect_timeout 60s; \
        proxy_send_timeout 60s; \
        proxy_read_timeout 60s; \
        client_max_body_size 50M; \
    } \
    \
    # Error page \
    error_page 500 502 503 504 /50x.html; \
    location = /50x.html { \
        root /usr/share/nginx/html; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]