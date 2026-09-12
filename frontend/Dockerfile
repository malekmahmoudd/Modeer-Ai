# Pinned by digest so a rebuild gets the Node the build was tested on. To move
# it: docker pull node:22-alpine, then take the digest it prints.
FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32 AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ENV BACKEND_URL=http://backend:8000
RUN npm run build
FROM node:22-alpine@sha256:c610fcdfb1d5b4740dd70c284ed3cb16bb857e0f7166196e36a5501df7a3aa32
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build --chown=node:node /app ./
USER node
EXPOSE 3000
CMD ["npm", "start", "--", "-H", "0.0.0.0"]

