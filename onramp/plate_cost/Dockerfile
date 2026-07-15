# Container image for the on-ramp web service (W7 — "a real deploy target").
#
# A generic, platform-agnostic image on purpose: this repo has not picked a hosting platform
# yet (no real pilot deploy exists — docs/phase_decisions/W7.md), and baking in one platform's
# proprietary config (e.g. a fly.toml tied to an unvalidated account) would presume a decision
# nobody has made. This Dockerfile is the reversible, low-risk artifact that makes "a real
# deploy target" concrete without committing to one: any container host (a single VM running
# `docker run`, or a managed container platform) can run this image behind a TLS-terminating
# reverse proxy or load balancer.
#
# Build + run from onramp/plate_cost/:
#   docker build -t plate-cost-onramp -f Dockerfile ../..
#   docker run -p 8000:8000 \
#     -e ONRAMP_ENV=production \
#     -e ONRAMP_DATABASE_URL=sqlite:////data/onramp.db \
#     -e ONRAMP_SMTP_HOST=... \
#     -v onramp-instance:/data \
#     plate-cost-onramp
#
# Note the build context is the REPO ROOT (../..), not onramp/plate_cost/ — the app imports
# schemas/ (platform-owned, outside this peer) at the seam-write boundary.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.lock.txt /app/requirements.lock.txt
RUN pip install --no-cache-dir -r requirements.lock.txt

COPY schemas/ /app/schemas/
COPY onramp/plate_cost/ /app/onramp/plate_cost/

WORKDIR /app/onramp/plate_cost

# The app DB (ONRAMP_DATABASE_URL) and the seam (repo-root data/raw/, mounted separately in a
# real deploy) both need to survive a container restart — mount a volume at /data and point
# ONRAMP_DATABASE_URL / ONRAMP_BACKUP_DIR at it; don't rely on the container's own filesystem.
EXPOSE 8000

CMD ["python", "-m", "web"]
