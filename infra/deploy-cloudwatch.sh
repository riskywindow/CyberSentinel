#!/bin/bash

# CyberSentinel CloudWatch Container Insights Deployment Script
# This script deploys CloudWatch Container Insights and Fluent Bit for comprehensive logging and monitoring
# 
# Usage: ./deploy-cloudwatch.sh <environment> [component]
# Environment: dev, staging, prod
# Component: cloudwatch-agent, fluent-bit, all (default)

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/terraform"
HELM_DIR="${SCRIPT_DIR}/helm/infrastructure"
NAMESPACE_CLOUDWATCH="amazon-cloudwatch"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if required tools are installed
    local tools=("kubectl" "aws" "jq")
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_error "$tool is not installed or not in PATH"
            exit 1
        fi
    done
    
    # Check if kubectl is configured
    if ! kubectl cluster-info &> /dev/null; then
        log_error "kubectl is not configured properly"
        log_info "Run: aws eks --region <region> update-kubeconfig --name <cluster-name>"
        exit 1
    fi
    
    # Check if AWS credentials are configured
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials are not configured"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Function to get Terraform outputs
get_terraform_outputs() {
    local environment=$1
    log_info "Getting Terraform outputs for environment: $environment"
    
    cd "$TERRAFORM_DIR"
    
    # Initialize terraform if needed
    if [ ! -d ".terraform" ]; then
        log_info "Initializing Terraform..."
        terraform init
    fi
    
    # Get outputs
    local outputs_json
    outputs_json=$(terraform output -json -var-file="environments/${environment}.tfvars" 2>/dev/null || echo "{}")
    
    if [ "$outputs_json" == "{}" ]; then
        log_warning "No Terraform outputs found. Make sure infrastructure is deployed."
        return 1
    fi
    
    # Extract values
    export AWS_ACCOUNT_ID=$(echo "$outputs_json" | jq -r '.aws_account_id.value // empty')
    export AWS_REGION=$(echo "$outputs_json" | jq -r '.aws_region.value // empty')
    export CLUSTER_NAME=$(echo "$outputs_json" | jq -r '.cluster_name.value // empty')
    export CLOUDWATCH_AGENT_ROLE_ARN=$(echo "$outputs_json" | jq -r '.cloudwatch_agent_role_arn.value // empty')
    
    # Validate required values
    if [[ -z "$AWS_ACCOUNT_ID" || -z "$CLUSTER_NAME" || -z "$CLOUDWATCH_AGENT_ROLE_ARN" ]]; then
        log_error "Missing required Terraform outputs"
        return 1
    fi
    
    log_success "Terraform outputs retrieved successfully"
    cd - > /dev/null
}

# Function to create namespace
create_namespace() {
    log_info "Creating CloudWatch namespace..."
    
    # Create amazon-cloudwatch namespace
    kubectl create namespace "$NAMESPACE_CLOUDWATCH" --dry-run=client -o yaml | kubectl apply -f -
    
    log_success "CloudWatch namespace created"
}

