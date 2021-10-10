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
# Created date: Sept 21, 2021
# Last modified: Aug 24, 2021
# Tested with : Python 3.8
# Script Revision: 0.5
#
##########################################################

# Import required python libraries

import os
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
Backup folders :

Create the following folders :

/data/backup/dayJ
/data/backup/dayJ-1
/data/backup/dayJ-2
/data/backup/dayJ-3
/data/backup/dayJ-4
/data/backup/dayJ-5
/data/backup/dayJ-6
/data/backup/dayJ-7

Before each new daily backup  :

1) Rotation :

/data/backup/day-J-7 rm files
/data/backup/day-J-6 mv to /data/backup/dayJ-7
/data/backup/day-J-5 mv to /data/backup/dayJ-6
/data/backup/day-J-4 mv to /data/backup/dayJ-5
/data/backup/day-J-3 mv to /data/backup/dayJ-4
/data/backup/day-J-2 mv to /data/backup/dayJ-3
/data/backup/day-J-1 mv to /data/backup/dayJ-2
/data/backup/day-J mv to /data/backup/dayJ-1

2) copy new backup files in /data/backup/dayJ
'''


def connexionftp(serveur="15.236.203.78" , nom='ftp1', mdpasse='root', passif=False):
    """connexion au serveur ftp et ouverture de la session
       - adresseftp: adresse du serveur ftp
       - nom: nom de l'utilisateur enregistré ('anonymous' par défaut)
       - mdpasse: mot de passe de l'utilisateur ('anonymous@' par défaut)
       - passif: active ou désactive le mode passif (True par défaut)
       retourne la variable 'ftplib.FTP' après connexion et ouverture de session
    """
    ftp = ftplib.FTP()
    ftp.connect(serveur)
    ftp.login(nom, mdpasse)
    ftp.set_pasv(passif)
    return ftp

def uploadftp(ftp, ficdsk, ftpPath):
    '''
    télécharge le fichier ficdsk du disque dans le rép. courant du Serv. ftp
        - ftp: variable 'ftplib.FTP' sur une session ouverte
        - ficdsk: nom du fichier disque avec son chemin en local
        - ficPath: chemin sur le FTP distant
    '''
    repdsk, ficdsk2 = os.path.split(ficdsk)
    ficftp = ficdsk2
    with open(ficdsk, "rb") as f:
        ftp.cwd(ftpPath)
        ftp.storbinary("STOR " + ficftp, f)

def fermerftp(ftp):
    """ferme la connexion ftp
       - ftp: variable 'ftplib.FTP' sur une connexion ouverte
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
    print("Bad value in " + CONFIG_FILE + ". Value of BACKUP_DEST should be S3 or FTP only. Exiting")
    exit(1)


# Checking if local backup folders already exists or not. If not, we will create them.

for index in range(int(BACKUP_RETENTION)):
    if index==0:
        BACKUP_PATH=BACKUP_ROOT_PATH + "/DAYJ"
    else:
        BACKUP_PATH=BACKUP_ROOT_PATH + "/DAYJ-" + str(index)
    try:
        os.stat(BACKUP_PATH)
    except:
        try:
            os.makedirs(BACKUP_PATH)
        except OSError as exc: 
            if exc.errno == errno.EEXIST and os.path.isdir(BACKUP_PATH):
                pass
    


# Part1 : Database backup.
print ("")
print ("Starting Backup of MySQL")

dumpcmd = "mysqldump -h " + DB_HOST + " " + DB_NAME + " > " + pipes.quote(BACKUP_PATH) + "/" + DB_NAME + ".sql"

os.system(dumpcmd)
gzipcmd = "gzip " + pipes.quote(BACKUP_PATH) + "/" + DB_NAME + ".sql"
os.system(gzipcmd)
localMysqlBackup=pipes.quote(BACKUP_PATH) + "/" + DB_NAME + ".sql.gz"

print ("")
print ("Backup of MySQL completed")

# Part2 : WP Site backup.

print ("")
print ("Starting backup of Wordpress Site folder")
#declare filename
wp_archive= BACKUP_PATH + "/" + "wordpress.site.tar.gz"

#open file in write mode
tar = tarfile.open(wp_archive,"w:gz")
tar.add(WP_PATH)
tar.close()

print ("")
print ("Backup of  Wordpress Site folder completed")


# Part 3 : Copy to BACKUP_DEST

if BACKUP_DEST == 'S3':
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
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_ACCESS_KEY, 
        config=my_config
    )

    for file in [localMysqlBackup,wp_archive]:
        file_name=os.path.basename(file)
        s3_client.upload_file(file, S3_BUCKET, file_name)

    print ("")
    print ("Copy to AWS S3 completed")   
    
else:
    print ("")
    print ("Starting Copy to FTP Server")    
    
    ftpserver=connexionftp(FTP_SERVER,FTP_USER,FTP_PASSWD)

    for index in range(int(BACKUP_RETENTION)-1):
        if index==0:
            FTP_PATH=FTP_ROOT_PATH + "/DAYJ"
        else:
            FTP_PATH=FTP_ROOT_PATH + "/DAYJ-" + str(index)
        try:
            ftpserver.mkd(FTP_PATH)
        except:
            pass

    # Delete DAYJ-RETENTION-1 folder
    FTP_PATH=FTP_ROOT_PATH + "/DAYJ-" + str(int(BACKUP_RETENTION)-1)
    try:
        ftpserver.rmd(FTP_PATH)
    except:
        pass


    # Move content of DAYJ-N to DAYJ-(N+1)
    for index in range(int(BACKUP_RETENTION)-1,0,-1):
        if index==0:
            FTP_PATH_FROM=FTP_ROOT_PATH + "/DAYJ"
            FTP_PATH_TO=FTP_ROOT_PATH + "/DAYJ-1"
        else:
            FTP_PATH_FROM=FTP_ROOT_PATH + "/DAYJ-" + str(index)
            FTP_PATH_TO=FTP_ROOT_PATH + "/DAYJ-" + str(index+1)
        ftpserver.rename(FTP_PATH_FROM,FTP_PATH_TO)
    
    # Create DAYJ folder
    FTP_PATH=FTP_ROOT_PATH + "/DAYJ"
    ftpserver.mkd(FTP_PATH)   

    for file in [localMysqlBackup,wp_archive]:
        print("Transfering" + file)
        result=uploadftp(ftpserver,file,FTP_PATH)

    fermerftp(ftpserver)

    print ("")
    print ("Copy to FTP Server completed")   



print ("")
print ("Backup script completed")
print ("Your backups have also been created locally in '" + BACKUP_PATH + "' directory")
