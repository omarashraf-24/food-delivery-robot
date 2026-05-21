#!/usr/bin/env python3
"""
IMU Reader - MPU6050 I2C Module
Reads accelerometer, gyroscope, temperature from Pi4 I2C
"""

import smbus2
import math
import threading
import time
from dataclasses import dataclass

@dataclass
class IMUData:
    """IMU sensor data"""
    accel_x: float = 0  # m/s²
    accel_y: float = 0
    accel_z: float = 0
    gyro_x: float = 0  # degrees/s
    gyro_y: float = 0
    gyro_z: float = 0
    temperature: float = 0  # Celsius
    yaw: float = 0  # degrees (rotation around Z axis)
    pitch: float = 0  # degrees (rotation around Y axis)
    roll: float = 0  # degrees (rotation around X axis)
    timestamp: float = 0

class MPU6050:
    """MPU6050 IMU sensor on I2C"""
    
    # I2C address
    MPU6050_ADDR = 0x68
    
    # Register addresses
    PWR_MGMT_1 = 0x6B
    ACCEL_XOUT_H = 0x3B
    GYRO_XOUT_H = 0x43
    TEMP_OUT_H = 0x41
    ACCEL_CONFIG = 0x1C
    GYRO_CONFIG = 0x1B
    
    # Calibration values (will be set during init)
    ACCEL_RANGE = 2  # g (±2, ±4, ±8, ±16)
    GYRO_RANGE = 250  # dps (±250, ±500, ±1000, ±2000)
    
    def __init__(self, bus: int = 1):
        self.bus_num = bus
        self.bus = None
        self.running = False
        self.read_thread = None
        
        self.data = IMUData()
        self.lock = threading.Lock()
        
        # Calibration offsets
        self.accel_offset = [0, 0, 0]
        self.gyro_offset = [0, 0, 0]
        
        # Complementary filter state
        self.last_time = 0
        self.alpha = 0.98  # Complementary filter coefficient
    
    def initialize(self) -> bool:
        """Initialize MPU6050"""
        try:
            self.bus = smbus2.SMBus(self.bus_num)
            
            # Wake up device
            self.bus.write_byte_data(self.MPU6050_ADDR, self.PWR_MGMT_1, 0x00)
            time.sleep(0.1)
            
            # Set accelerometer range (±2g)
            self.bus.write_byte_data(self.MPU6050_ADDR, self.ACCEL_CONFIG, 0x00)
            
            # Set gyroscope range (±250 dps)
            self.bus.write_byte_data(self.MPU6050_ADDR, self.GYRO_CONFIG, 0x00)
            
            time.sleep(0.1)
            print("  ✅ MPU6050 initialized")
            return True
        except Exception as e:
            print(f"  ✗ MPU6050 init failed: {e}")
            return False
    
    def calibrate(self, samples: int = 100):
        """Calibrate gyro and accel offsets"""
        print(f"  📏 Calibrating MPU6050 ({samples} samples)...")
        
        accel_sum = [0, 0, 0]
        gyro_sum = [0, 0, 0]
        
        for i in range(samples):
            accel, gyro, temp = self._read_raw()
            for j in range(3):
                accel_sum[j] += accel[j]
                gyro_sum[j] += gyro[j]
            time.sleep(0.01)
        
        # Average is the offset
        for j in range(3):
            self.accel_offset[j] = accel_sum[j] / samples
            self.gyro_offset[j] = gyro_sum[j] / samples
        
        print(f"  ✅ Calibration complete")
        print(f"     Accel offset: {[f'{x:.2f}' for x in self.accel_offset]}")
        print(f"     Gyro offset: {[f'{x:.2f}' for x in self.gyro_offset]}")
    
    def start(self):
        """Start continuous reading"""
        self.running = True
        self.last_time = time.time()
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        print("  ✅ IMU reading started")
    
    def stop(self):
        """Stop reading"""
        self.running = False
        if self.read_thread:
            self.read_thread.join(timeout=2)
        if self.bus:
            self.bus.close()
        print("  ✅ IMU stopped")
    
    def _read_loop(self):
        """Background thread: continuously read and update orientation"""
        while self.running:
            try:
                accel, gyro, temp = self._read_raw()
                
                # Subtract calibration offsets
                accel = [accel[i] - self.accel_offset[i] for i in range(3)]
                gyro = [gyro[i] - self.gyro_offset[i] for i in range(3)]
                
                # Update orientation using complementary filter
                self._update_orientation(accel, gyro)
                
                with self.lock:
                    self.data.temperature = temp
                    self.data.timestamp = time.time()
            except Exception as e:
                pass
            
            time.sleep(0.01)
    
    def _read_raw(self):
        """Read raw sensor values"""
        # Read accel
        accel_data = self.bus.read_i2c_block_data(self.MPU6050_ADDR, self.ACCEL_XOUT_H, 6)
        ax = self._bytes_to_short(accel_data[0], accel_data[1]) / 16384.0 * 9.81  # m/s²
        ay = self._bytes_to_short(accel_data[2], accel_data[3]) / 16384.0 * 9.81
        az = self._bytes_to_short(accel_data[4], accel_data[5]) / 16384.0 * 9.81
        
        # Read gyro
        gyro_data = self.bus.read_i2c_block_data(self.MPU6050_ADDR, self.GYRO_XOUT_H, 6)
        gx = self._bytes_to_short(gyro_data[0], gyro_data[1]) / 131.0  # dps
        gy = self._bytes_to_short(gyro_data[2], gyro_data[3]) / 131.0
        gz = self._bytes_to_short(gyro_data[4], gyro_data[5]) / 131.0
        
        # Read temperature
        temp_data = self.bus.read_i2c_block_data(self.MPU6050_ADDR, self.TEMP_OUT_H, 2)
        temp_raw = self._bytes_to_short(temp_data[0], temp_data[1])
        temp = (temp_raw / 340.0) + 36.53  # Celsius
        
        return [ax, ay, az], [gx, gy, gz], temp
    
    def _update_orientation(self, accel, gyro):
        """Update roll, pitch, yaw using complementary filter"""
        current_time = time.time()
        dt = current_time - self.last_time
        if dt <= 0:
            return
        self.last_time = current_time
        
        # Calculate pitch and roll from accelerometer
        accel_pitch = math.atan2(accel[0], math.sqrt(accel[1]**2 + accel[2]**2))
        accel_roll = math.atan2(accel[1], accel[2])
        
        # Convert to degrees
        accel_pitch_deg = math.degrees(accel_pitch)
        accel_roll_deg = math.degrees(accel_roll)
        
        # Complementary filter
        with self.lock:
            self.data.pitch = self.alpha * (self.data.pitch + gyro[0] * dt) + \
                              (1 - self.alpha) * accel_pitch_deg
            self.data.roll = self.alpha * (self.data.roll + gyro[1] * dt) + \
                             (1 - self.alpha) * accel_roll_deg
            self.data.yaw = (self.data.yaw + gyro[2] * dt) % 360
            
            # Store raw
            self.data.accel_x = accel[0]
            self.data.accel_y = accel[1]
            self.data.accel_z = accel[2]
            self.data.gyro_x = gyro[0]
            self.data.gyro_y = gyro[1]
            self.data.gyro_z = gyro[2]
    
    def get_data(self) -> IMUData:
        """Get latest IMU data"""
        with self.lock:
            return IMUData(
                accel_x=self.data.accel_x,
                accel_y=self.data.accel_y,
                accel_z=self.data.accel_z,
                gyro_x=self.data.gyro_x,
                gyro_y=self.data.gyro_y,
                gyro_z=self.data.gyro_z,
                temperature=self.data.temperature,
                yaw=self.data.yaw,
                pitch=self.data.pitch,
                roll=self.data.roll,
                timestamp=self.data.timestamp
            )
    
    @staticmethod
    def _bytes_to_short(high: int, low: int) -> int:
        """Convert two bytes to signed short"""
        value = (high << 8) | low
        if value & 0x8000:
            value = -(65536 - value)
        return value
