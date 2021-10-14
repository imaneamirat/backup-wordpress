#!/usr/bin/python3

###########################################################
#
# This python script is used to backup Wordpress website and associated mysql database
# using mysqldump and tar utility.
# Backups are copied to either :
# - AWS S3 and encrypted using a private AES-256 key
# or
# - FTP server
#
# This scripts needs root privileges
#
# Written by : Imane AMIRAT
# Created date: Jul 24, 2021
# Last modified: Oct 13, 2021
# Tested with : Python 3.8
# Script Revision: 0.8
#
##########################################################

# Import required python libraries

import os
import shutil
import errno
import time
import datetime
import pipes
import sys
import configparser
import tarfile
import boto3
import ftplib
from botocore.config import Config


# By Default, this script will read configuration from file /etc/backup-wp.conf
# Todo : Add the option -f to read parameters from a specified filename in the command line parameter
# Todo : Backup Folder Rotation Strategy
'''
Init : 

Create the following folders :

/data/backup/dayJ
/data/backup/dayJ-1
/data/backup/dayJ-2
/data/backup/dayJ-3
/data/backup/dayJ-4
/data/backup/dayJ-5
/data/backup/dayJ-6


Before each new daily backup  :

1) Rotation :

rmdir /data/backup/day-J-6 
mv /data/backup/day-J-5 to /data/backup/dayJ-6
mv /data/backup/day-J-4 to /data/backup/dayJ-5
mv /data/backup/day-J-3 to /data/backup/dayJ-4
mv /data/backup/day-J-2 to /data/backup/dayJ-3
mv /data/backup/day-J-1 to /data/backup/dayJ-2
mv /data/backup/day-J to /data/backup/dayJ-1
mkdir /data/backup/dayJ

2) copy new backup files in /data/backup/dayJ
'''

VERBOSE = 2

def moveFolderS3(s3,bucket,pathFrom, pathTo):   
    response = s3.list_objects(Bucket=bucket,Prefix=pathFrom + "/")
    for content in response.get('Contents', []):
        old_key = content.get('Key')
        filename = old_key.split("/")[-1]
        new_key = pathTo + "/" + filename
        if VERBOSE == 2:
            print("Copy " + old_key + " to " + new_key + " in Bucket " + bucket)
        s3.copy_object(Bucket=bucket,CopySource="/" + bucket + "/" + old_key,Key=new_key) 
        s3.delete_object(Bucket=bucket,Key=old_key) 

def deleteFolderS3(s3,bucket,prefix):
    response = s3.list_objects(Bucket=bucket,Prefix=prefix + "/")
    for content in response.get('Contents', []):
        key=content.get('Key')
        if VERBOSE == 2:
            print("Delete file " + key + " in Bucket " + bucket)
        s3.delete_object(Bucket=bucket,Key=key) 

def listObjectFolderS3(s3,bucket,prefix):
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

CONFIG_FILE = "/etc/backup-wp.conf"

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

WP_PATH = config.get('WP','WP_PATH')
DB_HOST = config.get('DB','DB_HOST')
DB_NAME = config.get('DB','DB_NAME')

BACKUP_RETENTION = config.get('BACKUP','BACKUP_RETENTION')
BACKUP_DEST = config.get('BACKUP','BACKUP_DEST')
BACKUP_ROOT_PATH = config.get('BACKUP','LOCALBKPATH')


if BACKUP_DEST == 'S3':
    S3_BUCKET = config.get('BACKUP','S3_BUCKET')
    S3_ACCESS_KEY = config.get('BACKUP','S3_ACCESS_KEY')
    S3_SECRET_ACCESS_KEY = config.get('BACKUP','S3_SECRET_ACCESS_KEY')
    S3_DEFAULT_REGION = config.get('BACKUP','S3_DEFAULT_REGION')
elif BACKUP_DEST == 'FTP':
    FTP_SERVER = config.get('BACKUP','FTP_SERVER')
    FTP_USER = config.get('BACKUP','FTP_USER')
    FTP_PASSWD = config.get('BACKUP','FTP_PASSWD')
    FTP_ROOT_PATH = config.get('BACKUP','FTP_PATH')
else:
    if VERBOSE >= 1:
        print("Bad value in " + CONFIG_FILE + ". Value of BACKUP_DEST should be S3 or FTP only. Exiting")
    exit(1)

# Starting process
if VERBOSE >= 1:
    print("")
    print("Starting Wordpress backup process")

# Checking if local backup folders already exists or not. If not, we will create them.
if VERBOSE == 2:
        print("")
        print("Create local backup folders if not existing")
