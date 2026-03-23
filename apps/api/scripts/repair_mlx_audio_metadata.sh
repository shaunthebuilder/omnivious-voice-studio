#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-$(command -v python || command -v python3 || true)}"
if [[ -z "${PYTHON_BIN}" ]]; then
  echo "python/python3 not found in PATH"
  exit 1
fi

SITE_PACKAGES="$(
  "${PYTHON_BIN}" - <<'PY'
import site
paths = [p for p in site.getsitepackages() if p.endswith('site-packages')]
print(paths[0] if paths else '')
PY
)"

if [[ -z "${SITE_PACKAGES}" ]]; then
  echo "Could not resolve site-packages path"
  exit 1
fi

META_DIR="$(ls -d "${SITE_PACKAGES}"/mlx_audio-*.dist-info 2>/dev/null | head -n 1 || true)"
if [[ -z "${META_DIR}" ]]; then
  echo "mlx-audio dist-info not found in ${SITE_PACKAGES}"
  exit 1
fi

META_FILE="${META_DIR}/METADATA"
if [[ ! -f "${META_FILE}" ]]; then
  echo "METADATA file not found: ${META_FILE}"
  exit 1
fi

cp "${META_FILE}" "${META_FILE}.bak"
perl -0777 -pe \
  's/Requires-Dist: transformers==5\.0\.0rc3/Requires-Dist: transformers>=5.0.0rc3/g; s/Requires-Dist: mlx-lm==0\.30\.5/Requires-Dist: mlx-lm>=0.30.5/g' \
  "${META_FILE}.bak" > "${META_FILE}"

echo "Patched ${META_FILE}"
"${PYTHON_BIN}" -m pip check
