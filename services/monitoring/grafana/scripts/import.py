from environs import Env
import os
import glob
import json
import requests
import typer

env = Env()
env.read_env("./../../../../repo.config", recurse=False)



def main(foldername: str = ""):
    # We first import the datasources
    url = "https://monitoring." + env.str('MACHINE_FQDN') + "/grafana/api/"
    session = requests.Session()
    session.auth = (env.str('SERVICES_USER'), env.str('SERVICES_PASSWORD'))
    hed = {'Content-Type': 'application/json'}

    if foldername == "":
        directoriesDatasources = glob.glob("./../" + env.str('MACHINE_FQDN') + "/datasources/*")
    else:
        directoriesDatasources = glob.glob(foldername + "/datasources/*")
    print("**************** Add datasources *******************")
    for file in directoriesDatasources:
        with open(file) as jsonFile:
            jsonObject = json.load(jsonFile)
            jsonFile.close()

        # We add the credentials for the PGSQL Databases with the secureJsonData field 
        if jsonObject["type"] == "postgres":
            jsonObject["secureJsonData"] = { "password": env.str('POSTGRES_GRAFANA_PASSWORD') }
            jsonObject["user"] = env.str('POSTGRES_GRAFANA_USER')
        elif jsonObject["type"] == "Prometheus":
            jsonObject["basicAuthUser"] = env.str('SERVICES_USER')
            jsonObject["basicAuthPassword"] = env.str('SERVICES_PASSWORD')
        
        r = session.post(url + "datasources", json = jsonObject, headers=hed)
        print("Import of datasource " + jsonObject["name"])
        if r.status_code != 200:
            print("Received non-200 status code upon import: ", str(r.status_code))
            print("JSON file failed uploading:")
            print(json.dumps(jsonObject, sort_keys=True, indent=2))


    # Second, we import the folders structure
    directoriesData = []
    if foldername == "":
        directoriesDashboards = glob.glob("./../" + env.str('MACHINE_FQDN') + "/dashboards/*")
    else:
        directoriesDashboards = glob.glob(foldername + "/dashboards/*")
    # We can't create folder with their originial Ids, so we store them and simulate how Grafana will create the new Ids (1, 2, 3, etc)
    countIds = 1
    for directory in directoriesDashboards:
        for file in glob.glob(directory + "/*"):
            with open(file) as jsonFile:
                jsonObject = json.load(jsonFile)
                jsonFile.close()
                break
        directoriesData.append({'title' : os.path.basename(os.path.normpath(directory)), 'oldId': jsonObject["meta"]["folderId"], "newId" : countIds })
        countIds =  countIds + 1

    # We add them in grafana
    print("**************** Add folders *******************")
    for directoryData in directoriesData:
        r = session.post(url + "folders", json = directoryData, headers=hed)
        print("Add folder " + directoryData["title"])
        if r.status_code != 200:
            print("Received non-200 status code upon import: ", str(r.status_code))
            print("JSON file failed uploading:")
            print(json.dumps(directoryData, sort_keys=True, indent=2))

    print("**************** Add dashboards *******************")
    # Finally we import the dashboards
    for directory in directoriesDashboards:
        for file in glob.glob(directory + "/*"):
            with open(file) as jsonFile:
                jsonObject = json.load(jsonFile)
                jsonFile.close()

                # We set the folder ID - and the dashboard ID to null, also we remove the META part of the recorded dashboard - All of that being grafana requirements
                folder = [folder for folder in directoriesData if folder["oldId"] == jsonObject["meta"]["folderId"]]
                dashboard = {"Dashboard": jsonObject["dashboard"] }
                dashboard["Dashboard"]["id"] = 'null'
                dashboard["overwrite"] = True
                dashboard["folderId"] = folder[0]["newId"]
                r = session.post(url + "dashboards/db", json = dashboard, headers=hed)
                print("Add dashboard " + jsonObject["dashboard"]["title"])
                if r.status_code != 200:
                    print("Received non-200 status code upon import: ", str(r.status_code))
                    print("JSON file failed uploading:")
                    print(json.dumps(dashboard, sort_keys=True, indent=2))

if __name__ == "__main__":
    """
    Imports grafana dashboard from dumped json files via the Grafana API

    If --foldername is used, the data is taken from this location.
    Otherwise, the default ops-repo folder is assumed.
    """
    typer.run(main)
