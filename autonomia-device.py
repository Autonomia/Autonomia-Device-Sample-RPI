#!/usr/bin/env python
"""
  Device-side Autonomia SDK test application

  Copyright 2016 Visible Energy Inc. All Rights Reserved.
"""
__license__ = """
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import time
import json
import os
import subprocess
from autonomialib import AutonomiaClient
from gpslib import GPS

gpsDevice='/dev/ttyACM0'
gpsSpeed='19200'

# Fetch from the environment the application Key created in the Autonomia portal
#
application_key = os.environ.get('AUTONOMIA_APP_KEY', None)

# Telemetry message period in seconds
#
telemetry_period = 15
# Telemetry data message
#
def telemetry_msg():
  ret = {}
  ret['time'] = str(int(time.time() * 1000))
  ret['device_id'] = auto.device_id
  return ret

def applog(msg, escape=False):
  """
  Simple system logger.
  """
  systime = int(time.time())
  if escape:
    print ("[%d] %s" % (systime, msg.replace('\n', '#015').replace('\r', '#012')))
  else:
    print ("[%d] %s" % (systime, msg))


# --------------------
# 
# RPC Methods

def _get_info(params):
  try:
      uptime = subprocess.Popen("/bin/cat /proc/uptime", shell=True, stdout=subprocess.PIPE).stdout.read().decode()
      meminfo = subprocess.Popen("head -3 /proc/meminfo", shell=True, stdout=subprocess.PIPE).stdout.read().decode()
      cpuinfo = subprocess.Popen("tail -12 /proc/cpuinfo", shell=True, stdout=subprocess.PIPE).stdout.read().decode()
      return '\nUpTime-------\n' + uptime + '\nMemInfo-------\n' + meminfo + '\nCpuInfo-------\n' + cpuinfo
  except Exception, e:
      print e
      return "{\"msg\":\"" + e + "\"}"

def _rexec(params):
  """Start a subprocess shell to execute the specified command and return its output.

  params - a one element list ["/bin/cat /etc/hosts"]
  """
  # check that params is a list
  if not isinstance(params, list) or len(params) == 0:
     return "Parameter must be a not empty list"    
  command = params[0]
  try:
      subprocess.check_call(command,shell=True)
      out = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE).stdout.read()
      return '\n' + out.decode()
  except Exception, e:
      print e
      return "{\"msg\":\"Invalid command.\"}"

def _video_devices(params):
  """List available video devices (v4l)."""
  vdevices = list_camera_devices()
  ret = {}
  ret['devices'] = vdevices[0]
  ret['names'] = vdevices[1]
  return ret

def _set_telemetry_period(params):
  """Set telemetry period in seconds.

  params - JSON object {'period':5} 
  """   
  if type(params) is not dict or 'period' not in params.keys():
      return {"success": False}
  if params['period'] <= 0:
      return {"success": False}
  
  telemetry_period=params['period']
  return {"success": True}

def _video_stop(params):
  auto.video_stop()
  return {"success": True}  

def _video_start(params):
  if type(params) is not dict or 'timestamp' not in params.keys():
    return {"success": False}
  timestamp = params['timestamp']
  _, url = auto.video_start(timestamp)
  return {"success": True, "url": url}  

#-----------------------------------

# Instantiate a global Autonomia object
auto = AutonomiaClient(application_key, applog, use_ssl=False)
auto.debug = False

# RPC method binding
rpc_methods = ({'name':'get_info','function':_get_info},
               {'name':'rexec','function':_rexec},
               {'name':'video_devices','function':_video_devices},
               {'name':'set_telemetry_period','function':_set_telemetry_period},
               {'name':'video_start','function':_video_start},
               {'name':'video_stop','function':_video_stop},
)

# Attach the device to Autonomia
connected = False

# Connecting loop
while not connected:
  ret = auto.attach(rpc_methods, device_info="ROV")
  if auto.error != 0:
    print "Error in attaching to Autonomia. Retrying ...", auto.perror()
    time.sleep(10)
    continue
  # Get the confirmation message from the server
  try:
    ret_obj = json.loads(ret)
  except Exception, e:
    print "Error in parsing the message returned after attaching to Autonomia. Message:", ret
    time.sleep(10)
    continue
  connected = True

# The server returns an object like: {"msg":"200 OK","heartbeat":60,"timestamp":1441405206}
applog("Device \"%s\" attached to Autonomia. Server timestamp: %d" % (auto.device_id, ret_obj['timestamp']))
applog("Server returned: %s" % ret)

# Connecting to GPS
gps = GPS(applog)
ret = gps.connect(gpsDevice, gpsSpeed)
if ret:
  applog("Connected to GPS.")
else:
  gps = None
  applog("Error connecting to GPS on % s. Disabling." % gpsDevice)

applog("Starting camera.")
_, url = auto.video_start()
applog("Streaming to %s" % url)

# main loop
last_telemetry = 0
while True:
  now = time.time()

  # Send telemetry data
  if telemetry_period < now - last_telemetry: 
    msg = telemetry_msg()
    if gps: 
      print "GPS readings", gps.readings
      msg.gps = gps.readings
    if auto.send_data(json.dumps(msg)) < 0:
      applog("Error in sending telemetry data.")
    else:
      applog("Sending telemetry data: %s " % msg)
    last_telemetry = now

  time.sleep(1)
