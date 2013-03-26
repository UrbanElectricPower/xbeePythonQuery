#! /usr/bin/python

import serial
import time, sys, random
from types import *
from xbee import XBee
from pymongo import Connection

# Things that need to be done:
#   data from header and body
#   make it work semi,kinda faster
#   database!!!!
#   Withdraw step number!!!
#   Documented Version 0.1.1

ser = serial.Serial(3,9600)
xbee = XBee(ser)

class Board(object):

    def __init__(self, address):
        self.address = address
        self.number = ord(address[-1:])
        self.cells = [0,0,0,0]
        self.LowestVoltage = None
        self.Lowest = False
        self.status = None
        self.resisters = None
        self.retries = 0

        ## Get the initial round of voltages
        self._getVoltInit()

    
    
    def _dataPush(self,payload):
        ## Function that interfaces with the serial port
        assert type(payload) is StringType , "Payload is not a string: %s" % 'payload'

        xbee.send('tx',dest_addr=self.address,data=payload)
            
        try: 
            self.frame = xbee.wait_read_frame()
            self._dataPull(self.frame)
        except AttributeError:
            if(self.retries < 3): 
                self.retries = self.retries + 1  
                self._dataPush(payload)
            else:
                print("A timeout has occured!")
    
    
    def _dataPull(self, das_frame):
        ## Extract data from the payload!

        self.rawData = das_frame['rf_data']
        self.data = self.rawData.replace('\x00','')
        self.data = self.data.split('|')
        self.header = self.data[0].split(',')
        try:
            self.resisters = ord(self.header[1])
        except:
            self.resisters = 0
        self.body = self.data[1].split(',')
    


    def _sortVoltages(self):
        if(sorted(self.body)[0] > 0):
            self.LowestVoltage = sorted(self.body)[0]

        else:
            for i in range(len(self.body)):
                if(sorted(self.body)[i] > 0):
                    self.LowestVoltage = sorted(self.body)[i]
        
        for voltage in range(len(self.body)):
            self.cells[voltage] = self.body[voltage]
        print self.cells
        print("The lowest voltage on board " + str(self.number) + " is " + str(self.LowestVoltage))
         
    
    def _getVoltInit(self):
        self._dataPush('v')
        self._sortVoltages()


    def setBleeders(self,drop):        
        if self.Lowest:
            self._dataPush('v')
            self._sortVoltages()
            self.status = "SelectBleeding"

        else:
            self._dataPush('V')
            self._sortVoltages()
            self.status = "AllBleeding"
        self.Lowest = False   


    def setHoldUpper(self,drop):
        self._dataPush("v"+str(drop))
        self._sortVoltages()
        self.status = "UpperVoltage"

    def setHoldLower(self,drop):
        self._dataPush("V"+str(drop))
        self._sortVoltages()
        self.status = "LowerVoltage"


    def setRecondition(self,drop):
        self._dataPush("D"+str(drop))
        self._sortVoltages()
        self.status = "Reconditioning"



###########################################################

Addresses = ['\x00\x01','\x00\x02','\x00\x03','\x00\x04','\x00\x05','\x00\x06','\x00\x07','\x00\x08']


Logicboards = [ Board(Addresses[i]) for i in range(len(Addresses))]

def getStep():
    try:
        conn = Connection('nightshops.info')
        print("Connected to DB")
        db = conn.String
        Step = db.stepArbin.find_one({"label":0})
        data = (Step['Step_Index'],Step['adj_Current'])           # Return the current step of the arbin
        return data
    except :
        print("There was an error connecting to the DB, will try again later")
        return (0,0)


def logPush(writer):
    try:
        conn = Connection('nightshops.info')
        db = conn.String
        print("Connected to DB")
        Logs = db.logsBMS
        Logs.insert(writer)         # Pushes the logged data from the BMS
        print("Pushed to the DB")
    except:
        print("There was an error connectiong to the DB, will try later")

def stepPush(writer):
    try:
        conn = Connection('nightshops.info')
        print("Connected to DB")
        db = conn.String
        stepBMS = db.stepBMS
        writer.update({'label':0})
        stepBMS.update({"label": 0},writer,True)        #Update the realtime BMS data
        print ("Pushed realtime data!")
    except :
        print("There was an error connecting to the DB, will try later")

##################################################################################################################3

