# Terraform Development Guidelines

This document provides Copilot with instructions for generating and reviewing Terraform code in this repository.

## Project Context

This Synapse Operator repository uses Terraform to deploy the Synapse charm using the Juju provider. The Terraform configuration manages the deployment of the Synapse application in Juju models.

**Key Details:**
- **Provider:** Juju Terraform Provider (>= 0.20.0)
- **Main Resource:** `juju_application.synapse`
- **Configuration Tool:** terraform-docs for documentation generation
- **Linting Tool:** tflint with custom rules

## Code Structure Requirements

### File Organization
- **main.tf:** Contains resource definitions (`juju_application.synapse`)
- **variables.tf:** Input variable declarations with descriptions and validation
- **outputs.tf:** Output definitions for cross-module communication
- **terraform.tf:** Provider configuration and Terraform version constraints
- **.tflint.hcl:** Linting configuration for code quality checks
- **README.md:** Auto-generated documentation (use terraform-docs)

### Module Structure
When creating modules:
- Store in `terraform/modules/` directory
- Include `main.tf`, `variables.tf`, and `outputs.tf` in each module
- Document all inputs and outputs
- Use meaningful names reflecting purpose

### Charm Module Requirements
Charm modules deployed in `terraform/modules/` must follow these requirements:

#### Required Files
- **main.tf:** Must contain a `juju_application` resource deploying the charm
- **variables.tf:** Must define all required input variables
- **outputs.tf:** Must define `app_name`, `requires`, `provides`, and `endpoints` outputs
- **terraform.tf:** Must define provider versions (use this file, not `versions.tf`)
- **README.md:** Required for documentation

#### Required Variables
All charm modules must include these variables in `variables.tf`:
- `app_name` - Name of the application in the Juju model (default to charm name)
- `base` - Operating system for deployment (default: `ubuntu@22.04`)
- `channel` - Charm channel (default: `latest/stable`)
- `config` - Application configuration map (default: `{}`)
- `model_uuid` - Juju model UUID reference
- `revision` - Charm revision number (default: `null`)
- `units` - Number of units to deploy (default: `1`)

#### Required Outputs
All charm modules must define these outputs in `outputs.tf`:
- **app_name:** The deployed application name
  ```hcl
  output "app_name" {
    description = "Name of the deployed application."
    value       = juju_application.<charm_name>.name
  }
  ```

- **requires:** Map of charm relation names this charm requires
  ```hcl
  output "requires" {
    description = "Mapping of relation names this charm requires."
    value = {
      relation_name = "relation_name"
      # ... additional required relations
    }
  }
  ```

- **provides:** Map of charm relation names this charm provides
  ```hcl
  output "provides" {
    description = "Mapping of relation names this charm provides."
    value = {
      relation_name = "relation_name"
      # ... additional provided relations
    }
  }
  ```

#### Provider Configuration
- Define provider versions in `terraform.tf` using `required_providers` block
- Do NOT create a separate `versions.tf` file
- Pin provider versions for reproducibility
- Example:
  ```hcl
  terraform {
    required_providers {
      juju = {
        source  = "juju/juju"
        version = ">= 0.22.0"
      }
    }
  }
  ```

#### Documentation
- Generate README.md using terraform-docs
- Document charm-specific configurations
- Include relation requirements and capabilities
- Reference charm documentation for configuration options

**Reference Implementation:** See `terraform/modules/redis-k8s/` for a complete example of a compliant charm module.

## Best Practices

### State Management
1. **Remote State Storage:**
   - Always use remote state backends for production environments
   - Never commit `terraform.tfstate` or `*.tfstate.backup` files
   - Use `.gitignore` to exclude state files

2. **State Locking:**
   - Enable state locking to prevent concurrent modifications
   - Use backend configurations that support locking (e.g., Consul, S3 with DynamoDB)

3. **Sensitive Data:**
   - Never hardcode sensitive values (passwords, API keys, tokens)
   - Use `sensitive = true` on variable outputs containing secrets
   - Store secrets in environment variables or secure backends
   - Use terraform.tfvars.example for template documentation

### Variable Management
1. **Naming Conventions:**
   - Use snake_case for variable names
   - Use descriptive, single-purpose variable names
   - Group related variables logically

2. **Variable Declaration:**
   ```hcl
   variable "example_name" {
     description = "Clear, concise description of the variable's purpose"
     type        = string
     default     = null
     sensitive   = false
     
     validation {
       condition     = can(regex("^[a-z0-9-]+$", var.example_name))
       error_message = "Example name must contain only lowercase letters, numbers, and hyphens."
     }
   }
   ```

3. **Input Validation:**
   - Include validation blocks for all variables
   - Provide meaningful error messages
   - Validate string patterns, value ranges, and required conditions

### Output Design
1. **Meaningful Outputs:**
   - Export only necessary values for consuming modules
   - Include clear descriptions
   - Mark sensitive outputs with `sensitive = true`

2. **Output Format:**
   ```hcl
   output "resource_id" {
     description = "The unique identifier of the deployed resource"
     value       = resource_type.resource_name.id
     sensitive   = false
   }
   ```

### Resource Configuration
1. **Resource Naming:**
   - Use descriptive local names reflecting resource purpose
   - Avoid generic names like "resource" or "app"
   - Example: `juju_application.synapse` (good) vs `juju_application.app` (poor)

