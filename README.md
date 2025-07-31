# pydantic-gitlab-cli

A comprehensive linting and validation tool for GitLab CI/CD configuration files with over 30 built-in rules to ensure best practices, security, and optimization.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## Features

- **🔍 Comprehensive Validation**: Over 30 built-in rules covering syntax, security, performance, and best practices
- **🎨 Multiple Output Formats**: Console (cargo-style), JSON, SARIF, and JUnit XML
- **⚙️ Highly Configurable**: Enable/disable rules, set severity levels, and customize checks
- **🚀 Fast and Efficient**: Built on Pydantic for robust parsing and validation
- **📊 Detailed Reports**: Clear error messages with actionable suggestions
- **🔒 Security Focused**: Detect hardcoded secrets, insecure configurations, and policy violations

## Installation

```bash
pip install pydantic-gitlab-cli
```

## Quick Start

### Basic Usage

Check a single GitLab CI file:

```bash
pydantic-gitlab-cli check .gitlab-ci.yml
```

Check multiple files:

```bash
pydantic-gitlab-cli check *.gitlab-ci.yml
```

### List Available Rules

```bash
pydantic-gitlab-cli list-rules
```

Filter rules by category:

```bash
pydantic-gitlab-cli list-rules --category security
```

### Generate Configuration

Create a default configuration file:

```bash
pydantic-gitlab-cli init-config
```

## Output Formats

### Console Output (Default)

Beautiful cargo-style output with colored messages:

```
error[GL001]: Job must have at least one of: script, trigger, extends, or run
  --> .gitlab-ci.yml:15:3
  help: Add a 'script' section with commands to execute

warning[GL005]: Docker image uses 'latest' tag which is not reproducible
  --> .gitlab-ci.yml:8:12
  help: Use specific version tags like 'python:3.9' instead of 'python:latest'
```

### JSON Output

```bash
pydantic-gitlab-cli check .gitlab-ci.yml --format json
```

### SARIF Format (for GitHub/GitLab Code Quality)

```bash
pydantic-gitlab-cli check .gitlab-ci.yml --format sarif --output report.sarif
```

### JUnit XML (for CI Integration)

```bash
pydantic-gitlab-cli check .gitlab-ci.yml --format junit --output junit.xml
```

## Configuration

Create a `.gitlab-ci-lint.yml` file in your project:

```yaml
# Linter configuration
strict_mode: false
fail_on_warnings: false

# Enable/disable rule categories
categories:
  security: true
  quality: true
  optimization: true
  structure: true

# Configure individual rules
rules:
  GL001:
    enabled: true
    level: error
  GL008:
    enabled: false  # Disable key ordering rule
  GL015:
    enabled: true
    level: info    # Change severity to info

# File patterns
include_patterns:
  - "*.gitlab-ci.yml"
  - ".gitlab-ci.yml"
exclude_patterns:
  - "**/node_modules/**"
  - "**/vendor/**"
```

## Built-in Rules

### Security Rules
- **GL012**: Detect hardcoded secrets and credentials
- **GL013**: Ensure protected resources run only on protected branches
- **GL020**: Prohibit permanent CI_DEBUG_TRACE enabling

### Structure & Syntax
- **GL001**: Validate basic YAML structure
- **GL002**: Check stage definitions and usage
- **GL004**: Validate job dependencies

### Docker & Images
- **GL005**: Prohibit 'latest' tag usage
- **GL006**: Warn about large base images

### Quality & Best Practices
- **GL007**: Enforce consistent key ordering
- **GL009**: Require cache configuration
- **GL010**: Set artifact expiration
- **GL011**: Enable interruptible for non-deployment jobs

### Optimization
- **GL014**: Variable scope optimization
- **GL015**: Suggest parallelization opportunities
- **GL016**: Appropriate timeout settings
- **GL017**: Job reuse with extends/anchors
- **GL018**: Cache policy optimization
- **GL033**: Check parallel:matrix job limit (max 200)

### Package Manager Caching
- **GL027**: Python pip cache optimization
- **GL028**: Node.js npm/yarn cache optimization
- **GL029**: Rust cargo cache optimization
- **GL030**: Go module cache optimization
- **GL031**: Java Maven/Gradle cache optimization

## CI/CD Integration

### GitLab CI

```yaml
lint:gitlab-ci:
  image: python:3.11
  before_script:
    - pip install pydantic-gitlab-cli
  script:
    - pydantic-gitlab-cli check .gitlab-ci.yml --format junit --output junit.xml
  artifacts:
    reports:
      junit: junit.xml
```

### GitHub Actions

```yaml
name: Lint GitLab CI
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install pydantic-gitlab-cli
        run: pip install pydantic-gitlab-cli
      
      - name: Run linter
        run: pydantic-gitlab-cli check .gitlab-ci.yml --format sarif --output results.sarif
      
      - name: Upload SARIF results
        uses: github/codeql-action/upload-sarif@v2
        with:
          sarif_file: results.sarif
```

## Advanced Usage

### Strict Mode

Enable strict validation mode for more thorough checks:

```bash
pydantic-gitlab-cli check .gitlab-ci.yml --strict
```

### Fail on Warnings

Exit with error code on warnings (useful for CI):

```bash
pydantic-gitlab-cli check .gitlab-ci.yml --fail-on-warnings
```

### Custom Configuration Path

```bash
pydantic-gitlab-cli check .gitlab-ci.yml --config custom-lint.yml
```

## Rule Examples

### Security: Hardcoded Secrets Detection

```yaml
# Bad - hardcoded secret
variables:
  DATABASE_PASSWORD: "mysecretpassword"

# Good - use CI/CD variables
variables:
  DATABASE_PASSWORD: $DB_PASSWORD
```

### Optimization: Parallel Matrix Limit

```yaml
# Bad - exceeds 200 job limit
test:
  parallel:
    matrix:
      - PROVIDER: [aws, gcp, azure]
        REGION: [us-east-1, us-west-2, eu-west-1, ...]  # 70 regions
        # Total: 3 * 70 = 210 jobs (exceeds limit!)

# Good - within limits
test:
  parallel:
    matrix:
      - PROVIDER: aws
        REGION: [us-east-1, us-west-2, eu-west-1]
      - PROVIDER: gcp
        REGION: [us-central1, europe-west1]
```

### Docker: Avoid Latest Tag

```yaml
# Bad - unpredictable builds
image: python:latest

# Good - reproducible builds
image: python:3.11.5
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Evgenii Lepikhin (johnlepikhin@gmail.com)

## Links

- [GitHub Repository](https://github.com/johnlepikhin/pydantic-gitlab-cli)
- [Issue Tracker](https://github.com/johnlepikhin/pydantic-gitlab-cli/issues)
- [PyPI Package](https://pypi.org/project/pydantic-gitlab-cli/)