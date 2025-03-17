<think>
Let me create a detailed outline for converting the application from multiple windows to a QStackedWidget approach. This should cover all the necessary steps, components to modify, and considerations during the transition.
</think>

# Detailed Migration Plan: Converting to QStackedWidget Architecture

## 1. Create the New Foundation Classes

### 1.1. Create Container Window (`MainContainerWindow`)
- [x] Create `container_window.py` (already done)
- [x] Implement core container functionality:
  - [x] Window sizing and appearance
  - [x] QStackedWidget setup
  - [x] Kiosk mode toggling
  - [x] Theming support
  - [x] Key event handling (ESC key)
  - [x] Screen transition animations

### 1.2. Create Base Screen Widget (`ScreenWidget`)
- [x] Base class for all screens (already done)
- [x] Key functionality to implement:
  - [x] Shared UI structure (navigation buttons, layouts)
  - [x] Theme handling
  - [x] Kiosk mode support
  - [x] Screen switching signals

### 1.3. Create Screen Manager (`ScreenManager`)
- [x] Class to manage screen lifecycle and transitions
- [x] Key functionality:
  - [x] Screen registration
  - [x] Screen instantiation and caching
  - [x] Transition handling
  - [x] Rotation handling
  - [x] Memory optimization
- [x] Integrate ScreenManager with ContainerWindow

## 2. Convert Existing Windows to Screens

### 2.1. Convert Clock Window
- [x] Create placeholder `ClockScreen` extending `ScreenWidget`
- [x] Migration tasks:
  - [x] Move layout from central widget to direct layout
  - [x] Preserve all clock display logic
  - [x] Update signal connections
  - [x] Transfer relevant methods
  - [x] Transfer any custom styling

### 2.2. Convert Chat Window
- [x] Create placeholder `ChatScreen` extending `ScreenWidget`
- [x] Migration tasks:
  - [x] Move layout from central widget to direct layout
  - [x] Preserve chat input and display functionality
  - [x] Update controller connections
  - [x] Transfer relevant methods
  - [x] Maintain styling and theme support

### 2.3. Prepare for Additional Windows/Screens
- [x] Establish pattern for converting any future windows to screens
- [x] Document the conversion process

## 3. Update Signal Routing and Communication

### 3.1. Remap Window Signals to Screen Signals
- [x] Change signal connections:
  - [x] `window_switch_requested` → `screen_switch_requested`
  - [x] `window_closed` → equivalent if needed
  - [x] `theme_changed` → connect to container window

### 3.2. Update Event Handlers
- [x] Move relevant event handlers to container window:
  - [x] `keyPressEvent` for global shortcuts
  - [x] `showEvent`/`hideEvent` equivalents for screens
  - [x] `closeEvent` handling

### 3.3. Implement Cross-Screen Communication
- [x] Design pattern for screens to communicate with each other
- [x] Consider using signals, shared manager class, or direct references

## 4. Transition Management

### 4.1. Implement Transition Animation System
- [x] Create smooth fade transitions between screens
- [x] Support for different transition types if needed
- [x] Ensure no flickering or desktop exposure during transitions

### 4.2. Handle Special Transition Cases
- [x] Initial display
- [x] Kiosk mode transitions
- [x] Theme change transitions

## 5. Memory and Resource Management

### 5.1. Implement Screen Lifecycle Management
- [x] Create `prepare()` and `cleanup()` methods for screens
- [x] Determine resource loading/unloading strategy:
  - [x] Eager loading (all screens at startup)
  - [x] Lazy loading (screens on demand)
  - [x] Resource unloading for inactive screens

### 5.2. Optimize Memory Usage
- [x] Identify memory-intensive components in screens
- [x] Implement resource cleanup for hidden screens
- [x] Consider background loading for frequently used screens

## 6. Controller and Service Integration

