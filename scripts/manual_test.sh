#!/bin/bash
# IncidentFox Agent Manual Testing Script
# Usage: ./manual_test.sh [inject|clear|test] [service]

set -e

NAMESPACE="otel-demo"
AGENT_NAMESPACE="incidentfox"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 <command> [service]"
    echo ""
    echo "Commands:"
    echo "  inject <service>  - Inject a crash fault into service (cart, payment, ad, etc.)"
    echo "  clear <service>   - Clear the fault from service"
    echo "  flag <flag> [on|off] - Set a feature flag (cartFailure, paymentUnreachable, etc.)"
    echo "  test <prompt>     - Test the agent with a prompt"
    echo "  status            - Show current pod status"
    echo "  flags             - List all available feature flags"
    echo ""
    echo "Examples:"
    echo "  $0 inject cart          # Crash the cart service"
    echo "  $0 test 'Cart is failing. Diagnose it.'"
    echo "  $0 clear cart           # Restore the cart service"
    echo "  $0 flag cartFailure on  # Enable cart failure flag"
    exit 1
}

inject_crash() {
    local service=$1
    echo -e "${YELLOW}Injecting crash into $service...${NC}"
    kubectl patch deployment "$service" -n $NAMESPACE --type='json' \
        -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/command", "value": ["/bin/sh", "-c", "echo SIMULATED CRASH; exit 1"]}]'
    sleep 10
    echo -e "${GREEN}✓ Crash injected. Pod should be in CrashLoopBackOff.${NC}"
    kubectl get pods -n $NAMESPACE | grep "$service"
}

clear_crash() {
    local service=$1
    echo -e "${YELLOW}Clearing crash from $service...${NC}"
    kubectl patch deployment "$service" -n $NAMESPACE --type='json' \
        -p='[{"op": "remove", "path": "/spec/template/spec/containers/0/command"}]' 2>/dev/null || true
    sleep 10
    echo -e "${GREEN}✓ Crash cleared. Pod should recover.${NC}"
    kubectl get pods -n $NAMESPACE | grep "$service"
}

set_flag() {
    local flag=$1
    local value=$2
    echo -e "${YELLOW}Setting flag $flag = $value...${NC}"
    
    # Get current config
    config=$(kubectl get configmap flagd-config -n $NAMESPACE -o jsonpath='{.data.demo\.flagd\.json}')
    
    # Update flag
    new_config=$(echo "$config" | python3 -c "
import json, sys
c = json.load(sys.stdin)
c['flags']['$flag']['defaultVariant'] = '$value'
print(json.dumps(c, indent=2))
")
    
    # Apply
    kubectl patch configmap flagd-config -n $NAMESPACE --type=merge \
        -p "{\"data\":{\"demo.flagd.json\":$(echo "$new_config" | jq -c .)}}"
    
    kubectl rollout restart deployment/flagd -n $NAMESPACE
    sleep 8
    echo -e "${GREEN}✓ Flag $flag set to $value${NC}"
}

list_flags() {
    echo -e "${YELLOW}Available feature flags:${NC}"
    kubectl get configmap flagd-config -n $NAMESPACE -o jsonpath='{.data.demo\.flagd\.json}' | \
        python3 -c "import json,sys; d=json.load(sys.stdin); [print(f'  {k}: {v[\"description\"]}') for k,v in d['flags'].items()]"
}

test_agent() {
    local prompt=$1
    echo -e "${YELLOW}Testing agent with prompt: $prompt${NC}"
    
    # Kill any existing port-forward
    pkill -f "kubectl port-forward.*incidentfox-agent" 2>/dev/null || true
    sleep 2
    
    # Start port-forward
    kubectl port-forward -n $AGENT_NAMESPACE deploy/incidentfox-agent 18080:8080 &
    PF_PID=$!
    sleep 4
    
    # Call agent
    echo ""
    echo -e "${YELLOW}Agent response:${NC}"
    curl -s -X POST http://localhost:18080/agents/investigation_agent/run \
        -H "Content-Type: application/json" \
        -d "{
            \"message\": \"$prompt\",
            \"context\": {\"target_namespace\": \"$NAMESPACE\"},
            \"timeout\": 60,
            \"max_turns\": 20
        }" | python3 -m json.tool
    
    # Cleanup
    kill $PF_PID 2>/dev/null || true
}

show_status() {
    echo -e "${YELLOW}Pod status in $NAMESPACE:${NC}"
    kubectl get pods -n $NAMESPACE
}

# Main
case "${1:-}" in
    inject)
        [ -z "${2:-}" ] && usage
        inject_crash "$2"
        ;;
    clear)
        [ -z "${2:-}" ] && usage
        clear_crash "$2"
        ;;
    flag)
        [ -z "${2:-}" ] && usage
        set_flag "$2" "${3:-on}"
        ;;
    flags)
        list_flags
        ;;
    test)
        [ -z "${2:-}" ] && usage
        test_agent "$2"
        ;;
    status)
        show_status
        ;;
    *)
        usage
        ;;
esac

