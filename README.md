# GitOps with ArgoCD – Homework 7

## 1. Deploy ArgoCD via Terraform

cd terraform/argocd
terraform init
terraform apply

## 2. Verify ArgoCD Pods

kubectl get pods -n infra-tools

## 3. Access ArgoCD UI

kubectl port-forward svc/argocd-server -n infra-tools 8080:80
Open: http://localhost:8080
Username: admin
Password: kubectl get secret argocd-initial-admin-secret -n infra-tools \
 -o jsonpath="{.data.password}" | base64 --decode

## 4. Verify Deployment

kubectl get applications -n infra-tools
kubectl get pods -n application
kubectl get svc -n application

## 5. Repository

https://github.com/OlgaHumphreys/goit-argo
