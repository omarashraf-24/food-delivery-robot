#!/usr/bin/env python3
"""
ESP32 Communicator - USB Serial Protocol
Handles USB communication between Pi4 and ESP32
"""

import serial
import threading
import time
from dataclasses import dataclass

@dataclass
class MotorFeedback:
    """Motor feedback from ESP32"""
    rpm_left: float = 0
    rpm_right: float = 0
    temperature: float = 0
    timestamp: float = 0

class ESP32Communicator:
    """USB serial communication with ESP32"""
    
    # Motor RPM to speed conversion
    WHEEL_DIAMETER = 0.165  # meters (6.5 inches)
    WHEEL_CIRCUMFERENCE = 3.14159 * WHEEL_DIAMETER
    
    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.running = False
        self.read_thread = None
        
        self.feedback = MotorFeedback()
        self.lock = threading.Lock()
        
        self.last_cmd_left = 0
        self.last_cmd_right = 0
    
    def connect(self) -> bool:
        """Connect to ESP32 via USB"""
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(0.5)  # Wait for ESP32 to be ready
            print(f"  ✅ ESP32 connected on {self.port}")
            return True
        except Exception as e:
            print(f"  ✗ ESP32 connection failed: {e}")
            return False
    
    def start(self):
        """Start reading feedback"""
        self.running = True
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        print("  ✅ ESP32 communication started")
    
    def stop(self):
        """Stop communication"""
        self.running = False
        self.set_motor_speed(0, 0)
        time.sleep(0.2)
        if self.read_thread:
            self.read_thread.join(timeout=2)
        if self.serial:
            self.serial.close()
        print("  ✅ ESP32 communication stopped")
    
    def set_motor_speed(self, speed_left: float, speed_right: float) -> bool:
        """
        Send motor speed commands to ESP32
        
        Args:
            speed_left: Left motor speed in m/s (-1.5 to +1.5)
            speed_right: Right motor speed in m/s (-1.5 to +1.5)
        
        Returns:
            True if sent successfully
        """
        if not self.serial:
            return False
        
        # Clamp speeds
        speed_left = max(-1.5, min(1.5, speed_left))
        speed_right = max(-1.5, min(1.5, speed_right))
        
        try:
            # Format: LEFT_SPEED,RIGHT_SPEED\n
            cmd = f"{speed_left:.2f},{speed_right:.2f}\n"
            self.serial.write(cmd.encode())
            
            with self.lock:
                self.last_cmd_left = speed_left
                self.last_cmd_right = speed_right
            
            return True
        except Exception as e:
            print(f"  ✗ Motor command failed: {e}")
            return False
    
    def _read_loop(self):
        """Background thread: read motor feedback"""
        while self.running:
            try:
                if self.serial and self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        self._parse_feedback(line)
            except Exception as e:
                pass
            
            time.sleep(0.01)
    
    def _parse_feedback(self, line: str):
        """Parse feedback from ESP32"""
        try:
            # Format: RPM_LEFT,RPM_RIGHT,TEMP\n
            parts = line.split(',')
            if len(parts) >= 3:
                rpm_left = float(parts[0])
                rpm_right = float(parts[1])
                temp = float(parts[2])
                
                with self.lock:
                    self.feedback.rpm_left = rpm_left
                    self.feedback.rpm_right = rpm_right
                    self.feedback.temperature = temp
                    self.feedback.timestamp = time.time()
        except Exception as e:
            pass
    
    def get_feedback(self) -> MotorFeedback:
        """Get latest motor feedback"""
        with self.lock:
            return MotorFeedback(
                rpm_left=self.feedback.rpm_left,
                rpm_right=self.feedback.rpm_right,
                temperature=self.feedback.temperature,
                timestamp=self.feedback.timestamp
            )
    
    def rpm_to_speed(self, rpm: float) -> float:
        """Convert RPM to m/s"""
        return (rpm * self.WHEEL_CIRCUMFERENCE) / 60
    
    def speed_to_rpm(self, speed_ms: float) -> float:
        """Convert m/s to RPM"""
        if speed_ms == 0:
            return 0
        return (speed_ms / self.WHEEL_CIRCUMFERENCE) * 60
