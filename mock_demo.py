#!/usr/bin/env python3
"""
Mock Robot Demo - Movement Pattern with Obstacle Avoidance
Demonstrates: Forward → Turn Right → Turn Left → Return to Start
Perfect for university demo video!
"""

import time
import math
import threading
from dataclasses import dataclass
from typing import Tuple
from enum import Enum


class RobotState(Enum):
    """Robot movement states"""
    IDLE = "IDLE"
    MOVING_FORWARD = "MOVING_FORWARD"
    TURNING_RIGHT = "TURNING_RIGHT"
    TURNING_LEFT = "TURNING_LEFT"
    MOVING_BACKWARD = "MOVING_BACKWARD"
    OBSTACLE_DETECTED = "OBSTACLE_DETECTED"
    RECOVERING = "RECOVERING"


@dataclass
class Position:
    """Robot position and orientation"""
    x: float = 0.0  # meters
    y: float = 0.0  # meters
    heading: float = 0.0  # degrees (0=North, 90=East, 180=South, 270=West)
    
    def __str__(self):
        return f"Pos({self.x:.2f}m, {self.y:.2f}m) Heading:{self.heading:.1f}°"


class MockGPS:
    """Simulates GPS sensor"""
    def __init__(self):
        self.position = Position()
    
    def get_position(self) -> Position:
        return Position(self.position.x, self.position.y, self.position.heading)
    
    def update(self, x: float, y: float, heading: float):
        self.position.x = x
        self.position.y = y
        self.position.heading = heading


class MockIMU:
    """Simulates IMU sensor (gyro + accelerometer)"""
    def __init__(self):
        self.heading = 0.0  # degrees
        self.roll = 0.0
        self.pitch = 0.0
    
    def get_heading(self) -> float:
        """Returns current heading (0-360 degrees)"""
        return self.heading % 360
    
    def update_heading(self, delta: float):
        """Update heading (positive = clockwise)"""
        self.heading = (self.heading + delta) % 360
    
    def __str__(self):
        return f"IMU - Heading: {self.get_heading():.1f}°"


class MockLiDAR:
    """Simulates LiDAR obstacle detection"""
    def __init__(self):
        self.min_distance = 100.0  # meters
        self.obstacle_detected = False
        self.closest_obstacle_angle = None
    
    def scan(self, position: Position) -> Tuple[bool, float]:
        """Returns: (obstacle_detected, min_distance)"""
        # Simulate obstacles at demo positions
        obstacles = [
            {"x": 2.5, "y": 1.0, "radius": 0.5},
            {"x": 2.5, "y": -1.0, "radius": 0.5},
        ]
        
        min_dist = 100.0
        
        for obstacle in obstacles:
            dx = obstacle["x"] - position.x
            dy = obstacle["y"] - position.y
            dist = math.sqrt(dx**2 + dy**2) - obstacle["radius"]
            
            if dist < min_dist:
                min_dist = dist
        
        self.min_distance = min_dist
        self.obstacle_detected = min_dist < 1.5
        
        return self.obstacle_detected, min_dist
    
    def __str__(self):
        status = "🚨 OBSTACLE!" if self.obstacle_detected else "✓ Clear"
        return f"LiDAR - {status} (min: {self.min_distance:.2f}m)"


class MockMotorController:
    """Simulates ESP32 motor controller"""
    def __init__(self):
        self.left_speed = 0.0
        self.right_speed = 0.0
        self.left_rpm = 0
        self.right_rpm = 0
        self.temperature = 35.0
        self.wheelbase = 0.3
    
    def set_speed(self, left_speed: float, right_speed: float):
        """Set motor speeds (-1.5 to +1.5 m/s)"""
        self.left_speed = max(-1.5, min(1.5, left_speed))
        self.right_speed = max(-1.5, min(1.5, right_speed))
        self.left_rpm = int(abs(self.left_speed) * 100)
        self.right_rpm = int(abs(self.right_speed) * 100)
    
    def stop(self):
        """Emergency stop"""
        self.left_speed = 0.0
        self.right_speed = 0.0
        self.left_rpm = 0
        self.right_rpm = 0
    
    def __str__(self):
        return f"Motors - L:{self.left_speed:.2f}m/s R:{self.right_speed:.2f}m/s T:{self.temperature:.1f}°C"