while True:
    for cycle in range(0,20):

        writer = ({"Time":time.time()})
        lowVoltArray = []
        LowBoard = 1
        MinVoltage = int(Logicboards[0].LowestVoltage)
        try:
            currStep, voltDrop = getStep()
        except TypeError:
            print("STILL ERROR!!!")
            print(getStep())
            exit()
        print("Current step index is " + str(currStep))
        print("Voltage Drop Constant is " + str(voltDrop))


        for board in range(len(Logicboards)):
            lowVoltArray.append( [int(Logicboards[board].LowestVoltage), int(Logicboards[board].number) ] ) 
            
            print(str(Logicboards[board].number) + "'s data " + str(Logicboards[board].cells))
        
        lowVoltArray = sorted(lowVoltArray)  
        print lowVoltArray
        
        LowBoard = lowVoltArray[0][1]
        MinVoltage = lowVoltArray[0][0]

        for volt, board in lowVoltArray:
            if(volt == MinVoltage) or (board -1 == LowBoard):
                Logicboards[board - 1].Lowest = True
                print("Selected board " + str(board) )

            elif ( (volt - MinVoltage) < 20 ):
                Logicboards[board - 1].Lowest = True
                print("Selected board " + str(board) )

            else:
                print("No more boards qualify!")
                break

        print("\n\nBoard " + str(lowVoltArray[0][1]) + " has the lowest voltage with " + str(lowVoltArray[0][0]) + "\t")
        print "Going into the selection portion!\n\n\n"

        if(currStep == 18):
            print("Reconditioning the cells now!")

            for board in range(len(Logicboards)):
                Logicboards[board].setRecondition(voltDrop)
                print("Board " + str(Logicboards[board].number) +"'s voltage " + str(Logicboards[board].cells))
                print("Board " + str(Logicboards[board].number) +"'s Status " + str(Logicboards[board].status))
                writer.update({"Board_"+str(Logicboards[board].number):{"Cells":Logicboards[board].cells,"Resisters":Logicboards[board].resisters,"Status":Logicboards[board].status}})
            
        elif(int(MinVoltage) > 1620):
            print("Halting all operations this cycle, still above threshold voltage, MinVoltage is " + str(MinVoltage))
            for board in range(len(Logicboards)):
                Logicboards[board].setHoldUpper(voltDrop)
                print("Board " + str(Logicboards[board].number) +"'s voltage " + str(Logicboards[board].cells))
                print("Board " + str(Logicboards[board].number) +"'s Status " + str(Logicboards[board].status))
                writer.update({"Board_"+str(Logicboards[board].number):{"Cells":Logicboards[board].cells,"Resisters":Logicboards[board].resisters,"Status":Logicboards[board].status}})

        elif(int(MinVoltage) < 1400):
            print("Halting all operations this cycle, lowest voltage has been reached! MinVoltage is " + str(MinVoltage))
            for board in range(len(Logicboards)):
                Logicboards[board].setHoldLower(voltDrop)
                print("Board " + str(Logicboards[board].number) +"'s voltage " + str(Logicboards[board].cells))
                print("Board " + str(Logicboards[board].number) +"'s Status " + str(Logicboards[board].status))
                writer.update({"Board_"+str(Logicboards[board].number):{"Cells":Logicboards[board].cells,"Resisters":Logicboards[board].resisters,"Status":Logicboards[board].status}})
                
        else:
            print("All checks are good, going into Select Balancing")
            for board in range(len(Logicboards)):
                Logicboards[board].setBleeders(voltDrop)
                print("Board " + str(Logicboards[board].number) +"'s voltage " + str(Logicboards[board].cells))
                print("Board " + str(Logicboards[board].number) +"'s Status " + str(Logicboards[board].status))
                writer.update({"Board_"+str(Logicboards[board].number):{"Cells":Logicboards[board].cells,"Resisters":Logicboards[board].resisters,"Status":Logicboards[board].status}})
        stepPush(writer)
            
    logPush(writer)

 
## Limits If one cell hits 1400
## If step 15, send D

#for board in range(len(Logicboards)):
#    print(str(Logicboards[board].number) + "\t\t" + str(Logicboards[board].cells))
#    writer.update({str(Logicboards[board].number)+"_volt":Logicboards[board].cells},)
#
#
#try:
#    connect = Connection('Nightshops.info')
#    db = connect.String
#    Step = db.Step.find_one({"label":0})
#    Logs = db.String
#    Logs.insert(writer)
#    writer = ({"Time":datetime.datetime.now()})
#
#except:
#    print("Error while trying to connect to the DB")
#
#currStep = Step['Step_Index']
#
#
#
#
#if(currStep == 15):
#    
#    for cycles in range(0,25):
#        for board in range(1,len(Logicboards)):
#            Logicboards[board].setRecondition()
#            print(str(Logicboards[board].number)+"'s voltages are: " + str(Logicboards[board].cells))
#
#        writer.update({str(Logicboards[board].number)+"_volt":Logicboards[board].cells},str(Logicboard[board])+"_status":Logicboards[board].status) 
#
#else:
#
#    for cycles in range(0,25):
#
#        for board in LogicBoards:
#            Logicboards[board].setBleeders()
#            writer.update("Board_"+(Logicboards[board].LowestVoltage,Logicboards[board].number)
#        sorted(LowestCells)[0]
#
#
#
#
#
#
#
#
#
#
#
#
#


