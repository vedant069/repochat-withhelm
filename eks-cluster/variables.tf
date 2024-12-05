variable "region" {
  default = "us-west-2"
}

variable "cluster_name" {
  default = "simple-eks-cluster"
}

variable "node_instance_type" {
  default = "c5.4xlarge"
}

variable "node_count" {
  default = 2
}
variable "subnet_cidrs" {
  type    = list(string)
  default = ["10.0.1.0/24", "10.0.2.0/24"]
}