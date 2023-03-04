import math
from multiprocessing import Manager, Process, Lock
import os
import time
from pytun import TunTapDevice
import scapy.all as scape
import argparse
from RF24 import RF24, RF24_PA_LOW, RF24_PA_MAX, RF24_2MBPS,RF24_CRC_8

manager = Manager()
outgoing = manager.Queue()
rx_nrf = RF24(17, 0)
rx_nrf.begin()
rx_process = Process
tx_nrf = RF24(27, 10)
tx_nrf.begin()
tx_process = Process

RecevivedBytes = 0
T = []
transmission_time = 0
R = []
receving_time = 0

def setupNRFModules(args):
    
    rx_nrf.setDataRate(RF24_2MBPS) 
    tx_nrf.setDataRate(RF24_2MBPS)

    rx_nrf.setAutoAck(False)
    tx_nrf.setAutoAck(False)

    rx_nrf.payloadSize = 32
    tx_nrf.payloadSize = 32

    rx_nrf.setCRCLength(RF24_CRC_8)
    tx_nrf.setCRCLength(RF24_CRC_8)

    #Low power because we are using them next to one another! 

    rx_nrf.setPALevel(RF24_PA_LOW) 
    tx_nrf.setPALevel(RF24_PA_LOW)

    # Other than initial setup, set up so the RX-TX pair are listening on each other's channels. 
    return {
        'src': args.src if args.base else args.dst,
        'rx': args.rxchannel if args.base else args.txchannel,
        'dst':  args.dst if args.base else args.src,
        'tx': args.txchannel if args.base else args.rxchannel
    }

def fragment(packet, fragmentSize):
    """ Fragments and returns a list of bytes. This is done by finding the number of fragments we want, and then splitting the bytes-like object into chunks of appropriate size. 
    The input parameter is an IP packet (or any bytes-like object) and the size the method should fragment these into.  
    """
    sizeExHeader = fragmentSize - 1 # This is very likely to always be 32 - 1. However, it does not hurt to future proof this method in case of size changes in radio MTU.
    frags = []
    dataRaw = bytes(packet)
    if len(dataRaw) <= sizeExHeader:
        frags.append('\xfd' + dataRaw)
    else: 
        numSteps = math.ceil(len(dataRaw)/sizeExHeader)
        for _ in range(1, numSteps + 1):
            data = b'\xfe' + dataRaw[0:sizeExHeader]
            frags.append(data)
            dataRaw = dataRaw[sizeExHeader:]
    
    frags[-1] = b'\xff' + frags[-1][1:] # Set the last fragment to be the identifier of a finished packet. 
    return frags
 

 
def tx(nrf: RF24, address, channel, size):
    global transmission_time
    nrf.openWritingPipe(address)
    nrf.stopListening()
    print("Init TX on channel {}".format(channel))
    nrf.printDetails()
    transmission_time = 0
    while len(T)<2000:
            #print("Size of the queue? {}".format(outgoing.qsize()))
            start_timer = time.monotonic_ns()   
            #packet = outgoing.get(True) #This method blocks until available. True is to ensure that happens if default ever changes.
            packet = transmission_time.to_bytes(31, "big") # may return OverflowError if packet is too big.
            T.append(transmission_time) 
            print("TX: {}".format(packet)) #TODO: DELETE. 
            fragments = fragment(packet, size)
            for i in fragments:
                #print("Fragment in TX: {}".format(scape.bytes_hex(i)))
                nrf.writeFast(i)
            end_timer = time.monotonic_ns()
            transmission_time += (end_timer - start_timer)/10^9 #convert to seconds. 
            
    print("Tx done, time: {}".format(transmission_time))
        

        
            
def rx(nrf: RF24, address, tun: TunTapDevice, channel):
    
    nrf.openReadingPipe(1, address)
    nrf.startListening()
    print("Init RX on channel {}".format(channel))
    nrf.printDetails()
    incoming = b''

    while True:
        global receving_time
        global RecevivedBytes
        hasData, _ = nrf.available_pipe() # Do not care about what pipe the data comes in at. 
        if hasData:
            start_timer = time.monotonic_ns()
            print("Received packet at  time : {}".format(start_timer))
            packet = readFromNRF(nrf)
            header = packet[0:1]
            data = packet[1:]
            print(scape.bytes_hex(header))
            
            # Checks if the packet received is a fragment, is small enough to not be one, or is the last fragment. 
            if header == b'\xfe':
                # more  fragments
                incoming += data
                
            elif header == b'\xff':
                # last fragment
                incoming += data
                RecevivedBytes += len(incoming)
                R.append(incoming)
                incoming = b''
                stop_timer = time.monotonic_ns()
                receving_time += (stop_timer - start_timer)/10^9 
                print("Packet complete.  timeElapsed: {time}".format(receving_time))
                
            elif header == b'\xfd':
                # small package 
                incoming += data
                RecevivedBytes += len(incoming)
                stop_timer = time.monotonic_ns()
                receving_time += (stop_timer - start_timer)/10^9 
                #print("Packet complete. Packet: {info} \n Size: {len}".format(info = scape.bytes_hex(incoming), len = len(incoming)))
                print("Packet complete.  timeElapsed: {time}".format(receving_time))
                #print(incoming)
                
            # An error occur if we do not account for packets not going through our fragment method. If so, just write it to the tun-interface. 
            else:
                
                tun.write(packet)

