# Build stage
FROM node:20-slim AS builder
WORKDIR /repo
# Shared package + web app (preserve the monorepo layout for the file: dep)
COPY packages/shared ./packages/shared
COPY apps/web ./apps/web
WORKDIR /repo/apps/web
RUN npm install --no-audit --no-fund
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Run stage
FROM node:20-slim AS runner
WORKDIR /repo/apps/web
ENV NODE_ENV=production
COPY --from=builder /repo/packages/shared /repo/packages/shared
COPY --from=builder /repo/apps/web ./
EXPOSE 3000
CMD ["npm", "run", "start"]
