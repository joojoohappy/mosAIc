# Verification-only image (next dev, not a production build). Needs the whole
# workspace as build context because apps/web depends on workspace:* packages.
FROM node:24-slim

WORKDIR /repo
RUN corepack enable && corepack prepare pnpm@11.19.0 --activate

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/api/package.json packages/api/package.json
COPY packages/core/package.json packages/core/package.json
COPY packages/design/package.json packages/design/package.json
COPY packages/types/package.json packages/types/package.json
RUN pnpm install --frozen-lockfile

COPY apps/web apps/web
COPY packages packages

WORKDIR /repo/apps/web
EXPOSE 3000
CMD ["pnpm", "exec", "next", "dev", "--webpack", "-H", "0.0.0.0", "-p", "3000"]