2. **Juju-Specific Considerations:**
   - Always reference `model_uuid` (not model name)
   - Specify charm channel explicitly (default to `latest/stable`)
   - Include charm revision pinning
   - Document storage requirements and constraints

3. **Explicit Defaults:**
   - Define sensible defaults in variables
   - Document default values in descriptions
   - Avoid null defaults unless optional

## Security Guidelines

### Access Control
1. **IAM & Authentication:**
   - Never embed credentials in Terraform code
   - Use authenticated providers with proper credentials management
   - For Juju provider, use properly configured credentials files
   - Rotate credentials regularly

### Data Protection
1. **Sensitive Data Handling:**
   - Mark all sensitive values with `sensitive = true`
   - Never log or display sensitive values in plan/apply output
   - Use encrypted backend storage for state files
   - Encrypt credentials in transit

2. **Secrets Management:**
   - Use external secret management systems (Vault, AWS Secrets Manager, etc.)
   - Reference secrets via data sources, not hardcoding
   - Rotate secrets regularly
   - Audit secret access

### Compliance & Auditing
1. **Resource Tagging:**
   - Include tags for resource identification and tracking
   - Use tags for cost allocation and compliance
   - Document tag naming conventions

2. **Change Tracking:**
   - Use version control for all Terraform code
   - Review all infrastructure changes via pull requests
   - Maintain change logs and audit trails

3. **Documentation:**
   - Document all resources and their purposes
   - Include security considerations in comments
   - Keep README.md updated via terraform-docs
   - Document any manual steps or out-of-band configurations

## Code Quality Standards

### Formatting & Style
1. **HCL Formatting:**
   - Run `terraform fmt` to enforce consistent formatting
   - Maximum line length: 120 characters
   - Use 2-space indentation
   - Alphabetically sort arguments and blocks

2. **Naming Conventions:**
   ```
   Variables:        snake_case (e.g., app_name)
   Resources:        snake_case (e.g., juju_application.synapse)
   Outputs:          snake_case (e.g., app_endpoint)
   Local values:     snake_case (e.g., common_tags)
   ```

### Documentation
1. **Inline Comments:**
   - Use `#` for single-line comments
   - Use `/*  */` for multi-line comments
   - Explain "why," not "what"
   - Document non-obvious logic

2. **Automated Documentation:**
   - Use terraform-docs to generate README.md
   - Keep documentation in sync with code
   - Update documentation before merging changes

### Testing & Validation
1. **Pre-commit Checks:**
   - Run `terraform fmt` to format code
   - Run `tflint` to check for best practices

2. **Code Review:**
   - Verify no unintended resource changes
   - Check for security issues (exposed secrets, weak permissions)
   - Validate variable values and defaults

## Juju Provider Specifics

### Application Deployment
1. **Required Configuration:**
   - Always specify `model_uuid` (not model name)
   - Include charm name
   - Define base operating system
   - Specify channel for version control

2. **Optional but Recommended:**
   - Set explicit `revision` for reproducibility
   - Include `constraints` for resource requirements
   - Document `storage` requirements
   - Specify `units` for scalability

3. **Configuration Management:**
   - Use `config` map for charm-specific settings
   - Validate all configuration values
   - Document configuration options
   - Keep sensitive config in variables with `sensitive = true`

### Example Pattern
```hcl
resource "juju_application" "synapse" {
  name       = var.app_name
  model_uuid = var.model_uuid

  charm {
    name     = "synapse"
    base     = var.base
    channel  = var.channel
    revision = var.revision
  }

  config             = var.config
  constraints        = var.constraints
  units              = var.units
  storage_directives = var.storage

  # Add depends_on for implicit dependencies
  # depends_on = [juju_model.example]
}
```

## Common Patterns to Avoid

❌ **Anti-patterns:**
- Hardcoding values (use variables)
- Using default values without documentation
- Omitting descriptions from variables/outputs
- Mixing environments in single configuration
- Storing state files in git
- Embedding secrets in code
- Ignoring terraform plan output
- Complex nested structures without documentation
- Using deprecated provider features
- Overlapping variable names without namespacing

✅ **Recommended patterns:**
- Variable-driven configurations
- Clear variable descriptions and validation
- Environment-specific tfvars files
- Modular resource organization
- Remote state with locking
- Explicit dependency management
- Comprehensive documentation
- Automated testing and validation
- Regular security audits
- Version-pinned providers

## Workflow

### Before Committing
1. Run `terraform fmt` to format code
2. Run `tflint` to check best practices
3. Review output for security issues
4. Ensure variables have validation rules (optional)
5. Update documentation if needed

### During Code Review
1. Verify `tflint` output
2. Check no unintended deletions/modifications
3. Validate all secret handling
4. Review variable defaults and validation
5. Ensure documentation is updated

## Resources & Tools

- [Terraform Official Documentation](https://www.terraform.io/docs/)
- [Juju Terraform Provider Docs](https://registry.terraform.io/providers/juju/juju/latest/docs)
- [Terraform Security Best Practices](https://www.terraform.io/docs/cloud/security/index.html)
- [HCL Best Practices](https://www.terraform.io/docs/language/syntax/index.html)
- [tflint](https://github.com/terraform-linters/tflint)
- [terraform-docs](https://github.com/terraform-docs/terraform-docs)

## Questions or Clarifications

When encountering ambiguity:
1. Refer to the Juju provider documentation
2. Check existing patterns in `terraform/` directory
3. Consult CONTRIBUTING.md for project guidelines
4. Open discussion in pull requests for security/design decisions
