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
    print("Connection to turret successfully terminated.\n")
    colorama.deinit()


def establish_connection_to_turret():
    if TURRET_CONFIG['noTurret']:
        return
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
    if command == 0:
        print("\nShutdown command received.\n")
        cleanup()
        print("Turret manager software exiting now.\n")
        sys.exit(0)

    if not TURRET_CONFIG['noTurret']:
        print("Sending command: " + hex(command))
        arduino_serial_conn.write(chr(command).encode())
        return command
    print("Serial connection disabled. Command was not sent to the turret.")
    return command + 1  # command was received but not written to the serial bus


def init_incoming_commands_server():
    port = TURRET_CONFIG['webSocketPort']  # default is 9001
    print("Initializing incoming command server on port "+str(port)+"...\n")

    if TURRET_CONFIG['useSSL'] is False:
        command_server = SimpleWebSocketServer('', port, TurretWebSocketServer)
        print("SSL is not enabled for WebSocketServer. Using unsecure HTTP.")
    else:
        certFile = TURRET_CONFIG['certFile']
        keyFile = TURRET_CONFIG['keyFile']
        command_server = SimpleSSLWebSocketServer('', port, TurretWebSocketServer, certfile=certFile, keyfile=keyFile)
        print("SSL is enabled for WebSocketServer. Using secure HTTPS.")

    command_server.serveforever()


def play_turret_ready_sound():
    return play_sound(TURRET_CONFIG['readySoundFile'])


def play_sound(file_name):
    return os.system("omxplayer " + file_name)


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


class TurretCommander:
    def __init__(self):
        from config import IN_CMD, SERIAL_CMD
        self.IN_CMD = IN_CMD
        self.SERIAL_CMD = SERIAL_CMD
        self.PASSWORD = TURRET_CONFIG['password']
        self.CHECK_IF_VALID = TURRET_CONFIG['validationBypass']  # True skips validation
        self.is_validated = self.CHECK_IF_VALID  # is_validated is for the current connection
        print("TurretCommander instantiated.")

    def reset_validation(self):
        self.is_validated = self.CHECK_IF_VALID

    def validate_client(self, data, sendmessage, close):
        incoming_password = data
        print("Authenticating Client.")
        if incoming_password == self.PASSWORD:
            self.is_validated = True
            print("Client is validated.")
            sendmessage('Login successful')
        else:
            print("Client used an invalid password.\nTerminating connection.\n")
            sendmessage('Invalid password. Connection terminated.')
            close()

    def process_incoming_command(self, command):
        print("processing incoming cmd: " + command)
        speed_check = command.split(' ')
        speed = 0
        cmd_key = command
        if len(speed_check) > 2:  # extract speed value from command
            speed = int(speed_check[2])
            speed_length = len(speed_check[2])+1
            cmd_key = command[:-speed_length]
        if cmd_key in self.IN_CMD:
            serial_key = self.IN_CMD[cmd_key]
        elif cmd_key in self.SERIAL_CMD:
            serial_key = cmd_key
        else:
            print("Unrecognized command received: " + str(command))
            return
        print("Executing cmd: " + serial_key)
        command_turret(self.SERIAL_CMD[serial_key] + speed)


class TurretWebSocketServer(WebSocket):
    tc = TurretCommander()

    def handleMessage(self):
        if self.tc.is_validated:
            incoming_command = self.data
            print("Incoming command: " + incoming_command)
            self.tc.process_incoming_command(incoming_command)
        else:
            self.tc.validate_client(self.data, self.sendMessage, self.close)

    def handleConnected(self):
        print("Client connected to command server.")

    def handleClose(self):
        print("Closing websocket server...")
        self.tc.reset_validation()


def main():
    colorama.init()
    parse_command_line_arguments()
    print("\nTurret manager software started.\n")
    establish_connection_to_turret()

    logging_thread = Thread(target=serial_logging_thread)
    logging_thread.start()

    # Lets the user know the gun is ready
    # Doing it after the server is ready is much harder due to threading sadly
    play_turret_ready_sound()
    init_incoming_commands_server()


if __name__ == "__main__":
    main()
