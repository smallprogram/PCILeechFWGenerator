# PCILeech Firmware Generator - Comprehensive Test Suite

This document describes the comprehensive test suite created for the PCILeech firmware generator project, providing extensive coverage of all core functionality and robust CI/CD pipeline integration.

## Overview

The test suite provides comprehensive coverage of:
- **Main orchestrator** (`generate.py`) - Device enumeration, VFIO binding, container orchestration
- **Firmware generation** (`src/build.py`) - SystemVerilog generation, TCL configuration, behavior profiling
- **Kernel module** (`src/donor_dump/`) - PCIe device information extraction
- **Driver analysis** (`src/scripts/driver_scrape.py`) - Linux driver register analysis
- **FPGA flashing** (`src/flash_fpga.py`) - Hardware programming functionality
- **Behavior profiling** (`src/behavior_profiler.py`) - Dynamic device behavior analysis

## Test Structure

### Core Test Files

```
tests/
├── __init__.py                 # Test package initialization
├── conftest.py                 # Shared fixtures and test configuration
├── test_generate.py            # Main orchestrator tests
├── test_build.py               # Firmware generation tests
├── test_behavior_profiler.py   # Behavior profiling tests
├── test_driver_scrape.py       # Driver analysis tests
├── test_flash_fpga.py          # FPGA flashing tests
├── test_donor_dump.py          # Kernel module tests
└── test_integration.py         # Integration and workflow tests
```

### Configuration Files

```
pytest.ini                     # Pytest configuration
requirements-test.txt           # Test dependencies
run_tests.py                   # Comprehensive test runner
.github/workflows/ci.yml       # GitHub Actions CI/CD pipeline
```

## Test Categories

### Unit Tests (`@pytest.mark.unit`)
- Individual function and class testing
- Mock-based testing for hardware dependencies
- Input validation and error handling
- Data structure and algorithm testing

### Integration Tests (`@pytest.mark.integration`)
- End-to-end workflow testing
- Component interaction validation
- Data flow verification
- Error propagation testing

### Performance Tests (`@pytest.mark.performance`)
- Large dataset processing
- Memory usage optimization
- Execution time benchmarking
- Scalability testing

### Hardware Tests (`@pytest.mark.hardware`)
- Hardware simulation for CI environments
- Mock PCIe device enumeration
- Simulated VFIO operations
- USB device simulation

## Key Features

### 1. Comprehensive Coverage
- **95%+ code coverage** target across all modules
- **456+ individual test cases** covering all major functionality
- **Mock-based testing** eliminates hardware dependencies
- **Edge case testing** for robust error handling

### 2. CI/CD Integration
- **Multi-Python version testing** (3.8, 3.9, 3.10, 3.11)
- **Automated code quality checks** (Black, flake8, isort, mypy)
- **Security scanning** (bandit, safety)
- **Performance regression testing**
- **Container build validation**

### 3. Advanced Testing Features
- **Behavior profiling simulation** for dynamic analysis
- **SystemVerilog generation validation** with timing constraints
- **Kernel module compilation testing** with mock hardware
- **Large dataset performance testing** up to 10,000 registers
- **Memory usage monitoring** and optimization validation

### 4. Developer-Friendly Tools
- **Unified test runner** (`run_tests.py`) with multiple modes
- **Rich test fixtures** for common test scenarios
- **Detailed error reporting** with context and suggestions
- **Performance benchmarking** with historical comparison

## Running Tests

### Quick Start
```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run quick unit tests
python run_tests.py --quick

# Run full test suite
python run_tests.py --full

# Run with coverage reporting
python run_tests.py --coverage
```

### Test Runner Options
```bash
python run_tests.py --quick          # Fast unit tests only
python run_tests.py --full           # Complete test suite
python run_tests.py --ci             # CI mode (non-interactive)
python run_tests.py --coverage       # With coverage reporting
python run_tests.py --performance    # Performance tests only
python run_tests.py --security       # Security tests only
python run_tests.py --legacy         # Legacy enhancement tests
```

### Direct Pytest Usage
```bash
# Run specific test categories
pytest tests/ -m "unit"              # Unit tests only
pytest tests/ -m "integration"       # Integration tests only
pytest tests/ -m "performance"       # Performance tests only

# Run specific test files
pytest tests/test_generate.py        # Main orchestrator tests
pytest tests/test_build.py           # Build system tests

# Run with coverage
pytest tests/ --cov=src --cov=generate --cov-report=html
```

## Test Fixtures and Utilities