# Function to deploy CloudWatch agent
deploy_cloudwatch_agent() {
    local environment=$1
    log_info "Deploying CloudWatch Container Insights agent for environment: $environment"
    
    # Create service account with IRSA
    kubectl -n "$NAMESPACE_CLOUDWATCH" apply -f - << EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: cloudwatch-agent
  namespace: $NAMESPACE_CLOUDWATCH
  annotations:
    eks.amazonaws.com/role-arn: $CLOUDWATCH_AGENT_ROLE_ARN
  labels:
    app.kubernetes.io/name: cloudwatch-agent
    app.kubernetes.io/component: monitoring
    app.kubernetes.io/part-of: cybersentinel
automountServiceAccountToken: true
EOF

    # Create ClusterRole for CloudWatch agent
    kubectl apply -f - << EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: cloudwatch-agent-role
  labels:
    app.kubernetes.io/name: cloudwatch-agent
rules:
- apiGroups: [""]
  resources: ["pods", "nodes", "services", "endpoints", "replicationcontrollers", "events"]
  verbs: ["list", "watch", "get"]
- apiGroups: ["extensions"]
  resources: ["daemonsets", "deployments", "replicasets"]
  verbs: ["list", "watch", "get"]
- apiGroups: ["apps"]
  resources: ["daemonsets", "deployments", "replicasets"]
  verbs: ["list", "watch", "get"]
- apiGroups: ["batch"]
  resources: ["jobs"]
  verbs: ["list", "watch", "get"]
- apiGroups: ["autoscaling"]
  resources: ["horizontalpodautoscalers"]
  verbs: ["list", "watch", "get"]
- apiGroups: ["metrics.k8s.io"]
  resources: ["nodes", "pods"]
  verbs: ["list", "get"]
EOF

    # Create ClusterRoleBinding
    kubectl apply -f - << EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: cloudwatch-agent-role-binding
  labels:
    app.kubernetes.io/name: cloudwatch-agent
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cloudwatch-agent-role
subjects:
- kind: ServiceAccount
  name: cloudwatch-agent
  namespace: $NAMESPACE_CLOUDWATCH
EOF

    # Create CloudWatch agent configuration
    local agent_config_json
    case $environment in
        "dev")
            agent_config_json='{"agent":{"region":"'$AWS_REGION'","debug":true},"logs":{"metrics_collected":{"kubernetes":{"cluster_name":"'$CLUSTER_NAME'","metrics_collection_interval":60}},"force_flush_interval":5}}'
            ;;
        "staging"|"prod")
            agent_config_json='{"agent":{"region":"'$AWS_REGION'","debug":false},"logs":{"metrics_collected":{"kubernetes":{"cluster_name":"'$CLUSTER_NAME'","metrics_collection_interval":60}},"force_flush_interval":5},"metrics":{"namespace":"CWAgent","metrics_collected":{"cpu":{"measurement":[{"name":"cpu_usage_idle","rename":"CPU_USAGE_IDLE","unit":"Percent"},{"name":"cpu_usage_user","rename":"CPU_USAGE_USER","unit":"Percent"},{"name":"cpu_usage_system","rename":"CPU_USAGE_SYSTEM","unit":"Percent"}],"metrics_collection_interval":60,"totalcpu":false},"disk":{"measurement":[{"name":"used_percent","rename":"DISK_USED_PERCENT","unit":"Percent"}],"metrics_collection_interval":60,"resources":["*"]},"mem":{"measurement":[{"name":"mem_used_percent","rename":"MEM_USED_PERCENT","unit":"Percent"}],"metrics_collection_interval":60}},"append_dimensions":{"ClusterName":"'$CLUSTER_NAME'"}}}'
            ;;
    esac

    kubectl -n "$NAMESPACE_CLOUDWATCH" apply -f - << EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: cwagentconfig
  namespace: $NAMESPACE_CLOUDWATCH
  labels:
    app.kubernetes.io/name: cloudwatch-agent
data:
  cwagentconfig.json: '$agent_config_json'
