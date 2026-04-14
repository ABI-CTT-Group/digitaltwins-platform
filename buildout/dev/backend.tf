terraform {
  backend "s3" {
    bucket  = "terraform-states-carvin"
    key     = "drai_cc/dev/terraform.tfstate"

    endpoints = {
      s3  = "https://object.akl-1.cloud.nesi.org.nz"
      sts = "https://object.akl-1.cloud.nesi.org.nz"
      iam = "https://object.akl-1.cloud.nesi.org.nz"
    }
    region = "akl-1"

    use_path_style              = true
    skip_credentials_validation = true
    skip_region_validation      = true
    skip_metadata_api_check     = true
    skip_requesting_account_id  = true
    skip_s3_checksum            = true

    # Credentials via environment variables (set before running terraform):
    #   export AWS_ACCESS_KEY_ID=<your-access-key>
    #   export AWS_SECRET_ACCESS_KEY=<your-secret-key>
  }
}
