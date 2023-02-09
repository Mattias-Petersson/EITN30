import scapy.all as scape


dest = "8.8.8.8"
ICMPPacket = scape.IP(dst=dest)/scape.ICMP()

payload="A"*496+"B"*500
UDPPacket = scape.IP(dst = dest)/scape.UDP()/payload


UDPTest = scape.raw(UDPPacket)
#print(UDPtest) #len 95 of stuff before payload.
#print(type(UDPtest)) #class 'bytes'

#ICMPTest = scape.raw(ICMPPacket)
#print(ICMPTest) #len 104 of bytes. ICMP has 20 bytes IP header, 8 bytes ICMP header, rest is payload (for ping we are guessing)
#print(type(ICMPTest)) class 'bytes'


def fragment(data, fragmentSize):
    """ Fragments and returns a list of any IP packet. The input parameter has to be an IP packet, as this is done via Scapy. 
    """
    frags = scape.fragment(data, fragsize=fragmentSize)
    return frags

def defrag(dataList):
    """ Defragments and returns a packet. The input parameter has to be a fragmented IP packet as a list. 
    """
    data = scape.defragment(dataList)
    return data

def send(data):
    scape.send(data)
    