### Mock Data Fixtures
- `mock_pci_device` - Simulated PCIe device data
- `mock_donor_info` - Mock kernel module output
- `mock_register_data` - Test register definitions with context
- `mock_behavior_profile` - Simulated behavior profiling data
- `mock_usb_devices` - USB device enumeration data

### Environment Fixtures
- `temp_dir` - Temporary directory for file operations
- `mock_subprocess` - Subprocess call mocking
- `mock_file_system` - File system operation mocking
- `mock_vfio_environment` - VFIO driver simulation
- `mock_container_runtime` - Container operation mocking

### Performance Fixtures
- `performance_test_data` - Benchmarking data and thresholds
- Large dataset generators for scalability testing
- Memory usage monitoring utilities

## CI/CD Pipeline

### GitHub Actions Workflow
The CI pipeline includes multiple parallel jobs:

1. **Code Quality** - Formatting, linting, type checking, security scanning
2. **Unit Tests** - Fast, isolated component testing
3. **Integration Tests** - End-to-end workflow validation
4. **Performance Tests** - Regression and benchmarking
5. **Container Tests** - Docker/Podman build validation
6. **Documentation** - README and code documentation validation
7. **Kernel Module** - Compilation testing with mock environment
8. **Dependencies** - Vulnerability and license scanning

### Test Matrix
- **Python versions**: 3.8, 3.9, 3.10, 3.11
- **Test types**: Unit, Integration, Performance
- **Environments**: Ubuntu Latest with kernel headers
- **Coverage**: Comprehensive reporting with Codecov integration

## Test Data and Scenarios

### Simulated Hardware
- **Intel I210 Gigabit Ethernet** (8086:1533) - Primary test device
- **Various PCIe device classes** - Network, storage, graphics
- **Multiple board configurations** - 35t, 75t, 100t FPGA targets
- **USB programming devices** - LambdaConcept Screamer/Squirrel

### Test Scenarios
- **Normal operation** - Successful firmware generation workflow
- **Error conditions** - Missing dependencies, invalid parameters
- **Edge cases** - Large datasets, unusual hardware configurations
- **Performance limits** - Memory usage, processing time constraints
- **Security scenarios** - Input validation, command injection prevention

## Performance Benchmarks

### Target Performance Metrics
- **Small device** (10 registers): < 1s build time, < 50MB memory
- **Medium device** (100 registers): < 5s build time, < 100MB memory  
- **Large device** (1000 registers): < 30s build time, < 200MB memory

### Regression Testing
- Automated performance regression detection
- Historical benchmark comparison
- Memory leak detection
- Processing time optimization validation

## Security Testing

### Security Measures
- **Input validation** - BDF format, file paths, command parameters
- **Command injection prevention** - Safe subprocess execution
- **File permission handling** - Secure temporary file creation
- **Dependency scanning** - Known vulnerability detection

### Security Test Coverage
- Malicious input handling
- Path traversal prevention
- Command injection attempts
- File permission validation
- Container security best practices

## Maintenance and Updates

### Adding New Tests
1. Create test file in `tests/` directory
2. Use appropriate test markers (`@pytest.mark.unit`, etc.)
3. Import fixtures from `conftest.py`
4. Follow naming convention: `test_<functionality>.py`
5. Update this documentation

### Test Maintenance
- Regular dependency updates via Dependabot
- Performance benchmark updates for new hardware
- Mock data updates for new device types
- CI pipeline optimization and updates

### Debugging Failed Tests
1. Check test output for specific failure details
2. Use `--verbose` flag for detailed information
3. Run individual test files for isolation
4. Check mock configurations for hardware dependencies
5. Verify test environment setup

## Integration with Development Workflow

### Pre-commit Testing
```bash
# Quick validation before commit
python run_tests.py --quick

# Code quality checks
python run_tests.py --no-quality=false
```

### Release Testing
```bash
# Comprehensive pre-release validation
python run_tests.py --full --coverage

# Performance regression check
python run_tests.py --performance
```

### Continuous Integration
- Automatic testing on all pull requests
- Nightly comprehensive test runs
- Performance regression monitoring
- Security vulnerability scanning

## Conclusion

This comprehensive test suite provides robust validation of the PCILeech firmware generator, ensuring reliability, performance, and security across all supported environments. The combination of unit, integration, and performance testing with extensive CI/CD integration creates a solid foundation for maintaining and extending the project.

The test suite is designed to:
- **Catch regressions early** through comprehensive coverage
- **Validate performance** with automated benchmarking
- **Ensure security** through input validation and vulnerability scanning
- **Support development** with fast feedback and detailed reporting
- **Enable confident releases** through thorough pre-release validation

For questions or contributions to the test suite, please refer to the project's contribution guidelines and feel free to open issues for test-related improvements.