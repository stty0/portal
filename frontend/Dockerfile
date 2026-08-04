# Portal Frontend (Vue + Nginx) — backend-design §5.2
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
# 비루트로 8080에서 서비스한다 (80은 root 권한이 필요하다)
# 비루트에서는 /run 에 pid를 쓸 수 없다. 경로 문자열에 의존하지 말고 지시자를 통째로 바꾼다.
RUN sed -i 's|^pid .*;|pid /tmp/nginx.pid;|' /etc/nginx/nginx.conf \
    && chown -R nginx:nginx /usr/share/nginx/html /var/cache/nginx \
    && grep -q '^pid /tmp/nginx.pid;' /etc/nginx/nginx.conf
USER nginx
EXPOSE 8080
