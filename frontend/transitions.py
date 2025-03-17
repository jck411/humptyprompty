#!/usr/bin/env python3
"""
Transitions - Handle screen transitions in the QStackedWidget.
Provides various transition effects for smooth UI navigation.
"""

import asyncio
from enum import Enum, auto
from typing import Optional, Callable

from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QParallelAnimationGroup, 
    QSequentialAnimationGroup, QEasingCurve, QPoint, QSize, QPointF
)
from PyQt6.QtWidgets import (
    QStackedWidget, QWidget, QVBoxLayout, QLabel, QGraphicsOpacityEffect
)
from PyQt6.QtGui import QColor

# Import logger before using it
from frontend.config import logger

class TransitionType(Enum):
    """Types of transitions available for switching between screens."""
    NONE = auto()       # No animation, instant switch
    FADE = auto()       # Fade out/in
    SLIDE_LEFT = auto() # Slide from right to left
    SLIDE_RIGHT = auto() # Slide from left to right
    SLIDE_UP = auto()   # Slide from bottom to top
    SLIDE_DOWN = auto() # Slide from top to bottom
    ZOOM_IN = auto()    # Zoom in from center
    ZOOM_OUT = auto()   # Zoom out to center
    ROTATE = auto()     # Rotation effect

class ScreenTransitionManager:
    """
    Manages transitions between screens in a QStackedWidget.
    Provides different animation effects when switching between screens.
    """
    
    def __init__(self, stacked_widget: QStackedWidget):
        """Initialize the transition manager with a stacked widget."""
        self.stacked_widget = stacked_widget
        
        # Default transition settings
        self.duration = 400  # milliseconds
        self.easing_curve = QEasingCurve.Type.InOutQuad
        
        # Track animations to prevent overlapping transitions
        self.animation_group = None
        self.is_animating = False
        
        # Make sure stacked widget background is fully opaque
        self.stacked_widget.setAutoFillBackground(True)
        
        # Store solid background widget reference
        self.solid_bg_widget = None
        
        # Apply robust styling to prevent transparency
        self._apply_robust_styling()
    
    def _apply_robust_styling(self):
        """Apply robust styling to stacked widget to prevent background bleed-through"""
        # Get parent window background color - fallback to dark gray if not available
        parent_window = self.stacked_widget.window()
        bg_color = "#1a1b26"  # Default dark color
        
        if hasattr(parent_window, 'colors') and 'background' in parent_window.colors:
            bg_color = parent_window.colors['background']
        
        # Apply solid styling to stacked widget and all child widgets
        style = f"""
            QStackedWidget {{
                background-color: {bg_color};
                border: none;
            }}
            QWidget {{
                background-color: {bg_color};
            }}
        """
        self.stacked_widget.setStyleSheet(style)
    
    def set_duration(self, duration_ms: int):
        """Set the duration for all transitions in milliseconds."""
        self.duration = max(1, duration_ms)  # Ensure positive duration
    
    def set_easing_curve(self, easing_curve: QEasingCurve.Type):
        """Set the easing curve for all transitions."""
        self.easing_curve = easing_curve
    
    def transition(self, 
                  next_widget: QWidget, 
                  transition_type: TransitionType = TransitionType.FADE,
                  on_complete: Optional[Callable] = None):
        """
        Perform a transition to the specified widget with the given effect.
        
        Args:
            next_widget: The widget to transition to
            transition_type: The type of transition effect to use
            on_complete: Optional callback to run when transition completes
        """
        # This is the entry point - log everything for debugging
        logger.info(f"Starting transition to {next_widget.__class__.__name__} with type {transition_type.name}")
        
        # If we're already animating, cancel the current animation
        if self.is_animating and self.animation_group is not None:
            logger.info("Canceling current animation to start new one")
            self.animation_group.stop()
            self.animation_group = None
            self.is_animating = False
            
            # Clean up any existing solid background
            if self.solid_bg_widget is not None:
                logger.info("Cleaning up existing solid background")
                self.solid_bg_widget.deleteLater()
                self.solid_bg_widget = None
        
        # Get current widget (if any) to transition from
        current_index = self.stacked_widget.currentIndex()
        current_widget = self.stacked_widget.currentWidget() if current_index >= 0 else None
        
        # Ensure both widgets exist
        if not next_widget:
            logger.error("Next widget is None, cannot transition")
            return
        
        # Get next widget index
        next_index = self.stacked_widget.indexOf(next_widget)
        if next_index < 0:
            logger.error(f"Widget {next_widget.__class__.__name__} not found in stacked widget")
            return
        
        # If no current widget or same widget, just show immediately
        if current_widget is None or current_widget == next_widget:
            logger.info("No current widget or same widget, showing immediately")
            self.stacked_widget.setCurrentWidget(next_widget)
            if on_complete:
                on_complete()
            return
            
        # ENSURE BOTH WIDGETS HAVE OPAQUE BACKGROUNDS
        self._ensure_opaque_backgrounds(current_widget, next_widget)
        
        # Prepare for transition based on transition type
        logger.info(f"Preparing transition from {current_widget.__class__.__name__} to {next_widget.__class__.__name__}")
        
        # Execute the transition
        if transition_type == TransitionType.NONE:
            # Instant switch without animation
            self.stacked_widget.setCurrentWidget(next_widget)
            if on_complete:
                on_complete()
        elif transition_type == TransitionType.FADE:
            self._fade_transition(current_widget, next_widget)
            self._connect_animation_finished(on_complete)
        elif transition_type == TransitionType.SLIDE_LEFT:
            self._slide_transition(current_widget, next_widget, "left")
            self._connect_animation_finished(on_complete)
        elif transition_type == TransitionType.SLIDE_RIGHT:
            self._slide_transition(current_widget, next_widget, "right")
            self._connect_animation_finished(on_complete)
        elif transition_type == TransitionType.SLIDE_UP:
            self._slide_transition(current_widget, next_widget, "up")
            self._connect_animation_finished(on_complete)
        elif transition_type == TransitionType.SLIDE_DOWN:
            self._slide_transition(current_widget, next_widget, "down")
            self._connect_animation_finished(on_complete)
        elif transition_type == TransitionType.ZOOM_IN:
            self._zoom_transition(current_widget, next_widget, "in")
            self._connect_animation_finished(on_complete)
        elif transition_type == TransitionType.ZOOM_OUT:
            self._zoom_transition(current_widget, next_widget, "out")
            self._connect_animation_finished(on_complete)
        elif transition_type == TransitionType.ROTATE:
            self._rotate_transition(current_widget, next_widget)
            self._connect_animation_finished(on_complete)
        else:
            # Unknown transition type, default to immediate switch
            logger.warning(f"Unknown transition type: {transition_type}, using immediate switch")
            self.stacked_widget.setCurrentWidget(next_widget)
            if on_complete:
                on_complete()
    
    def _fade_transition(self, current_widget: QWidget, next_widget: QWidget):
        """
        Perform a fade transition between widgets.
        Fades out the current widget while fading in the next widget.
        """
        logger.info("Performing fade transition")
        
        # Create a solid background to prevent desktop visibility
        solid_bg = self._ensure_solid_background()
        
        # Ensure both widgets are visible and have the right size
        current_widget.setVisible(True)
        next_widget.setVisible(True)
        current_widget.setGeometry(0, 0, self.stacked_widget.width(), self.stacked_widget.height())
        next_widget.setGeometry(0, 0, self.stacked_widget.width(), self.stacked_widget.height())
        
        # Create opacity effects for both widgets
        current_opacity_effect = QGraphicsOpacityEffect(current_widget)
        current_opacity_effect.setOpacity(1.0)
        current_widget.setGraphicsEffect(current_opacity_effect)
        
        next_opacity_effect = QGraphicsOpacityEffect(next_widget)
        next_opacity_effect.setOpacity(0.0)
        next_widget.setGraphicsEffect(next_opacity_effect)
        
        # Create animations for fading
        fade_out = QPropertyAnimation(current_opacity_effect, b"opacity")
        fade_out.setDuration(self.duration)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(self.easing_curve)
        
        fade_in = QPropertyAnimation(next_opacity_effect, b"opacity")
        fade_in.setDuration(self.duration)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(self.easing_curve)
        
        # Create animation group
        self.animation_group = QParallelAnimationGroup()
        self.animation_group.addAnimation(fade_out)
        self.animation_group.addAnimation(fade_in)
        
        # Switch widgets halfway through the animation
        def switch_widgets(value):
            if value >= 0.5 and self.stacked_widget.currentWidget() != next_widget:
                # Bring next widget to front but keep both visible
                self.stacked_widget.setCurrentWidget(next_widget)
        
        fade_in.valueChanged.connect(switch_widgets)
        
        # Connect finished signal to cleanup
        self.animation_group.finished.connect(
            lambda: self._cleanup_after_transition(current_widget, next_widget, solid_bg)
        )
        
        # Start the animation
        self.animation_group.start()
    
    def _slide_transition(self, current_widget: QWidget, next_widget: QWidget, direction: str):
        """
        Implement slide transition between widgets.
        
        Args:
            current_widget: The currently visible widget
            next_widget: The widget to transition to
            direction: The direction to slide ("left", "right", "up", "down")
        """
        # Prepare the next widget (make sure it's added to the stacked widget)
        self.stacked_widget.addWidget(next_widget)
        
        # Get widget size
        width = self.stacked_widget.width()
        height = self.stacked_widget.height()
        
        # Position the next widget outside the visible area
        if direction == "left":
            # Next widget starts at the right edge
            next_widget.setGeometry(width, 0, width, height)
            start_pos_current = QPoint(0, 0)
            end_pos_current = QPoint(-width, 0)
            start_pos_next = QPoint(width, 0)
            end_pos_next = QPoint(0, 0)
        elif direction == "right":
            # Next widget starts at the left edge
            next_widget.setGeometry(-width, 0, width, height)
            start_pos_current = QPoint(0, 0)
            end_pos_current = QPoint(width, 0)
            start_pos_next = QPoint(-width, 0)
            end_pos_next = QPoint(0, 0)
        elif direction == "up":
            # Next widget starts at the bottom edge
            next_widget.setGeometry(0, height, width, height)
            start_pos_current = QPoint(0, 0)
            end_pos_current = QPoint(0, -height)
            start_pos_next = QPoint(0, height)
            end_pos_next = QPoint(0, 0)
        else:  # "down"
            # Next widget starts at the top edge
            next_widget.setGeometry(0, -height, width, height)
            start_pos_current = QPoint(0, 0)
            end_pos_current = QPoint(0, height)
            start_pos_next = QPoint(0, -height)
            end_pos_next = QPoint(0, 0)
        
        # Create animation for current widget
        anim_current = QPropertyAnimation(current_widget, b"pos")
        anim_current.setDuration(self.duration)
        anim_current.setStartValue(start_pos_current)
        anim_current.setEndValue(end_pos_current)
        anim_current.setEasingCurve(self.easing_curve)
        
        # Create animation for next widget
        anim_next = QPropertyAnimation(next_widget, b"pos")
        anim_next.setDuration(self.duration)
        anim_next.setStartValue(start_pos_next)
        anim_next.setEndValue(end_pos_next)
        anim_next.setEasingCurve(self.easing_curve)
        
        # Create animation group to run both animations in parallel
        self.current_animation_group = QParallelAnimationGroup()
        self.current_animation_group.addAnimation(anim_current)
        self.current_animation_group.addAnimation(anim_next)
        
        # Set up the widgets before starting the animation
        self._prepare_widgets_for_slide(current_widget, next_widget)
        
        # Clean up effects after animation finishes
        self.current_animation_group.finished.connect(
            lambda: self._cleanup_after_slide(current_widget, next_widget)
        )
        
        # Start the animation
        self.current_animation_group.start()
    
    def _zoom_transition(self, current_widget: QWidget, next_widget: QWidget, direction: str):
        """
        Implement zoom transition between widgets.
        
        Args:
            current_widget: The currently visible widget
            next_widget: The widget to transition to
            direction: The zoom direction ("in" or "out")
        """
        # Prepare the next widget (make sure it's added to the stacked widget)
        self.stacked_widget.addWidget(next_widget)
        
        # Get widget size
        width = self.stacked_widget.width()
        height = self.stacked_widget.height()
        
        # Set initial opacity for next widget
        next_effect = QGraphicsOpacityEffect(next_widget)
        next_effect.setOpacity(0.0)
        next_widget.setGraphicsEffect(next_effect)
        
        # Create opacity animation for next widget
        opacity_anim = QPropertyAnimation(next_effect, b"opacity")
        opacity_anim.setDuration(self.duration)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)
        opacity_anim.setEasingCurve(self.easing_curve)
        
        if direction == "in":
            # Zoom in: next widget starts small and grows
            next_widget.setGeometry(width // 2, height // 2, 0, 0)
            
            # Create size animation for next widget
            size_anim = QPropertyAnimation(next_widget, b"size")
            size_anim.setDuration(self.duration)
            size_anim.setStartValue(QSize(0, 0))
            size_anim.setEndValue(QSize(width, height))
            size_anim.setEasingCurve(self.easing_curve)
            
            # Create position animation to keep centered
            pos_anim = QPropertyAnimation(next_widget, b"pos")
            pos_anim.setDuration(self.duration)
            pos_anim.setStartValue(QPoint(width // 2, height // 2))
            pos_anim.setEndValue(QPoint(0, 0))
            pos_anim.setEasingCurve(self.easing_curve)
            
            # Create animation group
            self.current_animation_group = QParallelAnimationGroup()
            self.current_animation_group.addAnimation(opacity_anim)
            self.current_animation_group.addAnimation(size_anim)
            self.current_animation_group.addAnimation(pos_anim)
        else:
            # Zoom out: current widget shrinks, next widget is shown underneath
            
            # Create effect for current widget
            current_effect = QGraphicsOpacityEffect(current_widget)
            current_effect.setOpacity(1.0)
            current_widget.setGraphicsEffect(current_effect)
            
            # Create opacity animation for current widget
            current_opacity_anim = QPropertyAnimation(current_effect, b"opacity")
            current_opacity_anim.setDuration(self.duration)
            current_opacity_anim.setStartValue(1.0)
            current_opacity_anim.setEndValue(0.0)
            current_opacity_anim.setEasingCurve(self.easing_curve)
            
            # Create size animation for current widget
            size_anim = QPropertyAnimation(current_widget, b"size")
            size_anim.setDuration(self.duration)
            size_anim.setStartValue(QSize(width, height))
            size_anim.setEndValue(QSize(0, 0))
            size_anim.setEasingCurve(self.easing_curve)
            
            # Create position animation to keep centered
            pos_anim = QPropertyAnimation(current_widget, b"pos")
            pos_anim.setDuration(self.duration)
            pos_anim.setStartValue(QPoint(0, 0))
            pos_anim.setEndValue(QPoint(width // 2, height // 2))
            pos_anim.setEasingCurve(self.easing_curve)
            
            # Create animation group
            self.current_animation_group = QParallelAnimationGroup()
            self.current_animation_group.addAnimation(current_opacity_anim)
            self.current_animation_group.addAnimation(opacity_anim)
            self.current_animation_group.addAnimation(size_anim)
            self.current_animation_group.addAnimation(pos_anim)
        
        # Set up the widgets before starting the animation
        self._prepare_widgets_for_zoom(current_widget, next_widget)
        
        # Clean up effects after animation finishes
        self.current_animation_group.finished.connect(
            lambda: self._cleanup_after_transition(current_widget, next_widget)
        )
        
        # Start the animation
        self.current_animation_group.start()
    
    def _rotate_transition(self, current_widget: QWidget, next_widget: QWidget):
        """
        Implement rotate transition between widgets.
        """
        # Prepare the next widget (make sure it's added to the stacked widget)
        self.stacked_widget.addWidget(next_widget)
        
        # Set up transform effects
        current_widget.setGraphicsEffect(None)
        next_widget.setGraphicsEffect(None)
        
        # Create effect for next widget (start transparent)
        next_effect = QGraphicsOpacityEffect(next_widget)
        next_effect.setOpacity(0.0)
        next_widget.setGraphicsEffect(next_effect)
        
        # Create opacity animation for next widget
        opacity_anim = QPropertyAnimation(next_effect, b"opacity")
        opacity_anim.setDuration(self.duration)
        opacity_anim.setStartValue(0.0)
        opacity_anim.setEndValue(1.0)
        opacity_anim.setEasingCurve(self.easing_curve)
        
        # Create a rotation effect (using transformOrigin and rotation properties)
        # Note: This is simplified since QPtropertyAnimation doesn't directly support transforms
        # For a full 3D rotation effect, you would need to use QGraphicsProxyWidget with QGraphicsRotationEffect
        
        # Create animation group
        self.current_animation_group = QSequentialAnimationGroup()
        
        # Start with a fade-out of the current widget
        current_effect = QGraphicsOpacityEffect(current_widget)
        current_effect.setOpacity(1.0)
        current_widget.setGraphicsEffect(current_effect)
        
        fade_out = QPropertyAnimation(current_effect, b"opacity")
        fade_out.setDuration(self.duration // 2)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(self.easing_curve)
        
        # Then do a fade-in of the next widget
        self.current_animation_group.addAnimation(fade_out)
        self.current_animation_group.addAnimation(opacity_anim)
        
        # Set up the widgets before starting the animation
        self._prepare_widgets_for_rotate(current_widget, next_widget)
        
        # In the middle, switch to the next widget
        fade_out.finished.connect(
            lambda: self.stacked_widget.setCurrentWidget(next_widget)
        )
        
        # Clean up effects after animation finishes
        self.current_animation_group.finished.connect(
            lambda: self._cleanup_after_transition(current_widget, next_widget)
        )
        
        # Start the animation
        self.current_animation_group.start()
    
    def _prepare_widgets_for_slide(self, current_widget: QWidget, next_widget: QWidget):
        """Prepare widgets for slide animation."""
        # Make sure both widgets are visible
        current_widget.show()
        next_widget.show()
        current_widget.raise_()
        next_widget.raise_()
    
    def _cleanup_after_slide(self, current_widget: QWidget, next_widget: QWidget):
        """Clean up after slide animation."""
        # Reset geometry for both widgets
        current_widget.setGeometry(0, 0, self.stacked_widget.width(), self.stacked_widget.height())
        next_widget.setGeometry(0, 0, self.stacked_widget.width(), self.stacked_widget.height())
        
        # Set the current widget in the stacked widget
        self.stacked_widget.setCurrentWidget(next_widget)
        
        # No need to call a callback here - this was incorrectly referencing a non-existent attribute
        # Simply reset animation state
        self.is_animating = False
    
    def _prepare_widgets_for_zoom(self, current_widget: QWidget, next_widget: QWidget):
        """Prepare widgets for zoom animation."""
        # Make sure both widgets are visible
        next_widget.show()
        current_widget.show()
        current_widget.raise_()
        next_widget.lower()  # Next widget should be behind current
    
    def _prepare_widgets_for_rotate(self, current_widget: QWidget, next_widget: QWidget):
        """Prepare widgets for rotate animation."""
        # Make sure both widgets are visible
        current_widget.show()
        next_widget.show()
    
    def _ensure_opaque_backgrounds(self, current_widget: QWidget, next_widget: QWidget):
        """Ensure both widgets have opaque backgrounds to prevent bleed-through"""
        # Force both widgets to have opaque backgrounds
        for widget in [current_widget, next_widget]:
            widget.setAutoFillBackground(True)
            
            # Get background color from the widget or parent window
            bg_color = "#1a1b26"  # Default fallback color
            if hasattr(widget, 'colors') and 'background' in widget.colors:
                bg_color = widget.colors['background']
            
            # Apply solid background style
            widget.setStyleSheet(f"background-color: {bg_color};")
            
            # Disable any existing opacity effects
            if widget.graphicsEffect():
                widget.setGraphicsEffect(None)
    
    def _ensure_solid_background(self):
        """
        Create a solid background widget to prevent desktop visibility during transitions.
        Returns the created widget.
        """
        # Determine background color based on current theme
        # Try to get background color from the current widget's stylesheet
        current_widget = self.stacked_widget.currentWidget()
        background_color = "#000000"  # Default to black
        
        # Try to determine background color from current widget
        if current_widget:
            # Check if the widget has a stylesheet with background-color
            style = current_widget.styleSheet()
            if "background-color:" in style:
                # Extract background color from stylesheet
                import re
                match = re.search(r'background-color:\s*([^;]+)', style)
                if match:
                    background_color = match.group(1).strip()
            # If no background color in stylesheet, check if it's a ScreenWidget with colors
            elif hasattr(current_widget, 'colors') and 'background' in current_widget.colors:
                background_color = current_widget.colors['background']
        
        # Create a widget with solid background
        solid_bg = QWidget(self.stacked_widget)
        solid_bg.setGeometry(0, 0, self.stacked_widget.width(), self.stacked_widget.height())
        solid_bg.setStyleSheet(f"background-color: {background_color}; border: none;")
        solid_bg.setAutoFillBackground(True)
        solid_bg.lower()  # Put it behind other widgets
        solid_bg.show()
        
        return solid_bg
    
    def _cleanup_after_transition(self, current_widget: QWidget, next_widget: QWidget, solid_bg: Optional[QWidget] = None):
        """Clean up after transition animation finishes."""
        # Reset the widget stack
        self.stacked_widget.setCurrentWidget(next_widget)
        
        # Reset opacity effect if it exists
        # Check if widgets have graphicsEffect() of type QGraphicsOpacityEffect
        current_effect = current_widget.graphicsEffect()
        if current_effect and isinstance(current_effect, QGraphicsOpacityEffect):
            current_effect.setOpacity(1.0)
            
        next_effect = next_widget.graphicsEffect()
        if next_effect and isinstance(next_effect, QGraphicsOpacityEffect):
            next_effect.setOpacity(1.0)
        
        # Reset properties and graphics effects
        current_widget.setGeometry(0, 0, self.stacked_widget.width(), self.stacked_widget.height())
        next_widget.setGeometry(0, 0, self.stacked_widget.width(), self.stacked_widget.height())
        
        # Remove graphics effects - only if they exist
        if current_effect:
            current_widget.setGraphicsEffect(None)
        if next_effect:
            next_widget.setGraphicsEffect(None)
        
        # Cleanup solid background if provided
        if solid_bg is not None:
            solid_bg.deleteLater()
        
        # Reset animation state
        self.is_animating = False
    
    def _connect_animation_finished(self, callback: Optional[Callable] = None):
        """Connect the animation finished signal to the callback."""
        if callback and self.animation_group:
            self.animation_group.finished.connect(callback) 