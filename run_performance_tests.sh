#!/bin/bash
# Performance testing script for Smart Display application
# This script runs a variety of performance tests and saves the results

# Create results directory if it doesn't exist
mkdir -p performance_results

echo "Running performance tests..."

# Test 1: Standard test (20 transitions, 1 second interval)
echo "Running standard test..."
python -m frontend.test_performance --report performance_results/standard_test.json

# Test 2: Rapid transitions (50 transitions, 200ms interval)
echo "Running rapid transition test..."
python -m frontend.test_performance --transitions 50 --interval 200 \
  --report performance_results/rapid_transitions.json

# Test 3: Long-running test (100 transitions, 500ms interval)
echo "Running long-running test..."
python -m frontend.test_performance --transitions 100 --interval 500 \
  --report performance_results/long_running.json

# Compare results
echo
echo "=== Test Results Summary ==="
echo

echo "Standard test:"
grep -A 8 "Performance Test Results" performance_results/standard_test.json | tail -n 8

echo
echo "Rapid transitions:"
grep -A 8 "Performance Test Results" performance_results/rapid_transitions.json | tail -n 8

echo
echo "Long-running test:"
grep -A 8 "Performance Test Results" performance_results/long_running.json | tail -n 8

echo
echo "Tests completed. Detailed results are available in the performance_results directory."
echo "You can analyze them further using the guidelines in performance_test_summary.md" 