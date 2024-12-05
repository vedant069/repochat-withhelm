resource "aws_eks_cluster" "eks_cluster" {
  name     = var.cluster_name
  role_arn = aws_iam_role.eks_cluster_role.arn

  vpc_config {
    subnet_ids = aws_subnet.eks_subnets.*.id
    security_group_ids = [aws_security_group.eks_cluster_sg.id]
  }
}