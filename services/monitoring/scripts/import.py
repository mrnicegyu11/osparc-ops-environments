from environs import Env
import os
import glob
import json
import requests


env = Env()
env.read_env("./../../../repo.config", recurse=False)


if __name__ == '__main__':


    # We first import the datasources
    url = "https://monitoring." + env.str('MACHINE_FQDN') + "/grafana/api/"
    session = requests.Session()
    session.auth = (env.str('SERVICES_USER'), env.str('SERVICES_PASSWORD'))
    #auth_token='eyJrIjoiVXlFMDVaZzJOWEFXN1pIcGlXMkptT2hzdDdDVDNXMWUiLCJuIjoidGVzdCIsImlkIjoxfQ=='
    #hed = {'Authorization': 'Bearer ' + auth_token, 'Content-Type': 'application/json'}
    hed = {'Content-Type': 'application/json'}


    directories = glob.glob("./../grafana/" + env.str('MACHINE_FQDN') + "/datasources/*")
    for file in directories:
        with open(file) as jsonFile:
            jsonObject = json.load(jsonFile)
            jsonFile.close()

        # We add the credentials for the PGSQL Databases with the secureJsonData field (password can't be exported so we have to set it here manually)
        if jsonObject["type"] == "postgres":
            jsonObject["secureJsonData"] = { "password": env.str('POSTGRES_GRAFANA_PASSWORD') }
            jsonObject["user"] = env.str('POSTGRES_GRAFANA_USER')
            print(jsonObject)
        
        r = session.post(url + "datasources", json = jsonObject, headers=hed)
        print(r.text)


    # Second, we import the folders structure
    directoriesData = []
    directories = glob.glob("./../grafana/"+ env.str('MACHINE_FQDN') + "/dashboards/*")
    # We can't create folder with their originial Ids, so we store them and simulate how Grafana will create the new Ids (1, 2, 3, etc)
    countIds = 1
    for directory in directories:
        for file in glob.glob(directory + "/*"):
            with open(file) as jsonFile:
                jsonObject = json.load(jsonFile)
                jsonFile.close()
                break
        directoriesData.append({'title' : os.path.basename(os.path.normpath(directory)), 'oldId': jsonObject["meta"]["folderId"], "newId" : countIds })
        countIds =  countIds + 1

    # We add them in grafana
    print(directoriesData)
    for directoryData in directoriesData:
        r = session.post(url + "folders", json = directoryData, headers=hed)
        print(r.text)

    # Finally we import the dashboards
    for directory in directories:
        for file in glob.glob(directory + "/*"):
            with open(file) as jsonFile:
                jsonObject = json.load(jsonFile)
                jsonFile.close()
                #jsonObject["meta"]["id"] = "null"
                #jsonObject["id"] = "null"
                #print(jsonObject)

                # New id for the folder
                folder = [folder for folder in directoriesData if folder["oldId"] == jsonObject["meta"]["folderId"]]
                print(folder)
                dashboard = {"Dashboard": jsonObject["dashboard"] }
                dashboard["Dashboard"]["id"] = 'null'
                dashboard["overwrite"] = True
                dashboard["folderId"] = folder[0]["newId"]
                print(dashboard)
                #{"Dashboard": jsonObject, "overwrite": True, "id": 'null', "folderId": folder[0]["newId"] }
                #print(dashboard)
                #print(url + "dashboards/db")
                r = session.post(url + "dashboards/db", json = dashboard, headers=hed)
                print(r.text)




