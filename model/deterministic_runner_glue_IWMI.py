#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

import pcraster as pcr
from pcraster.framework import DynamicModel
from pcraster.framework import DynamicFramework

from configuration import Configuration
from currTimeStep import ModelTime
from reporting import Reporting
from spinUp import SpinUp

from pcrglobwb import PCRGlobWB

import logging
logger = logging.getLogger(__name__)

class DeterministicRunner(DynamicModel):

    def __init__(self, configuration, modelTime, initialState = None, system_argument = None):
        DynamicModel.__init__(self)

        self.modelTime = modelTime        
        self.model = PCRGlobWB(configuration, modelTime, initialState)
        self.reporting = Reporting(configuration, self.model, modelTime)
        
        # the model will set paramaters based on global pre-multipliers given in the argument:
        if system_argument != None: self.adusting_parameters(configuration, system_argument)

    def adusting_parameters(self, configuration, system_argument): 

        logger.info("Adjusting some model parameters based on given values in the system argument.")
        
        # global pre-multipliers given in the argument:
        multiplier_for_minSoilDepthFrac = float(system_argument[4])
        multiplier_for_kSat             = float(system_argument[5])
        multiplier_for_recessionCoeff   = float(system_argument[6])
        multiplier_for_degreeDayFactor  = float(system_argument[7])    
        
        # saving global pre-multipliers to the log file:
        msg  = "\n" 
        msg += "\n" 
        msg += "Multiplier values used: "+"\n" 
        msg += "For minSoilDepthFrac           : "+str(multiplier_for_minSoilDepthFrac)+"\n"
        msg += "For kSat (log-scale)           : "+str(multiplier_for_kSat            )+"\n"
        msg += "For recessionCoeff (log-scale) : "+str(multiplier_for_recessionCoeff  )+"\n"
        msg += "For degreeDayFactor            : "+str(multiplier_for_degreeDayFactor )+"\n"
        logger.info(msg)
        # - also to a txt file 
        f = open("multiplier.txt","w") # this will be stored in the "map" folder of the 'outputDir' (as we set the current working directory to this "map" folder, see configuration.py)
        f.write(msg)
        f.close()

        # set paramaters "kSat" and "recessionCoeff" based on pre-multipliers
        self.model.landSurface.parameters.kSatUpp = pcr.max(0.0, (10**(multiplier_for_kSat)) * self.model.landSurface.parameters.kSatUpp)
        self.model.landSurface.parameters.kSatLow = pcr.max(0.0, (10**(multiplier_for_kSat)) * self.model.landSurface.parameters.kSatLow)
        self.model.groundwater.recessionCoeff     = pcr.min(1.0, pcr.max(0.0, (10**(multiplier_for_recessionCoeff)) * self.model.groundwater.recessionCoeff))
        # - also saving the adjusted parameter maps to pcraster files
        # - these will be stored in the "map" folder of the 'outputDir' (as we set the current working directory to this "map" folder, see configuration.py)
        pcr.report(self.model.landSurface.parameters.kSatUpp, "kSatUpp.map")
        pcr.report(self.model.landSurface.parameters.kSatLow, "kSatLow.map") 
        pcr.report(self.model.groundwater.recessionCoeff    , "recessionCoeff.map")
        
        # set paramaters "minSoilDepthFrac" and "degreeDayFactor" based on pre-multipliers
        # - also saving the adjusted parameter maps to pcraster files
        # - these will be stored in the "map" folder of the 'outputDir' (as we set the current working directory to this "map" folder, see configuration.py)
        for coverType in self.model.landSurface.coverTypes:
            # 
            # - for minSoilDepthFrac - values will be limited by maxSoilDepthFrac
            self.model.landSurface.landCoverObj[coverType].minSoilDepthFrac = pcr.min(1.0, pcr.min(\
                                                                              pcr.max(0.0, multiplier_for_minSoilDepthFrac *\
                                                           self.model.landSurface.landCoverObj[coverType].minSoilDepthFrac),\
                                                           self.model.landSurface.landCoverObj[coverType].maxSoilDepthFrac))
            pcraster_filename = "minSoilDepthFrac"+ "_" + coverType + ".map" 
            pcr.report(self.model.landSurface.landCoverObj[coverType].minSoilDepthFrac, pcraster_filename)
            #
            # - for degreeDayFactor
            self.model.landSurface.landCoverObj[coverType].degreeDayFactor  = pcr.max(0.0, multiplier_for_degreeDayFactor  *\
                                                           self.model.landSurface.landCoverObj[coverType].degreeDayFactor)
            pcraster_filename = "degreeDayFactor" + "_" + coverType + ".map" 
            pcr.report(self.model.landSurface.landCoverObj[coverType].degreeDayFactor , pcraster_filename)

    def initial(self): 
        pass

    def dynamic(self):

        # re-calculate current model time using current pcraster timestep value
        self.modelTime.update(self.currentTimeStep())

        # update model (will pick up current model time from model time object)
        self.model.read_forcings()
        self.model.update(report_water_balance=True)
        
        #do any needed reporting for this time step        
        self.reporting.report()

