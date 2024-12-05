resource "aws_vpc" "eks_vpc" {
  cidr_block = "10.0.0.0/16"
  enable_dns_support = true
  enable_dns_hostnames = true
}

resource "aws_subnet" "eks_subnets" {
  count = 2

  vpc_id            = aws_vpc.eks_vpc.id
  cidr_block        = ["10.0.1.0/24", "10.0.2.0/24"][count.index]
  availability_zone = data.aws_availability_zones.available.names[count.index]
}

data "aws_availability_zones" "available" {
  state = "available"
}