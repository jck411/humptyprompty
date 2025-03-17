#!/usr/bin/env python3
"""
Performance Test Script - Tests performance of screen transitions and memory usage.
This script runs a series of automated tests to measure memory consumption,
CPU usage, and transition smoothness.
"""

import os
import sys
import time
import asyncio
import argparse
import json
from datetime import datetime
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# Add the parent directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from frontend.container_window import ContainerWindow
from frontend.config import logger

class PerformanceTest:
    """
    Automated performance test for the application.
    Runs a series of tests and reports results.
    """
    
    def __init__(self, num_transitions=20, interval_ms=1000, report_file=None):
        """
        Initialize the performance test.
        
        Args:
            num_transitions: Number of screen transitions to perform
            interval_ms: Interval between transitions in milliseconds
            report_file: File to write results to (JSON format)
        """
        self.num_transitions = num_transitions
        self.interval_ms = interval_ms
        self.report_file = report_file
        
        # Initialize state
        self.app = None
        self.window = None
        self.transitions_completed = 0
        self.transition_timer = None
        self.test_results = {
            'timestamp': datetime.now().isoformat(),
            'test_config': {
                'num_transitions': num_transitions,
                'interval_ms': interval_ms
            },
            'transitions': [],
            'memory': {
                'initial': None,
                'final': None,
                'peak': None
            },
            'cpu': {
                'avg': None,
                'peak': None
            }
        }
        
    async def run(self):
        """Run the performance test."""
        logger.info("Starting performance test")
        
        # Create Qt application
        self.app = QApplication(sys.argv)
        
        # Create container window
        self.window = ContainerWindow()
        
        # Connect to performance monitor signals
        self.window.performance_monitor.metrics_updated.connect(self.handle_metrics_updated)
        
        # Register test completion callback
        self.window.screen_manager.post_screen_change.connect(self.handle_transition_completed)
        
        # Show the window and initialize first screen
        self.window.show()
        self.window.screen_manager.initialize("clock")
        
        # Capture initial metrics after a short delay to let things settle
        QTimer.singleShot(2000, self.start_test)
        
        # Start the event loop
        return_code = await asyncio.to_thread(self.app.exec)
        
        # Generate report
        self.generate_report()
        
        return return_code
    
    def start_test(self):
        """Start the test after initial setup."""
        logger.info(f"Beginning performance test with {self.num_transitions} transitions")
        
        # Record initial metrics
        metrics = self.window.performance_monitor.get_metrics_summary()
        if metrics.get('memory_avg') is not None:
            self.test_results['memory']['initial'] = metrics['memory_avg']
        
        # Start transition timer
        self.transition_timer = QTimer()
        self.transition_timer.timeout.connect(self.perform_next_transition)
        self.transition_timer.start(self.interval_ms)
        
        # Perform first transition immediately
        self.perform_next_transition()
    
    def perform_next_transition(self):
        """Perform the next screen transition."""
        # If we've completed all transitions, finish the test
        if self.transitions_completed >= self.num_transitions:
            self.finish_test()
            return
        
        # Determine which screen to show next
        current_screen = self.window.screen_manager.current_screen_name
        next_screen = "chat" if current_screen == "clock" else "clock"
        
        # Log the transition
        logger.info(f"Transition {self.transitions_completed + 1}/{self.num_transitions}: {current_screen} -> {next_screen}")
        
        # Perform the transition
        self.window.screen_manager.show_screen(next_screen)
    
    def handle_transition_completed(self, from_screen, to_screen):
        """Handle the completion of a screen transition."""
        # Only count transitions that are part of our test
        if self.transition_timer and self.transition_timer.isActive():
            self.transitions_completed += 1
            
            # Record transition data
            transition_time = self.window.performance_monitor.current_transition_data.get('duration_ms')
            if transition_time:
                self.test_results['transitions'].append({
                    'from': from_screen,
                    'to': to_screen,
                    'duration_ms': transition_time
                })
    
    def handle_metrics_updated(self, metrics):
        """Handle updated metrics from the performance monitor."""
        # Track peak memory usage
        memory_percent = metrics.get('memory', {}).get('percent')
        if memory_percent is not None:
            if self.test_results['memory']['peak'] is None or memory_percent > self.test_results['memory']['peak']:
                self.test_results['memory']['peak'] = memory_percent
        
        # Track peak CPU usage
        cpu_percent = metrics.get('cpu', {}).get('percent')
        if cpu_percent is not None:
            if self.test_results['cpu']['peak'] is None or cpu_percent > self.test_results['cpu']['peak']:
                self.test_results['cpu']['peak'] = cpu_percent
    
    def finish_test(self):
        """Finish the performance test and clean up."""
        logger.info("Performance test completed")
        
        # Stop the transition timer
        if self.transition_timer:
            self.transition_timer.stop()
        
        # Record final metrics
        metrics = self.window.performance_monitor.get_metrics_summary()
        if metrics.get('memory_avg') is not None:
            self.test_results['memory']['final'] = metrics['memory_avg']
        
        if metrics.get('cpu_avg') is not None:
            self.test_results['cpu']['avg'] = metrics['cpu_avg']
        
        # Exit the application with a delay to ensure final metrics are recorded
        QTimer.singleShot(1000, self.app.quit)
    
    def generate_report(self):
        """Generate and save a performance report."""
        # Calculate some additional statistics
        if self.test_results['transitions']:
            durations = [t['duration_ms'] for t in self.test_results['transitions']]
            avg_duration = sum(durations) / len(durations)
            max_duration = max(durations)
            min_duration = min(durations)
            
            self.test_results['summary'] = {
                'avg_transition_time_ms': avg_duration,
                'max_transition_time_ms': max_duration,
                'min_transition_time_ms': min_duration,
                'memory_change_percent': self.test_results['memory']['final'] - self.test_results['memory']['initial'] 
                    if self.test_results['memory']['final'] is not None and self.test_results['memory']['initial'] is not None else None
            }
        
        # Print summary to console
        logger.info("--- Performance Test Results ---")
        logger.info(f"Transitions completed: {self.transitions_completed}")
        
        if 'summary' in self.test_results:
            logger.info(f"Average transition time: {self.test_results['summary']['avg_transition_time_ms']:.1f}ms")
            logger.info(f"Min/Max transition time: {self.test_results['summary']['min_transition_time_ms']:.1f}ms / {self.test_results['summary']['max_transition_time_ms']:.1f}ms")
        
        if self.test_results['memory']['initial'] is not None and self.test_results['memory']['final'] is not None:
            memory_change = self.test_results['memory']['final'] - self.test_results['memory']['initial']
            logger.info(f"Memory usage: {self.test_results['memory']['initial']:.1f}% -> {self.test_results['memory']['final']:.1f}% (change: {memory_change:+.1f}%)")
            logger.info(f"Peak memory usage: {self.test_results['memory']['peak']:.1f}%")
        
        if self.test_results['cpu']['avg'] is not None:
            logger.info(f"Average CPU usage: {self.test_results['cpu']['avg']:.1f}%")
            logger.info(f"Peak CPU usage: {self.test_results['cpu']['peak']:.1f}%")
        
        # Save report to file if requested
        if self.report_file:
            with open(self.report_file, 'w') as f:
                json.dump(self.test_results, f, indent=2)
            logger.info(f"Saved performance report to {self.report_file}")


async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Performance test for Smart Display application")
    parser.add_argument("--transitions", type=int, default=20, help="Number of transitions to perform")
    parser.add_argument("--interval", type=int, default=1000, help="Interval between transitions (ms)")
    parser.add_argument("--report", type=str, default="performance_report.json", help="Output report file")
    args = parser.parse_args()
    
    # Run the performance test
    test = PerformanceTest(
        num_transitions=args.transitions,
        interval_ms=args.interval,
        report_file=args.report
    )
    
    return await test.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(1) 