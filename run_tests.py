#!/usr/bin/env python3
"""
Test runner script for IMPulse application.

This script provides various options for running the test suite.
"""
import subprocess
import sys
import os


def run_command(command, description):
    """Run a command and display the result."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {command}")
    print('='*60)
    
    try:
        result = subprocess.run(command, shell=True, check=True, 
                              capture_output=False, text=True)
        print(f"{description} completed successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"{description} failed with exit code {e.returncode}")
        return False


def main():
    """Main test runner function."""
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
    else:
        test_type = "all"
    
    # Change to project directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    commands = {
        "all": ("python3 -m pytest tests/ -v", "All tests"),
        "unit": ("python3 -m pytest tests/test_utils.py tests/test_time.py -v", "Unit tests"),
        "config": ("python3 -m pytest tests/test_config/ -v", "Configuration tests"),
        "incident": ("python3 -m pytest tests/test_incident/ -v", "Incident tests"),
        "main": ("python3 -m pytest tests/test_main.py -v", "Main application tests"),
        "coverage": ("python3 -m pytest tests/ --cov=app --cov-report=html --cov-report=term", "Tests with coverage"),
        "fast": ("python3 -m pytest tests/ -x --tb=short", "Fast tests (stop on first failure)"),
        "parallel": ("python3 -m pytest tests/ -n auto", "Parallel tests"),
    }
    
    if test_type not in commands:
        print(f"Available test types: {', '.join(commands.keys())}")
        print(f"Usage: python3 run_tests.py [test_type]")
        print(f"Example: python3 run_tests.py unit")
        return
    
    command, description = commands[test_type]
    success = run_command(command, description)
    
    if success:
        print(f"\nTest execution completed successfully!")
    else:
        print(f"\nTest execution failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
