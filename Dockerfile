# syntax=docker/dockerfile:1
FROM --platform=$BUILDPLATFORM python:3.13-alpine AS release
ARG PHOTOCRAFT_VERSION=latest
COPY scripts/download-release.py /download-release.py
RUN python /download-release.py "$PHOTOCRAFT_VERSION" /site

FROM nginx:stable-alpine
COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=release /site/ /usr/share/nginx/html/
USER nginx
EXPOSE 8080
ENTRYPOINT []
CMD ["nginx", "-g", "daemon off;"]
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/healthz || exit 1
