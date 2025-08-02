#!/usr/bin/env python3
"""
Test runner script for the PolySynergy Router
Provides convenient commands for running different test suites
"""

import subprocess
import sys
import argparse


def run_command(command, description):
    """Run a command and handle the output"""
    print(f"\n🚀 {description}")
    print("=" * 50)
    
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Run tests for PolySynergy Router")
    parser.add_argument("--unit", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration", action="store_true", help="Run only integration tests")
    parser.add_argument("--coverage", action="store_true", help="Run tests with coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fast", action="store_true", help="Skip slow tests")
    
    args = parser.parse_args()
    
    # Build base pytest command
    base_cmd = "python -m pytest"
    
    if args.verbose:
        base_cmd += " -v"
    
    if args.fast:
        base_cmd += " -m 'not slow'"
    
    success = True
    
    if args.unit:
        cmd = f"{base_cmd} tests/unit/"
        success &= run_command(cmd, "Running unit tests")
    elif args.integration:
        cmd = f"{base_cmd} tests/integration/"
        success &= run_command(cmd, "Running integration tests")
    elif args.coverage:
        # Install pytest-cov if not already installed
        run_command("pip install pytest-cov", "Installing coverage dependencies")
        cmd = f"{base_cmd} --cov=. --cov-report=html --cov-report=term-missing"
        success &= run_command(cmd, "Running tests with coverage")
        print("\n📊 Coverage report generated in htmlcov/index.html")
    else:
        # Run all tests
        cmd = f"{base_cmd} tests/"
        success &= run_command(cmd, "Running all tests")
    
    if success:
        print("\n🎉 All tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()