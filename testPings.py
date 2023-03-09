import scapy.all as scape

global local; local = scape.IP(src="20.0.0.2", dst="20.0.0.1")/scape.ICMP()
global png
payload = 'A'*5000
global big; big = scape.IP(src="20.0.0.2", dst="8.8.8.8")/scape.UDP()/payload
global bigLocal; bigLocal = scape.IP(src="20.0.0.2", dst="20.0.0.1")/scape.UDP()/payload
def ping(IP):
    png = scape.IP(src="20.0.0.2", dst=IP)/scape.ICMP()
    arbSend(png)

def arbSend(p):
    scape.send(p, iface="longge")

def testTurboTX():
    packet = scape.IP(src="20.0.0.2", dst="20.0.0.1")/scape.UDP()/(b'\xff\xff\xff\x01')
    print(len(packet))
    scape.send(packet, iface="longge")