import pickle

def main():
    with open('data.pkl', 'rb') as f:
        obj = pickle.load(f)   #  unsafe!
    print("Loaded object:", obj)

if __name__ == "__main__":
    main()
