# Performance Testing Documentation

This document outlines how to run performance tests for the QStackedWidget-based UI architecture and how to interpret the results.

## Running Performance Tests

The performance testing framework is designed to evaluate:
- Memory usage during screen transitions
- CPU utilization
- Transition smoothness (timing)

### Basic Usage

To run a basic performance test:

```bash
python -m frontend.test_performance
```

This will run 20 transitions between screens with a 1-second interval and save results to `performance_report.json`.

### Advanced Options

You can customize the test with the following parameters:

```bash
python -m frontend.test_performance --transitions 50 --interval 500 --report custom_report.json
```

- `--transitions`: Number of transitions to perform (default: 20)
- `--interval`: Interval between transitions in milliseconds (default: 1000)
- `--report`: File to save the JSON report to (default: performance_report.json)

## Interpreting Test Results

The test will output a summary to the console and save a detailed JSON report. Here's how to interpret the results:

### Console Output

The console output will show:
- Number of transitions completed
- Average transition time (ms)
- Minimum and maximum transition times (ms)
- Memory usage change (start → end)
- Peak memory usage
- Average and peak CPU usage

Example:
```
--- Performance Test Results ---
Transitions completed: 20
Average transition time: 42.5ms
Min/Max transition time: 38.2ms / 67.4ms
Memory usage: 2.1% -> 2.3% (change: +0.2%)
Peak memory usage: 2.7%
Average CPU usage: 4.2%
Peak CPU usage: 12.5%
```

### JSON Report Structure

The JSON report contains more detailed information:

```json
{
  "timestamp": "2023-03-17T12:34:56.789",
  "test_config": {
    "num_transitions": 20,
    "interval_ms": 1000
  },
  "transitions": [
    {
      "from": "clock",
      "to": "chat",
      "duration_ms": 45.2
    },
    ...
  ],
  "memory": {
    "initial": 2.1,
    "final": 2.3,
    "peak": 2.7
  },
  "cpu": {
    "avg": 4.2,
    "peak": 12.5
  },
  "summary": {
    "avg_transition_time_ms": 42.5,
    "max_transition_time_ms": 67.4,
    "min_transition_time_ms": 38.2,
    "memory_change_percent": 0.2
  }
}
```

## Performance Benchmarks

For a good user experience, aim for:

1. **Transition Time**:
   - Excellent: < 50ms
   - Good: 50-100ms
   - Acceptable: 100-200ms
   - Poor: > 200ms

2. **Memory Usage**:
   - Memory should remain stable over many transitions
   - Steady increase indicates a potential memory leak
   - Peak usage should be < 5% higher than baseline

3. **CPU Usage**:
   - Average: < 10% of a single core
   - Peak: < 30% during transitions

## Manual Performance Testing

You can also monitor performance manually:

1. Press `Ctrl+P` in the application to display a performance summary
2. Use system monitoring tools like `top` or `htop` to watch resource usage
3. Enable memory optimization with different timeouts to see the effect:
   ```python
   window.screen_manager.set_memory_optimization(True, 120000)  # 2 minutes
   ```

## Troubleshooting Common Performance Issues

### Slow Transitions

If transitions are slow (> 200ms):
- Check for heavy resource loading during screen initialization
- Move resource-intensive operations to background threads
- Consider implementing caching for frequently used resources

### Memory Growth

If memory usage grows steadily:
- Ensure `cleanup()` is properly implemented in all screens
- Check for object references that prevent garbage collection
- Consider reducing image cache sizes or unloading unused resources

### High CPU Usage

If CPU usage is consistently high:
- Look for timers or polling operations that might be too frequent
- Check for inefficient layouts that cause frequent redraws
- Move CPU-intensive operations to background threads 