EOF

    # Create CloudWatch agent DaemonSet
    local cpu_limit="500m"
    local memory_limit="512Mi"
    local cpu_request="100m"
    local memory_request="128Mi"

    case $environment in
        "dev")
            cpu_limit="200m"
            memory_limit="256Mi"
            cpu_request="50m"
            memory_request="64Mi"
            ;;
        "staging")
            cpu_limit="400m"
            memory_limit="384Mi"
            cpu_request="75m"
            memory_request="96Mi"
            ;;
        "prod")
            cpu_limit="1000m"
            memory_limit="1Gi"
            cpu_request="200m"
            memory_request="256Mi"
            ;;
    esac

    kubectl -n "$NAMESPACE_CLOUDWATCH" apply -f - << EOF
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: cloudwatch-agent
  namespace: $NAMESPACE_CLOUDWATCH
  labels:
    app.kubernetes.io/name: cloudwatch-agent
    app.kubernetes.io/component: monitoring
    app.kubernetes.io/part-of: cybersentinel
    environment: $environment
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: cloudwatch-agent
  template:
    metadata:
      labels:
        app.kubernetes.io/name: cloudwatch-agent
        app.kubernetes.io/component: monitoring
        environment: $environment
    spec:
      serviceAccountName: cloudwatch-agent
      terminationGracePeriodSeconds: 60
      containers:
      - name: cloudwatch-agent
        image: public.ecr.aws/cloudwatch-agent/cloudwatch-agent:1.300026.1b317
        imagePullPolicy: IfNotPresent
        resources:
          limits:
            cpu: $cpu_limit
            memory: $memory_limit
          requests:
            cpu: $cpu_request
            memory: $memory_request
        env:
        - name: AWS_REGION
          value: $AWS_REGION
        - name: CLUSTER_NAME
          value: $CLUSTER_NAME
        - name: CI_VERSION
          value: "k8s/1.3.26"
        - name: NODE_NAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
        - name: POD_NAME
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        volumeMounts:
        - name: cwagentconfig
          mountPath: /etc/cwagentconfig
          readOnly: true
        - name: rootfs
          mountPath: /rootfs
          readOnly: true
        - name: dockersock
          mountPath: /var/run/docker.sock
          readOnly: true
        - name: varlibdocker
          mountPath: /var/lib/docker
          readOnly: true
        - name: varlog
          mountPath: /var/log
          readOnly: true
        - name: sys
          mountPath: /sys
          readOnly: true
        - name: devdisk
          mountPath: /dev/disk
          readOnly: true
        securityContext:
          runAsUser: 0
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: false
          capabilities:
            add:
            - SYS_PTRACE
            drop:
            - ALL
      volumes:
      - name: cwagentconfig
        configMap:
          name: cwagentconfig
      - name: rootfs
        hostPath:
          path: /
      - name: dockersock
        hostPath:
          path: /var/run/docker.sock
      - name: varlibdocker
        hostPath:
          path: /var/lib/docker
      - name: varlog
        hostPath:
          path: /var/log
      - name: sys
        hostPath:
          path: /sys
      - name: devdisk
        hostPath:
          path: /dev/disk
      tolerations:
      - operator: Exists
        effect: NoSchedule
      - operator: Exists
        effect: NoExecute
      - key: CriticalAddonsOnly
        operator: Exists
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 10%
EOF

    log_success "CloudWatch agent deployed successfully"
}

