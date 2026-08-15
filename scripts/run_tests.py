#!/usr/bin/env python
"""
Simple test runner to avoid shell quoting issues.
Executes pytest programmatically and reports results clearly.
"""
import sys
import pytest

def run_tests(test_paths=None, verbose=False):
    """Run pytest with the given paths and return the exit code."""
    args = []
    if test_paths:
        args.extend(test_paths)
    else:
        args.append("-q")
    
    if verbose:
        args.append("-v")
    
    return pytest.main(args)

if __name__ == "__main__":
    # Run all tests
    print("\n" + "="*60)
    print("RUNNING FULL TEST SUITE")
    print("="*60)
    rc = run_tests()
    
    print("\n" + "="*60)
    if rc == 0:
        print("PYTEST RESULT: PASS")
    else:
        print(f"PYTEST RESULT: FAIL (exit code {rc})")
    print("="*60)
    
    sys.exit(rc)
