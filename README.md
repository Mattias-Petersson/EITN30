# EITN30
Useful commands (format this later):

To see available devices on the same network. CDIR. 
sudo  nmap  192.168.1.0/24

To catch incoming packets:
sudo tcpdump --interface longge

Scapy:
Creating an IP packet:
import scapy.all as scape
packet = scape.IP(dst = "8.8.8.8")/scape.ICMP()

or

payload ="A"*500
packet = scape.IP(dst = "8.8.8.8")/scape.UDP()/scape.Raw(load=payload)
scape.send(packet, iface="longge")
