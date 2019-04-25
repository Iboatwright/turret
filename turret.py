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

if os.path.isfile("/etc/terror-turret/config.py"):
    sys.path.append("/etc/terror-turret")
from config import TURRET_CONFIG

# no SSL support or yes SSL support...
if TURRET_CONFIG['useSSL'] is False:
    from SimpleWebSocketServer import SimpleWebSocketServer
else:
    from SimpleWebSocketServer import SimpleSSLWebSocketServer

arduino_serial_conn = serial.Serial()

# Used to know when are about to exit, to allow threads to clean up things
exiting = False


def parse_command_line_arguments():
    program_description = "Main control software for the Terror Turret."
    parser = argparse.ArgumentParser(description=program_description)
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


def init_incoming_commands_server():
    global command_server
    port = TURRET_CONFIG['webSocketPort']  # default is 9001
    print("Initializing incoming commands server on port "+str(port)+"...\n")

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
    sys.exit(1)


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
    def __init__(self):
        from config import IN_CMD, SERIAL_CMD
        self.IN_CMD = IN_CMD
        self.SERIAL_CMD = SERIAL_CMD
        self.PASSWORD = TURRET_CONFIG['password']
        self._validated = TURRET_CONFIG['validationBypass']  # True skips validation
        self.is_validated = self._validated  # is_validated is for the current connection
        super().__init__(self)

    def handleMessage(self):
        if self.is_validated:
            incoming_command = self.data
            print("Incoming command: " + incoming_command)
            self.process_incoming_command(incoming_command)
        else:
            self.validate_client()

    def handleConnected(self):
        print("Client connected to command server.")

    def handleClose(self):
        print("Closing websocket server...")
        self.is_validated = self._validated

    def validate_client(self):
        incoming_password = self.data
        print("Authenticating Client.")
        if incoming_password == self.PASSWORD:
            self.is_validated = True
            print("Client is validated.")
            self.sendMessage('Login successful')
        else:
            print("Client used an invalid password.\nTerminating connection.\n")
            self.sendMessage('Invalid password. Connection terminated.')
            self.close()

    def process_incoming_command(self, command):
        print("processing incoming cmd: " + command)
        speed_check = command.split(' ')[2]
        speed = ''
        cmd = command
        if speed_check.isdigit():
            speed = int(speed_check)
            cmd = command[:-len(speed_check + 1)]
        if cmd in self.IN_CMD:
            command_turret(self.SERIAL_CMD[cmd] + speed)
            print("Executing cmd: " + str(command))
        else:
            print("Unrecognized command received: " + str(command))


def main():
    colorama.init()
    parse_command_line_arguments()
    print("\nTurret manager software started.\n")
    if not TURRET_CONFIG['noTurret']:
        establish_connection_to_turret()

    logging_thread = Thread(target=serial_logging_thread)
    logging_thread.start()

    # Lets the user know the gun is ready
    # Doing it after the server is ready is much harder due to threading sadly
    play_turret_ready_sound()
    init_incoming_commands_server()
    cleanup()
    sys.exit(0)


if __name__ == "__main__":
    main()