def readFromNRF(nrf: RF24):
    size = nrf.getDynamicPayloadSize()
    tmp = nrf.read(size)
    return bytes(tmp)
        

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
    if isBase:
        os.system('''
        sudo iptables -t nat -A POSTROUTING -o wlan0 -j MASQUERADE
        sudo iptables -A FORWARD -i wlan0 -o longge -m state --state RELATED,ESTABLISHED -j ACCEPT
        sudo iptables -A FORWARD -i longge -o wlan0 -j ACCEPT
        ''')
    else:
        os.system('sudo ip route add default via {} dev longge'.format(ipBase))
    print("TUN interface online, with values \n Address:  {} \n Destination: {} \n Network mask: {}".format(tun.addr, tun.dstaddr, tun.netmask) )
    return tun


def doubleTX(timeToLive):
    Process(target=doubleProcess, args=(timeToLive, rx_process)).start()
def doubleRX(timeToLive):
    Process(target=doubleProcess, args=(timeToLive, tx_process)).start()


# The NRF process this takes in is the one to kill. 
lock = Lock()
def doubleProcess(timeToLive, nrf_process: Process):
    lock.acquire()
    print("Successfully shut down old operation. Starting new process for {}".format(nrf_process))
     # Since we want the pairs to work together, we need to set the new tx to use the old RX values. 
    new_process = createDoubledProcess(nrf_process is tx_process)
    new_process.start()
    print("Letting this manager thread sleep for {} seconds".format(timeToLive))
    time.sleep(timeToLive)
 
    new_process.join()
    print("Time expired, recreating old process.")
    old_process = createDoubledProcess(nrf_process is not tx_process)
    old_process.start()
    lock.release()

def createDoubledProcess(isTX):
    if(isTX):
        return Process(target=tx, kwargs={'nrf':rx_nrf, 'address':bytes(vars['src'], 'utf-8'), 'channel': vars['rx'], 'size':args.size})
    return Process(target=rx, kwargs={'nrf':tx_nrf, 'address':bytes(vars['dst'], 'utf-8'), 'tun': tun, 'channel': vars['tx']})

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='NRF24L01+. Please note that you should use the same src/dst for the base and the mobile unit, put the isBase to False and let the program handle the RX/TX pair.')
    parser.add_argument('--base', dest='base', default=True, action=argparse.BooleanOptionalAction)
    parser.add_argument('--src', dest='src', type=str, default='1Node', help='NRF24L01+\'s source address (Base)')
    parser.add_argument('--dst', dest='dst', type=str, default='2Node', help='NRF24L01+\'s destination address (Base)')
    parser.add_argument('--size', dest='size', type=int, default=32, help='Packet size') 
    parser.add_argument('--txchannel', dest='txchannel', type=int, default=101, help='Tx channel', choices=range(0,125)) 
    parser.add_argument('--rxchannel', dest='rxchannel', type=int, default=103, help='Rx channel', choices=range(0,125))
    
    args = parser.parse_args()

    #With a data rate of 2 Mbps, we need to at least tell the user that the channels should be at least 2Mhz from each other to ensure no cross talk. 
    if abs(args.txchannel - args.rxchannel) < 2:
        print("Do note that having tx and rx channels this close to each other can introduce cross-talk.")

    # Setup of NRF modules, channels, and the Tun interface. 
    vars = setupNRFModules(args)
    tun = setupIP(args.base)
   
    rx_process = Process(target=rx, kwargs={'nrf':rx_nrf, 'address':bytes(vars['src'], 'utf-8'), 'tun': tun, 'channel': vars['rx']})
    rx_process.start()
    time.sleep(0.01)

    tx_process = Process(target=tx, kwargs={'nrf':tx_nrf, 'address':bytes(vars['dst'], 'utf-8'), 'channel': vars['tx'], 'size':args.size})
    tx_process.start()

    ICMPPacket = scape.IP(dst="8.8.8.8")/scape.ICMP() # Merely for testing. Remove later. 
    
    try:    
        while True:    
            packet = tun.read(tun.mtu)
            outgoing.put(packet)
            print("In main thread, size of the queue is: {}".format(outgoing.qsize()))


    except KeyboardInterrupt:
        print("Main thread no longer listening on the TUN interface. ")

    tx_process.join()
    rx_process.join()

    print("TXThroughput :".format(len(T)*31/transmission_time))
    print("RXThroughput :".format(RecevivedBytes/receving_time))

    # Setting the radios to stop listening seems to be best practice. 
    rx_nrf.stopListening()  
    tx_nrf.stopListening()
    outgoing.close()
    tun.down()
    print("Threads ended, radios stopped listening, TUN interface down.")