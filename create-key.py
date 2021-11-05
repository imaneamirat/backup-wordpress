from Crypto.Random import get_random_bytes
import argparse

# create parser
parser = argparse.ArgumentParser()

# add arguments to the parser
parser.add_argument("--path",type=str,default="./Key")

# parse the arguments
args = parser.parse_args()


key_location = args.path # A safe place to store a key. Can be on a USB or even locally on the machine (not recommended unless it has been further encrypted)

# Generate the key
key = get_random_bytes(32) # 32 bytes * 8 = 256 bits (1 byte = 8 bits)

# Save the key to a file
file_out = open(key_location, "wb") # wb = write bytes
file_out.write(key)
file_out.close()

'''
# Later on ... (assume we no longer have the key)
file_in = open(key_location, "rb") # Read bytes
key_from_file = file_in.read() # This key should be the same
file_in.close()

# Since this is a demonstration, we can verify that the keys are the same (just for proof - you don't need to do this)
assert key == key_from_file, 'Keys do not match' # Will throw an AssertionError if they do not match
'''