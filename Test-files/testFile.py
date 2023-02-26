



def main():
    test = 'a'*50 + 'b'*50 + 'c'*50
    test2 = "Hej"
    print(test2)
    lenString = len(test)

    for i in range(lenString):
        print(test[0:32])
        test = test[32:]
