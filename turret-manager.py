#!/usr/bin/python3

# Python server to manage the turret

import os.path
import sys
import argparse

import serial
import serial.tools.list_ports
from threading import Thread
from time import sleep
import colorama
from colorama import Fore
from colorama import Style
from SimpleWebSocketServer import WebSocket

if os.path.isfile("/etc/terror-turret/turretManagerConfig.py"):
    sys.path.append("/etc/terror-turret")
from turretManagerConfig import TURRET_CONFIG

# no SSL support or yes SSL support...
if TURRET_CONFIG['useSSL'] is False:
    from SimpleWebSocketServer import SimpleWebSocketServer
else:
    from SimpleWebSocketServer import SimpleSSLWebSocketServer

# SERIAL_BAUD_RATE = TURRET_CONFIG['baudrate']  # 9600

CMD_FIRE = 0x21
CMD_STOP_FIRE = 0x22
CMD_SAFETY_ON = 0x23
CMD_SAFETY_OFF = 0x24
CMD_REBOOT = 0x25
CMD_ROTATE_LEFT_MAX = 0x26
CMD_ROTATE_ZERO = 0x30
CMD_ROTATE_RIGHT_MAX = 0x3A
CMD_PITCH_DOWN_MAX = 0x3B
CMD_PITCH_ZERO = 0x45
CMD_PITCH_UP_MAX = 0x4F

arduino_serial_conn = serial.Serial()

in_test_mode = False

# Used to know when are about to exit, to allow threads to clean up things
exiting = False


def main():
    colorama.init()
    parse_command_line_arguments()
    print("\nTurret manager software started.\n")
    if not TURRET_CONFIG['noTurret']:
        establish_connection_to_turret()

    logging_thread = Thread(target=serial_logging_thread)
    logging_thread.start()

    if testmode:
        test_turret_commands()
        cleanup()
        exit(0)

    # Lets the user know the gun is ready
    # Doing it after the server is ready is much harder due to threading sadly
    play_turret_ready_sound()
    init_incoming_commands_server()
    cleanup()
    exit(0)


def parse_command_line_arguments():
    program_description = "Main control software for the Terror Turret."
    parser = argparse.ArgumentParser(description=program_description)
    parser.add_argument(
        '-t', '--test-mode',
        action='store_true',
        dest='testmode',
        help="Runs the test script instead of normal program")
    parser.add_argument(
        '-s', '--serial-port',
        action='store_const',
        const='/dev/ttyUSB0',
        default='/dev/ttyUSB0',
        dest='serialport',
        help="The name of the serial port to connect from.")
    parser.add_argument(
        '-n', '--no-turret',
        action='store_true',
        dest='noturret',
        help="Runs without creating a serial connection.")
    parser.add_argument(
        '-p', '--port',
        action='store_const',
        const=9001,
        default=9001,
        dest='port',
        help="The port the websocket server will listen on.")
    parsed_args = parser.parse_args()

    global testmode
    testmode = parsed_args.testmode

    if parsed_args.serialport != '/dev/ttyUSB0':
        TURRET_CONFIG['serialPort'] = parsed_args.serialport

    if parsed_args.noturret:
        TURRET_CONFIG['noTurret'] = True

    if parsed_args.port != 9001:
        TURRET_CONFIG['webSocketPort'] = parsed_args.port


def cleanup():
    global exiting
    exiting = True
    # Allow threads to have a moment to react
    sleep(1)
    arduino_serial_conn.close()
    print("\nTurret manager software exited.\n")
    colorama.deinit()


def establish_connection_to_turret():
    print("Available serial ports: ")
    for port in serial.tools.list_ports.comports():
        print(str(port))
    print("")

    print("Attempting to connect to turret on " + TURRET_CONFIG['serialPort'] + "...")
    try:
        # The serial port takes some time to init 
        arduino_serial_conn.baudrate = TURRET_CONFIG['baudrate']
        arduino_serial_conn.port = TURRET_CONFIG['serialPort']
        arduino_serial_conn.timeout = 2
        arduino_serial_conn.close()
        arduino_serial_conn.open()
        sleep(3)
        print("Connection established")
    except serial.SerialException as e:
        crash("Failed to connect to turret on " + str(TURRET_CONFIG['serialPort']) + "\n\n" + str(e))


def command_turret(command):
    print("Sending command: " + hex(command))
    if not TURRET_CONFIG['noTurret']:
        arduino_serial_conn.write(chr(command).encode())


