import json
import os
import hashlib
import requests
from pathlib import Path
from datetime import datetime
import sys



class Backup:
 
  def __init__(self):
    print("MainClass instanziiert")
    self.jobConfigJson = self.loadJobConfigJson()

    
    #pc.listfolder(folderid=0)
    #self.getDigest()
    #self.getPCloudAccessToken()
    self.runJobsPCloud()
    #
    #self.getFolderMetadata("/archive-tst/asdf")

    

  def loadJobConfigJson(self):
    try:
     with open('../conf/pcloud-config.json') as f:
       jobConfigJson = json.load(f)

    except json.JSONDecodeError as e:
      print(f"Invalid JSON format: {e}")
    except KeyError as e:
      print(f"Missing expected key: {e}")

    return jobConfigJson
  

  def convertPathToSha256Path(self, path):
      path = os.path.normpath(path)
      pathParts = path.split(os.sep)
      #print(pathParts)

      convertedPath = ""

      for pathPart in pathParts:
        convertedPath += self.calcSHA256FromString(pathPart) + "/"

      return convertedPath
        




  
  def runJobsPCloud(self):
    print("Job started")
    srcRootDir = self.jobConfigJson['srcRootDir']
    backupJobPath = self.jobConfigJson['jobs'][0]['backupDir']
    backupPath = srcRootDir + backupJobPath
    #print(backupPath)
    
    for currentDir, dirs, files in Path(backupPath).walk(on_error=print):

      #relativeFilePath = currentDir.relative_to(srcRootDir)
      #print(relativeFilePath)
      #print(self.convertPathToSha256Path(relativeFilePath))

      relativeFilePath = currentDir.relative_to(srcRootDir)
      print("current relative path: " + str(relativeFilePath))
      sha256RelativePath = self.createDestinationFilePath(relativeFilePath)
      print("curreten sha256 path: " + str(sha256RelativePath))
      destinationPath = Path(self.jobConfigJson['destRootDir']).joinpath(sha256RelativePath)
      print("current full destination path: " + str(destinationPath) )
      convertedDesPath = str(destinationPath).replace('\\', '/')
      print("converted current dest path: " + convertedDesPath)
      self.createFolderIfNotExists(convertedDesPath)
  
      #create the metadata file path
      archiveMetaFilePath = Path(currentDir).joinpath(self.jobConfigJson['metadataFileName'])

      #create empty metadata file
      if not Path(archiveMetaFilePath).exists():
        self.createEmptyMetadataFile(archiveMetaFilePath)
      
      metadataJson = []
      metadataJsonDelete = []
      if Path(archiveMetaFilePath).exists():
        metadataJson = self.loadMetadataFile(archiveMetaFilePath)
        metadataJsonDelete = self.loadMetadataFile(archiveMetaFilePath)

        if not "path" in metadataJson:
          #convertedRelativeFilePath = self.convertPathToSha256Path(relativeFilePath)
          #print("File converted relative path: " + convertedRelativeFilePath)

          metadataJson['path'] = str(currentDir)
          metadataJson['files'] = []
          self.writeMetadataFile(archiveMetaFilePath, metadataJson)
       

      for file in files:

        # skip metadata file in current directory
        if file == self.jobConfigJson['metadataFileName']:
          continue

        fullFilePath = Path(currentDir).joinpath(file)
        print("full file path: " + str(fullFilePath))
        print("filen name:" + str(file))

        # file size is needed every time
        fileSize = Path(fullFilePath).stat().st_size
        print("File size: " + str(fileSize))

        #file modified date is neeeded every time
        fileModifiedDate = Path(fullFilePath).stat().st_mtime
        print("File modified date: " + str(fileModifiedDate))
        print("File modified date hr: " + str(datetime.fromtimestamp(fileModifiedDate)))

        # filesum is first not calculated
        fileSumSha256 = ""

        
        # check if file entry allready exists in json metadata file 
        if any(obj.get("name") == file for obj in metadataJson['files']):

          metadataJsonDelete['files'] = [item for item in metadataJsonDelete['files'] if item["name"] != file]


          
         
          jsonFileObject = next(itemFile for itemFile in metadataJson['files'] if itemFile["name"] == file)
          if not jsonFileObject['size'] == fileSize and not jsonFileObject['modDate'] == fileModifiedDate:
            fileSumSha256 =  self.calcSHA256FromFile(fullFilePath)
            print("File SHA256 sum: " + fileSumSha256)
            if not jsonFileObject['sha265'] == fileSumSha256:
              metadataJson['files'] = [obj for obj in metadataJson['files'] if obj.get('name') != file]
              fileState = "update"
          else:
            fileState = "existing"
        else:
          fileState = "new"


        print("FileState: " + fileState)
        if(fileState == "new" or fileState == "update") and file != self.jobConfigJson['metadataFileName']:

          fileSumSha256 =  self.calcSHA256FromFile(fullFilePath)
          print("File SHA256 sum: " + fileSumSha256)

          fileArray = {}
          fileArray['name'] = file
          fileArray['size'] = fileSize
          fileArray['modDate'] = fileModifiedDate
          fileArray['sha265'] = fileSumSha256

          metadataJson["files"].append(fileArray)

        #encrypt and upload file if state is new or updated
        if(fileState == 'new' or fileState == 'update'):
          print("upload file ...")
          sha256FileName = self.calcSHA256FromString(file)
          print(sha256FileName)
          self.uploadFile(fullFilePath, convertedDesPath)
        


      sha256MetaDataFileName = self.calcSHA256FromString(self.jobConfigJson["metadataFileName"])
      print("metadata Filename: " + sha256MetaDataFileName)
      metaDataFilePath = Path(currentDir).joinpath(self.jobConfigJson["metadataFileName"])
      self.uploadFile(metaDataFilePath, convertedDesPath)

      print("-----------------------------------------------------")
      print("See delete files: " + str(metadataJsonDelete['files']))
      for item in metadataJsonDelete['files']:
        fileToDelete = item['name']
        deletePath = str(convertedDesPath) + "/" + fileToDelete
        print(deletePath)
        self.deleteFile(deletePath)
        #remove file in metadata json before writing
        metadataJson['files'] = [item for item in metadataJson['files'] if item["name"] != fileToDelete]


      #write metadata once for the whole directory to metadatafile
      self.writeMetadataFile(archiveMetaFilePath, metadataJson)

        



        


            #

            
            #sha256RelFilePath = self.calcSHA256FromString(relativeFilePath)
            #sha256FileSum = self.calcSHA256FromFile(fullFilePath)
            
            #print(relativeFilePath)

            #if(relativeFilePath in metadataJson.keys()):              
            #  if (sha256FileSum != metadataJson[relativeFilePath]['SHA265File']):
            #    pass
            
            
            #if(not relativeFilePath in metadataJson.keys()):
            #  self.writeMetadataFile(relativeFilePath, sha256RelFilePath, sha256FileSum)

            #print(relativeFilePath)  # Output: subdir/file.txt
            
            #print(self.calcSHA256FromFile(fullFilePath))
            #print(self.calcSHA256FromString(relativeFilePath))

  def createDestinationFilePath(self, relativeFilePath):
    sha256Path = []
    for part in relativeFilePath.parts:
      sha256Path.append(self.calcSHA256FromString(part))
    return Path(*sha256Path)
    


  def loadMetadataFile(self, archiveMetaFilePath):
    try:
     with open(archiveMetaFilePath) as f:
       metadataJson = json.load(f)

    except json.JSONDecodeError as e:
      print(f"Invalid JSON format: {e}")
    except KeyError as e:
      print(f"Missing expected key: {e}")

    return metadataJson
  

  # Authentication
  def getDigest(self):
    url = "https://eapi.pcloud.com/getdigest"
    response = requests.get(url).json()
    print(response)
    return bytes(response["digest"], "utf-8")
  

  def getPCloudAccessTokenOld(self):
    # Requires username/password - not recommended
    auth_url = "https://eapi.pcloud.com/userinfo"

    username = "accounts@m-mosimann.com"
    password = "fkJCT1djkjInKzrig_8AKdMiHqkPayFi"
    
    params = {
      "getauth": 1,
      "logout": 1,
      "username": username,
      "password" : password
    }

    response = requests.get(auth_url, params=params)
    authToken = response.json()['auth']

    print(authToken)

    return authToken
  

  def getPCloudAccessToken(self):

    # Requires username/password - not recommended
    auth_url = "https://eapi.pcloud.com/userinfo"

    username = "accounts@m-mosimann.com".lower().encode('utf-8')
    password = "fkJCT1djkjInKzrig_8AKdMiHqkPayFi".encode('utf-8')
    digest = self.getDigest()
    passwordDigest =  hashlib.sha1(password + bytes(hashlib.sha1(username).hexdigest(), "utf-8") + digest).hexdigest()
    
    params = {
      "getauth": 1,
      "logout": 1,
      "username": username.decode('utf-8'),
      "digest": digest.decode('utf-8'),
      "passworddigest" : passwordDigest
    }

    response = requests.get(auth_url, params=params)
    authToken = response.json()['auth']

    print(authToken)

    return authToken

  def uploadFile(self, filePath, targetPath):
    upload_url = 'https://eapi.pcloud.com/uploadfile'
    authToken = self.getPCloudAccessToken()
    #target_path = '/'  # or '/target-folder-in-pcloud'

    with open(filePath, 'rb') as f:
      files = {'file': f}
      params = {
        'auth': authToken,
        'path': targetPath
      }
      response = requests.post(upload_url, params=params, files=files)
      print(response.json())

  def deleteFile(self, filePath):
    upload_url = 'https://eapi.pcloud.com/deletefile'
    authToken = self.getPCloudAccessToken()
    #target_path = '/'  # or '/target-folder-in-pcloud'

   
    params = {
        'auth': authToken,
        'path': filePath
    }
    response = requests.post(upload_url, params=params)
    print(response.json())
    

  
  def createEmptyMetadataFile(self, archiveMetaFilePath):
    # Create empty dictionary (JSON object)
    data = {}
    # Write to file
    with open(archiveMetaFilePath, "w") as f:
      json.dump(data, f)


  def pathExists(self, folderPath):
    """Check if a folder exists in pCloud using API"""
    authToken = self.getPCloudAccessToken()
    url = "https://eapi.pcloud.com/listfolder"

    params = {
        "path": folderPath,
        "auth": authToken
    }
    
    response = requests.get(url, params=params).json()
    
    if response.get("result") == 0:
        return True
    elif response.get("result") == 2005:  # Folder not found error code
        return False
    else:
        raise Exception(f"API Error {response.get('result')}: {response.get('error')}")
    
  def createFolderIfNotExists(self, folderPath):
    """Check if a folder exists in pCloud using API"""
    authToken = self.getPCloudAccessToken()
    url = "https://eapi.pcloud.com/createfolderifnotexists"
    
    params = {
        "path": folderPath,
        "auth": authToken
    }

    response = requests.get(url, params=params).json()
    print(json.dumps(response, indent=2))
    
    if response.get("result") == 0:
        return True
    elif response.get("result") == 2001:  # Folder not found error code
        return False
    else:
        raise Exception(f"API Error {response.get('result')}: {response.get('error')}")


    

  def getFolderMetadata(self, folderPath):
    """Check if a folder exists in pCloud using API"""
    authToken = self.getPCloudAccessToken()
    url = "https://eapi.pcloud.com/listfolder"
    
    params = {
        "path": folderPath,
        "auth": authToken
    }
    
    response = requests.get(url, params=params).json()
    print(json.dumps(response, indent=2))
    
    if response.get("result") == 0:
        return True
    elif response.get("result") == 2005:  # Folder not found error code
        return False
    else:
        raise Exception(f"API Error {response.get('result')}: {response.get('error')}")


  def writeMetadataFile(self, filePath, data):
    #print(data)
    with open(filePath, 'w') as file:
      json.dump(data, file)


    
  def calcSHA256FromFile(self, filePath):
    sha256_hash = hashlib.sha256()
    with open(filePath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()
  
  
  def calcSHA256FromString(self, filePath):
    sha256_hash = hashlib.sha256()
    sha256_hash.update(str(filePath).encode('utf-8'))
    return sha256_hash.hexdigest()

  







if __name__ == "__main__":
 app = Backup()  # Instanz der Main-Klasse erstellen