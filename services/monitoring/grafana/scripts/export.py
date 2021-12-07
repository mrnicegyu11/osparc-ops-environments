from environs import Env
import glob
import json
import os
import requests
import shutil


env = Env()
env.read_env("./../../../../repo.config", recurse=False)


if __name__ == '__main__':


    # We delete the previous files
    directory = "./../" + env.str('MACHINE_FQDN')
    if os.path.exists(directory):
        shutil.rmtree(directory)
    os.mkdir(directory)

    # We export the Datasources
    print("**************** Export datasources *******************")
    os.mkdir(directory + "/datasources")
    url = "https://monitoring." + env.str('MACHINE_FQDN') + "/grafana/api/"
    session = requests.Session()
    session.auth = (env.str('SERVICES_USER'), env.str('SERVICES_PASSWORD'))
    hed = {'Content-Type': 'application/json'}

    r = session.get(url + "datasources", headers=hed)
    for datasource in r.json():
        rDatasource = session.get(url + "datasources/" + str(datasource["id"]), headers=hed)
        with open(directory + "/datasources/" + str(datasource["id"]) + ".json", 'w') as outfile:
            # If the datasource is Prometheus, we remove the login/password credentials
            jsonData = rDatasource.json()
            if jsonData["type"] == "prometheus":
                jsonData["basicAuthUser"] = ""
                jsonData["basicAuthPassword"] = ""
            json.dump(jsonData, outfile) 
            print("Export datasource " + jsonData["name"])


    # We export the dashboards
    print("**************** Export dashboards *******************")
    os.mkdir(directory + "/dashboards")
    r = session.get(url + "search?query=%", headers=hed)
    for dashboard in r.json():
            rDashboard = session.get(url + "dashboards/uid/" + str(dashboard["uid"]), headers=hed)
            if rDashboard.json()["meta"]["isFolder"] is not True:
                if os.path.exists(directory + "/dashboards/" + rDashboard.json()["meta"]["folderTitle"]) == False:
                    os.mkdir(directory + "/dashboards/" + rDashboard.json()["meta"]["folderTitle"])

                with open(directory + "/dashboards/" + rDashboard.json()["meta"]["folderTitle"] + "/" + str(dashboard["id"]) + ".json", 'w') as outfile:
                    print("Export Dashboard " + rDashboard.json()["dashboard"]["title"])
                    json.dump(rDashboard.json(), outfile)
