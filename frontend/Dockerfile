FROM node:22.23.2-bookworm-slim AS build
WORKDIR /app
ARG NPM_REGISTRY=https://registry.npmmirror.com
RUN npm install --global "npm@11.6.2" --registry="$NPM_REGISTRY"
COPY package*.json ./
RUN npm ci --ignore-scripts --registry="$NPM_REGISTRY"
COPY . .
RUN npm run build

FROM build AS test
RUN npm test

FROM nginx:1.27.5-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
