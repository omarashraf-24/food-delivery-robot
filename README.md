# 🤖🍕 Autonomous Food Delivery Robot

Autonomous hoverboard-based food delivery robot with GPS waypoint navigation, LiDAR obstacle avoidance, and computer vision.

## Hardware Stack

- **Hoverboard Base**: 2 differential drive motors (center) + 4 caster wheels
- **ESP32**: Motor controller + Hall sensor feedback
- **Raspberry Pi 4**: Main AI/navigation brain
- **GPS (NEO-6M)**: GPS17 GPIO8/10 (UART0)
- **IMU (MPU6050)**: I2C on Pi4
- **LiDAR (X2-Lidar 8M)**: 360° scanner on Pi4
- **Camera (Pi Camera V2 8MP)**: CSI ribbon on Pi4

## Mission Profile

1. **Start**: Restaurant location (GPS waypoint)
2. **Navigation**: Autonomous waypoint following with obstacle avoidance
3. **Delivery**: Arrive at drop-off location
4. **Return**: Autonomous return to restaurant

## Speed Profile

- **Min Speed**: 0.1 m/s (slow, safe)
- **Cruise Speed**: 0.8 m/s (normal walking pace)
- **Max Speed**: 1.5 m/s (fast, safe for pedestrians)

## Architecture

```
Pi4 (ROS2 - High Level)
├── Read GPS (UART0: GPIO8/10)
├── Read IMU (MPU6050 I2C)
├── Read LiDAR (X2-Lidar)
├── Read Camera (Pi V2)
├── SLAM mapping + navigation
└── Send motor commands → ESP32

ESP32 (Low Level - Motor Controller)
├── Receive motor speed commands (m/s)
├── Control left/right motors
├── Read Hall sensors (RPM feedback)
└── Send feedback to Pi4 (USB serial)
```

## Directory Structure

```
food-delivery-robot/
├── esp32/
│   ├── motor_controller.cpp      # Motor control + Hall feedback
│   ├── motor_config.h            # Motor constants
│   └── platformio.ini            # ESP32 build config
├── pi4_ros2/
│   ├── gps_reader.py             # GPS reader (UART0)
│   ├── imu_reader.py             # MPU6050 I2C reader
│   ├── lidar_reader.py           # X2-Lidar reader
│   ├── camera_reader.py          # Pi Camera V2
│   ├── navigation.py             # ROS2 Nav2 + waypoint following
│   ├── obstacle_avoidance.py     # LiDAR + camera fusion
│   └── ros2_launch.py            # ROS2 launch file
├── integration/
│   ├── esp32_pi_comm.py          # USB serial communication protocol
│   ├── mission_controller.py     # Mission orchestrator
│   ├── speed_controller.py       # Speed control (m/s)
│   └── delivery_mission.py       # Restaurant → Dropoff → Return
├── setup/
│   ├── install_ros2.sh           # ROS2 installation
│   ├── install_dependencies.sh   # Python packages + ROS2 packages
│   ├── configure_gpio.sh         # GPIO setup
│   └── calibrate_sensors.py      # Sensor calibration
├── config/
│   ├── waypoints.yaml            # Mission waypoints
│   ├── robot_params.yaml         # Robot parameters
│   └── navigation_params.yaml    # Nav2 parameters
├── launch/
│   ├── robot.launch.py           # Full robot launch
│   ├── nav2.launch.py            # Navigation stack
│   └── delivery_mission.launch.py # Delivery mission
└── requirements.txt
```

## Quick Start

### Pi4 Setup
```bash
cd setup/
bash install_ros2.sh
bash install_dependencies.sh
bash configure_gpio.sh
python3 calibrate_sensors.py
```

### Launch Robot
```bash
cd launch/
ros2 launch robot.launch.py
```

### Start Delivery Mission
```bash
ros2 launch delivery_mission.launch.py
```

## Communication Protocol

**ESP32 ↔ Pi4 (USB Serial)**

### Pi4 → ESP32 (Motor Commands)
```
Format: [SPEED_LEFT][SPEED_RIGHT][CHECKSUM]\n
Example: 0.8,-0.8,CRC\n  (turn left at 0.8 m/s)
```

### ESP32 → Pi4 (Feedback)
```
Format: [RPM_LEFT][RPM_RIGHT][TEMP][CHECKSUM]\n
Example: 250,250,45,CRC\n  (both motors at 250 RPM, 45°C)
```

## Navigation Stack

- **ROS2 Nav2**: Autonomous navigation
- **SLAM**: LiDAR-based mapping (Cartographer)
- **Path Planning**: A* algorithm
- **Obstacle Avoidance**: Dynamic Window Approach (DWA)

## Calibration

Run before first mission:
```bash
python3 calibrate_sensors.py
```

Calibrates:
- GPS accuracy check
- IMU gyro bias
- Wheel odometry baseline
- Camera focal length

## Safety Features

- **Max Speed Limit**: 1.5 m/s (pedestrian safe)
- **Obstacle Detection**: LiDAR 8m range + camera
- **Emergency Stop**: If obstacles within 0.5m
- **GPS Loss Recovery**: Fall back to IMU + LiDAR
- **Battery Monitoring**: Auto-return if low

## Testing

### Stage 1: Motor Control
```bash
python3 test_motors.py
```

### Stage 2: Sensor Integration
```bash
python3 test_sensors.py
```

### Stage 3: Navigation
```bash
python3 test_navigation.py --waypoint 30.0199,31.2299
```

### Stage 4: Full Mission
```bash
python3 test_delivery_mission.py
```

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

## Authors

- **@omarashraf-24** - Lead developer

---

**Status**: 🔧 In Development
**Last Updated**: 2026-05-21
