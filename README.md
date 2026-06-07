# GitOps with ArgoCD – Homework 7

## Prerequisites

Install tools (run once):
```powershell
winget install Kubernetes.kubectl
winget install Helm.Helm
winget install HashiCorp.Terraform
$env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("PATH", "User")
```

Connect to the cluster:
```powershell
aws eks update-kubeconfig --name ml-eks-cluster --region us-east-1
```

## 1. Deploy ArgoCD via Terraform

```powershell
cd gitops-argocd/terraform/argocd
terraform init
terraform apply
```

## 2. Verify ArgoCD Pods

```powershell
kubectl get pods -n infra-tools
```

All pods should show `Running`.

## 3. Access ArgoCD UI

```powershell
kubectl port-forward svc/argocd-server -n infra-tools 8080:80
```

Open: http://localhost:8080
- Username: `admin`
- Password (PowerShell — base64 not available on Windows natively):
```powershell
$encoded = kubectl get secret argocd-initial-admin-secret -n infra-tools -o jsonpath="{.data.password}"
[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($encoded))
```

## 4. Deploy MLflow Application via ArgoCD

```powershell
kubectl apply -f namespaces/application/application.yaml
```

## 5. Fix: t3.micro Node Pod & IP Limits

> t3.micro nodes have a hard limit of 4 pods AND 4 IPs per node (2 ENIs × 2 IPs).
> MLflow also needs ~500MB RAM which exceeds t3.micro's ~530MB allocatable.
> A dedicated t3.small node group is required.

### 5a. Create t3.small node group for MLflow

```powershell
# Create new launch template version with t3.small
aws ec2 create-launch-template-version `
  --region us-east-1 `
  --launch-template-id lt-0b2f05c09bcc1dd08 `
  --source-version 1 `
  --launch-template-data '{"InstanceType":"t3.small"}' `
  --query "LaunchTemplateVersion.VersionNumber" --output text

# Create the node group (uses version 2 of launch template)
aws eks create-nodegroup `
  --cluster-name ml-eks-cluster `
  --nodegroup-name mlflow-nodes `
  --region us-east-1 `
  --node-role arn:aws:iam::366447948269:role/cpu-node-group-eks-node-group-20260531094637660200000005 `
  --subnets subnet-038ccc9ba4db1069a subnet-0ea19ec3edcce256e `
  --launch-template id=lt-0b2f05c09bcc1dd08,version=2 `
  --scaling-config minSize=1,maxSize=1,desiredSize=1 `
  --ami-type AL2023_x86_64_STANDARD `
  --capacity-type ON_DEMAND

# Wait for node to join (~3-4 min)
kubectl get nodes -w
```

### 5b. Patch max-pods on the new node (Kubernetes default is 4 on t3.micro/small)

```powershell
# Replace <new-node> with the actual node name shown by kubectl get nodes
kubectl patch node <new-node>.ec2.internal --subresource=status --type=json `
  -p='[{"op":"replace","path":"/status/allocatable/pods","value":"10"}]'
```

### 5c. Taint old t3.micro nodes to keep MLflow off them

```powershell
kubectl taint node ip-10-0-1-119.ec2.internal ip-full=true:NoSchedule
kubectl taint node ip-10-0-1-172.ec2.internal ip-full=true:NoSchedule
kubectl taint node ip-10-0-2-107.ec2.internal ip-full=true:NoSchedule
kubectl taint node ip-10-0-2-45.ec2.internal  ip-full=true:NoSchedule
```

## 6. Verify Deployment

```powershell
kubectl get applications -n infra-tools   # Synced + Healthy
kubectl get pods -n application           # 1/1 Running
kubectl get svc -n application            # LoadBalancer with EXTERNAL-IP
```

## 7. Teardown / Cost Saving

When done, delete the t3.small node group to stop charges:
```powershell
aws eks delete-nodegroup --cluster-name ml-eks-cluster --nodegroup-name mlflow-nodes --region us-east-1
```

## Repository

https://github.com/OlgaHumphreys/goit-argo
