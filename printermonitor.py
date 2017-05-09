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
  Requires
    A. pysnmp sudo pip install pysnmp
       I think this is installed with the SNMP component in HA, but just in case:
       sudo pip install pysnmp        

  Installation
  1. Copy this file our appdaemon application directory
  2. Make input_sliders in your ha configuration.yaml file as follows
    A. input_slider.Printername_markercolor
       for example
         input_slider.oshp1_black # happens to be a monochrome laserjet
         input_slider.dsp1hp_black # inkjet color printer black cartridge
         input_slider.dsp1hp_yellow # inkjet color printer yellow cartridge
         input_slider.dsp1hp_cyan # inkjet color printer cyan cartridge
         input_slider.dsp1yp_magenta # inkjet color printer magenta cartridge
    B. each input slider should have 
       min value of 0
       max value of 100
       initial value of 0
    C. setup a group for each printer and put the input sliders associated with that 
       printer in the group. Use the printer name as the group name.  For example
       my printers are named ofhp1 (office hp 1) and dsp1hp (downstairs printer 1 HP). So
       my groups are named entity_ofhp1, and entity_dsp1hp respectively.
    D. in your appdaemon.cfg file
      [printermonitor]
      module = printermonitor
      class = printermonitor
      community = <read only community name> defaults to public
      PrinterAddresses = ["192.168.2.247","192.168.2.249"]
    E. Restart HA

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
    self.host_name_odi="1.3.6.1.2.1.1.5"
    self.printer_name_odi='1.3.6.1.2.1.1.5.0'
    self.marker_base_odi="1.3.6.1.2.1.43.11.1.1"
    self.marker_name_suffix="6"
    self.marker_capacity_suffix="8"
    self.marker_current_level_suffix="9"
    if "community" in self.args:
      self.community=self.args["community"]
    else:
      self.log("community not provided in appdaemon.cfg file, defaulting to public")
      self.community="public"
    self.log("Community set to {}".format(self.community))
    
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
      hostname=self.getsnmptree(ipa,self.host_name_odi)     
      result=self.getsnmptree(ipa,self.marker_base_odi)
      num_markers=0
      for mkrs in result:
        #self.log("mkrs={}".format(mkrs))
        namebase=mkrs.find(self.marker_base_odi+"."+self.marker_name_suffix)
        strangevalue=mkrs[len(self.marker_base_odi+"."+self.marker_name_suffix)+1:][:1]
        #self.log("strangevalue={}".format(strangevalue))
        if namebase>=0:
          num_markers=num_markers+1
          #self.log("num_markers={}".format(num_markers))
      #num_markers=0
      #if len(result)%4==0:
      #   num_markers=4
      #else:
      #   num_markers=1
      if result=={}:
        self.log("printer ipa={} not responding".format(ipa))
        continue
      result.update(hostname)                       # combine everything together in one dictionary
      printername=result[self.printer_name_odi].strip().lower()
      self.log("hostname={}".format(printername))
      #num_markers=int((len(result)-1)/8)             # there are 8 attributes for each printer

      low=False                                      # we are not low on ink or toner
      for i in range (1, num_markers+1):             # loop through markers could be ink or toner
        tail="."+strangevalue+"."+str(i)
        
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
        
        #prtMarkerSupplies	1.3.6.1.2.1.43.11
        #prtMarkerSuppliesTable	1.3.6.1.2.1.43.11.1
        #prtMarkerSuppliesEntry	1.3.6.1.2.1.43.11.1.1
        #prtMarkerSuppliesIndex	1.3.6.1.2.1.43.11.1.1.1          - one entry here
        #Each of the following entries is followed by either an indicator of whether
        #it's a monocrome printer or color.  It will end in a 1.1 if it is monocrome
        #if it's color, it will end with a .0. and a range of 1-4 one digit for each color
        #so suppliesdescription for a color printer would look similar to this
        # 1.3.6.1.2.1.43.11.1.1.6.0.1 black
        # 1.3.6.1.2.1.43.11.1.1.6.0.2 Yellow
        # 1.3.6.1.2.1.43.11.1.1.6.0.3 Cyan
        # 1.3.6.1.2.1.43.11.1.1.6.0.4 Magenta
        #prtMarkerSuppliesMarkerIndex	1.3.6.1.2.1.43.11.1.1.2
        #prtMarkerSuppliesColorantIndex	1.3.6.1.2.1.43.11.1.1.3
        #prtMarkerSuppliesClass	1.3.6.1.2.1.43.11.1.1.4
        #prtMarkerSuppliesType	1.3.6.1.2.1.43.11.1.1.5
        #prtMarkerSuppliesDescription	1.3.6.1.2.1.43.11.1.1.6
        #prtMarkerSuppliesSupplyUnit	1.3.6.1.2.1.43.11.1.1.7
        #prtMarkerSuppliesMaxCapacity	1.3.6.1.2.1.43.11.1.1.8
        #prtMarkerSuppliesLevel	1.3.6.1.2.1.43.11.1.1.9
     
        # put odi data into variables to make later statements easier to understand and read
        markername=result[self.marker_base_odi+"."+self.marker_name_suffix+tail]
        markername=markername[:markername.find(" ")].lower()
        markercapacity=int(result[self.marker_base_odi+"."+self.marker_capacity_suffix+tail])
        markercurrent=int(result[self.marker_base_odi+"."+self.marker_current_level_suffix+tail])
        markerpctfull=int((markercurrent/markercapacity)*100)
        
        if markerpctfull < 10:         # < 10% marker means we are low on something
          low=True
          
        self.log("{}-{} is {:0.2f}% full".format(self.marker_base_odi+"."+self.marker_name_suffix+tail,
                                    markername,
                                    (markercurrent/markercapacity)*100))
        #self.log("markerpctfull={}".format(markerpctfull))                                    
        # set values for input_sliders                            
        self.select_value("input_slider."+printername+"_"+markername,markerpctfull if markerpctfull>0 else 1)
      # outside marker loop, set group state to either low or ok ink levels
      self.set_state("group.entity_"+printername,state="Low" if low==True else "Ok")

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
                          CommunityData(self.community, mpModel=0),
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