class MockRobot:
    """Main robot controller with obstacle avoidance"""
    
    def __init__(self):
        self.gps = MockGPS()
        self.imu = MockIMU()
        self.lidar = MockLiDAR()
        self.motors = MockMotorController()
        
        self.state = RobotState.IDLE
        self.start_position = Position(0.0, 0.0, 0.0)
        self.demo_running = False
        self.dt = 0.1
    
    def update_position(self, dt: float):
        """Update robot position based on motor speeds"""
        v_forward = (self.motors.left_speed + self.motors.right_speed) / 2
        v_turn = (self.motors.right_speed - self.motors.left_speed) / (2 * self.motors.wheelbase)
        
        self.imu.update_heading(v_turn * dt * 180 / math.pi)
        
        if abs(v_forward) > 0.01:
            heading_rad = self.imu.get_heading() * math.pi / 180
            self.gps.position.x += v_forward * math.cos(heading_rad) * dt
            self.gps.position.y += v_forward * math.sin(heading_rad) * dt
        
        self.gps.position.heading = self.imu.get_heading()
    
    def check_obstacles(self) -> bool:
        """Check for obstacles with LiDAR"""
        obstacle_detected, min_dist = self.lidar.scan(self.gps.position)
        
        if obstacle_detected:
            print(f"⚠️  OBSTACLE DETECTED at {min_dist:.2f}m")
            return True
        return False
    
    def move_forward(self, distance: float, speed: float = 0.8):
        """Move forward by distance meters"""
        print(f"→ Moving forward {distance}m at {speed}m/s...")
        self.state = RobotState.MOVING_FORWARD
        
        start_x = self.gps.position.x
        start_y = self.gps.position.y
        
        while True:
            if self.check_obstacles():
                self.state = RobotState.OBSTACLE_DETECTED
                self.motors.stop()
                print("🛑 OBSTACLE! Stopping...")
                time.sleep(1.0)
                self.state = RobotState.RECOVERING
                continue
            
            dx = self.gps.position.x - start_x
            dy = self.gps.position.y - start_y
            distance_traveled = math.sqrt(dx**2 + dy**2)
            
            if distance_traveled >= distance:
                break
            
            self.motors.set_speed(speed, speed)
            self.update_position(self.dt)
            time.sleep(self.dt)
        
        self.motors.stop()
        print(f"✓ Position: {self.gps.position}")
    
    def turn(self, angle_degrees: float, speed: float = 0.5):
        """Turn by angle degrees (positive = right/clockwise)"""
        direction = "right ↻" if angle_degrees > 0 else "left ↺"
        print(f"↻ Turning {direction} {abs(angle_degrees):.1f}°...")
        self.state = RobotState.TURNING_RIGHT if angle_degrees > 0 else RobotState.TURNING_LEFT
        
        start_heading = self.imu.get_heading()
        target_heading = (start_heading + angle_degrees) % 360
        
        while True:
            current_heading = self.imu.get_heading()
            error = target_heading - current_heading
            if error > 180:
                error -= 360
            elif error < -180:
                error += 360
            
            if abs(error) < 2.0:
                break
            
            if angle_degrees > 0:
                self.motors.set_speed(speed, -speed)
            else:
                self.motors.set_speed(-speed, speed)
            
            self.update_position(self.dt)
            time.sleep(self.dt)
        
        self.motors.stop()
        print(f"✓ Heading: {self.imu.get_heading():.1f}°")
    
    def move_backward(self, distance: float, speed: float = 0.6):
        """Move backward by distance meters"""
        print(f"← Moving backward {distance}m at {speed}m/s...")
        self.state = RobotState.MOVING_BACKWARD
        
        start_x = self.gps.position.x
        start_y = self.gps.position.y
        
        while True:
            dx = self.gps.position.x - start_x
            dy = self.gps.position.y - start_y
            distance_traveled = math.sqrt(dx**2 + dy**2)
            
            if distance_traveled >= distance:
                break
            
            self.motors.set_speed(-speed, -speed)
            self.update_position(self.dt)
            time.sleep(self.dt)
        
        self.motors.stop()
        print(f"✓ Position: {self.gps.position}")
    
    def demo_pattern(self):
        """University demo pattern"""
        print("\n" + "="*70)
        print("🎬 AUTONOMOUS FOOD DELIVERY ROBOT - DEMO")
        print("="*70 + "\n")
        
        print("📍 START: ", self.gps.position)
        self.start_position = Position(self.gps.position.x, self.gps.position.y, self.gps.position.heading)
        
        try:
            print("\n[1/7] FORWARD →")
            self.move_forward(3.0, 0.8)
            time.sleep(0.5)
            
            print("\n[2/7] TURN RIGHT ↻")
            self.turn(90, 0.5)
            time.sleep(0.5)
            
            print("\n[3/7] FORWARD →")
            self.move_forward(2.0, 0.8)
            time.sleep(0.5)
            
            print("\n[4/7] TURN LEFT ↺ (180°)")
            self.turn(-180, 0.5)
            time.sleep(0.5)
            
            print("\n[5/7] FORWARD →")
            self.move_forward(2.0, 0.8)
            time.sleep(0.5)
            
            print("\n[6/7] TURN RIGHT ↻")
            self.turn(90, 0.5)
            time.sleep(0.5)
            
            print("\n[7/7] RETURN ←")
            self.move_backward(3.0, 0.8)
            time.sleep(0.5)
            
            print("\n[FINAL] ALIGN")
            self.turn(-90, 0.5)
            
            print("\n" + "="*70)
            print("✅ DEMO COMPLETE!")
            print("="*70)
            print(f"📍 FINAL: {self.gps.position}")
            print(f"📍 START: {self.start_position}")
            
            pos_error = math.sqrt(
                (self.gps.position.x - self.start_position.x)**2 +
                (self.gps.position.y - self.start_position.y)**2
            )
            heading_error = abs(self.gps.position.heading - self.start_position.heading)
            
            print(f"\n📊 ACCURACY:")
            print(f"   Position: {pos_error:.3f}m error")
            print(f"   Heading: {heading_error:.1f}° error")
            print(f"   Temperature: {self.motors.temperature:.1f}°C")
            
        except KeyboardInterrupt:
            print("\n❌ Demo interrupted!")
            self.motors.stop()
    
    def telemetry_thread(self):
        """Print telemetry every second"""
        while self.demo_running:
            print(f"\n📡 {self.motors} | {self.imu} | {self.lidar} | {self.gps.position}")
            time.sleep(1.0)
    
    def run_demo(self):
        """Run full demo with telemetry"""
        self.demo_running = True
        
        telemetry = threading.Thread(target=self.telemetry_thread, daemon=True)
        telemetry.start()
        
        try:
            self.demo_pattern()
        finally:
            self.demo_running = False
            self.motors.stop()


def main():
    print("\n🤖 Autonomous Food Delivery Robot - Mock Demo for University Video")
    print("=" * 70)
    print("Features demonstrated:")
    print("  ✓ Forward movement with obstacle avoidance")
    print("  ✓ Right/Left turning")
    print("  ✓ Return to starting position")
    print("  ✓ Real-time telemetry")
    print("=" * 70 + "\n")
    
    robot = MockRobot()
    input("Press ENTER to start demo (Ctrl+C to abort)...\n")
    robot.run_demo()


if __name__ == "__main__":
    main()
