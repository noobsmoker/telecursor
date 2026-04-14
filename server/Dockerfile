FROM node:20-alpine

# Install build dependencies for native modules (better-sqlite3, etc.)
RUN apk add --no-cache python3 make g++

# Create non-root user for security
RUN addgroup -g 1001 -S nodejs && \
    adduser -S telecursor -u 1001

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies (with build tools available)
RUN npm ci

# Copy source
COPY --chown=telecursor:nodejs . .

# Create data directory
RUN mkdir -p /data && chown -R telecursor:nodejs /app

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/api/v1/health', (r) => process.exit(r.statusCode === 200 ? 0 : 1))"

# Switch to non-root user
USER telecursor

EXPOSE 3000

CMD ["node", "src/index.js"]