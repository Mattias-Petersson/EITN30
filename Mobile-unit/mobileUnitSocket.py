import socket

host = "20.0.0.2"
recieverPort = 9003 #Out of common port numbers on the Wiki, anything above 1024 is free to use and not reserved. 9003 is ours now.

# Create a socket using the port number, bind the local hostname and the arbitrary port to it:
localSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #UDP is SOCK_DRAM, TCP is SOCK_STREAM

localSocket.connect((host, recieverPort))

localSocket.sendall(b"Testing")
data = localSocket.recv(1024)

localSocket.close()