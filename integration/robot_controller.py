#!/usr/bin/env python3
"""
Main Robot Controller - Full Integration
Coordinates all systems: GPS, IMU, Motors, Communication
"""

import sys
import time
import argparse
import math
from enum import Enum

# Import custom modules
sys.path.insert(0, '/home/pi/food-delivery-robot')

from pi4_ros2.gps_reader import GPSReader, GPSData
from pi4_ros2.imu_reader import MPU6050, IMUData
from integration.esp32_pi_comm import ESP32Communicator, MotorFeedback
from integration.speed_controller import SpeedController, SpeedMode, MotorSpeeds

class MissionState(Enum):
    """Robot mission states"""
    IDLE = 0
    NAVIGATING_TO_DELIVERY = 1
    ARRIVED_AT_DELIVERY = 2
    NAVIGATING_TO_START = 3
    COMPLETE = 4

class RobotController:
    def __init__(self, restaurant_lat: float, restaurant_lon: float,
                 delivery_lat: float, delivery_lon: float,
                 control_rate: int = 10):
        """
        Initialize robot controller
        
        Args:
            restaurant_lat/lon: Starting location (restaurant)
            delivery_lat/lon: Delivery location
            control_rate: Control loop rate in Hz
        """
        self.restaurant_lat = restaurant_lat
        self.restaurant_lon = restaurant_lon
        self.delivery_lat = delivery_lat
        self.delivery_lon = delivery_lon
        self.control_rate = control_rate
        self.dt = 1.0 / control_rate
        
        # Components
        self.gps = GPSReader()
        self.imu = MPU6050()
        self.comm = ESP32Communicator()
        self.speed_controller = SpeedController()
        
        # State
        self.mission_state = MissionState.IDLE
        self.current_target = None
        self.arrival_tolerance = 3.0  # meters
        self.obstacle_detected = False
        
        # Statistics
        self.start_time = 0
        self.waypoint_distance_total = 0
        self.waypoint_distance_current = 0
        
        print("🤖 Autonomous Delivery Robot Initialized")
    
    def setup(self) -> bool:
        """Setup all hardware components"""
        print("\n⚙️ Setting up hardware...\n")
        
        # GPS setup
        print("📍 GPS Setup")
        if not self.gps.connect():
            print("  ✗ GPS connection failed")
            return False
        self.gps.start()
        time.sleep(1)
        
        # IMU setup
        print("🎯 IMU Setup")
        if not self.imu.initialize():
            print("  ✗ IMU initialization failed")
            return False
        imu_initialized = True
        try:
            self.imu.calibrate(samples=100)
            self.imu.start()
        except Exception as e:
            print(f"  ⚠ IMU calibration warning: {e}")
        
        # ESP32 communication setup
        print("⚡ ESP32 Communication Setup")
        if not self.comm.connect():
            print("  ✗ ESP32 connection failed")
            return False
        self.comm.start()
        time.sleep(1)
        
        print("\n✅ Hardware setup complete!\n")
        return True
    
    def start_mission(self):
        """Start autonomous delivery mission"""
        print("\n🚀 Starting delivery mission...\n")
        self.start_time = time.time()
        self.mission_state = MissionState.NAVIGATING_TO_DELIVERY
        self.current_target = (self.delivery_lat, self.delivery_lon)
        
        self.waypoint_distance_total = self.gps.distance_to(self.delivery_lat, self.delivery_lon)
        print(f"Distance to delivery: {self.waypoint_distance_total:.1f}m\n")
    
    def update_gps_status(self):
        """Print GPS status"""
        gps_data = self.gps.get_data()
        if self.gps.is_valid():
            print(f"  📍 GPS: {gps_data.latitude:.6f}°, {gps_data.longitude:.6f}° "
                  f"({gps_data.satellites} sats, HDOP={gps_data.hdop:.1f})")
        else:
            print(f"  📍 GPS: SEARCHING ({gps_data.satellites} sats)")
    
    def update_imu_status(self):
        """Print IMU status"""
        imu_data = self.imu.get_data()
        print(f"  🎯 IMU: Heading={imu_data.yaw:.1f}°, Pitch={imu_data.pitch:.1f}°, "
              f"Roll={imu_data.roll:.1f}° ({imu_data.temperature:.0f}°C)")
    
    def update_motor_status(self):
        """Print motor status"""
        feedback = self.comm.get_feedback()
        speed_left = self.comm.rpm_to_speed(feedback.rpm_left)
        speed_right = self.comm.rpm_to_speed(feedback.rpm_right)
        print(f"  ⚡ Motors: L={speed_left:.2f} m/s, R={speed_right:.2f} m/s "
              f"({feedback.rpm_left:.0f},{feedback.rpm_right:.0f} RPM, {feedback.temperature:.0f}°C)")
    
    def control_loop(self):
        """Main control loop"""
        while self.mission_state != MissionState.COMPLETE:
            loop_start = time.time()
            
            # Get current state
            gps_data = self.gps.get_data()
            imu_data = self.imu.get_data()
            
            # Update motor commands based on mission state
            motor_speeds = self.execute_state()
            
            # Send motor commands
            self.comm.set_motor_speed(motor_speeds.left, motor_speeds.right)
            
            # Print status every 2 seconds
            if int(time.time()) % 2 == 0:
                elapsed = time.time() - self.start_time
                print(f"\n⏱️  Time: {int(elapsed)}s | State: {self.mission_state.name}")
                self.update_gps_status()
                self.update_imu_status()
                self.update_motor_status()
            
            # Maintain control rate
            elapsed = time.time() - loop_start
            sleep_time = max(0, self.dt - elapsed)
            time.sleep(sleep_time)
    
    def execute_state(self) -> MotorSpeeds:
        """Execute current mission state, return motor speeds"""
        if self.mission_state == MissionState.IDLE:
            return self.speed_controller.stop()
        
        elif self.mission_state == MissionState.NAVIGATING_TO_DELIVERY:
            return self.navigate_to_waypoint(self.delivery_lat, self.delivery_lon)
        
        elif self.mission_state == MissionState.ARRIVED_AT_DELIVERY:
            print("\n✅ Arrived at delivery location!")
            print("   Waiting 5 seconds before returning...\n")
            time.sleep(5)
            self.mission_state = MissionState.NAVIGATING_TO_START
            self.current_target = (self.restaurant_lat, self.restaurant_lon)
            self.waypoint_distance_total = self.gps.distance_to(self.restaurant_lat, self.restaurant_lon)
            return self.speed_controller.stop()
        
        elif self.mission_state == MissionState.NAVIGATING_TO_START:
            return self.navigate_to_waypoint(self.restaurant_lat, self.restaurant_lon)
        
        elif self.mission_state == MissionState.COMPLETE:
            print("\n✅ Mission complete! Robot returned to restaurant.\n")
            return self.speed_controller.stop()
        
        return self.speed_controller.stop()
    
    def navigate_to_waypoint(self, target_lat: float, target_lon: float) -> MotorSpeeds:
        """Navigate to target waypoint"""
        gps_data = self.gps.get_data()
        imu_data = self.imu.get_data()
        
        # Check if we've reached the waypoint
        distance_to_target = self.gps.distance_to(target_lat, target_lon)
        
        if distance_to_target < self.arrival_tolerance and self.gps.is_valid():
            if self.mission_state == MissionState.NAVIGATING_TO_DELIVERY:
                self.mission_state = MissionState.ARRIVED_AT_DELIVERY
            elif self.mission_state == MissionState.NAVIGATING_TO_START:
                self.mission_state = MissionState.COMPLETE
            return self.speed_controller.stop()
        
        # Calculate desired bearing to target
        bearing_to_target = self.gps.bearing_to(target_lat, target_lon)
        
        # Heading error: positive = turn right, negative = turn left
        heading_error = bearing_to_target - imu_data.yaw
        
        # Normalize to ±180
        heading_error = ((heading_error + 180) % 360) - 180
        
        # Choose speed based on heading alignment
        if abs(heading_error) < 15:  # Well aligned
            speed_mode = SpeedMode.CRUISE
        elif abs(heading_error) < 45:  # Moderately aligned
            speed_mode = SpeedMode.SLOW
        else:  # Badly aligned, turn more
            speed_mode = SpeedMode.SLOW
        
        # Get motor speeds with heading correction
        motor_speeds = self.speed_controller.turn_while_moving(heading_error, speed_mode)
        
        return motor_speeds
    
    def shutdown(self):
        """Shutdown all systems"""
        print("\n🛑 Shutting down...\n")
        self.comm.set_motor_speed(0, 0)
        time.sleep(0.5)
        self.comm.stop()
        self.imu.stop()
        self.gps.stop()
        print("✅ Shutdown complete\n")


