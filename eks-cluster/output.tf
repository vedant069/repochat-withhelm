data "aws_eks_cluster_auth" "eks_cluster_auth" {
  name = aws_eks_cluster.eks_cluster.name
}

locals {
  kubeconfig_yaml = yamlencode({
    apiVersion = "v1"
    clusters = [
      {
        name = var.cluster_name
        cluster = {
          server = aws_eks_cluster.eks_cluster.endpoint
          certificate-authority-data = aws_eks_cluster.eks_cluster.certificate_authority.data
        }
      }
    ]
    contexts = [
      {
        name = var.cluster_name
        context = {
          cluster = var.cluster_name
          user = var.cluster_name
        }
      }
    ]
    users = [
      {
        name = var.cluster_name
        user = {
          token = data.aws_eks_cluster_auth.eks_cluster_auth.token
          exec = null
        }
      }
    ]
    current-context = var.cluster_name
  })
}

output "kubeconfig" {
  value = local.kubeconfig_yaml
}