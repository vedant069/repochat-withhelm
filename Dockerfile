# Build stage
FROM node:18-alpine AS builder

# Install necessary build dependencies
RUN apk add --no-cache python3 make g++

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies including monaco-editor
RUN npm install @monaco-editor/react
RUN npm ci

# Copy rest of the application
COPY . .

# Production stage
FROM node:18-alpine

WORKDIR /app

# Copy built node modules and application files
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app .

# Expose port
EXPOSE 5173

# Add tini
RUN apk add --no-cache tini
ENTRYPOINT ["/sbin/tini", "--"]

# Start the application
CMD ["npm", "run", "dev", "--", "--host"]