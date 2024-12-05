resource "aws_eks_node_group" "eks_node_group" {
  cluster_name    = aws_eks_cluster.eks_cluster.name
  node_group_name = "eks-node-group"
  node_role_arn   = aws_iam_role.eks_node_role.arn
  subnet_ids      = aws_subnet.eks_subnets.*.id
  instance_types  = [var.node_instance_type]
  scaling_config {
    desired_size = var.node_count
    min_size     = 1
    max_size     = 3
  }
  disk_size = 30
}