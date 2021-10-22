import sys
import os
from Crypto.Cipher import AES
from Crypto import Random
from binascii import b2a_hex
from pathlib import Path

def encrypt_file(path,key):
    # get the plaintext
    with open(path,"rb") as f:
        clear_data = f.read()

    # The key length must be 16 (AES-128), 24 (AES-192), or 32 (AES-256) Bytes.
    cipher = AES.new(key, AES.MODE_GCM)
    cipher_data, tag = cipher.encrypt_and_digest(clear_data)
    
    # output
    file_out = open(path + ".bin", "wb")
    [ file_out.write(x) for x in (cipher.nonce, tag, cipher_data) ]
    file_out.close()


def decrypt_file(path,key):
    # get the plaintext
    with open(path,"rb") as f:
        nonce, tag, cipher_data = [ f.read(x) for x in (16, 16, -1) ]

    # let's assume that the key is somehow available again
    cipher = AES.new(key, AES.MODE_GCM, nonce)
    clear_data = cipher.decrypt_and_verify(cipher_data, tag)

    # output
    fullpath = Path(path)
    path_dest = fullpath.with_suffix('')

    with open(path_dest, "wb") as file_out:
        file_out.write(clear_data)