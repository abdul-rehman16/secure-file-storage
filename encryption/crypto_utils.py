from cryptography.fernet import Fernet

# ONLY RUN THIS ONCE — to generate a key
# key = Fernet.generate_key()
# print(key.decode())  # Copy this and paste it below

# 🔐 Paste the key you generated here
key = b'='

fernet = Fernet(key)

def encrypt_file(file_data):
    return fernet.encrypt(file_data)

def decrypt_file(encrypted_data):
    return fernet.decrypt(encrypted_data)
