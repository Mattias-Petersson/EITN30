import time
import struct
import board
from digitalio import DigitalInOut
from pytun import TunTapDevice
import scapy.all as scape
import threading
import queue
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

ipBase = '20.0.0.1'
ipMobile = '20.0.0.2'
base = False
tun = TunTapDevice()

tun = TunTapDevice(name='longge')
tun.addr = ipBase if base else ipMobile
tun.dstaddr = ipMobile if base else ipBase
tun.netmask = '255.255.255.252'
tun.mtu = 1500
tun.up()


print("Address:  {} \n Destination: {} \n Network mask: {}".format(tun.addr, tun.dstaddr, tun.netmask) )

# to use different addresses on a pair of radios, we need a variable to
# uniquely identify which address this radio will use to transmit
# 0 uses address[0] to transmit, 1 uses address[1] to transmit
#radio_number = bool(
#    int(input("Which radio is this? Enter '0' or '1'. Defaults to '0' ") or 0)
#)



# uncomment the following 3 lines for compatibility with TMRh20 library
# nrf.allow_ask_no_ack = False
# nrf.dynamic_payloads = False
# nrf.payload_length = 4

# These queues have auto-blocking features. This proved useful. 
outgoing = queue.Queue()


nrf.open_tx_pipe(address[0])  # always uses pipe 0
nrf.open_rx_pipe(1, address[1])


def fragment(data, fragmentSize):
    """ Fragments and returns a list of any IP packet. The input parameter has to be an IP packet, as this is done via Scapy. 
    """
    frags = scape.fragment(data, fragsize=fragmentSize)
    return frags

def processReceived(data):  
    if not data: 
        return    
    nrf.listen = False  # ensures the nRF24L01 is in TX mode
    frag = fragment(data, 32)

    for f in frag:
        nrf.send(f)
 
ICMPPacket = scape.IP(dst="8.8.8.8")/scape.ICMP()
def send():
    outgoing.append(ICMPPacket)

def sender():
    while True:
        data = outgoing.get(True) # Auto blocks until an element is available to send. 
        nrf.listen = False
        frags = fragment(data, 32)

        for f in frags:
            nrf.send(f)
            tun.write(f)
            print("Sent: {}".format(f))


def receiver():
    nrf.listen = True
    while True:
        if nrf.available():
            payload_size = (nrf.any())
            payload = nrf.read(payload_size)
            tun.read(payload)
            print("Payload: {}".format(payload))



def main():
    sendThread = threading.Thread(target=sender)
    sendThread.start()

    rxThread = threading.Thread(target=receiver)
    rxThread.start()
    print("Threads started successfully, please stand by.")