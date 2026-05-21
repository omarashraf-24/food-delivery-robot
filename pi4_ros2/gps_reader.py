#!/usr/bin/env python3
"""
GPS Reader - NEO-6M via UART
Reads GPS data from UART0 (GPIO8/10) on Pi4
"""

import serial
import threading
import time
import math
from dataclasses import dataclass

@dataclass
class GPSData:
    """GPS sensor data"""
    latitude: float = 0
    longitude: float = 0
    altitude: float = 0
    speed: float = 0  # m/s
    heading: float = 0  # degrees
    satellites: int = 0
    hdop: float = 999  # Horizontal dilution of precision
    valid: bool = False
    timestamp: float = 0

class GPSReader:
    """NEO-6M GPS reader via UART"""
    
    def __init__(self, port: str = '/dev/ttyAMA0', baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.running = False
        self.read_thread = None
        
        self.data = GPSData()
        self.lock = threading.Lock()
    
    def connect(self) -> bool:
        """Connect to GPS via UART"""
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(0.5)
            print(f"  ✅ GPS connected on {self.port}")
            return True
        except Exception as e:
            print(f"  ✗ GPS connection failed: {e}")
            return False
    
    def start(self):
        """Start reading GPS data"""
        self.running = True
        self.read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self.read_thread.start()
        print("  ✅ GPS reading started")
    
    def stop(self):
        """Stop reading"""
        self.running = False
        if self.read_thread:
            self.read_thread.join(timeout=2)
        if self.serial:
            self.serial.close()
        print("  ✅ GPS stopped")
    
    def _read_loop(self):
        """Background thread: continuously read NMEA sentences"""
        while self.running:
            try:
                if self.serial and self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        self._parse_nmea(line)
            except Exception as e:
                pass
            
            time.sleep(0.01)
    
    def _parse_nmea(self, sentence: str):
        """Parse NMEA sentence"""
        try:
            if sentence.startswith('$GNGGA') or sentence.startswith('$GPGGA'):
                self._parse_gga(sentence)
            elif sentence.startswith('$GNRMC') or sentence.startswith('$GPRMC'):
                self._parse_rmc(sentence)
            elif sentence.startswith('$GNGSA') or sentence.startswith('$GPGSA'):
                self._parse_gsa(sentence)
        except Exception as e:
            pass
    
    def _parse_gga(self, sentence: str):
        """Parse GGA sentence (position, altitude, quality)"""
        try:
            parts = sentence.split(',')
            if len(parts) < 9:
                return
            
            # Time
            time_str = parts[1]
            
            # Latitude
            lat_str = parts[2]
            lat_dir = parts[3]
            if lat_str:
                lat = self._parse_coordinate(lat_str)
                if lat_dir == 'S':
                    lat = -lat
            
            # Longitude
            lon_str = parts[4]
            lon_dir = parts[5]
            if lon_str:
                lon = self._parse_coordinate(lon_str)
                if lon_dir == 'W':
                    lon = -lon
            
            # Fix quality (0=invalid, 1=GPS, 2=DGPS, 3=PPS, 4=RTK, 5=Float RTK)
            fix_quality = int(parts[6])
            
            # Satellites
            sats = int(parts[7])
            
            # HDOP
            hdop = float(parts[8]) if parts[8] else 999
            
            # Altitude
            alt_str = parts[9]
            alt = float(alt_str) if alt_str else 0
            
            with self.lock:
                self.data.latitude = lat
                self.data.longitude = lon
                self.data.altitude = alt
                self.data.satellites = sats
                self.data.hdop = hdop
                self.data.valid = (fix_quality > 0)
                self.data.timestamp = time.time()
        
        except Exception as e:
            pass
    
    def _parse_rmc(self, sentence: str):
        """Parse RMC sentence (speed, heading)"""
        try:
            parts = sentence.split(',')
            if len(parts) < 9:
                return
            
            # Status (A=active, V=void)
            status = parts[2]
            
            # Speed in knots
            speed_knots_str = parts[7]
            speed_knots = float(speed_knots_str) if speed_knots_str else 0
            speed_ms = speed_knots * 0.51444  # Convert to m/s
            
            # Heading
            heading_str = parts[8]
            heading = float(heading_str) if heading_str else 0
            
            with self.lock:
                self.data.speed = speed_ms
                self.data.heading = heading
                self.data.valid = (status == 'A')
                self.data.timestamp = time.time()
        
        except Exception as e:
            pass
    
    def _parse_gsa(self, sentence: str):
        """Parse GSA sentence (satellites used)"""
        try:
            parts = sentence.split(',')
            if len(parts) < 3:
                return
            
            # Mode (1=no fix, 2=2D, 3=3D)
            mode = int(parts[2])
            
            with self.lock:
                if mode == 1:
                    self.data.valid = False
        
        except Exception as e:
            pass
    
    @staticmethod
    def _parse_coordinate(coord_str: str) -> float:
        """Parse latitude/longitude coordinate string DDMM.MMMMM"""
        if not coord_str:
            return 0
        
        # Find decimal point
        dot_idx = coord_str.find('.')
        
        # Degrees = all digits before the 2 digits before decimal
        degree_end = dot_idx - 2
        degrees = int(coord_str[:degree_end])
        
        # Minutes = 2 digits before decimal + digits after
        minutes = float(coord_str[degree_end:])
        
        return degrees + (minutes / 60.0)
    
    def is_valid(self) -> bool:
        """Check if GPS has valid lock"""
        with self.lock:
            return self.data.valid and self.data.satellites >= 4
    
    def get_data(self) -> GPSData:
        """Get latest GPS data"""
        with self.lock:
            return GPSData(
                latitude=self.data.latitude,
                longitude=self.data.longitude,
                altitude=self.data.altitude,
                speed=self.data.speed,
                heading=self.data.heading,
                satellites=self.data.satellites,
                hdop=self.data.hdop,
                valid=self.data.valid,
                timestamp=self.data.timestamp
            )
    
    def distance_to(self, target_lat: float, target_lon: float) -> float:
        """
        Calculate distance to target in meters (Haversine formula)
        """
        with self.lock:
            lat1 = math.radians(self.data.latitude)
            lon1 = math.radians(self.data.longitude)
        
        lat2 = math.radians(target_lat)
        lon2 = math.radians(target_lon)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        R = 6371000  # Earth radius in meters
        return R * c
    
    def bearing_to(self, target_lat: float, target_lon: float) -> float:
        """
        Calculate bearing to target in degrees (0-360)
        """
        with self.lock:
            lat1 = math.radians(self.data.latitude)
            lon1 = math.radians(self.data.longitude)
        
        lat2 = math.radians(target_lat)
        lon2 = math.radians(target_lon)
        
        dlon = lon2 - lon1
        
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        
        bearing = math.degrees(math.atan2(y, x))
        return (bearing + 360) % 360
