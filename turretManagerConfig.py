TURRET_CONFIG = {
    'baudrate': 9600,
    'serialPort': '/dev/ttyUSB0',
    'noTurret': True,
    'useSSL': False,
    'validationBypass': True,
    'password': "Z",
    'webSocketPort': 9001,
    'certFile': '/etc/uv4l/fullchain.pem',
    'keyFile': '/etc/uv4l/privkey.key'
}
# maps friendly name to the Arduino hex encoded turret commands
SERIAL_CMD = {
    "FIRE": 0x21,
    "STOP_FIRE": 0x22,
    "SAFETY_ON": 0x23,
    "SAFETY_OFF": 0x24,
    "REBOOT": 0x25,
    "ROTATE_LEFT_MAX": 0x26,
    "ROTATE_ZERO": 0x30,
    "ROTATE_RIGHT_MAX": 0x3A,
    "PITCH_DOWN_MAX": 0x3B,
    "PITCH_ZERO": 0x45,
    "PITCH_UP_MAX": 0x4F,
}
# maps friendly SERIAL_CMD name to the expected inbound value
#   (sent from Android app via WebSocket atm)
IN_CMD = {
    "FIRE": "FIRE",
    "CEASE FIRE": "STOP_FIRE",
    "SAFETY ON": "SAFETY_ON",
    "SAFETY OFF": "SAFETY_OFF",
    "ROTATE SPEED": "ROTATE_ZERO",
    "PITCH SPEED": "PITCH_ZERO"
}
