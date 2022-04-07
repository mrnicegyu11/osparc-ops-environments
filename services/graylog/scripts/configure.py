from environs import Env
import os
import glob
import json
import requests
from tenacity import retry, stop_after_attempt
from time import sleep


env = Env()
env.read_env("./../../../repo.config", recurse=False)



@retry(stop=stop_after_attempt(100))
def checkGraylogOnline():
    url = "https://monitoring." + env.str('MACHINE_FQDN') + "/graylog/api/users"
    hed = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    session = requests.Session()
    r = session.get(url, headers=hed)
    if r.status_code != 401:
            sleep(5)
            print("Waiting for graylog to run...")
            raise Exception
    else:
        print("Graylog is online :)")


if __name__ == '__main__':
    try:
        checkGraylogOnline()
    except Exception:
        print("Waiting is still not online. Graylog script will now stop")
        pass

    # We check if graylog has inputs, if not we add a new one
    url = "https://monitoring." + env.str('MACHINE_FQDN') + "/graylog/api/system/inputs"
    hed = {'Content-Type': 'application/json', 'Accept': 'application/json', 'X-Requested-By': 'cli'}
    session = requests.Session()
    session.auth = (env.str('SERVICES_USER'), env.str('SERVICES_PASSWORD'))
    r = session.get(url, headers=hed)
    if int(r.json()["total"]) == 0:
        print("No input found.")
        json_data= {
		"title": "standard GELF UDP input",
		"type": "org.graylog2.inputs.gelf.udp.GELFUDPInput",
		"global": "true",
		"configuration": {
			"bind_address": "0.0.0.0",
			"port":12201
		    }       
	    }
        json_dump = json.dumps(json_data)
        r = session.post(url, headers=hed, data=json_dump)
        if r.status_code == 201:
            print("Input added with success !")
        else:
            print("Error while adding the input. Status code of the request : " + str(r.status_code) + " " + r.text)
        print(r)
    else:
        print(str(r.json()["total"]) + " input(s) have been found.")
    
    # Configure sending email notifications
    url = "https://monitoring." + env.str('MACHINE_FQDN') + "/graylog/api/events/notifications"
    raw_data = '{"title":"Graylog ' + env.str('MACHINE_FQDN') + ' mail notification","description":"","config":{"sender":"","subject":"Graylog event notification: ${event_definition_title}","user_recipients":[],"email_recipients":["' +  env.str('OSPARC_DEVOPS_MAIL_ADRESS') + '"],"type":"email-notification-v1"}}'
    r = session.post(url, headers=hed,data=raw_data)
    if r.status_code == 200:
        print("Mail Notification added with success !")
    else:
        print("Error while adding the Mail Notification. Status code of the request : " + str(r.status_code) + " " + r.text)