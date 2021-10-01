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


def connexionftp(serveur="15.236.203.78" , nom='ftp1', mdpasse='root', passif=True):
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

def uploadftp(ftp, ficdsk, ficftp=None):
    '''
    télécharge le fichier ficdsk du disque dans le rép. courant du Serv. ftp
        - ftp: variable 'ftplib.FTP' sur une session ouverte
        - ficdsk: nom du fichier disque avec son chemin
        - ficftp: si mentionné => c'est le nom qui sera utilisé sur ftp
    '''
    repdsk, ficdsk2 = os.path.split(ficdsk)
    if ficftp==None:
        ficftp = ficdsk2
    with open(ficdsk, "rb") as f:
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

'''
Example of config file content :

[WP]
WP_PATH=/var/www/html
[DB]
DB_HOST=localhost
DB_NAME=wordpress
DB_USERNAME=wpu
DB_PASSWORD=Imane$2021!
[BACKUP]
LOCALBKPATH=/data/backup
BACKUP_DEST=S3
S3_BUCKET=ImaneAIC-WP
S3_ACCESS_KEY=XXXXXXXXXXX
S3_SECRET_ACCESS_KEY=YYYYYYYY
S3_DEFAULT_REGION=eu-west-3

Or
[BACKUP]
LOCALBKPATH=/data/backup
BACKUP_DEST=FTP
FTP_SERVER=ftp.imaneaic.com
FTP_USER=backupwp
FTP_PASSWD=1edd!ai3$
FTP_PATH=backup-wp
'''

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

WP_PATH = config.get('WP','WP_PATH')
DB_HOST = config.get('DB','DB_HOST')
DB_NAME = config.get('DB','DB_NAME')
DB_USERNAME = config.get('DB','DB_USERNAME')
DB_PASSWORD = config.get('DB','DB_PASSWORD')

BACKUP_DEST = config.get('BACKUP','BACKUP_DEST')
BACKUP_PATH = config.get('BACKUP','LOCALBKPATH')


if BACKUP_DEST == 'S3':
    S3_BUCKET = config.get('BACKUP','S3_BUCKET')
    S3_ACCESS_KEY = config.get('BACKUP','S3_ACCESS_KEY')
    S3_SECRET_ACCESS_KEY = config.get('BACKUP','S3_SECRET_ACCESS_KEY')
    S3_DEFAULT_REGION = config.get('BACKUP','S3_DEFAULT_REGION')
elif BACKUP_DEST == 'FTP':
    FTP_SERVER = config.get('BACKUP','FTP_SERVER')
    FTP_USER = config.get('BACKUP','FTP_USER')
    FTP_PASSWD = config.get('BACKUP','FTP_PASSWD')
    FTP_PATH = config.get('BACKUP','FTP_PATH')
else:
    print("Bad value in " + CONFIG_FILE + ". Value of BACKUP_DEST should be S3 or FTP only. Exiting")
    exit(1)

# Getting current DateTime to create the separate backup folder like "20210921".
DATETIME = time.strftime('%Y%m%d')
TODAYBACKUPPATH = BACKUP_PATH + '/' + DATETIME

# Checking if backup folder already exists or not. If not exists will create it.
try:
    os.stat(TODAYBACKUPPATH)
except:
    os.mkdir(TODAYBACKUPPATH)

# Part1 : Database backup.
print ("")
print ("Starting Backup of MySQL")

dumpcmd = "mysqldump -h " + DB_HOST + " -u " + DB_USERNAME + " -p\'" + DB_PASSWORD + "\' " + DB_NAME + " > " + pipes.quote(TODAYBACKUPPATH) + "/" + DB_NAME + ".sql"

os.system(dumpcmd)
gzipcmd = "gzip " + pipes.quote(TODAYBACKUPPATH) + "/" + DB_NAME + ".sql"
os.system(gzipcmd)
localMysqlBackup=pipes.quote(TODAYBACKUPPATH) + "/" + DB_NAME + ".sql.gz"

print ("")
print ("Backup of MySQL completed")

# Part2 : WP Site backup.

print ("")
print ("Starting backup of Wordpress Site folder")
#declare filename
wp_archive= TODAYBACKUPPATH + "/" + "wordpress.site.tar.gz"

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
        file_name=DATETIME + "/" + os.path.basename(file)
        s3_client.upload_file(file, S3_BUCKET, file_name)

    print ("")
    print ("Copy to AWS S3 completed")   
    
else:
    print ("")
    print ("Starting Copy to FTP Server")    
    
    ftp=connexionftp(FTP_SERVER,FTP_USER,FTP_PASSWD)
    ftp.cwd(FTP_PATH)

    for file in [localMysqlBackup,wp_archive]:
        result=uploadftp(ftp,file)

    fermerftp(ftp)

    print ("")
    print ("Copy to FTP Server completed")   



print ("")
print ("Backup script completed")
print ("Your backups have also been created locally in '" + TODAYBACKUPPATH + "' directory")
