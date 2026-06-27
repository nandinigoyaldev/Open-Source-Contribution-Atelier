FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

COPY index.html vite.config.ts tsconfig*.json tailwind.config.ts postcss.config.js eslint.config.js ./
COPY public/ ./public/
COPY src/ ./src/

RUN npm run build

FROM nginx:alpine AS runner

COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]