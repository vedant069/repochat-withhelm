resource "aws_internet_gateway" "eks_igw" {
  vpc_id = aws_vpc.eks_vpc.id
}

resource "aws_route_table" "eks_route_table" {
  vpc_id = aws_vpc.eks_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.eks_igw.id
  }
}

resource "aws_route_table_association" "eks_route_table_assoc" {
  count          = length(var.subnet_cidrs)
  subnet_id      = aws_subnet.eks_subnets[count.index].id
  route_table_id = aws_route_table.eks_route_table.id
}