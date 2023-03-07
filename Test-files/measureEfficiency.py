import gzip
import numpy
import matplotlib.pyplot as plt

def testCompression():
    f = open('lorem.txt')
    str = f.read()
    byteString = str.encode('utf-8')
    totalLength = 2000 #len(byteString)
    x = numpy.arange(0, totalLength)
    y = []
    for i in range(totalLength):
        temp = gzip.compress(byteString[0:i])
        y.append(len(temp))

    plt.plot(x, y, label='Compression using py-gzip')
    plt.plot(x, 0.5*x, label='Half size of no compression')
    plt.plot(x, x, label='No compression')
    plt.xlabel('Payload length')
    plt.ylabel('Effective data sent')
    plt.legend(loc='best')
    plt.savefig('compressEfficiency.png')

def testFragment():
    x = numpy.arange(0, 65535)
    plt.plot(x, 32/31 * x, label='Our fragment method')
    plt.plot(x, 32/12 * x, label='Crafting a minimal IP packet for every fragment')
    plt.plot(x, 32/29 * x, label='Our "improved" fragment method')
    plt.xlabel("Total length")
    plt.ylabel("Total data sent including header")
    plt.legend(loc='best')
    plt.savefig("fragmentEfficiency.png")

if __name__ == "__main__":
    testCompression()
    plt.clf()
    testFragment()
    print("All done. :)")


