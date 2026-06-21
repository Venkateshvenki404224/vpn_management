# Layer vpn_management into the base image's venv so:
#   * `import vpn_management` works (Frappe loads hooks for every app in apps.txt
#     during `bench new-site`/migrate), and
#   * its Python deps (qrcode, Pillow) persist across container recreation
#     (the venv lives in the image, not in a volume).
# At runtime the ./apps bind-mount overlays the editable code at the same path,
# so the bundled copy here only seeds the venv + egg-link.
ARG BASE_IMAGE=vpn_management-base:latest
FROM ${BASE_IMAGE}
USER frappe
WORKDIR /home/frappe/frappe-bench
COPY --chown=frappe:frappe apps/vpn_management apps/vpn_management
RUN env/bin/pip install -e apps/vpn_management
