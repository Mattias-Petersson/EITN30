from tuntap import TunTap
from fcntl import ioctl
import struct
ip = "20.0.0.14"
mask = "/24"
gate = "20.0.0.1"
tun = TunTap(nic_type="Tun", nic_name="tun0")

tun.config(ip = ip, mask = mask, gateway = gate)


print("IP: {ip} \n Mask: {mask} \n Gateway: {gate}".format(ip = ip, mask = mask, gate = gateway))