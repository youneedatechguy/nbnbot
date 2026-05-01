FROM node:20-alpine
WORKDIR /app
RUN apk add --no-cache python3 make g++ git
COPY package.json .
RUN npm install --omit=dev
RUN apk del python3 make g++ git
COPY index.js ./
CMD ["node", "index.js"]