def test_turret_commands():
    print("\nInitiating turret commands test...\n")
    sleep(3)

    print("Commanding SAFETY OFF")
    command_turret(CMD_SAFETY_OFF)
    sleep(3)

    print("Commanding SAFETY ON")
    command_turret(CMD_SAFETY_ON)
    sleep(3)

    print("Commanding SAFETY OFF")
    command_turret(CMD_SAFETY_OFF)
    sleep(3)

    print("Firing for 1 second")
    command_turret(CMD_FIRE)
    sleep(1)
    command_turret(CMD_STOP_FIRE)
    sleep(3)

    print("Left at speed 7")
    command_turret(CMD_ROTATE_ZERO - 7)
    sleep(7)

    print("Right at speed 3")
    command_turret(CMD_ROTATE_ZERO + 3)
    sleep(7)

    print("Up at speed 10")
    command_turret(CMD_PITCH_UP_MAX)
    sleep(7)

    print("Down at speed 1")
    command_turret(CMD_PITCH_ZERO - 1)
    sleep(7)

    print("Testing moving and firing")
    command_turret(CMD_ROTATE_ZERO + 3)
    command_turret(CMD_FIRE)
    sleep(1)
    command_turret(CMD_STOP_FIRE)
    sleep(7)

    print("Turning safety back on")
    command_turret(CMD_SAFETY_ON)
    sleep(2)

    print("Test complete. Exiting program.")


def init_incoming_commands_server():
    global command_server
    print("Initializing incoming commands server...\n")
    port = TURRET_CONFIG['webSocketPort']  # default is 9001

    if TURRET_CONFIG['useSSL'] is False:
        command_server = SimpleWebSocketServer('', port, TurretCommandServer)
        print("SSL is not enabled for WebSocketServer. Using unsecure HTTP.")
    else:
        certFile = TURRET_CONFIG['certFile']
        keyFile = TURRET_CONFIG['keyFile']
        command_server = SimpleSSLWebSocketServer('', port, TurretCommandServer, certfile=certFile, keyfile=keyFile)
        print("SSL is enabled for WebSocketServer. Using secure HTTPS.")

    command_server.serveforever()


# turret_ready.wav is a symlink that can be changed to use a different sound
def play_turret_ready_sound():
    play_sound('/usr/share/terror-turret/turret_ready.wav')


def play_sound(file_name):
    os.system("omxplayer " + file_name)


def crash(reason):
    print(Fore.RED + reason + Style.RESET_ALL)
    colorama.deinit()
    exit(1)


def serial_logging_thread():
    print("Beginning turret output logging...\n")
    while not exiting:
        if arduino_serial_conn.isOpen():
            turret_output = str(arduino_serial_conn.readline(), "utf-8")
            if turret_output != "":
                print("Turret: " + turret_output, end='')
        else:
            return


class TurretCommandServer(WebSocket):
    IN_CMD_FIRE = "FIRE"
    IN_CMD_CEASE_FIRE = "CEASE FIRE"
    IN_CMD_SAFETY_ON = "SAFETY ON"
    IN_CMD_SAFETY_OFF = "SAFETY OFF"
    IN_CMD_ROTATE = "ROTATE SPEED"
    IN_CMD_PITCH = "PITCH SPEED"
    is_validated = TURRET_CONFIG['validationBypass']  # True skips validation

    def handleMessage(self):
        if self.is_validated:
            incoming_command = self.data
            print("Incoming command: " + incoming_command)
            self.process_incoming_command(incoming_command)
        else:
            TurretCommandServer.validate_client(self)

    def handleConnected(self):
        print("Client connected to command server.")

    def handleClose(self):
        print("Closing websocket server...")
        self.is_validated = TURRET_CONFIG['validationBypass']

    def process_incoming_command(self, command):
        if command == self.IN_CMD_FIRE:
            command_turret(CMD_FIRE)
        elif command == self.IN_CMD_CEASE_FIRE:
            command_turret(CMD_STOP_FIRE)
        elif command == self.IN_CMD_SAFETY_ON:
            command_turret(CMD_SAFETY_ON)
        elif command == self.IN_CMD_SAFETY_OFF:
            command_turret(CMD_SAFETY_OFF)
        elif command.startswith(self.IN_CMD_ROTATE):
            speed = command.split(' ')[2]
            command_turret(CMD_ROTATE_ZERO + int(speed))
        elif command.startswith(self.IN_CMD_PITCH):
            speed = command.split(' ')[2]
            command_turret(CMD_PITCH_ZERO + int(speed))
        else:
            print("Unrecognized command received: " + str(command))

    def validate_client(self):
        incoming_password = self.data
        print("Authenticating Client.")
        if incoming_password == TURRET_CONFIG['password']:
            self.is_validated = True
            print("Client is validated.")
            self.sendMessage('Login successful')
        else:
            print("Client used an invalid password.\nTerminating connection.\n")
            self.sendMessage('Invalid password.')
            self.close(self)


if __name__ == "__main__":
    main()
