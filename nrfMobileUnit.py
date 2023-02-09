import inspect
import time
import struct
import board
from digitalio import DigitalInOut
#from pytun import TunTapDevice
from pytun import TunTapDevice
# if running this on a ATSAMD21 M0 based board
# from circuitpython_nrf24l01.rf24_lite import RF24
from circuitpython_nrf24l01.rf24 import RF24

# invalid default values for scoping
SPI_BUS, CSN_PIN, CE_PIN = (None, None, None)

try:  # on Linux
    import spidev
    SPI_BUS = spidev.SpiDev()  # for a faster interface on linux
    CSN_PIN = 0  # use CE0 on default bus (even faster than using any pin)
    CE_PIN = DigitalInOut(board.D17)  # using pin gpio22 (BCM numbering) 
    #Changed the above CE_Pin from D22 to D17 thanks to a comment in Teams. 

except ImportError:  # on CircuitPython only
    # using board.SPI() automatically selects the MCU's
    # available SPI pins, board.SCK, board.MOSI, board.MISO
    SPI_BUS = board.SPI()  # init spi bus object

    # change these (digital output) pins accordingly
    CE_PIN = DigitalInOut(board.D4)
    CSN_PIN = DigitalInOut(board.D5)


# initialize the nRF24L01 on the spi bus object
nrf = RF24(SPI_BUS, CSN_PIN, CE_PIN)
# On Linux, csn value is a bit coded
#                 0 = bus 0, CE0  # SPI bus 0 is enabled by default
#                10 = bus 1, CE0  # enable SPI bus 2 prior to running this
#                21 = bus 2, CE1  # enable SPI bus 1 prior to running this

# set the Power Amplifier level to -12 dBm since this test example is
# usually run with nRF24L01 transceivers in close proximity
nrf.pa_level = -12

# addresses needs to be in a buffer protocol object (bytearray)
address = [b"1Node", b"2Node"]

# to use different addresses on a pair of radios, we need a variable to
# uniquely identify which address this radio will use to transmit
# 0 uses address[0] to transmit, 1 uses address[1] to transmit


# set TX address of RX node into the TX pipe


# set RX address of TX node into an RX pipe
#nrf.open_rx_pipe(1, address[1])  # using pipe 1

# using the python keyword global is bad practice. Instead we'll use a 1 item
# list to store our float number for the payloads sent
payload = [0.0]

# uncomment the following 3 lines for compatibility with TMRh20 library
# nrf.allow_ask_no_ack = False
# nrf.dynamic_payloads = False
# nrf.payload_length = 4

def tx():  # count = 5 will only transmit 5 packets
    nrf.open_tx_pipe(address[0])  # always uses pipe 0
    nrf.listen = False  # ensures the nRF24L01 is in TX mode
    print("Tx started.")
    while True:
        tun.write(struct.pack("<f", payload[0]))
"""     while count:
        # use struct.pack to structure your data
        # into a usable payload
        buffer = struct.pack("<f", payload[0])
        # "<f" means a single little endian (4 byte) float value.
        start_timer = time.monotonic_ns()  # start timer
        result = nrf.send(buffer)
        end_timer = time.monotonic_ns()  # end timer
        if not result:
            print("send() failed or timed out")
        else:
            print(
                "Transmission successful! Time to Transmit:",
                "{} us. Sent: {}".format((end_timer - start_timer) / 1000, payload[0]),
            )
            payload[0] += 0.01
        time.sleep(1)
        count -= 1 """

def rx():
    nrf.open_rx_pipe(0, address[1])
    nrf.listen = True
    print("Rx started")

    if nrf.available():
        payload_size, pipe_number = (nrf.any(), nrf.pipe)
        # fetch 1 payload from RX FIFO
        buffer = nrf.read()  # also clears nrf.irq_dr status flag
        # expecting a little endian float, thus the format string "<f"
        # buffer[:4] truncates padded 0s if dynamic payloads are disabled
        payload[0] = struct.unpack("<f", buffer[:4])[0]
        # print details about the received packet
        print(
            "Received {} bytes on pipe {}: {}".format(
              payload_size, pipe_number, payload[0]
           )
        )
    data = nrf.read()


ipBase = '20.0.0.1'
ipMobile = '20.0.0.2'
base = False
tun = TunTapDevice()

tun = TunTapDevice(name='longge')
tun.addr = ipBase if base else ipMobile
tun.dstaddr = ipMobile if base else ipBase
tun.netmask = '255.255.255.240'
tun.mtu = 1500
tun.up()


print("Address:  {} \n Destination: {} \n Network mask: {}".format(tun.addr, tun.dstaddr, tun.netmask) )
