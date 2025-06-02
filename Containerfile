# Multi-stage build for smaller final image
# Build stage - includes development tools
FROM ubuntu:22.04@sha256:77906da86b60585ce12215807090eb327e7386c8fafb5402369e421f44eff17e AS builder

# Set environment variables for reproducible builds
ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Install build dependencies with pinned versions
RUN apt-get update && apt-get install -y \
    build-essential=12.9ubuntu3 \
    linux-headers-generic=5.15.0.91.88 \
    make=4.3-4.1build1 \
    git=1:2.34.1-1ubuntu1.10 \
    python3=3.10.6-1~22.04 \
    python3-pip=22.0.2+dfsg-1ubuntu0.4 \
    python3-dev=3.10.6-1~22.04 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy source code for any compilation steps
COPY ./src /build/src
WORKDIR /build

# Pre-compile any Python modules or build kernel modules if needed
RUN cd src/donor_dump && make clean && make

# Runtime stage - minimal runtime environment
FROM ubuntu:22.04@sha256:77906da86b60585ce12215807090eb327e7386c8fafb5402369e421f44eff17e AS runtime

# Set environment variables for reproducible builds
ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Install only runtime dependencies with pinned versions
RUN apt-get update && apt-get install -y \
    python3=3.10.6-1~22.04 \
    python3-pip=22.0.2+dfsg-1ubuntu0.4 \
    pciutils=1:3.7.0-6 \
    bsdextrautils=2.37.2-4ubuntu3 \
    sudo=1.9.9-1ubuntu2.4 \
    kmod=29-1ubuntu1 \
    ca-certificates=20230311ubuntu0.22.04.1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# Create non-root user for security (though privileged access needed for PCI operations)
RUN groupadd -r appuser && useradd -r -g appuser -s /bin/bash -m appuser

# Set working directory
WORKDIR /app

# Copy application files from builder stage
COPY --from=builder --chown=appuser:appuser /build/src /app

# Create output directory with proper permissions
RUN mkdir -p /app/output && chown appuser:appuser /app/output

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)" || exit 1

# Add container usage documentation
LABEL maintainer="Ramsey McGrath <ramseymcgrath@gmail.com>" \
      description="PCILeech DMA firmware generator container (multi-stage optimized)" \
      version="1.1" \
      usage="podman run --rm -it --privileged --device=/dev/vfio/X --device=/dev/vfio/vfio -v ./output:/app/output dma-fw sudo python3 /app/build.py --bdf XXXX:XX:XX.X --board XXt" \
      security.notes="Requires privileged mode for PCI device access via VFIO"

# Create entrypoint script for better container usage
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Display usage information\n\
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then\n\
    echo "PCILeech DMA Firmware Generator Container"\n\
    echo "Usage: podman run --rm -it --privileged \\"\n\
    echo "         --device=/dev/vfio/GROUP --device=/dev/vfio/vfio \\"\n\
    echo "         -v ./output:/app/output dma-fw \\"\n\
    echo "         sudo python3 /app/build.py --bdf XXXX:XX:XX.X --board XXt"\n\
    echo ""\n\
    echo "Required arguments:"\n\
    echo "  --bdf XXXX:XX:XX.X  PCI Bus:Device.Function (e.g., 0000:03:00.0)"\n\
    echo "  --board XXt         Target board (35t, 75t, or 100t)"\n\
    echo ""\n\
    echo "Example:"\n\
    echo "  sudo python3 /app/build.py --bdf 0000:03:00.0 --board 75t"\n\
    exit 0\n\
fi\n\
\n\
# Execute the command\n\
exec "$@"\n' > /entrypoint.sh && chmod +x /entrypoint.sh

# Note: Vivado tools should be installed separately or use Xilinx's official container images
# This container provides the optimized base environment for DMA firmware generation

ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
