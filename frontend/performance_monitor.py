#!/usr/bin/env python3
"""
PerformanceMonitor - Tool for measuring application performance.
Used for tracking memory usage, CPU utilization, and transition smoothness.
"""

import os
import time
import psutil
import asyncio
import threading
from typing import Dict, List, Optional, Callable
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QElapsedTimer

from frontend.config import logger

class PerformanceMonitor(QObject):
    """
    Monitors application performance metrics including:
    - Memory usage
    - CPU utilization
    - Screen transition smoothness
    """
    
    # Signals
    metrics_updated = pyqtSignal(dict)  # Emits performance metrics
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Initialize state
        self.process = psutil.Process(os.getpid())
        self.monitoring_active = False
        self.metrics_history = []
        self.max_history_size = 100
        
        # Create tracking for frame times and transitions
        self.transition_timer = QElapsedTimer()
        self.frame_times = []
        self.last_frame_time = 0
        self.is_transition_active = False
        self.current_transition_data = None
        
        # Create monitoring timer
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.collect_metrics)
        self.monitoring_interval_ms = 1000  # Default to 1 second interval
        
        # Storage for callbacks to be notified about metrics
        self.metrics_callbacks = []
    
    def start_monitoring(self, interval_ms=None):
        """Start collecting performance metrics periodically"""
        if interval_ms is not None:
            self.monitoring_interval_ms = max(100, interval_ms)  # Minimum 100ms to avoid excessive CPU use
        
        logger.info(f"Starting performance monitoring with interval {self.monitoring_interval_ms}ms")
        self.monitoring_active = True
        self.monitor_timer.start(self.monitoring_interval_ms)
    
    def stop_monitoring(self):
        """Stop collecting performance metrics"""
        logger.info("Stopping performance monitoring")
        self.monitoring_active = False
        self.monitor_timer.stop()
    
    def collect_metrics(self):
        """Collect current performance metrics"""
        if not self.monitoring_active:
            return
        
        # Collect memory usage
        memory_info = self.process.memory_info()
        memory_percent = self.process.memory_percent()
        
        # Collect CPU usage (as percentage of one core)
        cpu_percent = self.process.cpu_percent()
        
        # Create metrics dictionary
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'memory': {
                'rss': memory_info.rss,  # Resident Set Size in bytes
                'vms': memory_info.vms,  # Virtual Memory Size in bytes
                'percent': memory_percent
            },
            'cpu': {
                'percent': cpu_percent
            },
            'fps': self._calculate_fps() if self.frame_times else None,
            'is_transition': self.is_transition_active
        }
        
        # Store metrics in history
        self.metrics_history.append(metrics)
        
        # Trim history if needed
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history = self.metrics_history[-self.max_history_size:]
        
        # Emit signal with metrics
        self.metrics_updated.emit(metrics)
        
        # Notify callbacks
        for callback in self.metrics_callbacks:
            try:
                callback(metrics)
            except Exception as e:
                logger.error(f"Error in metrics callback: {e}")
    
    def register_metrics_callback(self, callback: Callable[[dict], None]):
        """Register a callback to be notified when new metrics are available"""
        if callback not in self.metrics_callbacks:
            self.metrics_callbacks.append(callback)
    
    def unregister_metrics_callback(self, callback):
        """Unregister a previously registered callback"""
        if callback in self.metrics_callbacks:
            self.metrics_callbacks.remove(callback)
    
    def start_transition_timer(self, from_screen, to_screen):
        """Start timing a transition between screens"""
        self.transition_timer.start()
        self.is_transition_active = True
        self.current_transition_data = {
            'from_screen': from_screen,
            'to_screen': to_screen,
            'start_time': time.time()
        }
    
    def stop_transition_timer(self):
        """Stop timing the current transition and return the elapsed time in ms"""
        if not self.is_transition_active:
            return None
        
        elapsed_ms = self.transition_timer.elapsed()
        self.is_transition_active = False
        
        if self.current_transition_data:
            self.current_transition_data['duration_ms'] = elapsed_ms
            self.current_transition_data['end_time'] = time.time()
            
            # Log the transition data
            logger.info(f"Screen transition from {self.current_transition_data['from_screen']} "
                        f"to {self.current_transition_data['to_screen']} "
                        f"took {elapsed_ms}ms")
        
        return elapsed_ms
    
    def record_frame_time(self):
        """Record a new frame time for FPS calculation"""
        current_time = time.time()
        if self.last_frame_time > 0:
            frame_duration = current_time - self.last_frame_time
            self.frame_times.append(frame_duration)
            
            # Keep only the last 60 frame times
            if len(self.frame_times) > 60:
                self.frame_times = self.frame_times[-60:]
        
        self.last_frame_time = current_time
    
    def _calculate_fps(self):
        """Calculate current FPS based on recorded frame times"""
        if not self.frame_times:
            return 0
        
        # Calculate average frame duration
        avg_frame_duration = sum(self.frame_times) / len(self.frame_times)
        
        # Calculate FPS (avoid division by zero)
        if avg_frame_duration > 0:
            fps = 1.0 / avg_frame_duration
        else:
            fps = 0
            
        return fps
    
    def get_metrics_summary(self):
        """Get a summary of collected metrics"""
        if not self.metrics_history:
            return {
                'memory_avg': None,
                'cpu_avg': None,
                'fps_avg': None
            }
        
        # Calculate averages
        memory_values = [m['memory']['percent'] for m in self.metrics_history if 'memory' in m]
        cpu_values = [m['cpu']['percent'] for m in self.metrics_history if 'cpu' in m]
        fps_values = [m['fps'] for m in self.metrics_history if m.get('fps') is not None]
        
        summary = {
            'memory_avg': sum(memory_values) / len(memory_values) if memory_values else None,
            'memory_max': max(memory_values) if memory_values else None,
            'cpu_avg': sum(cpu_values) / len(cpu_values) if cpu_values else None,
            'cpu_max': max(cpu_values) if cpu_values else None,
            'fps_avg': sum(fps_values) / len(fps_values) if fps_values else None
        }
        
        return summary
    
    def reset_metrics(self):
        """Reset collected metrics"""
        self.metrics_history = []
        self.frame_times = []
        self.last_frame_time = 0 