import artikcloud
from artikcloud.rest import ApiException
import sys, getopt
import time, json
from pprint import pprint

#===============global_variable_declaration_start===============#	
ledPin ='135'
waterInPin ='122'  #plz check pins 
waterOutPin ='123'
pumpPin ='125'

wlPin = '0'

HIGH = '1'
LOW = '0'

INPUT = 'in'
OUTPUT = 'out'

TRACE = None
recStart = 'OFF'
recentFull = 'OFF'
fullTime = None
manualWaterOut = 'OFF'

recordTime ={'wotime':None, 'wostart':False,
             'ptime':None, 'pstart':False,'plasttime':None}
#================global_variable_declaration_end================#		
 
#===================function_definition_start===================#
def digitalPinMode(pin, dir):  # pin and dir -> string type
  # export
  try:
    with open('/sys/class/gpio/export', 'wb', 0) as export_file:
      export_file.write(pin)
	debugprint("Exported pin {0}".format(pin))
  except:
    debugprint("Pin {0} has been export".format(pin))

  # direction
  try:
    path_dir = '/sys/class/gpio/gpio%s/direction' % pin
    with open(path_dir, 'wb', 0) as dir_file:
	  dir_file.write(dir)
	debugprint("Set pin {0} as digital {1}put".format(pin,dir))

  except:
    debugprint("Failed to set pin {0} direction".format(pin))
 
def digitalWrite(pin, val):  # pin and val -> string type
  path_val = '/sys/class/gpio/gpio%s/value' % pin
  with open(path_val, 'wb', 0) as val_file:
    val_file.write(val)
  debugprint("Pin {0}'s value has been set to {1}".format(pin,val))
	
def analogRead(pin): 
  path_anal = '/sys/devices/126c0000.adc/iio:device0/in_voltage%s_raw' % pin
  with open(path_anal, 'r') as anal_file:
    anal_val = float(anal_file.read(8))
  return anal_val
  
def debugprint(sentence):
  if TRACE > 3:
    print(sentence)

def ctrComp(operation):
  if operation == 'alloff':
    digitalWrite(pumpPin,LOW)
    digitalWrite(waterOutPin,LOW)
    digitalWrite(waterInPin,LOW)
  elif operation == 'waterin':
    digitalWrite(pumpPin,LOW)
    digitalWrite(waterOutPin,LOW)
    digitalWrite(waterInPin,HIGH)
  elif operation == 'waterout':
    digitalWrite(pumpPin,LOW)
    digitalWrite(waterOutPin,HIGH)
    digitalWrite(waterInPin,LOW)
  elif operation == 'pump':
    digitalWrite(pumpPin,HIGH)
    digitalWrite(waterOutPin,LOW)
    digitalWrite(waterInPin,LOW)    
  else:
    print('ctrComp(): need to check sys.')
#====================function definition_end====================#

#====================main()_definition_start====================#
def main(argv):
  DEFAULT_CONFIG_PATH = 'config.json'
  global TRACE
  global recStart
  global recentFull
  global fullTime
  global manualWaterOut
  global recordTime
  
  TRACE = sys.argv[1]  # for Debug
	
  with open(DEFAULT_CONFIG_PATH, 'r') as config_file:
    config = json.load(config_file)  # dict instance of config.json

  # Configure Oauth2 access token for the client application 
  artikcloud.configuration = artikcloud.Configuration()
  artikcloud.configuration.access_token = config['device_token']
  
  # Read ADC Pin (water level sensor)
  water_level = analogRead(wlPin)
  debugprint('water level is {0}'.format(water_level))
  
  # create an instance of the API class 
  api_instance = artikcloud.MessagesApi()
  
  # for getting actions
  count = 1		
  start_date = int(time.time()*1000) - 86400000
  end_date = int(time.time()*1000)
  order = 'desc'

  # Get Normalized Actions
  try:
    api_actions = api_instance.get_normalized_actions(count=count, end_date = end_date, start_date = start_date, order = order)
    Mode = str(api_actions.data[0].data.actions[0].parameters[u'Code'])
  debugprint(Mode)
  except ApiException as e:
    print("Exception when calling MessagesApi->get_normalized_actions: %s\n" % e)
  Mode = Mode.split(',')  
  STATE = Mode[0][6:]
  WATER = Mode[1][6:]
  PUMP = Mode[2][5:]
  LED = Mode[3][4:]
  
