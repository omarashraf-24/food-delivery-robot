#!/usr/bin/env python3
"""
Speed Controller - Differential Drive Motor Control
Converts desired heading + speed into left/right motor commands
"""

import math
from enum import Enum
from dataclasses import dataclass

class SpeedMode(Enum):
    """Speed profiles"""
    STOP = 0
    SLOW = 0.5  # m/s
    CRUISE = 0.8  # m/s
    FAST = 1.2  # m/s

@dataclass
class MotorSpeeds:
    """Left and right motor speeds"""
    left: float = 0  # m/s
    right: float = 0  # m/s

class SpeedController:
    """Differential drive speed controller"""
    
    def __init__(self, max_speed: float = 1.5, max_turning_speed: float = 0.8):
        self.max_speed = max_speed
        self.max_turning_speed = max_turning_speed
        
        # PID for heading control
        self.heading_kp = 0.01  # Proportional gain
        self.heading_ki = 0  # Integral gain
        self.heading_kd = 0.02  # Derivative gain
        
        self.heading_error_prev = 0
        self.heading_error_integral = 0
    
    def stop(self) -> MotorSpeeds:
        """Stop motors"""
        return MotorSpeeds(0, 0)
    
    def move_forward(self, speed_ms: float, max_speed: float = None) -> MotorSpeeds:
        """
        Move forward at constant speed
        
        Args:
            speed_ms: Desired speed in m/s
            max_speed: Maximum speed limit
        
        Returns:
            Motor speeds
        """
        if max_speed is None:
            max_speed = self.max_speed
        
        speed_ms = max(-max_speed, min(max_speed, speed_ms))
        return MotorSpeeds(speed_ms, speed_ms)
    
    def turn_in_place(self, heading_error: float, speed_factor: float = 0.5) -> MotorSpeeds:
        """
        Turn in place to correct heading
        
        Args:
            heading_error: Desired heading minus current heading (degrees)
                Positive = turn right, negative = turn left
            speed_factor: Speed factor (0-1)
        
        Returns:
            Motor speeds for turning
        """
        # Normalize heading error to ±180
        heading_error = ((heading_error + 180) % 360) - 180
        
        # Calculate turn speed
        turn_speed = min(abs(heading_error) / 45.0, 1.0) * self.max_turning_speed * speed_factor
        
        if heading_error > 0:
            # Turn right
            return MotorSpeeds(-turn_speed, turn_speed)
        else:
            # Turn left
            return MotorSpeeds(turn_speed, -turn_speed)
    
    def turn_while_moving(self, heading_error: float, speed_mode: SpeedMode) -> MotorSpeeds:
        """
        Turn while moving forward (differential steering)
        
        Args:
            heading_error: Desired heading minus current heading (degrees)
            speed_mode: Speed profile to use
        
        Returns:
            Motor speeds for differential steering
        """
        # Normalize heading error to ±180
        heading_error = ((heading_error + 180) % 360) - 180
        
        # Base forward speed
        base_speed = speed_mode.value if isinstance(speed_mode.value, float) else 0.8
        
        # Calculate steering correction (0 to 1)
        # More heading error = more steering
        steering_factor = max(0, min(1, abs(heading_error) / 90.0))
        
        if heading_error > 0:
            # Turn right: reduce left motor, increase right motor
            left_speed = base_speed * (1 - steering_factor * 0.5)
            right_speed = base_speed * (1 + steering_factor * 0.3)
        else:
            # Turn left: reduce right motor, increase left motor
            left_speed = base_speed * (1 + steering_factor * 0.3)
            right_speed = base_speed * (1 - steering_factor * 0.5)
        
        return MotorSpeeds(left_speed, right_speed)
    
    def curved_path(self, heading_error: float, forward_speed: float, 
                   curvature: float = 0.5) -> MotorSpeeds:
        """
        Follow curved path with desired forward speed and heading
        
        Args:
            heading_error: Heading error (degrees)
            forward_speed: Desired forward speed (m/s)
            curvature: Turning aggressiveness (0-1)
        
        Returns:
            Motor speeds
        """
        # Normalize heading error
        heading_error = ((heading_error + 180) % 360) - 180
        
        # Base speed
        speed_ms = max(-self.max_speed, min(self.max_speed, forward_speed))
        
        # Steering correction
        steering = (heading_error / 180.0) * curvature
        steering = max(-0.5, min(0.5, steering))
        
        # Differential steering
        left_speed = speed_ms * (1 - abs(steering))
        right_speed = speed_ms * (1 + abs(steering))
        
        if steering < 0:
            # Turn left
            left_speed = speed_ms * (1 + abs(steering))
            right_speed = speed_ms * (1 - abs(steering))
        
        return MotorSpeeds(left_speed, right_speed)
