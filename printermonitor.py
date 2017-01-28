#  Printermonitor -
#                   Monitor printers for low ink or toner level
#  Written by Chip Cox
#  Date 16Jan2017
##################################
#
#   27JAN2017 - updated to handle bulk snmp reads to take care of magenta issue
#
##################################
"""
  Installation
 
   1. Copy this file our appdaemon application directory
   2. Make groups in your ha configuration.yaml file as follows
      A. input_slider.Printername_markercolor
            input_slider.oshp1_black      # happens to be a monochrome laserjet
            input_slider.dsp1hp_black     # inkjet color printer
            input_slider.dsp1hp_yellow    # inkjet color printer
            input_slider.dsp1hp_cyan      # inkjet color printer
            input_slider.dsp1yp_magenta   # inkjet color printer
      B. each input slider should have 
      	    min value of 0
      	    max value of 100
      	    initial value of 0
      C. setup any groups you want to display the sliders.
      D. in your appdaemon.cfg file
            [printermonitor]
            module = printermonitor
            class = printermonitor
            PrinterAddresses = ["192.168.2.247","192.168.2.249"]
      E. Restart HA
    3. Requires
      A. pysnmp         sudo pip install pysnmp  
    
"""
##################################  
import appdaemon.appapi as appapi
from pysnmp.hlapi import *
            
class printermonitor(appapi.AppDaemon):

  #######################
  #
  #  Initialize (not much to do here
  # 
  ########################
  def initialize(self):
    self.check_printers()
    self.run_every(self.hourly_check_handler,self.datetime(),5*60)

  #######################
  #
  # run_every handler to check to see if the print status has changed.
  #
  #######################
  def hourly_check_handler(self,kwargs):
    self.check_printers()
    
  ########################
  #
  # main process to check the printers and update their status in HA
  #
  ########################
  def check_printers(self):
    ipalist=eval(self.args["PrinterAddresses"])    # get ip addresses from appdaemon.cfg file
    #self.log("ipalist={}".format(ipalist))
    for ipa in ipalist:                            # loop through addresses in list
      self.log("looking up printer {}".format(ipa))
      result={}
      # because we are using nextcmd we are starting with an odi one level prior to what we need
      hostname=self.getsnmptree(ipa,"1.3.6.1.2.1.1.5")     
      result=self.getsnmptree(ipa,"1.3.6.1.2.1.43.11.1.1")
      result.update(hostname)                       # combine everything together in one dictionary
  
      printername=result['1.3.6.1.2.1.1.5.0'].strip().lower()
      self.log("hostname={}".format(printername))
      num_markers=int((len(result)-1)/8)             # there are 8 attributes for each printer

      low=False                                      # we are not low on ink or toner
      for i in range (1, num_markers+1):             # loop through markers could be ink or toner
        if num_markers==1:                           # monochrome printer
          tail=".1."+str(i)
        else:                                        # color printer
          tail=".0."+str(i) 
        
        #This is just to document the information
        #
        #black ink is 97.98% full
        #yellow ink is 99.12% full
        #cyan ink is 99.15% full
        #magenta ink is 99.20% full
        #Black Cartridge HP CE278A is 46.00% full
        
        #
        # This is what our input sliders are called
        #- input_slider.dsp1hp_black
        #- input_slider.dsp1hp_cyan
        #- input_slider.dsp1hp_yellow
        #- input_slider.dsp1hp_magenta
     
        # put odi data into variables to make later statements easier to understand and read
        markername=result['1.3.6.1.2.1.43.11.1.1.6'+tail]
        markername=markername[:markername.find(" ")]
        markercapacity=int(result['1.3.6.1.2.1.43.11.1.1.8'+tail])
        markercurrent=int(result['1.3.6.1.2.1.43.11.1.1.9'+tail])
        markerpctfull=int((markercurrent/markercapacity)*100)
        
        if markerpctfull < 10:         # < 10% marker means we are low on something
          low=True
          
        self.log("{} is {:0.2f}% full".format(markername,
                                    (markercurrent/markercapacity)*100))
                                    
        # set values for input_sliders                            
        self.set_state("input_slider."+printername+"_"+markername,state=markerpctfull)
      # outside marker loop, set group state to either low or ok ink levels
      self.set_state("group."+printername,state="Low" if low==True else "Ok")

  #################################
  #
  #   read SNMP data for each ip address and return dictionary of results
  #
  #################################
  def getsnmptree(self,ipaddr,oid):
    resultDict={}
    
    # This actually does the snmp reading.  
    for (errorIndication,      # while no errors reading next value
       errorStatus,
       errorIndex,
       varBinds) in nextCmd(SnmpEngine(),
                          CommunityData('public', mpModel=0),
                          UdpTransportTarget((ipaddr, 161)),
                          ContextData(),
                          ObjectType(ObjectIdentity(oid)),
                          lexicographicMode=False):

      # handle errors                          
      if errorIndication:
        print(errorIndication)
        break
      elif errorStatus:
        print('%s at %s' % (errorStatus.prettyPrint(),
                            errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
        break
      else:   # no errors with SNMP lookup
        odistr={}
        odibind, valuebind=varBinds[0]     # start building our dictionary
        odistr[str(odibind)]=str(valuebind)
        #print("odistr={}".format(odistr))
        resultDict.update(odistr)
        #print("resultDict={}\n",format(resultDict))
        varBinds={}
    return(resultDict)     # return our dictionary