#------------------------- Controller_start---------------------#
  if recStart == 'OFF':
    if STATE == 'start':
	  recStart = 'ON'
	  debugprint('finallly recieve start: execute the operation next time ')	
	else:
	  debugprint('not yet recieve start')
  else:
    if STATE == 'auto':
	  # determine LED state
	  if LED == 'ON':
	    digitalWrite(ledPin,HIGH)
	  else:	# LED OFF
	    digitalWrite(ledPin,LOW)
	  if recentFull == 'OFF':
        if water_level > 1000:  # water-level reaches full
          recentFull = 'ON'        #record water reaches full
		  fullTime =int(time.time())  #record water first full time
		  recordTime['plasttime'] = fullTime  #last pump time == firstfulltime
		  manualWaterOut = 'OFF'   #delete the record of manual-water-out
		  ctrComp('alloff')
		else:
		  ctrComp('waterin')
      else:
        # time that passes from the moment that water reached full
	    elapsetime = int(time.time())-fullTime
	    if manualWaterOut == 'ON':
		  if elapsetime >=41400: # 11h 30m passed
            manualWaterOut = 'OFF'
			ctrComp('alloff')
	      else:
		    if water_level >10200:
			  manualWaterOut = 'OFF'
			  ctrComp('alloff')
			else:
			  ctrComp('waterin')
		else:
		  elapse_pump = int(time.time()) - recordTime['plasttime']
		  if elapsetime >= 43200: # 12h passed
		    time_wo = (int(time.time())- recordTime['wotime']) if recordTime['wostart']==True else 0
            if(time_wo >= 300) and (recordTime['wostart']==True):  #5m passed from water-out 
			  recentFull= 'OFF'
			  fullTime = None
              recordTime.update(wostart=False,pstart=False,wotime=None,ptime=None,plasttime=None)
			  ctrComp('alloff')
			elif recordTime['wostart']==False:
			  recordTime.update(wotime=int(time.time()), wostart=True)
			  ctrComp('waterout')
			else:
			  ctrComp('waterout')
		  elif elapse_pump >= 3600: # 1h passes from last pump
		    time_pump = (int(time.time())- recordTime['ptime']) if recordTime['pstart']==True else 0
			if (time_pump >= 180) and (recordTime['pstart']==True):
			  recordTime.update(pstart=False,ptime=None,plasttime=int(time.time()))
			  ctrComp('alloff')
			elif recordTime['pstart']==False:
			  recordTime.update(ptime=int(time.time()), pstart=True)
              ctrComp('pump')
			else:
			  ctrComp('pump')
		  else:
		    pass
    elif STATE == 'handoper':
	  # determine LED state
	  if LED == 'ON':
	    digitalWrite(ledPin,HIGH)
	  else:	# LED OFF
	    digitalWrite(ledPin,LOW)
	  if WATER == 'out':  #manually water-out process
	    manualWaterOut = 'ON'
		ctrComp('waterout')
	  elif WATER == 'in':  #manually water-in process
	    if water_level <= 1000:
		  ctrComp('waterin')
		elif recentFull == 'OFF':
		  recentFull = 'ON'
		  fullTime =int(time.time())  
		  recordTime['plasttime'] = fullTime  
		  manualWaterOut = 'OFF'
		  ctrComp('alloff')
		else:
		  manualWaterOut = 'OFF'
		  ctrComp('alloff')
      elif PUMP == 'on':
	    if water_level > 900:
		  ctrComp('pump')
		else:
		  print("DANGER: not enough water to pump")
		  ctrComp('alloff')
      else:
	    ctrComp('alloff')
    else: #STATE == start
	  # determine LED state
	  if LED == 'ON':
	    digitalWrite(ledPin,HIGH)
	  else:	# LED OFF
	    digitalWrite(ledPin,LOW)		
#-------------------------- Controller_end----------------------#

  # for sending message
  device_message = {}
  device_message['water_level'] = water_level	
  device_sdid = config['device_id'] 
  ts = None
  # Construct a Message Object for request
  data_instance = artikcloud.Message(device_message, device_sdid, ts)
  # Send Message
  try:
    if TRACE > 4:
      pprint(artikcloud.configuration.auth_settings())			
    api_response = api_instance.send_message(data_instance)  # Send Message
	if TRACE > 4:
      pprint(api_response)									
  except ApiException as e:
    pprint("Exception when calling MessagesApi->send_message: %s\n" % e)

#=====================main()_definition_end=====================#
  
if __name__ == "__main__":
  # initialize
  for i in (ledPin, waterInPin, waterOutPin, pumpPin):
    digitalPinMode(i, OUTPUT)
    digitalWrite(i, LOW)

  while True:
    main(sys.argv[1:])
    time.sleep(3)
