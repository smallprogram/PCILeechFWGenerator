# Contributing to PCILeech Firmware Generator

Thank you for your interest in contributing to the PCILeech Firmware Generator! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Guidelines](#contributing-guidelines)
- [Testing](#testing)
- [Code Style](#code-style)
- [Submitting Changes](#submitting-changes)
- [Release Process](#release-process)

## Code of Conduct

This project adheres to a code of conduct that promotes a welcoming and inclusive environment. By participating, you are expected to uphold this code.

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Git
- Podman or Docker
- Vivado (for FPGA synthesis)
- Linux environment (required for PCIe operations)

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/yourusername/PCILeechFWGenerator.git
   cd PCILeechFWGenerator
   ```

2. **Create Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Development Dependencies**
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Install Pre-commit Hooks**
   ```bash
   pre-commit install
   ```

5. **Verify Installation**
   ```bash
   python -m pytest tests/
   ```

## Contributing Guidelines

### Types of Contributions

We welcome several types of contributions:

- **Bug Reports**: Help us identify and fix issues
- **Feature Requests**: Suggest new functionality
- **Code Contributions**: Implement features or fix bugs
- **Documentation**: Improve or add documentation
- **Testing**: Add or improve test coverage

### Bug Reports

When reporting bugs, please include:

- **Environment Details**: OS, Python version, hardware setup
- **Steps to Reproduce**: Clear, step-by-step instructions
- **Expected vs Actual Behavior**: What should happen vs what does happen
- **Error Messages**: Full error output and logs
- **Hardware Configuration**: PCIe devices, DMA boards, etc.

### Feature Requests

For feature requests, please provide:

- **Use Case**: Why is this feature needed?
- **Proposed Solution**: How should it work?
- **Alternatives Considered**: Other approaches you've thought about
- **Implementation Ideas**: Technical approach if you have one

## Development Workflow

### Branch Strategy

- `main`: Stable release branch
- `develop`: Integration branch for new features
- `feature/feature-name`: Feature development branches
- `bugfix/issue-description`: Bug fix branches
- `hotfix/critical-fix`: Critical fixes for production

### Making Changes

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Write code following our style guidelines
   - Add tests for new functionality
   - Update documentation as needed

3. **Test Changes**
   ```bash
   # Run full test suite
   python -m pytest tests/
   
   # Run specific tests
   python -m pytest tests/test_specific_module.py
   
   # Run with coverage
   python -m pytest --cov=src tests/
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add new TUI feature for device selection"
   ```

### Commit Message Format

We use conventional commits for clear history:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(tui): add real-time build progress monitoring
fix(build): resolve SystemVerilog generation error for network devices
docs(readme): update installation instructions for TUI
test(core): add unit tests for device manager
```

## Testing

### Test Structure

```
tests/
├── unit/           # Unit tests for individual modules
├── integration/    # Integration tests for workflows
├── fixtures/       # Test data and fixtures
└── conftest.py     # Pytest configuration
```

### Writing Tests

- **Unit Tests**: Test individual functions and classes
- **Integration Tests**: Test complete workflows
- **Mock External Dependencies**: Use pytest-mock for external services
- **Test Edge Cases**: Include error conditions and boundary cases

### Running Tests

```bash
# All tests
python -m pytest

# Specific test file
python -m pytest tests/test_build.py

# With coverage
python -m pytest --cov=src --cov-report=html

# Parallel execution
python -m pytest -n auto

# Specific markers
python -m pytest -m "not slow"
```

## Code Style

### Python Style Guide

We follow PEP 8 with some modifications:

- **Line Length**: 88 characters (Black default)
- **Import Sorting**: Use isort with Black profile
- **Type Hints**: Required for all public functions
- **Docstrings**: Google style for all modules, classes, and functions

### Formatting Tools

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

### Pre-commit Hooks

Our pre-commit configuration automatically runs:
- Black (code formatting)
- isort (import sorting)
- flake8 (linting)
- mypy (type checking)
- pytest (basic tests)

## Documentation

### Code Documentation

- **Docstrings**: All public functions, classes, and modules
- **Type Hints**: All function parameters and return values
- **Comments**: Explain complex logic and business rules
- **README Updates**: Keep installation and usage instructions current

### Documentation Style

```python
def generate_firmware(device_bdf: str, board_type: str) -> Path:
    """Generate firmware for specified PCIe device.
    
    Args:
        device_bdf: PCIe device Bus:Device.Function identifier
        board_type: Target FPGA board type (35t, 75t, 100t)
        
    Returns:
        Path to generated firmware binary
        
    Raises:
        DeviceNotFoundError: If specified device doesn't exist
        BuildError: If firmware generation fails
        
    Example:
        >>> firmware_path = generate_firmware("0000:03:00.0", "75t")
        >>> print(f"Firmware generated: {firmware_path}")
    """
```

## Submitting Changes

### Pull Request Process

1. **Update Documentation**: Ensure README, docstrings, and comments are current
2. **Add Tests**: Include tests for new functionality
3. **Run Full Test Suite**: Ensure all tests pass
4. **Update Changelog**: Add entry to CHANGELOG.md
5. **Create Pull Request**: Use our PR template

### Pull Request Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Tests pass locally
```

### Review Process

1. **Automated Checks**: CI/CD pipeline runs tests and linting
2. **Code Review**: Maintainers review code and provide feedback
3. **Testing**: Changes are tested in development environment
4. **Approval**: At least one maintainer approval required
5. **Merge**: Changes merged to appropriate branch

## Release Process

### Version Management

We use semantic versioning (MAJOR.MINOR.PATCH):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Steps

1. **Update Version**: Increment version in `src/__version__.py`
2. **Update Changelog**: Add release notes to CHANGELOG.md
3. **Create Release Branch**: `release/vX.Y.Z`
4. **Final Testing**: Comprehensive testing of release candidate
5. **Tag Release**: Create git tag with version
6. **Build Distribution**: Create wheel and source distributions
7. **Publish**: Upload to PyPI
8. **GitHub Release**: Create GitHub release with notes

### Distribution

```bash
# Build distributions
python -m build

# Check distributions
twine check dist/*

# Upload to PyPI
twine upload dist/*
```

## Getting Help

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and community discussion
- **Email**: Direct contact for security issues

### Development Resources

- **Architecture Documentation**: See `docs/` directory
- **API Reference**: Generated from docstrings
- **Examples**: See `examples/` directory
- **Test Cases**: See `tests/` directory

## Recognition

Contributors are recognized in:
- **CHANGELOG.md**: Release notes mention contributors
- **GitHub Contributors**: Automatic recognition
- **Release Notes**: Major contributions highlighted

Thank you for contributing to PCILeech Firmware Generator!