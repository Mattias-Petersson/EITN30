import math
from multiprocessing import Process, Queue
import sys
import time
import struct
import board
import digitalio as dio
import busio
from pytun import TunTapDevice
import scapy.all as scape
import argparse
from RF24 import RF24, RF24_PA_LOW, RF24_PA_MIN, RF24_2MBPS, RF24_CRC_8
import spidev

global outgoing; outgoing = Queue()
"""
SPI_BUS0 = spidev.SpiDev()
SPI_BUS1 = spidev.SpiDev()

SPI0 = {
    'MOSI':10,#dio.DigitalInOut(board.D10),
    'MISO':9,#dio.DigitalInOut(board.D9),
    'clock':11,#dio.DigitalInOut(board.D11),
    'ce_pin':dio.DigitalInOut(board.D17),
    'csn':dio.DigitalInOut(board.D8),
    }
SPI1 = {
    'MOSI':20,#dio.DigitalInOut(board.D10),
    'MISO':19,#dio.DigitalInOut(board.D9),
    'clock':21,#dio.DigitalInOut(board.D11),
    'ce_pin':dio.DigitalInOut(board.D27),
    'csn':dio.DigitalInOut(board.D18), #Not allowed to be on the same PIN as SPI0! No other configuration of this works. 
    }
"""
 
#processargs: kwargs={'nrf':tx_nrf, 'address':bytes(args.dst, 'utf-8'), 'queue': incoming, 'channel': args.txchannel, 'size':args.size})
def tx(nrf: RF24, address, channel, size):
    nrf.openWritingPipe(address)
    nrf.setAutoAck(True)
    nrf.stopListening()
    nrf.payloadSize = 32
    print("Init TX on channel {}".format(channel))
    nrf.printDetails()
    count = 0
    delayList =[]
    while count<2000:
        payload = bytearray(32)    
        start_timer = time.monotonic_ns()  # start timer
        payload[0:7] =start_timer
        result = nrf.write(payload)
        end_timer = time.monotonic_ns()
        print("Transmit :{} p".format(result))
        delayList.append(end_timer-start_timer) 
        count+=1
    print(delayList)    
            

#processargs: kwargs={'nrf':rx_nrf, 'address':bytes(args.src, 'utf-8'), 'tun': tun, 'channel': args.rxchannel})
def rx(nrf: RF24, address, tun: TunTapDevice, channel):
    nrf.openReadingPipe(1, address)
    nrf.setAutoAck(True)
    rx_nrf.startListening()
    print("Init RX on channel {}".format(channel))
    nrf.printDetails()
    incoming = 0
    totalTime = float(0.0)
    count = 0
    start_timer = time.monotonic_ns()
    while totalTime<2000000:
        hasData, whatPipe = nrf.available_pipe()
        if hasData:
            start_timer = time.monotonic_ns()
            #size = nrf.getDynamicPayLoadSize()
            size = nrf.payloadSize #32
            incoming+=size
            test = nrf.read(size)
            packet = bytes(test)
        end_timer = time.monotonic_ns()
        totalTime = end_timer-start_timer
    print("Time elapse in ms : {} ".format(totalTime))
    print("Incoming bytes: {} ".format(incoming))
    print("Throughput: "+ incoming/totalTime*1000)

# Troubleshooting tool. Since I am getting radio hardware not found, it is useful to break the program into smaller chunks. 
def setupSingle(nrf):
    nrf.setDataRate(RF24_2MBPS) #(1) represents 2 Mbps
    nrf.setAutoAck(False)# for all pipe or nrf.setAutoAck(0,True)
    nrf.payloadSize = 32 
    nrf.setCRCLength(RF24_CRC_8) #RF24_CRC_8 or RF24_CRC_16
    nrf.setPALevel(RF24_PA_LOW )

def setupNRFModules(rx, tx):
    
    # From the API, 1 sets freq to 1Mbps, 2 sets freq to 2Mbps, 250 to 250kbps.
    rx.setDataRate(RF24_2MBPS)  
    tx.setDataRate(RF24_2MBPS)

    rx.setAutoAck(True) # enable autoAck for pipeline 0 This number should be in range [0, 5]
    tx.setAutoAck(True) 

    rx.payloadSize = 32
    tx.payloadSize = 32

    # From the API, 1 enables CRC using 1 byte (weak), 2 enables CRC using 2 bytes (stronger), 0 disables. 
    rx.setCRCLength(RF24_CRC_8)
    tx.setCRCLength(RF24_CRC_8)
    
def setupIP(isBase):
    ipBase = '20.0.0.1'
    ipMobile = '20.0.0.2'
    tun = TunTapDevice()
    tun = TunTapDevice(name='longge')
    tun.addr = ipBase if isBase else ipMobile
    tun.dstaddr = ipMobile if isBase else ipBase
    tun.netmask = '255.255.255.252' # /30
    tun.mtu = 1500
    tun.up()
    return tun




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='NRF24L01+')
    parser.add_argument('--isBase', dest='base', type= bool, default=True, help='If this is a base-station, set it to True.') 
    parser.add_argument('--src', dest='src', type=str, default='1Node', help='NRF24L01+\'s source address')
    parser.add_argument('--dst', dest='dst', type=str, default='2Node', help='NRF24L01+\'s destination address')
    parser.add_argument('--count', dest='cnt', type=int, default=10, help='Number of transmissions')
    parser.add_argument('--size', dest='size', type=int, default=32, help='Packet size') 
    parser.add_argument('--txchannel', dest='txchannel', type=int, default=76, help='Tx channel', choices=range(0,125)) 
    parser.add_argument('--rxchannel', dest='rxchannel', type=int, default=81, help='Rx channel', choices=range(0,125))

    args = parser.parse_args()

    #With a data rate of 2 Mbps, we need to at least tell the user that the channels should be at least 2Mhz from each other to ensure no cross talk. 
    if abs(args.txchannel - args.rxchannel) < 2:
        print("Do note that having tx and rx channels this close to each other can introduce cross-talk.")


    # initialize the nRF24L01 on the spi bus object
    rx_nrf = RF24(17, 0)
    rx_nrf.begin()
    tx_nrf = RF24(27, 10)
    tx_nrf.begin()
    setupNRFModules(rx_nrf, tx_nrf)
    txchannel = args.txchannel if args.base else args.rxchannel
    rxchannel = args.rxchannel if args.base else args.txchannel
    src = args.src if args.base else args.dst
    dst = args.dst if args.base else args.src
    tun = setupIP(args.base)
   
    rx_process = Process(target=rx, kwargs={'nrf':rx_nrf, 'address':bytes(src, 'utf-8'), 'tun': tun, 'channel': rxchannel})
    rx_process.start()
    time.sleep(0.01)

    tx_process = Process(target=tx, kwargs={'nrf':tx_nrf, 'address':bytes(dst, 'utf-8'), 'channel': txchannel, 'size':args.size})
    tx_process.start()
   
    try:    
        while True:
            packet = tun.read(tun.mtu)
            outgoing.put(packet)

    except KeyboardInterrupt:
        print("KeyboardInterrupt exit!")
        exit

    tx_process.join()
    rx_process.join()
    tun.down()
    print("Threads ended successfully, please stand by.")