for index in range(int(BACKUP_RETENTION)):
    if index == 0:
        BACKUP_PATH = BACKUP_ROOT_PATH + "/DAYJ"
    else:
        BACKUP_PATH = BACKUP_ROOT_PATH + "/DAYJ-" + str(index)
    try:
        os.stat(BACKUP_PATH)
    except:
        try:
            os.makedirs(BACKUP_PATH)
        except OSError as exc: 
            if exc.errno == errno.EEXIST and os.path.isdir(BACKUP_PATH):
                pass

# Local Backup Rotation
if VERBOSE == 2:
        print("")
        print("Local backup folders rotation")
        print("")

# Delete DAYJ-RETENTION-1 folder
BACKUP_PATH = BACKUP_ROOT_PATH + "/DAYJ-" + str(int(BACKUP_RETENTION)-1)
try:
    if VERBOSE == 2:
        print("Delete of " + BACKUP_PATH)
    shutil.rmtree(BACKUP_PATH, ignore_errors=False, onerror=None)
except:
    if VERBOSE == 2:
        print("Error during delete of " + BACKUP_PATH)
    pass


# Move content of DAYJ-N to DAYJ-(N+1)
for index in range(int(BACKUP_RETENTION)-2,-1,-1):
    if index == 0:
        BACKUP_PATH_FROM = BACKUP_ROOT_PATH + "/DAYJ"
        BACKUP_PATH_TO = BACKUP_ROOT_PATH + "/DAYJ-1"
    else:
        BACKUP_PATH_FROM = BACKUP_ROOT_PATH + "/DAYJ-" + str(index)
        BACKUP_PATH_TO = BACKUP_ROOT_PATH + "/DAYJ-" + str(index+1)
    if VERBOSE == 2:
        print("Rename from " + BACKUP_PATH_FROM + " to " + BACKUP_PATH_TO)

    os.rename(BACKUP_PATH_FROM,BACKUP_PATH_TO)
    
# Create DAYJ folder
BACKUP_PATH = BACKUP_ROOT_PATH + "/DAYJ"
if VERBOSE == 2:
        print("Create folder " + BACKUP_PATH )
os.mkdir(BACKUP_PATH)     


# Part1 : Database backup.
if VERBOSE >=1 :
    print ("")
    print ("Starting Backup of MySQL")

dumpcmd = "mysqldump -h " + DB_HOST + " " + DB_NAME + " > " + pipes.quote(BACKUP_PATH) + "/" + DB_NAME + ".sql"

os.system(dumpcmd)
gzipcmd = "gzip " + pipes.quote(BACKUP_PATH) + "/" + DB_NAME + ".sql"
os.system(gzipcmd)
localMysqlBackup=pipes.quote(BACKUP_PATH) + "/" + DB_NAME + ".sql.gz"

if VERBOSE == 2:
        print("Local MySQL dump copied in " + localMysqlBackup )

if VERBOSE >=1:
    print ("")
    print ("Backup of MySQL completed")

# Part2 : WP Site backup.

if VERBOSE >=1:
    print ("")
    print ("Starting backup of Wordpress Site folder")
#declare filename
wp_archive = BACKUP_PATH + "/" + "wordpress.site.tar.gz"

#open file in write mode
tar = tarfile.open(wp_archive,"w:gz")
tar.add(WP_PATH)
tar.close()

if VERBOSE == 2:
        print("Local Wordpress site dump copied in " + wp_archive )

if VERBOSE >= 1:
    print ("")
    print ("Backup of  Wordpress Site folder completed")


# Part 3 : Copy to BACKUP_DEST

if BACKUP_DEST == 'S3':
    if VERBOSE >= 1:
        print ("")
        print ("Starting Copy to AWS S3")

    bucket_name = S3_BUCKET # name of the bucket

    my_config = Config(
        region_name = S3_DEFAULT_REGION,
        retries = {
            'max_attempts': 10,
            'mode': 'standard'
        }
    )


    s3_client = boto3.client(
        's3',
        aws_access_key_id = S3_ACCESS_KEY,
        aws_secret_access_key = S3_SECRET_ACCESS_KEY, 
        config = my_config
    )

    # Rotation of backup "folders"
    if VERBOSE == 2:
        print("")
        print ("S3 folders rotation")  
    # Delete DAYJ-RETENTION-1 folder
    S3_PATH="DAYJ-" + str(int(BACKUP_RETENTION)-1)
    if VERBOSE == 2:
        print("")
        print("First delete all files in " + S3_PATH    )
    deleteFolderS3(s3_client,S3_BUCKET,S3_PATH)

    if VERBOSE == 2:
        print("")

    # Move content of DAYJ-N to DAYJ-(N+1)
    for index in range(int(BACKUP_RETENTION)-2,-1,-1):
        if index == 0:
            S3_PATH_FROM = "DAYJ"
            S3_PATH_TO = "DAYJ-1"
        else:
            S3_PATH_FROM = "DAYJ-" + str(index)
            S3_PATH_TO = "DAYJ-" + str(index+1)
        if VERBOSE == 2:
            print("Move files from " + S3_PATH_FROM + " to " + S3_PATH_TO) 