### 6.1. Update Chat Controller
- [x] Adapt chat controller to work with `ChatScreen` instead of `ChatWindow`
- [x] Ensure all signal connections are preserved
- [x] Maintain state management and event handling

### 6.2. Update Other Service Integrations
- [x] Audio services
- [x] Network connections
- [x] Any other external services

## 7. Entry Point and Application Flow

### 7.1. Update Application Entry Point
- [x] Create/modify main entry point to use container window
- [x] Initialize all necessary components
- [x] Handle command-line arguments if any
- [x] Add asyncio support for better resource management

### 7.2. Update Application Flow
- [x] Startup sequence
- [x] Screen rotation logic
- [x] Shutdown sequence

## 8. Testing and Refinement

### 8.1. Comprehensive Testing
- [x] Test all functionality:
  - [x] Clock display and updates
  - [x] Chat input and display
  - [x] Transitions between screens
  - [x] Kiosk mode toggling
  - [x] Theme switching

### 8.2. Performance Testing
- [x] Measure memory usage
- [x] Evaluate transition smoothness
- [x] Check CPU usage during transitions

### 8.3. Refinement
- [x] Address any issues found during testing
- [x] Optimize any slow or resource-intensive operations
- [x] Polish UI transitions and animations

## 9. Documentation

### 9.1. Update Code Documentation
- [x] Document new classes and architecture
- [x] Update existing documentation to reflect changes

### 9.2. Create Migration Notes
- [x] Document any lessons learned during migration
- [x] Create guide for handling future components

## Implementation Sequence Recommendation

1. Create the container window and base screen widget ✓
2. Convert a single window (e.g., Clock) to test the approach ✓
3. Implement basic transitions between the test screen and an empty placeholder ✓
4. Once working, convert the remaining windows one by one ✓
5. Implement memory optimization ✓
6. Refine transitions and polish ✓

This phased approach allows testing the core concepts early before doing a complete conversion.

## 10. Future Improvements and Considerations

### 10.1. Further Performance Optimizations
- [ ] Consider lazy-loading heavyweight resources
- [ ] Implement background preloading for frequently accessed screens
- [ ] Profile and optimize any remaining performance bottlenecks

### 10.2. Enhanced Transition Effects
- [x] Add support for different transition animations (slide, zoom, etc.)
- [x] Allow configurable transition speeds and effects
- [ ] Consider hardware acceleration for animations on resource-limited devices

### 10.3. Maintenance Recommendations
- [ ] Set up automated performance regression tests
- [ ] Create performance benchmarks for future comparison
- [ ] Monitor memory usage over longer periods for potential leaks

## 11. Lessons Learned

- Using QStackedWidget provides cleaner transitions than separate windows
- Memory optimization is essential when dealing with multiple screens
- Performance monitoring helps identify issues early
- Consistent base class structure simplifies conversion and maintenance
- Event-driven screen changing is more maintainable than direct function calls

## 12. Enhanced Transition System Documentation

### 12.1. Available Transition Types
- **NONE**: Instant switch with no animation
- **FADE**: Smooth fade between screens
- **SLIDE_LEFT**: Slide from right to left
- **SLIDE_RIGHT**: Slide from left to right
- **SLIDE_UP**: Slide from bottom to top
- **SLIDE_DOWN**: Slide from top to bottom
- **ZOOM_IN**: Zoom in from center
- **ZOOM_OUT**: Zoom out to center
- **ROTATE**: Simple rotation effect

### 12.2. Using Transitions
- Use keyboard shortcuts (Ctrl+1 through Ctrl+9) to quickly change transition types
- Use Alt+T to open transition settings dialog
- Right-click anywhere for context menu with transition options
- Customize duration and easing curve in settings dialog

### 12.3. Implementing Custom Transitions
To implement a new transition type:
1. Add the new type to `TransitionType` enum in `transitions.py`
2. Create a new private method in `ScreenTransitionManager` for the transition
3. Add the type to the `transition()` method's logic
