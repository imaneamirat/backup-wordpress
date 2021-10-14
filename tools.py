import os
import ftplib
import boto3
from botocore.config import Config


def moveFolderS3(s3,bucket,pathFrom, pathTo, VERBOSE=0):   
    response = s3.list_objects(Bucket=bucket,Prefix=pathFrom + "/")
    for content in response.get('Contents', []):
        old_key = content.get('Key')
        filename = old_key.split("/")[-1]
        new_key = pathTo + "/" + filename
        if VERBOSE == 2:
            print("Copy " + old_key + " to " + new_key + " in Bucket " + bucket)
        s3.copy_object(Bucket=bucket,CopySource="/" + bucket + "/" + old_key,Key=new_key) 
        s3.delete_object(Bucket=bucket,Key=old_key) 

def deleteFolderS3(s3,bucket,prefix,VERBOSE=0):
    response = s3.list_objects(Bucket=bucket,Prefix=prefix + "/")
    for content in response.get('Contents', []):
        key=content.get('Key')
        if VERBOSE == 2:
            print("Delete file " + key + " in Bucket " + bucket)
        s3.delete_object(Bucket=bucket,Key=key) 

def listObjectFolderS3(s3,bucket,prefix,VERBOSE=0):
    response = s3.list_objects(Bucket=bucket,Prefix=prefix + "/")
    for content in response.get('Contents', []):
        key=content.get('Key')
        print("key = " + key)

def connectftp(ftpserver = "172.16.30.32" , username = 'anonymous', password = 'anonymous@', passive = False):
    """connect to ftp server and open a session
       - ftpserver: IP address of the ftp server
       - username: login of the ftp user ('anonymous' by défaut)
       - password: password of the ftp user ('anonymous@' by défaut)
       - passive: activate or disable ftp passive mode (False par défaut)
       return the object 'ftplib.FTP' after connection and opening of a session
    """
    ftp = ftplib.FTP()
    ftp.connect(ftpserver)
    ftp.login(username, password)
    ftp.set_pasv(passive)
    return ftp

def uploadftp(ftp, ficdsk,ftpPath):
    '''
    Upload the file ficdsk from local folder to the current ftp folder
        - ftp: object 'ftplib.FTP' on an open session
        - ficdsk: local name of the file to upload
        - ficPath: FTP path where to store the file
    '''
    repdsk, ficdsk2 = os.path.split(ficdsk)
    ficftp = ftpPath + "/" + ficdsk2
    with open(ficdsk, "rb") as f:
        ftp.storbinary("STOR " + ficftp, f)

def closeftp(ftp):
    """Close FTP connection
       - ftp: variable 'ftplib.FTP' on open connection
    """
    try:
        ftp.quit()
    except:
        ftp.close() 