#        listObjectFolderS3(s3_client,S3_BUCKET,S3_PATH_FROM,S3_PATH_TO)
        moveFolderS3(s3_client,S3_BUCKET,S3_PATH_FROM,S3_PATH_TO)
    
    # Finaly copy new backup files to DAYJ folder
    for file in [localMysqlBackup,wp_archive]:
        file_name = os.path.basename(file)
        new_name = "DAYJ/" + file_name
        if VERBOSE == 2:
            print("Transfering file " + file_name + " to " + new_name) 
        s3_client.upload_file(file, S3_BUCKET, new_name)

    if VERBOSE >= 1:
        print ("")
        print ("Copy to AWS S3 completed")   
    
else:
    if VERBOSE >= 1:
        print ("")
        print ("Starting Copy to FTP Server")    
        print ("")

    ftpserver=connectftp(FTP_SERVER,FTP_USER,FTP_PASSWD)
    ftpserver.cwd(FTP_ROOT_PATH)
    
    if VERBOSE == 2:
        print ("Init : Create FTP folder if not existing")   

    for index in range(int(BACKUP_RETENTION)):
        if index == 0:
            FTP_PATH = "DAYJ"
        else:
            FTP_PATH = "DAYJ-" + str(index)
        if VERBOSE == 2:
            print("Create folder " + FTP_PATH)
        
        try:
            ftpserver.mkd(FTP_PATH)
        except:
            if VERBOSE == 2:
                print("Error during Create folder of " + BACKUP_PATH + " ie Folder already exist")
            pass

    # Backup Rotation
    if VERBOSE == 2:
        print("")
        print ("FTP folders rotation")  
    # Delete DAYJ-RETENTION-1 folder
    FTP_PATH="DAYJ-" + str(int(BACKUP_RETENTION)-1)
    if VERBOSE == 2:
        print("")
        print("First delete all files in " + FTP_PATH)
    ftpserver.cwd(FTP_PATH)
    for file in ftpserver.nlst():
        if VERBOSE == 2:
            print("Delete file " + file)
        ftpserver.delete(file)
    ftpserver.cwd("..")
    try:
        if VERBOSE == 2:
            print("Delete folder " + FTP_PATH)
        ftpserver.rmd(FTP_PATH)
    except:
        if VERBOSE == 2:
            print("Error during delete of folder " + FTP_PATH + " ie Folder not empty")
        pass
    
    if VERBOSE == 2:
        print("")

    # Move content of DAYJ-N to DAYJ-(N+1)
    for index in range(int(BACKUP_RETENTION)-2,-1,-1):
        if index == 0:
            FTP_PATH_FROM = "DAYJ"
            FTP_PATH_TO = "DAYJ-1"
        else:
            FTP_PATH_FROM = "DAYJ-" + str(index)
            FTP_PATH_TO = "DAYJ-" + str(index+1)
        if VERBOSE == 2:
            print("Rename from " + FTP_PATH_FROM + " to " + FTP_PATH_TO) 
        ftpserver.rename(FTP_PATH_FROM,FTP_PATH_TO)
    
    # Create DAYJ folder
    FTP_PATH="DAYJ"
    if VERBOSE == 2:
            print("")
            print("Create folder " + FTP_PATH)
            print("")
    ftpserver.mkd(FTP_PATH)   

    for file in [localMysqlBackup,wp_archive]:
        if VERBOSE >= 1:
            print("Transfering " + file + " to " + FTP_PATH)
        result=uploadftp(ftpserver,file,FTP_PATH)

    closeftp(ftpserver)

    if VERBOSE >= 1:
        print ("")
        print ("Copy to FTP Server completed")   



if VERBOSE >= 1:
    print ("")
    print ("Backup script completed")
    print ("Your backups have also been created locally in '" + BACKUP_PATH + "' directory")
