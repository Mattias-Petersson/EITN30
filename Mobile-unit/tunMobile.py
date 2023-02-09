from pytun import TunTapDevice
ipBase = '20.0.0.1'
ipMobile = '20.0.0.2'
base = False

tun = TunTapDevice(name='longge')
tun.addr = ipBase if base else ipMobile
tun.dstaddr = ipMobile if base else ipBase
tun.netmask = '255.255.255.240'
tun.mtu = 1500

tun.up()
print("Address:  {} \n Destination: {} \n Network mask: {}".format(tun.addr, tun.dstaddr, tun.netmask) )
#tun.close()


