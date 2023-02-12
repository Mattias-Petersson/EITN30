import socket


recieverPort = 9003 #Out of common port numbers on the Wiki, anything above 1024 is free to use and not reserved. 9003 is ours now.

# Create a socket using the port number, bind the local hostname and the arbitrary port to it:
localSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #UDP is SOCK_DRAM, TCP is SOCK_STREAM
print ("Socket successfully created")

# Allows re-connection to a socket in use
localSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Socket sends data immidatley
localSocket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

localSocket.bind(('', recieverPort))

# configure how many client the server can listen simultaneously, 2 connections is all
localSocket.listen(2)
print ("socket is listening")   

conn, addr = localSocket.accept()
print("Connection from: " + str(addr))

while (True):
    try:
        data = conn.recv(1024)
        print(data)
        if not data:
            break
        conn.sendAll(data.encode())
    except:
        localSocket.close()
        print("Error! {}".format(Exception))

localSocket.close()