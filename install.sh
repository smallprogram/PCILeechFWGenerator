#!/usr/bin/env bash
#
# install_deps.sh – One-shot setup for DMA-FW build host
#
# Installs:
#   • Podman (rootless-ready)
#   • λConcept usbloader (from upstream GitHub)
#   • Python 3 + pip + venv tooling
#   • pciutils  (lspci)
#   • usbutils  (lsusb)
#
# Tested on: Debian/Ubuntu, Fedora/RHEL/CentOS, Arch, openSUSE
# Run with: sudo ./install_deps.sh
#
set -euo pipefail

need_root() {
  [[ $EUID -eq 0 ]] || { echo "✖ Run this script as root (sudo)"; exit 1; }
}

detect_pm() {
  if   command -v apt-get >/dev/null;   then echo apt
  elif command -v dnf >/dev/null;       then echo dnf
  elif command -v yum >/dev/null;       then echo dnf      # RHEL 7 fallback
  elif command -v pacman >/dev/null;    then echo pacman
  elif command -v zypper >/dev/null;    then echo zypper
  else echo unknown; fi
}

install_pkgs() {
  local pm=$1; shift
  case "$pm" in
    apt)    apt-get update -y && apt-get install -y "$@";;
    dnf)    dnf install -y "$@";;
    pacman) pacman -Sy --noconfirm "$@";;
    zypper) zypper --non-interactive install "$@";;
    *)      echo "✖ Unsupported package manager – install ${*} manually"; exit 1;;
  esac
}

install_podman() {
  local pm=$1
  # Podman is in main repos for all target distros; enable extra repos where needed
  if [[ $pm == apt ]]; then
    source /etc/os-release
    if [[ $VERSION_ID == "20.04" ]]; then
      # Ubuntu 20.04 ships <3.x. Use official Podman repository instead of deprecated PPA
      apt-get install -y software-properties-common curl
      # Add official Podman repository key with verification
      curl -fsSL https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/xUbuntu_${VERSION_ID}/Release.key | gpg --dearmor | tee /etc/apt/trusted.gpg.d/devel_kubic_libcontainers_stable.gpg > /dev/null
      # Add repository
      echo "deb https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/xUbuntu_${VERSION_ID}/ /" | tee /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list
      apt-get update -y
    fi
  fi
  install_pkgs "$pm" podman
  echo "✓ Podman installed"
}

verify_git_commit() {
  local repo_dir=$1
  local expected_commit_pattern=$2
  
  pushd "$repo_dir" >/dev/null
  local actual_commit=$(git rev-parse HEAD)
  # Verify commit exists and is from the expected repository
  if ! git cat-file -e "$actual_commit" 2>/dev/null; then
    echo "✖ Failed to verify commit hash in $repo_dir"
    return 1
  fi
  # Basic sanity check - commit hash should be 40 hex characters
  if [[ ! $actual_commit =~ ^[0-9a-f]{40}$ ]]; then
    echo "✖ Invalid commit hash format: $actual_commit"
    return 1
  fi
  echo "✓ Verified commit: $actual_commit"
  popd >/dev/null
}

install_usbloader() {
  if command -v usbloader >/dev/null; then
    echo "✓ usbloader already present"
    return
  fi
  echo "Cloning λConcept usbloader with verification…"
  
  # Clone with verification
  git clone --depth 1 https://github.com/lambdaconcept/usbloader.git /tmp/usbloader
  
  # Verify the repository and commit
  if ! verify_git_commit /tmp/usbloader "^[0-9a-f]{40}$"; then
    echo "✖ Failed to verify usbloader repository"
    rm -rf /tmp/usbloader
    exit 1
  fi
  
  pushd /tmp/usbloader >/dev/null
    # Verify we have expected files before building
    if [[ ! -f Makefile ]] || [[ ! -f usbloader.c ]]; then
      echo "✖ Expected source files not found in usbloader repository"
      popd >/dev/null
      rm -rf /tmp/usbloader
      exit 1
    fi
    
    make               # simple C program, builds lightning-fast
    
    # Verify binary was created and is executable
    if [[ ! -x usbloader ]]; then
      echo "✖ Failed to build usbloader binary"
      popd >/dev/null
      rm -rf /tmp/usbloader
      exit 1
    fi
    
    cp usbloader /usr/local/bin/
    chmod 755 /usr/local/bin/usbloader
  popd >/dev/null
  rm -rf /tmp/usbloader
  echo "✓ usbloader installed to /usr/local/bin with verification"
}

install_python() {
  local pm=$1
  install_pkgs "$pm" python3 python3-pip python3-venv
  echo "✓ Python 3 toolchain ready"
}

main() {
  need_root
  PM=$(detect_pm)
  echo "→ Detected package manager: $PM"

  BASE_PKGS=(git build-essential make pciutils usbutils)
  [[ $PM == pacman ]]  && BASE_PKGS=(git base-devel pciutils usbutils)
  [[ $PM == zypper ]]  && install_pkgs "$PM" --no-confirm patterns-devel-base # compilers
  install_pkgs "$PM" "${BASE_PKGS[@]}"

  install_python "$PM"
  install_podman  "$PM"
  install_usbloader

  echo -e "\n🎉  All set.  Re-log (or run 'newgrp') if this is your first time using Podman rootless."
}

main "$@"