def main():
    parser = argparse.ArgumentParser(description="Autonomous Delivery Robot")
    parser.add_argument('--restaurant-lat', type=float, default=30.0199, help='Restaurant latitude')
    parser.add_argument('--restaurant-lon', type=float, default=31.2299, help='Restaurant longitude')
    parser.add_argument('--delivery-lat', type=float, default=30.0250, help='Delivery latitude')
    parser.add_argument('--delivery-lon', type=float, default=31.2350, help='Delivery longitude')
    parser.add_argument('--rate', type=int, default=10, help='Control loop rate (Hz)')
    
    args = parser.parse_args()
    
    # Create controller
    robot = RobotController(
        restaurant_lat=args.restaurant_lat,
        restaurant_lon=args.restaurant_lon,
        delivery_lat=args.delivery_lat,
        delivery_lon=args.delivery_lon,
        control_rate=args.rate
    )
    
    try:
        # Setup hardware
        if not robot.setup():
            print("❌ Setup failed!")
            return 1
        
        # Wait for GPS lock
        print("⏳ Waiting for GPS lock...")
        while not robot.gps.is_valid():
            gps_data = robot.gps.get_data()
            print(f"  GPS: {gps_data.satellites} satellites, HDOP={gps_data.hdop:.1f}")
            time.sleep(1)
        
        print("✅ GPS locked!\n")
        
        # Start mission
        robot.start_mission()
        
        # Run control loop
        robot.control_loop()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    finally:
        robot.shutdown()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