# Function to deploy Fluent Bit
deploy_fluent_bit() {
    local environment=$1
    log_info "Deploying Fluent Bit for environment: $environment"
    
    # Create Fluent Bit configuration
    kubectl -n "$NAMESPACE_CLOUDWATCH" apply -f - << EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
  namespace: $NAMESPACE_CLOUDWATCH
  labels:
    app.kubernetes.io/name: fluent-bit
data:
  fluent-bit.conf: |
    [SERVICE]
        Flush                     5
        Grace                     30
        Log_Level                 info
        Daemon                    off
        Parsers_File              parsers.conf
        HTTP_Server               On
        HTTP_Listen               0.0.0.0
        HTTP_Port                 2020
        storage.path              /var/fluent-bit/state/flb-storage/
        storage.sync              normal
        storage.checksum          off
        storage.backlog.mem_limit 5M

    @INCLUDE application-log.conf
    @INCLUDE dataplane-log.conf
    @INCLUDE host-log.conf

  application-log.conf: |
    [INPUT]
        Name                tail
        Tag                 application.*
        Exclude_Path        /var/log/containers/cloudwatch-agent*, /var/log/containers/fluent-bit*, /var/log/containers/aws-node*, /var/log/containers/kube-proxy*
        Path                /var/log/containers/*.log
        Docker_Mode         On
        Docker_Mode_Flush   5
        Docker_Mode_Parser  container_firstline
        Parser              docker
        DB                  /var/fluent-bit/state/flb_container.db
        Mem_Buf_Limit       50MB
        Skip_Long_Lines     On
        Refresh_Interval    10
        Rotate_Wait         30
        storage.type        filesystem
        Read_from_Head      Off

    [FILTER]
        Name                kubernetes
        Match               application.*
        Kube_URL            https://kubernetes.default.svc:443
        Kube_CA_File        /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
        Kube_Token_File     /var/run/secrets/kubernetes.io/serviceaccount/token
        Kube_Tag_Prefix     application.var.log.containers.
        Merge_Log           On
        Keep_Log            Off
        K8S-Logging.Parser  On
        K8S-Logging.Exclude On
        Annotations         Off
        Labels              On

    [OUTPUT]
        Name                cloudwatch_logs
        Match               application.*
        region              $AWS_REGION
        log_group_name      /aws/containerinsights/$CLUSTER_NAME/application
        log_stream_prefix   \${HOSTNAME}-
        auto_create_group   true
        extra_user_agent    container-insights

  dataplane-log.conf: |
    [INPUT]
        Name                tail
        Tag                 dataplane.tail.*
        Path                /var/log/containers/aws-node*, /var/log/containers/kube-proxy*
        Docker_Mode         On
        Docker_Mode_Flush   5
        Docker_Mode_Parser  container_firstline
        Parser              docker
        DB                  /var/fluent-bit/state/flb_dataplane_tail.db
        Mem_Buf_Limit       50MB
        Skip_Long_Lines     On
        Refresh_Interval    10
        Rotate_Wait         30
        storage.type        filesystem
        Read_from_Head      Off

    [FILTER]
        Name                kubernetes
        Match               dataplane.tail.*
        Kube_URL            https://kubernetes.default.svc:443
        Kube_CA_File        /var/run/secrets/kubernetes.io/serviceaccount/ca.crt
        Kube_Token_File     /var/run/secrets/kubernetes.io/serviceaccount/token
        Kube_Tag_Prefix     dataplane.tail.var.log.containers.
        Merge_Log           On
        Keep_Log            Off
        K8S-Logging.Parser  On
        K8S-Logging.Exclude On
        Annotations         Off
        Labels              On

    [FILTER]
        Name                aws
        Match               dataplane.*
        imds_version        v1

    [OUTPUT]
        Name                cloudwatch_logs
        Match               dataplane.*
        region              $AWS_REGION
        log_group_name      /aws/containerinsights/$CLUSTER_NAME/dataplane
        log_stream_prefix   \${HOSTNAME}-
        auto_create_group   true
        extra_user_agent    container-insights

  host-log.conf: |
    [INPUT]
        Name                systemd
        Tag                 host.*
        Systemd_Filter      _SYSTEMD_UNIT=kubelet.service
        Systemd_Filter      _SYSTEMD_UNIT=docker.service
        Systemd_Filter      _SYSTEMD_UNIT=containerd.service
        DB                  /var/fluent-bit/state/systemd.db
        Path                /var/log/journal
        Read_From_Tail      On

    [INPUT]
        Name                tail
        Tag                 host.dmesg
        Path                /var/log/dmesg
        Parser              syslog
        DB                  /var/fluent-bit/state/dmesg.db
        Mem_Buf_Limit       5MB
        Skip_Long_Lines     On
        Refresh_Interval    10
        Read_from_Head      Off

    [FILTER]
        Name                aws
        Match               host.*
        imds_version        v1

    [OUTPUT]
        Name                cloudwatch_logs
        Match               host.*
        region              $AWS_REGION
        log_group_name      /aws/containerinsights/$CLUSTER_NAME/host
        log_stream_prefix   \${HOSTNAME}.
        auto_create_group   true
        extra_user_agent    container-insights

  parsers.conf: |
    [PARSER]
        Name                docker
        Format              json
        Time_Key            time
        Time_Format         %Y-%m-%dT%H:%M:%S.%LZ

    [PARSER]
        Name                syslog
        Format              regex
        Regex               ^(?<time>[^ ]* {1,2}[^ ]* [^ ]*) (?<host>[^ ]*) (?<ident>[a-zA-Z0-9_\/\.\-]*)(?:\[(?<pid>[0-9]+)\])?(?:[^\:]*\:)? *(?<message>.*)$
        Time_Key            time
        Time_Format         %b %d %H:%M:%S

    [PARSER]
        Name                container_firstline
        Format              regex
        Regex               (?<log>(?<="log":")\S(?!\.).*?)(?<!\\\\)".*(?<stream>(?<="stream":").*?)".*(?<time>\d{4}-\d{1,2}-\d{1,2}T\d{2}:\d{2}:\d{2}\.\w*).*(?=})
        Time_Key            time
        Time_Format         %Y-%m-%dT%H:%M:%S.%LZ
EOF

    # Create Fluent Bit DaemonSet
    local cpu_limit="500m"
    local memory_limit="200Mi"
    local cpu_request="100m"
    local memory_request="50Mi"

    case $environment in
        "dev")
            cpu_limit="200m"
            memory_limit="100Mi"
            cpu_request="50m"
            memory_request="25Mi"
            ;;
        "staging")
            cpu_limit="300m"
            memory_limit="150Mi"
            cpu_request="75m"
            memory_request="37Mi"
            ;;
        "prod")
            cpu_limit="1000m"
            memory_limit="400Mi"
            cpu_request="200m"
            memory_request="100Mi"
            ;;
    esac

    kubectl -n "$NAMESPACE_CLOUDWATCH" apply -f - << EOF
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluent-bit
  namespace: $NAMESPACE_CLOUDWATCH
  labels:
    app.kubernetes.io/name: fluent-bit
    app.kubernetes.io/component: logging
    app.kubernetes.io/part-of: cybersentinel
    environment: $environment
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: fluent-bit
  template:
    metadata:
      labels:
        app.kubernetes.io/name: fluent-bit
        app.kubernetes.io/component: logging
        environment: $environment
    spec:
      serviceAccountName: cloudwatch-agent
      terminationGracePeriodSeconds: 10
      containers:
      - name: fluent-bit
        image: public.ecr.aws/aws-for-fluent-bit/aws-for-fluent-bit:2.32.0
        imagePullPolicy: IfNotPresent
        resources:
          limits:
            cpu: $cpu_limit
            memory: $memory_limit
          requests:
            cpu: $cpu_request
            memory: $memory_request
        env:
        - name: AWS_REGION
          value: $AWS_REGION
        - name: CLUSTER_NAME
          value: $CLUSTER_NAME
        - name: HTTP_SERVER
          value: "On"
        - name: HTTP_PORT
          value: "2020"
        - name: READ_FROM_HEAD
          value: "Off"
        - name: READ_FROM_TAIL
          value: "On"
        - name: HOSTNAME
          valueFrom:
            fieldRef:
              fieldPath: spec.nodeName
        volumeMounts:
        - name: fluentbitstate
          mountPath: /var/fluent-bit/state
        - name: varlog
          mountPath: /var/log
          readOnly: true
        - name: varlibdocker
          mountPath: /var/lib/docker/containers
          readOnly: true
        - name: fluent-bit-config
          mountPath: /fluent-bit/etc/
          readOnly: true
        securityContext:
          runAsUser: 0
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop:
            - ALL
        ports:
        - containerPort: 2020
          name: metrics
          protocol: TCP
      volumes:
      - name: fluentbitstate
        hostPath:
          path: /var/fluent-bit/state
      - name: varlog
        hostPath:
          path: /var/log
      - name: varlibdocker
        hostPath:
          path: /var/lib/docker/containers
      - name: fluent-bit-config
        configMap:
          name: fluent-bit-config
      tolerations:
      - operator: Exists
        effect: NoSchedule
      - operator: Exists
        effect: NoExecute
      - key: CriticalAddonsOnly
        operator: Exists
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 10%
EOF

    # Create service for Fluent Bit metrics
    kubectl -n "$NAMESPACE_CLOUDWATCH" apply -f - << EOF
apiVersion: v1
kind: Service
metadata:
  name: fluent-bit-metrics
  namespace: $NAMESPACE_CLOUDWATCH
  labels:
    app.kubernetes.io/name: fluent-bit
    app.kubernetes.io/component: logging
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "2020"
    prometheus.io/path: "/api/v1/metrics/prometheus"
spec:
  selector:
    app.kubernetes.io/name: fluent-bit
  ports:
  - name: metrics
    port: 2020
    targetPort: 2020
    protocol: TCP
  type: ClusterIP
EOF

    log_success "Fluent Bit deployed successfully"
}

# Function to verify deployments
verify_deployments() {
    local environment=$1
    log_info "Verifying CloudWatch deployments..."
    
    # Check CloudWatch agent
    log_info "Checking CloudWatch agent..."
    kubectl -n "$NAMESPACE_CLOUDWATCH" wait --for=condition=ready --timeout=300s pod -l app.kubernetes.io/name=cloudwatch-agent
    
    # Check Fluent Bit
    log_info "Checking Fluent Bit..."
    kubectl -n "$NAMESPACE_CLOUDWATCH" wait --for=condition=ready --timeout=300s pod -l app.kubernetes.io/name=fluent-bit
    
    # Check if logs are flowing
    log_info "Checking log group creation in CloudWatch..."
    if aws logs describe-log-groups --log-group-name-prefix "/aws/containerinsights/$CLUSTER_NAME" --region "$AWS_REGION" &>/dev/null; then
        log_success "CloudWatch log groups are being created"
    else
        log_warning "CloudWatch log groups not yet visible (may take a few minutes)"
    fi
    
    # Check DaemonSet status
    local cw_desired=$(kubectl -n "$NAMESPACE_CLOUDWATCH" get daemonset cloudwatch-agent -o jsonpath='{.status.desiredNumberScheduled}')
    local cw_ready=$(kubectl -n "$NAMESPACE_CLOUDWATCH" get daemonset cloudwatch-agent -o jsonpath='{.status.numberReady}')
    local fb_desired=$(kubectl -n "$NAMESPACE_CLOUDWATCH" get daemonset fluent-bit -o jsonpath='{.status.desiredNumberScheduled}')
    local fb_ready=$(kubectl -n "$NAMESPACE_CLOUDWATCH" get daemonset fluent-bit -o jsonpath='{.status.numberReady}')
    
    log_info "CloudWatch Agent: $cw_ready/$cw_desired pods ready"
    log_info "Fluent Bit: $fb_ready/$fb_desired pods ready"
    
    if [[ "$cw_ready" == "$cw_desired" ]] && [[ "$fb_ready" == "$fb_desired" ]]; then
        log_success "All deployments verified successfully"
    else
        log_warning "Some pods may still be starting up"
    fi
}

# Main function
main() {
    local environment=${1:-}
    local component=${2:-"all"}
    
    # Validate arguments
    if [[ -z "$environment" ]]; then
        log_error "Environment is required"
        echo "Usage: $0 <environment> [component]"
        echo "Environment: dev, staging, prod"
        echo "Component: cloudwatch-agent, fluent-bit, all (default)"
        exit 1
    fi
    
    if [[ ! "$environment" =~ ^(dev|staging|prod)$ ]]; then
        log_error "Invalid environment: $environment"
        exit 1
    fi
    
    if [[ ! "$component" =~ ^(cloudwatch-agent|fluent-bit|all)$ ]]; then
        log_error "Invalid component: $component"
        exit 1
    fi
    
    log_info "Deploying CloudWatch components for environment: $environment"
    log_info "Component: $component"
    
    # Run deployment steps
    check_prerequisites
    get_terraform_outputs "$environment"
    create_namespace
    
    case $component in
        "cloudwatch-agent")
            deploy_cloudwatch_agent "$environment"
            ;;
        "fluent-bit")
            deploy_fluent_bit "$environment"
            ;;
        "all")
            deploy_cloudwatch_agent "$environment"
            deploy_fluent_bit "$environment"
            verify_deployments "$environment"
            ;;
    esac
    
    log_success "CloudWatch deployment completed successfully!"
    log_info "Monitor the logs with: kubectl -n $NAMESPACE_CLOUDWATCH logs -l app.kubernetes.io/name=cloudwatch-agent -f"
    log_info "Monitor Fluent Bit with: kubectl -n $NAMESPACE_CLOUDWATCH logs -l app.kubernetes.io/name=fluent-bit -f"
    log_info "Check CloudWatch Container Insights in AWS Console: https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#container-insights:infrastructure"
}

# Run main function with all arguments
main "$@"