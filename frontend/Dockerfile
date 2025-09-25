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

# Configurar nginx para SPA
RUN echo 'server { \
    listen 80; \
    server_name localhost; \
    root /usr/share/nginx/html; \
    index index.html; \
    \
    # API proxy (in-cluster) - TODOS los endpoints del backend
    location ~ ^/(user|v2|status|process|upload|upload-xml|job|tasks|prefs|email-config|email-configs|invoices|export-templates|export|health|cache|imap|docs|openapi.json|system|debug|email-processing) { \
        proxy_pass http://cuenly-backend-service.cuenly-backend.svc.cluster.local:8000; \
        proxy_http_version 1.1; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; \
        proxy_set_header X-Forwarded-Proto $scheme; \
        proxy_set_header Upgrade $http_upgrade; \
        proxy_set_header Connection "upgrade"; \
        proxy_cache_bypass $http_upgrade; \
        client_max_body_size 50M; \
    } \
    \
    # API proxy con /api prefix (compatibilidad) \
    location /api/ { \
        rewrite ^/api/(.*)$ /\$1 break; \
        proxy_pass http://cuenly-backend-service.cuenly-backend.svc.cluster.local:8000; \
        proxy_http_version 1.1; \
        proxy_set_header Host $host; \
        proxy_set_header X-Real-IP $remote_addr; \
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; \
        proxy_set_header X-Forwarded-Proto $scheme; \
        proxy_set_header Upgrade $http_upgrade; \
        proxy_set_header Connection "upgrade"; \
        proxy_cache_bypass $http_upgrade; \
        client_max_body_size 50M; \
    } \
    \
    # App routes -> SPA
    location / { \
        try_files $uri $uri/ /index.html; \
    } \
    \
    location /health { return 200; } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
