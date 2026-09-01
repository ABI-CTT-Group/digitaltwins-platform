#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# build_image_bundle.sh — build the observability airgap IMAGE bundle
# DETERMINISTICALLY, on a CONNECTED build box. No running stack required.
#
# The image set is derived from the Helm CHARTS themselves (`helm template`,
# which is client-side — no cluster), so it always matches what will actually
# deploy, including subcharts (MinIO) and hook Jobs (the make-bucket job whose
# missing image caused the airgap install to hang). Each image is pulled into
# k3s's containerd and then ALL are exported in a SINGLE archive — the format
# `k3s ctr images import` reads completely (a `cat` of separate tars is the bug
# this replaces; import stops at the first archive).
#
# Output (matches what install_observability_airgap.yaml imports + verifies):
#   ${AIRGAP_DIR}/images/k3s-images.tar.gz   one valid multi-image archive
#   ${AIRGAP_DIR}/images/image-list.txt      the manifest (used by the verify gate)
#
# Requirements on the build box: internet, `helm`, and k3s running (its
# containerd is the pull+export engine — installing k3s is enough; you do NOT
# need to deploy the charts). Using k3s ctr guarantees image refs are normalised
# exactly as the airgapped target expects, so pods never try to re-pull.
#
#   AIRGAP_DIR=/mnt/install_src/airgap util/build_image_bundle.sh
#     IMAGE_LIST=/path/to/refs.txt  ...   # skip helm-templating; use an explicit
#                                          # newline-separated ref list instead
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OBS_DIR="${SCRIPT_DIR}/observability"
AIRGAP_DIR="${AIRGAP_DIR:-${SCRIPT_DIR}/airgap}"
IMAGE_DIR="${AIRGAP_DIR}/images"
IMAGE_LIST="${IMAGE_LIST:-}"

command -v helm  >/dev/null 2>&1 || { echo "ERROR: helm not found (needed to derive the image list)." >&2; exit 1; }
command -v k3s   >/dev/null 2>&1 || { echo "ERROR: k3s not found (its containerd pulls + exports the images)." >&2; exit 1; }
sudo k3s ctr version >/dev/null 2>&1 || { echo "ERROR: 'sudo k3s ctr' not working — is k3s running on this box?" >&2; exit 1; }

mkdir -p "${IMAGE_DIR}"

# ── 1. Determine the image set ──────────────────────────────────────────────
if [ -n "${IMAGE_LIST}" ]; then
  echo "==> Using explicit image list: ${IMAGE_LIST}"
  [ -f "${IMAGE_LIST}" ] || { echo "ERROR: ${IMAGE_LIST} not found." >&2; exit 1; }
  mapfile -t IMAGES < <(grep -vE '^\s*(#|$)' "${IMAGE_LIST}" | sort -u)
else
  echo "==> Deriving images from the charts via 'helm template' (loki, mimir, grafana)"
  # chart .tgz + its values file; release name is arbitrary for templating.
  CHARTS=(
    "loki:loki-*.tgz:loki-values.yaml"
    "mimir:mimir-distributed-*.tgz:mimir-values.yaml"
    "grafana:grafana-*.tgz:grafana-values.yaml"
  )
  tmp="$(mktemp)"
  for spec in "${CHARTS[@]}"; do
    name="${spec%%:*}"; rest="${spec#*:}"; chart_glob="${rest%%:*}"; values="${rest##*:}"
    # charts live in observability/charts/; values files live in observability/
    chart=$(ls "${OBS_DIR}/charts/${chart_glob}" 2>/dev/null | head -1 || true)
    [ -n "${chart}" ] || { echo "ERROR: no chart matching ${OBS_DIR}/charts/${chart_glob}" >&2; exit 1; }
    echo "    templating ${name}  (${chart##*/})"
    # -f the values so conditionally-rendered images are included; ignore secret
    # validation (images render regardless). Grab every 'image:' in the manifests.
    helm template "${name}" "${chart}" -f "${OBS_DIR}/${values}" 2>/dev/null \
      | grep -E '^[[:space:]]*image:' \
      | sed -E 's/^[[:space:]]*image:[[:space:]]*//; s/^["'\'']//; s/["'\'']*[[:space:]]*$//' \
      | grep -E '[a-z0-9._-]+/[a-z0-9._/-]+:[a-zA-Z0-9._-]+$' \
      >> "${tmp}" || true
  done
  mapfile -t IMAGES < <(sort -u "${tmp}")
  rm -f "${tmp}"
fi

[ "${#IMAGES[@]}" -gt 0 ] || { echo "ERROR: no images resolved — check the charts/values or pass IMAGE_LIST=." >&2; exit 1; }
echo "==> ${#IMAGES[@]} images to bundle:"
printf '    %s\n' "${IMAGES[@]}"

# ── 2. Pull each image into containerd (needs internet) ─────────────────────
echo "==> Pulling images..."
for img in "${IMAGES[@]}"; do
  echo "    pull ${img}"
  sudo k3s ctr images pull "${img}"
done

# ── 3. Export ALL of them in ONE archive (imports completely) ───────────────
echo "==> Exporting ${#IMAGES[@]} images -> ${IMAGE_DIR}/k3s-images.tar"
sudo k3s ctr images export "${IMAGE_DIR}/k3s-images.tar" "${IMAGES[@]}"
echo "==> Compressing..."
gzip -f "${IMAGE_DIR}/k3s-images.tar"

# ── 4. Manifest (the install playbook verifies containerd against this) ──────
printf '%s\n' "${IMAGES[@]}" > "${IMAGE_DIR}/image-list.txt"
echo "built: $(date -u +%Y-%m-%dT%H:%M:%SZ) (build_image_bundle.sh)" >> "${IMAGE_DIR}/image-list.txt"

SIZE=$(du -sh "${IMAGE_DIR}/k3s-images.tar.gz" | cut -f1)
echo
echo "================================================"
echo " Observability image bundle built + verified-by-construction"
echo "   ${IMAGE_DIR}/k3s-images.tar.gz  (${SIZE})"
echo "   ${IMAGE_DIR}/image-list.txt     (${#IMAGES[@]} images)"
echo "================================================"
echo "Ship ${AIRGAP_DIR}/images with the bundle. The airgap install imports it and"
echo "fails fast if any of these ${#IMAGES[@]} images is not in containerd."