def main():
    
    # get the full path of configuration/ini file given in the system argument
    iniFileName   = os.path.abspath(sys.argv[1])
    
    # debug option
    debug_mode = False
    if len(sys.argv) > 2: 
        if sys.argv[2] == "debug": debug_mode = True
    
    # object to handle configuration/ini file
    configuration = Configuration(iniFileName = iniFileName, \
                                  debug_mode = debug_mode, \
                                  no_modification = False)      
    # modfiying 'outputDir' (based on the given system argument
    configuration.globalOptions['outputDir'] += "/"+str(sys.argv[3])+"/" 
    configuration.set_configuration()

    # timeStep info: year, month, day, doy, hour, etc
    currTimeStep = ModelTime() 

    # object for spin_up
    spin_up = SpinUp(configuration)            
    
    # spinning-up 
    noSpinUps = int(configuration.globalOptions['maxSpinUpsInYears'])
    initial_state = None
    if noSpinUps > 0:
        
        logger.info('Spin-Up #Total Years: '+str(noSpinUps))

        spinUpRun = 0 ; has_converged = False
        while spinUpRun < noSpinUps and has_converged == False:
            spinUpRun += 1
            currTimeStep.getStartEndTimeStepsForSpinUp(
                    configuration.globalOptions['startTime'],
                    spinUpRun, noSpinUps)
            logger.info('Spin-Up Run No. '+str(spinUpRun))
            deterministic_runner = DeterministicRunner(configuration, currTimeStep, initial_state, sys.argv)
            
            all_state_begin = deterministic_runner.model.getAllState() 
            
            dynamic_framework = DynamicFramework(deterministic_runner,currTimeStep.nrOfTimeSteps)
            dynamic_framework.setQuiet(True)
            dynamic_framework.run()
            
            all_state_end = deterministic_runner.model.getAllState() 
            
            has_converged = spin_up.checkConvergence(all_state_begin, all_state_end, spinUpRun, deterministic_runner.model.routing.cellArea)
            
            initial_state = deterministic_runner.model.getState()
    #
    # Running the deterministic_runner (excluding DA scheme)
    currTimeStep.getStartEndTimeSteps(configuration.globalOptions['startTime'],
                                      configuration.globalOptions['endTime'])
    
    logger.info('Transient simulation run started.')
    deterministic_runner = DeterministicRunner(configuration, currTimeStep, initial_state, sys.argv)
    
    dynamic_framework = DynamicFramework(deterministic_runner,currTimeStep.nrOfTimeSteps)
    dynamic_framework.setQuiet(True)
    dynamic_framework.run()

if __name__ == '__main__':
    sys.exit(main())
