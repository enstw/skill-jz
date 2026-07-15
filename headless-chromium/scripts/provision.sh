#!/usr/bin/env bash
# provision.sh — get a working user-space headless Chromium, no root needed.
#
# Idempotent. On success prints exactly one line to stdout:
#   export BROWSER_BIN=<wrapper>
# The wrapper bakes in LD_LIBRARY_PATH (locally-extracted libs) and
# --no-sandbox when the kernel lacks unprivileged user namespaces, so any
# consumer (browser-screenshot's shot.sh, project e2e scripts, playwright
# executablePath) can use it as a plain browser binary.
#
# Env: FORCE=1 rebuilds the wrapper even if a working one exists.
set -u

STATE="$HOME/.cache/headless-chromium"
WRAPPER="$STATE/chrome"
LIBS="$STATE/libs"
log() { echo "provision: $*" >&2; }
die() { log "$*"; exit 1; }

# A browser "works" if a devtools endpoint comes up (--version alone doesn't
# exercise the sandbox or the renderer).
probe() { # probe <binary> [extra flags...]
  local profile out
  profile="$(mktemp -d)"
  "$@" --headless=new --remote-debugging-port=0 --user-data-dir="$profile" \
       --no-first-run --disable-gpu about:blank >/dev/null 2>&1 &
  local pid=$!
  for _ in $(seq 1 40); do
    [ -s "$profile/DevToolsActivePort" ] && { kill "$pid" 2>/dev/null; rm -rf "$profile"; return 0; }
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.25
  done
  kill "$pid" 2>/dev/null; rm -rf "$profile"; return 1
}

# fast path: existing wrapper still works
if [ "${FORCE:-0}" != "1" ] && [ -x "$WRAPPER" ] && probe "$WRAPPER"; then
  log "existing wrapper OK ($WRAPPER)"
  echo "export BROWSER_BIN=$WRAPPER"
  exit 0
fi
mkdir -p "$STATE"

# ---- 1. find or download a real browser binary ----
REAL="${BROWSER_BIN:-}"
if [ -z "$REAL" ]; then
  for c in \
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "$(command -v chromium 2>/dev/null)" \
    "$(command -v chromium-browser 2>/dev/null)" \
    "$(command -v google-chrome 2>/dev/null)"; do
    [ -n "$c" ] && [ -x "$c" ] && { REAL="$c"; break; }
  done
fi
if [ -z "$REAL" ]; then
  REAL="$(ls -d "$HOME"/.cache/ms-playwright/chromium_headless_shell-*/chrome-linux/headless_shell 2>/dev/null | sort -V | tail -1)"
fi
if [ -z "$REAL" ]; then
  command -v pnpm >/dev/null || die "no browser found and no pnpm to download one; install pnpm first"
  log "downloading playwright chromium-headless-shell (user-space, ~100 MB)…"
  # NOTE: run from \$HOME — pnpm projects/stores break on tmpfs, and a
  # package.json with devEngines.packageManager can make pnpm re-exec a
  # broken self-downloaded binary on some arches
  (cd "$HOME" && pnpm dlx playwright install chromium-headless-shell >&2) \
    || die "playwright download failed"
  REAL="$(ls -d "$HOME"/.cache/ms-playwright/chromium_headless_shell-*/chrome-linux/headless_shell 2>/dev/null | sort -V | tail -1)"
  [ -n "$REAL" ] || die "download reported success but no headless_shell found"
fi
log "browser binary: $REAL"

# ---- 2. resolve missing shared libraries locally (Linux only) ----
LIBDIRS=""
if [ "$(uname)" = "Linux" ]; then
  missing() { ldd "$REAL" 2>/dev/null | awk '/not found/ {print $1}' | sort -u; }
  if [ -n "$(missing)" ]; then
    command -v apt >/dev/null && command -v dpkg >/dev/null \
      || die "missing libs ($(missing | tr '\n' ' ')) and no apt/dpkg to fetch them"
    mkdir -p "$LIBS"
    dl="$(mktemp -d)"
    for so in $(missing); do
      stem="${so%%.so*}"                      # libnss3.so    -> libnss3
      ver="${so##*.so}"; ver="${ver#.}"       # libgbm.so.1   -> 1
      # known groupings first, then generic package-name guesses
      case "$so" in
        libnss*|libsmime*|libssl3*) pkgs="libnss3" ;;
        libnspr*|libplc*|libplds*)  pkgs="libnspr4" ;;
        libasound*)                 pkgs="libasound2t64 libasound2" ;;
        *)                          pkgs="$stem$ver $stem ${stem}${ver}t64 ${stem}t64" ;;
      esac
      got=""
      for p in $pkgs; do
        (cd "$dl" && apt download "$p" >/dev/null 2>&1) && { got="$p"; break; }
      done
      [ -n "$got" ] && log "fetched $got (for $so)" || log "WARN: no package found for $so"
    done
    for deb in "$dl"/*.deb; do [ -e "$deb" ] && dpkg -x "$deb" "$LIBS"; done
    rm -rf "$dl"
  fi
  # every extracted lib dir, deepest first
  LIBDIRS="$(find "$LIBS" -name '*.so*' -exec dirname {} \; 2>/dev/null | sort -u | paste -sd: -)"
  if [ -n "$LIBDIRS" ]; then
    still="$(LD_LIBRARY_PATH="$LIBDIRS" ldd "$REAL" 2>/dev/null | awk '/not found/ {print $1}' | sort -u)"
    [ -n "$still" ] && log "WARN: still unresolved: $(echo "$still" | tr '\n' ' ')— try: sudo apt install ..."
  fi
fi

# ---- 3. sandbox probe, then generate the wrapper ----
FLAGS="--disable-dev-shm-usage"
launch() { # launch with candidate flags via env wrapper semantics
  LD_LIBRARY_PATH="${LIBDIRS:+$LIBDIRS:}${LD_LIBRARY_PATH:-}" probe "$REAL" $1
}
if ! launch "$FLAGS"; then
  if launch "$FLAGS --no-sandbox"; then
    FLAGS="$FLAGS --no-sandbox"
    log "kernel lacks unprivileged user namespaces — baking in --no-sandbox"
  else
    die "browser fails to start even with --no-sandbox; check ldd '$REAL'"
  fi
fi

{
  echo "#!/bin/sh"
  echo "# generated by the headless-chromium skill — user-space Chromium wrapper"
  [ -n "$LIBDIRS" ] && echo "export LD_LIBRARY_PATH=\"$LIBDIRS\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}\""
  echo "exec \"$REAL\" $FLAGS \"\$@\""
} > "$WRAPPER"
chmod +x "$WRAPPER"

probe "$WRAPPER" || die "generated wrapper failed its smoke test"
log "wrapper OK: $WRAPPER"
echo "export BROWSER_BIN=$WRAPPER"
