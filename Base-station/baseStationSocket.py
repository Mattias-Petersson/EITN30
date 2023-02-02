import socket


recieverPort = 9003 #Out of common port numbers on the Wiki, anything above 1024 is free to use and not reserved. 9003 is ours now.

# Create a socket using the port number, bind the local hostname and the arbitrary port to it:
localSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #UDP is SOCK_DRAM, TCP is SOCK_STREAM

localSocket.bind(('', recieverPort))

localSocket.listen()
conn, addr = localSocket.accept()
while (True):
    try:
        data = conn.recv(1024)
        print(data)
        if not data:
            break

    except:
        localSocket.close()
        print("Error! {}".format(Exception))

localSocket.close()