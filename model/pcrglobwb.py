import os
import sys
import math
import gc

import pcraster as pcr

import virtualOS as vos
import meteo
import landSurface
import groundwater
import routing


import logging
logger = logging.getLogger(__name__)

'''
Created on Oct 25, 2013

@author: Niels Drost
'''
class PCRGlobWB(object):
    
    def __init__(self, configuration, currTimeStep, initialState = None):
        self._configuration = configuration
        self._modelTime = currTimeStep
        
        pcr.setclone(configuration.cloneMap)

        # Read the ldd map.
        self.lddMap = vos.readPCRmapClone(\
                  configuration.routingOptions['lddMap'],
                  configuration.cloneMap,configuration.tmpDir,configuration.globalOptions['inputDir'],True)
        #ensure ldd map is correct, and actually of type "ldd"
        self.lddMap = pcr.lddrepair(pcr.ldd(self.lddMap))
 
        if configuration.globalOptions['landmask'] != "None":
            self.landmask = vos.readPCRmapClone(\
            configuration.globalOptions['landmask'],
            configuration.cloneMap,configuration.tmpDir,configuration.globalOptions['inputDir'])
        else:
            self.landmask = pcr.defined(self.lddMap)
        
        # defining catchment areas
        self.catchment_class = 1.0
        
        # number of upperSoilLayers:
        self.numberOfSoilLayers = int(configuration.landSurfaceOptions['numberOfUpperSoilLayers'])

        self.createSubmodels(initialState)
         
    @property
    def configuration(self):
        return self._configuration
         
    def createSubmodels(self, initialState):

        # initializing sub modules
        self.meteo = meteo.Meteo(self._configuration,self.landmask,initialState)
        self.landSurface = landSurface.LandSurface(self._configuration,self.landmask,initialState)
        self.groundwater = groundwater.Groundwater(self._configuration,self.landmask,initialState)
        self.routing = routing.Routing(self._configuration, initialState, self.lddMap)
 
        # short name for every land cover type (needed for file name)
        self.shortNames = ['f','g','p','n']
        
        
    def dumpState(self, outputDirectory):
        #write all state to disk to facilitate restarting

        state = self.getState()
        
        landSurfaceState = state['landSurface']
        
        for coverType, coverTypeState in landSurfaceState.iteritems():
            for variable, map in coverTypeState.iteritems():
                vos.writePCRmapToDir(\
                map,\
                 str(variable)+"_"+coverType+"_"+
                 str(self._modelTime.fulldate)+".map",\
                 outputDirectory)
                
        groundWaterState = state['groundwater']
        for variable, map in groundWaterState.iteritems():
            vos.writePCRmapToDir(\
             map,\
             str(variable)+"_"+
             str(self._modelTime.fulldate)+".map",\
             outputDirectory)

        routingState = state['routing']
        for variable, map in routingState.iteritems():
            vos.writePCRmapToDir(\
             map,\
             str(variable)+"_"+
             str(self._modelTime.fulldate)+".map",\
             outputDirectory)

    def dumpStateDir(self, outputDirectory):
        #write all state to disk to facilitate restarting.
        #uses a directory rather than filenames to denote the date

        if outputDirectory == None:
            return

        stateDirectory = outputDirectory + self._modelTime.fulldate

        if not os.path.exists(stateDirectory):
            os.makedirs(stateDirectory)
        
        state = self.getState()
        
        landSurfaceState = state['landSurface']
        
        for coverType, coverTypeState in landSurfaceState.iteritems():
            for variable, map in coverTypeState.iteritems():
                vos.writePCRmapToDir(\
                map,\
                 str(variable)+"_"+coverType+".map",\
                 stateDirectory)
                
        groundWaterState = state['groundwater']
        for variable, map in groundWaterState.iteritems():
            vos.writePCRmapToDir(\
             map,\
             str(variable)+"_"+".map",\
             stateDirectory)

        routingState = state['routing']
        for variable, map in routingState.iteritems():
            vos.writePCRmapToDir(\
             map,\
             str(variable)+"_"+".map",\
             stateDirectory)
        
    def resume(self):
        #restore state from disk. used when restarting
        pass


    #FIXME: implement
    def setState(self, state):
        logger.error("cannot set state")

        
    def report_summary(self, landWaterStoresAtBeginning, landWaterStoresAtEnd,\
                             surfaceWaterStoresAtBeginning, surfaceWaterStoresAtEnd):

        # set total to 0 on first day of the year                             
        if self._modelTime.doy == 1 or self._modelTime.isFirstTimestep():

            # set all accumulated variables to zero

            self.precipitationAcc  = pcr.ifthen(self.landmask, pcr.scalar(0.0)) 

            for var in self.landSurface.fluxVars: vars(self)[var+'Acc'] = pcr.ifthen(self.landmask, pcr.scalar(0.0))            

            self.baseflowAcc                  = pcr.ifthen(self.landmask, pcr.scalar(0.0))

            self.surfaceWaterInfAcc           = pcr.ifthen(self.landmask, pcr.scalar(0.0))

            self.runoffAcc                    = pcr.ifthen(self.landmask, pcr.scalar(0.0))
            self.unmetDemandAcc               = pcr.ifthen(self.landmask, pcr.scalar(0.0))

            self.waterBalanceAcc              = pcr.ifthen(self.landmask, pcr.scalar(0.0))
            self.absWaterBalanceAcc           = pcr.ifthen(self.landmask, pcr.scalar(0.0))

            # non irrigation water use (unit: m) 
            self.nonIrrigationWaterUseAcc     = pcr.ifthen(self.landmask, pcr.scalar(0.0))
            
            # non irrigation return flow to water body and water body evaporation (unit: m) 
            self.nonIrrReturnFlowAcc          = pcr.ifthen(self.landmask, pcr.scalar(0.0))
            self.waterBodyEvaporationAcc      = pcr.ifthen(self.landmask, pcr.scalar(0.0))

            # surface water input/loss volume (m3) and outgoing volume (m3) at pits 
            self.surfaceWaterInputAcc         = pcr.ifthen(self.landmask, pcr.scalar(0.0))
            self.dischargeAtPitAcc            = pcr.ifthen(self.landmask, pcr.scalar(0.0))
            
            # also save the storages at the first day of the year (or the first time step)
            # - land surface storage (unit: m)
            self.storageAtFirstDay            = pcr.ifthen(self.landmask, landWaterStoresAtBeginning)
            # - channel storages (unit: m3)
            self.channelVolumeAtFirstDay      = pcr.ifthen(self.landmask, surfaceWaterStoresAtBeginning)
            
        # accumulating until the last day of the year:
        self.precipitationAcc   += self.meteo.precipitation
        for var in self.landSurface.fluxVars: vars(self)[var+'Acc'] += vars(self.landSurface)[var]            

        self.baseflowAcc         += self.groundwater.baseflow

        self.surfaceWaterInfAcc  += self.groundwater.surfaceWaterInf
        
        self.runoffAcc           += self.routing.runoff
        self.unmetDemandAcc      += self.groundwater.unmetDemand

        self.waterBalance = \
          (landWaterStoresAtBeginning - landWaterStoresAtEnd +\
           self.meteo.precipitation + self.landSurface.irrGrossDemand + self.groundwater.surfaceWaterInf -\
           self.landSurface.actualET - self.routing.runoff - self.groundwater.nonFossilGroundwaterAbs)

        self.waterBalanceAcc    += self.waterBalance
        self.absWaterBalanceAcc += pcr.abs(self.waterBalance)

        # consumptive water use for non irrigation demand (m)
        self.nonIrrigationWaterUseAcc += self.routing.nonIrrWaterConsumption 
        
        self.nonIrrReturnFlowAcc      += self.routing.nonIrrReturnFlow
        self.waterBodyEvaporationAcc  += self.routing.waterBodyEvaporation

        self.surfaceWaterInputAcc     += self.routing.local_input_to_surface_water  # unit: m3
        self.dischargeAtPitAcc        += self.routing.outgoing_volume_at_pits       # unit: m3
        
        if self._modelTime.isLastDayOfYear() or self._modelTime.isLastTimeStep():

	#TODO: hack for eWatercycle operational spinup
	if self._modelTime.isLastDayOfMonth() or self._modelTime.isLastTimestep():
            self.dumpStateDir(self._configuration.endStateDir)


        if self._modelTime.isLastDayOfYear():
            self.dumpState(self._configuration.endStateDir)
            
            logger.info("")
            msg = 'The following summary values do not include storages in surface water bodies (lake, reservoir and channel storages).'
            logger.info(msg)                        # TODO: Improve these water balance checks. 

            totalCellArea = vos.getMapTotal(pcr.ifthen(self.landmask,self.routing.cellArea))
            msg = 'Total area = %e km2'\
                    % (totalCellArea/1e6)
            logger.info(msg)

            deltaStorageOneYear = vos.getMapVolume( \
                                     pcr.ifthen(self.landmask,landWaterStoresAtBeginning) - \
                                     pcr.ifthen(self.landmask,self.storageAtFirstDay),
                                     self.routing.cellArea)
            msg = 'Delta total storage days 1 to %i in %i = %e km3 = %e mm'\
                % (    int(self._modelTime.doy),\
                       int(self._modelTime.year),\
                       deltaStorageOneYear/1e9,\
                       deltaStorageOneYear*1000/totalCellArea)
            logger.info(msg)

            variableList = ['precipitation',
                            'baseflow',
                            'surfaceWaterInf',
                            'runoff',
                            'unmetDemand']
            variableList += self.landSurface.fluxVars
            variableList += ['waterBalance','absWaterBalance','irrigationWaterUse','nonIrrigationWaterUse']                

            # consumptive water use for irrigation (unit: m)
            self.irrigationWaterUseAcc = vos.getValDivZero(self.irrGrossDemandAcc,\
                                                           self.precipitationAcc + self.irrGrossDemandAcc) * self.actualETAcc

            for var in variableList:
                volume = vos.getMapVolume(\
                            self.__getattribute__(var + 'Acc'),\
                            self.routing.cellArea)
                msg = 'Accumulated %s days 1 to %i in %i = %e km3 = %e mm'\
                    % (var,int(self._modelTime.doy),\
                           int(self._modelTime.year),volume/1e9,volume*1000/totalCellArea)
                logger.info(msg)

            logger.info("")
            msg = 'The following summary is for surface water bodies.'
            logger.info(msg) 

            deltaChannelStorageOneYear = vos.getMapTotal( \
                                         pcr.ifthen(self.landmask,surfaceWaterStoresAtEnd) - \
                                         pcr.ifthen(self.landmask,self.channelVolumeAtFirstDay))
            msg = 'Delta surface water storage days 1 to %i in %i = %e km3 = %e mm'\
                % (    int(self._modelTime.doy),\
                       int(self._modelTime.year),\
                       deltaChannelStorageOneYear/1e9,\
                       deltaChannelStorageOneYear*1000/totalCellArea)
            logger.info(msg)
            
            variableList = ['nonIrrReturnFlow','waterBodyEvaporation']
            for var in variableList:
                volume = vos.getMapVolume(\
                            self.__getattribute__(var + 'Acc'),\
                            self.routing.cellArea)
                msg = 'Accumulated %s days 1 to %i in %i = %e km3 = %e mm'\
                    % (var,int(self._modelTime.doy),\
                           int(self._modelTime.year),volume/1e9,volume*1000/totalCellArea)
                logger.info(msg)


            # surface water balance check 
            surfaceWaterInputTotal = vos.getMapTotal(self.surfaceWaterInputAcc)
            msg = 'Accumulated %s days 1 to %i in %i = %e km3 = %e mm'\
                    % ("surfaceWaterInput",int(self._modelTime.doy),\
                           int(self._modelTime.year),surfaceWaterInputTotal/1e9,surfaceWaterInputTotal*1000/totalCellArea)
            logger.info(msg)

            dischargeAtPitTotal = vos.getMapTotal(self.dischargeAtPitAcc)
            msg = 'Accumulated %s days 1 to %i in %i = %e km3 = %e mm'\
                    % ("dischargeAtPitTotal",int(self._modelTime.doy),\
                           int(self._modelTime.year),dischargeAtPitTotal/1e9,      dischargeAtPitTotal*1000/totalCellArea)
            logger.info(msg)

            surfaceWaterBalance = surfaceWaterInputTotal - dischargeAtPitTotal + deltaChannelStorageOneYear 
            msg = 'Accumulated %s days 1 to %i in %i = %e km3 = %e mm'\
                    % ("surfaceWaterBalance",int(self._modelTime.doy),\
                           int(self._modelTime.year),surfaceWaterBalance/1e9,      surfaceWaterBalance*1000/totalCellArea)
            logger.info(msg)
            
                
        
    def getState(self):
        result = {}
        
        result['landSurface'] = self.landSurface.getState()
        result['groundwater'] = self.groundwater.getState()
        result['routing'] = self.routing.getState()
        
        return result
        
    def getPseudoState(self):
        result = {}
        
        result['landSurface'] = self.landSurface.getPseudoState()
        result['groundwater'] = self.groundwater.getPseudoState()
        result['routing'] = self.routing.getPseudoState()
        
        return result
    
    def getAllState(self):
        result = {}
        
        result['landSurface'] = self.landSurface.getState()
        result['landSurface'].update(self.landSurface.getPseudoState())
        
        result['groundwater']= self.groundwater.getState()
        result['groundwater'].update(self.groundwater.getPseudoState())
        
        result['routing'] = self.routing.getState()
        result['routing'].update(self.routing.getPseudoState())
        
        return result
        
    
    def totalLandWaterStores(self):
        # unit: m, not including surface water bodies
        
        
        if self.numberOfSoilLayers == 2: total = \
                self.landSurface.interceptStor  +\
                self.landSurface.snowFreeWater  +\
                self.landSurface.snowCoverSWE   +\
                self.landSurface.topWaterLayer  +\
                self.landSurface.storUpp        +\
                self.landSurface.storLow        +\
                self.groundwater.storGroundwater

        if self.numberOfSoilLayers == 3: total = \
                self.landSurface.interceptStor  +\
                self.landSurface.snowFreeWater  +\
                self.landSurface.snowCoverSWE   +\
                self.landSurface.topWaterLayer  +\
                self.landSurface.storUpp000005  +\
                self.landSurface.storUpp005030  +\
                self.landSurface.storLow030150  +\
                self.groundwater.storGroundwater
        
        total = pcr.ifthen(self.landmask, total)
        
        return total
    
    def totalSurfaceWaterStores(self):
        # unit: m3, only surface water bodies
        
        return pcr.ifthen(self.landmask, self.routing.channelStorage)

    def checkLandSurfaceWaterBalance(self, storesAtBeginning, storesAtEnd):
		
		# for the entire stores from snow + interception + soil + groundwater, but excluding river/routing
		# 
        # - incoming fluxes (unit: m)
        precipitation   = pcr.ifthen(self.landmask, self.meteo.precipitation)
        irrGrossDemand  = pcr.ifthen(self.landmask, self.landSurface.irrGrossDemand)
        surfaceWaterInf = pcr.ifthen(self.landmask, self.groundwater.surfaceWaterInf)
		# 
        # - outgoing fluxes (unit: m)
        actualET                = pcr.ifthen(self.landmask, self.landSurface.actualET)
        runoff                  = pcr.ifthen(self.landmask, self.routing.runoff)
        nonFossilGroundwaterAbs = pcr.ifthen(self.landmask, self.groundwater.nonFossilGroundwaterAbs)   
		# 
        vos.waterBalanceCheck([precipitation,surfaceWaterInf,irrGrossDemand],\
                              [actualET,runoff,nonFossilGroundwaterAbs],\
                              [storesAtBeginning],\
                              [storesAtEnd],\
                              'all stores (snow + interception + soil + groundwater), but except river/routing',\
                               True,\
                               self._modelTime.fulldate,threshold=1e-3)
    
    def read_forcings(self):
        logger.info("reading forcings for time %s", self._modelTime)
        self.meteo.read_forcings(self._modelTime)
    
    def update(self, report_water_balance=False):
        logger.info("updating model to time %s", self._modelTime)
        
        if (report_water_balance):
            landWaterStoresAtBeginning    = self.totalLandWaterStores()    # not including surface water bodies
            surfaceWaterStoresAtBeginning = self.totalSurfaceWaterStores()     

        self.meteo.update(self._modelTime)                                         
        self.landSurface.update(self.meteo,self.groundwater,self.routing,self._modelTime)      
        self.groundwater.update(self.landSurface,self.routing,self._modelTime)
        self.routing.update(self.landSurface,self.groundwater,self._modelTime,self.meteo)

        if (report_water_balance):
            landWaterStoresAtEnd    = self.totalLandWaterStores()          # not including surface water bodies
            surfaceWaterStoresAtEnd = self.totalSurfaceWaterStores()     
            
            # water balance check for the land surface water part
            self.checkLandSurfaceWaterBalance(landWaterStoresAtBeginning, landWaterStoresAtEnd)
            
            # TODO: include water balance checks for the surface water part and combination of both land surface and surface water parts

            self.report_summary(landWaterStoresAtBeginning, landWaterStoresAtEnd,\
                                surfaceWaterStoresAtBeginning, surfaceWaterStoresAtEnd)
