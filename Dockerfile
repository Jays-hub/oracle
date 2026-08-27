# Container image for the operator-facing web service (W7 — "a real deploy target").
#
# A generic, platform-agnostic image on purpose: this repo has not picked a hosting platform
# yet (no real pilot deploy exists — docs/phase_decisions/W7.md), and baking in one platform's
# proprietary config (e.g. a fly.toml tied to an unvalidated account) would presume a decision
# nobody has made. This Dockerfile is the reversible, low-risk artifact that makes "a real
# deploy target" concrete without committing to one: any container host (a single VM running
# `docker run`, or a managed container platform) can run this image behind a TLS-terminating
# reverse proxy or load balancer.
#
# Build + run from the repo root:
#   docker build -t plate-cost-onramp .
#   docker run -p 8000:8000 \
#     -e ONRAMP_ENV=production \
#     -e ONRAMP_DATABASE_URL=sqlite:////data/onramp.db \
#     -e ONRAMP_SMTP_HOST=... \
#     -v onramp-instance:/data \
#     plate-cost-onramp
#
# Since the layer restructure the build context IS the repo root and the image copies the layer
# packages the L4 surface depends on — the same downward arrows `.importlinter` enforces, spelled
# out as COPY lines. If a new layer becomes a dependency of surface/, it belongs here too; if one
# stops being needed, dropping it here is how the image stays minimal.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.lock.txt /app/requirements.lock.txt
RUN pip install --no-cache-dir -r requirements.lock.txt

# L4 and everything below it that surface/ imports, plus the shared leaf modules.
COPY surface/   /app/surface/
COPY measures/  /app/measures/
COPY ingest/    /app/ingest/
COPY identity/  /app/identity/
COPY store/     /app/store/
COPY db/        /app/db/
COPY schemas/   /app/schemas/
COPY examples/  /app/examples/
COPY migrations/ /app/migrations/
COPY alembic.ini /app/alembic.ini

# The app DB (ONRAMP_DATABASE_URL) and the seam (repo-root data/raw/, mounted separately in a
# real deploy) both need to survive a container restart — mount a volume at /data and point
# ONRAMP_DATABASE_URL / ONRAMP_BACKUP_DIR at it; don't rely on the container's own filesystem.
EXPOSE 8000

# /app is the import root for every layer package, so no sys.path bootstrap is needed.
CMD ["python", "-m", "surface.web"]
