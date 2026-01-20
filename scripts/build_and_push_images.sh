#!/bin/bash
set -e

# Build and Push IncidentFox Docker Images to Docker Hub
#
# This script builds all 4 core services and pushes them to Docker Hub.
# Prerequisites:
#   1. Docker installed and running
#   2. Logged into Docker Hub: docker login -u incidentfox
#   3. Run from mono-repo root directory

VERSION="${1:-v1.0.0}"
REGISTRY="${DOCKER_REGISTRY:-incidentfox}"  # Can override with DOCKER_REGISTRY env var
PLATFORM="linux/amd64"  # AMD64 for Kubernetes compatibility

echo "============================================"
echo "IncidentFox Image Build & Push"
echo "============================================"
echo "Version: $VERSION"
echo "Registry: $REGISTRY"
echo "Platform: $PLATFORM"
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# Check if logged into Docker Hub
if ! docker info 2>&1 | grep -q "Username:"; then
    echo -e "${YELLOW}Warning: Not logged into Docker Hub${NC}"
    echo "Please run: docker login -u incidentfox"
    exit 1
fi

# Function to build and push an image
build_and_push() {
    local service_name=$1
    local service_dir=$2
    local image_name=$3

    echo -e "${BLUE}Building ${service_name}...${NC}"

    # Check if Dockerfile exists
    if [ ! -f "$service_dir/Dockerfile" ]; then
        echo -e "${RED}Error: Dockerfile not found in $service_dir${NC}"
        return 1
    fi

    # Build image
    echo "  → Building $REGISTRY/$image_name:$VERSION"
    docker build \
        --platform $PLATFORM \
        -t $REGISTRY/$image_name:$VERSION \
        -t $REGISTRY/$image_name:latest \
        $service_dir

    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ Build failed for $service_name${NC}"
        return 1
    fi

    # Push versioned tag
    echo "  → Pushing $REGISTRY/$image_name:$VERSION"
    docker push $REGISTRY/$image_name:$VERSION

    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ Push failed for $service_name:$VERSION${NC}"
        return 1
    fi

    # Push latest tag
    echo "  → Pushing $REGISTRY/$image_name:latest"
    docker push $REGISTRY/$image_name:latest

    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ Push failed for $service_name:latest${NC}"
        return 1
    fi

    echo -e "${GREEN}✓ ${service_name} built and pushed successfully${NC}"
    echo ""

    return 0
}

# Track failures
FAILURES=0

# Build and push all services
echo -e "${BLUE}Step 1/4: Building Agent Service${NC}"
if build_and_push "Agent Service" "agent" "agent"; then
    echo -e "${GREEN}✓ Agent Service complete${NC}"
else
    ((FAILURES++))
    echo -e "${RED}✗ Agent Service failed${NC}"
fi
echo ""

echo -e "${BLUE}Step 2/4: Building Config Service${NC}"
if build_and_push "Config Service" "config_service" "config-service"; then
    echo -e "${GREEN}✓ Config Service complete${NC}"
else
    ((FAILURES++))
    echo -e "${RED}✗ Config Service failed${NC}"
fi
echo ""

echo -e "${BLUE}Step 3/4: Building Orchestrator${NC}"
if build_and_push "Orchestrator" "orchestrator" "orchestrator"; then
    echo -e "${GREEN}✓ Orchestrator complete${NC}"
else
    ((FAILURES++))
    echo -e "${RED}✗ Orchestrator failed${NC}"
fi
echo ""

echo -e "${BLUE}Step 4/4: Building Web UI${NC}"
if build_and_push "Web UI" "web_ui" "web-ui"; then
    echo -e "${GREEN}✓ Web UI complete${NC}"
else
    ((FAILURES++))
    echo -e "${RED}✗ Web UI failed${NC}"
fi
echo ""

# Summary
echo "============================================"
if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}✓ All images built and pushed successfully!${NC}"
    echo ""
    echo "Images published:"
    echo "  - $REGISTRY/agent:$VERSION (and :latest)"
    echo "  - $REGISTRY/config-service:$VERSION (and :latest)"
    echo "  - $REGISTRY/orchestrator:$VERSION (and :latest)"
    echo "  - $REGISTRY/web-ui:$VERSION (and :latest)"
    echo ""
    echo "Customers can now pull these images with:"
    echo "  docker pull $REGISTRY/agent:$VERSION"
    echo ""
    echo "Next steps:"
    echo "  1. Verify images on Docker Hub: https://hub.docker.com/u/$REGISTRY"
    echo "  2. Test customer installation with these images"
    echo "  3. Update Helm chart if needed"
else
    echo -e "${RED}✗ $FAILURES service(s) failed to build/push${NC}"
    exit 1
fi
echo "============================================"
