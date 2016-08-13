#!/usr/bin/python
# -*- coding: utf-8 -*-

import ConfigParser
import optparse
import os
import sys
import virtualOS as vos
import time
import datetime
import shutil
import glob

import logging
logger = logging.getLogger(__name__)

class Configuration(object):

    def __init__(self, iniFileName, debug_mode = False, no_modification = True, relative_ini_meteo_paths = False):
        object.__init__(self)

        if iniFileName is None:
            raise Exception('Error: No configuration file specified')

        # timestamp of this run, used in logging file names, etc
        self._timestamp = datetime.datetime.now()
        
        # get the full path of iniFileName
        self.iniFileName = os.path.abspath(iniFileName)

        # debug option
        self.debug_mode = debug_mode

        # save cwd for later use, it may be changed later by some util functions
        self._cwd = os.getcwd()
        
        # read configuration from given file
        self.parse_configuration_file(self.iniFileName)

        #Added this option to be able to run PCRGlobWB in a sandbox with meteo files and initial conditions
        if relative_ini_meteo_paths:
            self.make_ini_meteo_paths_absolute()

        # if no_modification, set configuration directly (otherwise, the function/method  
        if no_modification: self.set_configuration()

    def set_configuration(self):

        # set all paths, clean output when requested
        self.set_input_files()
        self.create_output_directories()
        
        # initialize logging 
        self.initialize_logging()
        
        # copy ini file
        self.backup_configuration()

        # repair key names of initial conditions
        self.repair_ini_key_names()

    def make_ini_meteo_paths_absolute(self):
        for section in self.allSections:
            sec = getattr(self, section)

            for key, value in sec.iteritems():
                if key.endswith("Ini") and value is not None and value != 'None':
                    sec[key] = os.path.abspath(value)

                if key == 'precipitationNC' or key == 'temperatureNC':
                    sec[key] = os.path.abspath(value)

            for key, value in sec.iteritems():
                if key.endswith("Ini"):
                    if not os.path.exists(value):
                        print key, ":", value

    # make absolute to cwd when config was created
    def make_absolute_path(self, path):
        return os.path.normpath(os.path.join(self._cwd, path))

    def initialize_logging(self):
        """
        Initialize logging. Prints to both the console and a log file, at configurable levels
        """

        # set root logger to debug level        
        logging.getLogger().setLevel(logging.DEBUG)

        # logging format 
        formatter = logging.Formatter('%(asctime)s %(name)s %(levelname)s %(message)s')

        # default logging levels
        log_level_console    = "INFO"
        log_level_file       = "INFO"
        # order: DEBUG, INFO, WARNING, ERROR, CRITICAL
        
        # log level based on ini/configuration file:
        if "log_level_console" in self.globalOptions.keys():
            log_level_console = self.globalOptions['log_level_console']        
        if "log_level_file" in self.globalOptions.keys():
            log_level_file = self.globalOptions['log_level_file']        

        # log level for debug mode:
        if self.debug_mode == True: 
            log_level_console = "DEBUG"
            log_level_file    = "DEBUG"

        console_level = getattr(logging, log_level_console.upper(), logging.INFO)
        if not isinstance(console_level, int):
            raise ValueError('Invalid log level: %s', log_level_console)
        
        # create handler, add to root logger
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(console_level)
        logging.getLogger().addHandler(console_handler)

        # log file name
        log_filename = self.logFileDir + os.path.basename(self.iniFileName) + '_' + self._timestamp.isoformat() + '.log'

        file_level = getattr(logging, log_level_file.upper(), logging.DEBUG)
        if not isinstance(console_level, int):
            raise ValueError('Invalid log level: %s', log_level_file)

        # create handler, add to root logger
        file_handler = logging.FileHandler(log_filename)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(file_level)
        logging.getLogger().addHandler(file_handler)
        
        # file name for debug log 
        dbg_filename = self.logFileDir + os.path.basename(self.iniFileName) + '_' + self._timestamp.isoformat() + '.dbg'

        #create handler, add to root logger
        debug_handler = logging.FileHandler(dbg_filename)
        debug_handler.setFormatter(formatter)
        debug_handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(debug_handler)

        logger.info('Model run started at %s', self._timestamp)
        logger.info('Logging output to %s', log_filename)
        logger.info('Debugging output to %s', dbg_filename)
        
	

    def backup_configuration(self):
        
        # copy ini File to logDir:
        
        shutil.copy(self.iniFileName, self.logFileDir + \
                                     os.path.basename(self.iniFileName) + '_' + self._timestamp.isoformat() + '.ini')

    def parse_configuration_file(self, modelFileName):

        config = ConfigParser.ConfigParser()
        config.optionxform = str
        config.read(modelFileName)

        # all sections provided in the configuration/ini file
        self.allSections = config.sections()

        # read all sections 
        for sec in self.allSections:
            vars(self)[sec] = {}  # example: to instantiate self.globalOptions 
            options = config.options(sec)  # example: logFileDir
            for opt in options:
                val = config.get(sec, opt)  # value defined in every option 
                self.__getattribute__(sec)[opt] = val  # example: self.globalOptions['logFileDir'] = val
        
    def set_input_files(self):
        # fullPath of CLONE:
        self.cloneMap = vos.getFullPath(self.globalOptions['cloneMap'], \
                                        self.globalOptions['inputDir'])

        # Get the fullPaths of the INPUT directories/files mentioned in 
        #      a list/dictionary:         
        dirsAndFiles = ['precipitationNC', 'temperatureNC', 'refETPotFileNC']
        for item in dirsAndFiles:
            if self.meteoOptions[item] != "None":
                self.meteoOptions[item] = vos.getFullPath(self.meteoOptions[item], self.globalOptions['inputDir'])

    def create_output_directories(self):
        outputDir = self.make_absolute_path(self.globalOptions['outputDir'])
        
        
        # making the root/parent of OUTPUT directory:
        cleanOutputDir = False
        if cleanOutputDir:
            try: 
                shutil.rmtree(outputDir)
            except: 
                pass  # for new outputDir (not exist yet)

        try: 
            os.makedirs(outputDir)
        except: 
            pass  # for new outputDir (not exist yet)

        # making temporary directory:
        self.tmpDir = outputDir + '/tmp/'
        
        if os.path.exists(self.tmpDir):
            shutil.rmtree(self.tmpDir)
        os.makedirs(self.tmpDir)
        
        self.outNCDir = outputDir + '/netcdf/'
                                         
        if os.path.exists(self.outNCDir):
            shutil.rmtree(self.outNCDir)
        os.makedirs(self.outNCDir)

        # making backup for the python scripts used:
        self.scriptDir =  outputDir + '/scripts/'

        if os.path.exists(self.scriptDir):
            shutil.rmtree(self.scriptDir)
        os.makedirs(self.scriptDir)
        
        path_of_this_module = os.path.abspath(os.path.dirname(__file__))
                           
        for filename in glob.glob(os.path.join(path_of_this_module, '*.py')):
            shutil.copy(filename, self.scriptDir)

        # making log directory:
        self.logFileDir = outputDir + '/log/'
        
        cleanLogDir = True
        if os.path.exists(self.logFileDir) and cleanLogDir:
            shutil.rmtree(self.logFileDir)
        os.makedirs(self.logFileDir)

        # making endStateDir directory:
        self.endStateDir = outputDir + '/states/'
        
        if os.path.exists(self.endStateDir):
            shutil.rmtree(self.endStateDir)
        os.makedirs(self.endStateDir)

        # making pcraster maps directory:
        self.mapsDir = outputDir + '/maps/'
        
        cleanMapDir = True
        if os.path.exists(self.mapsDir) and cleanMapDir:
            shutil.rmtree(self.mapsDir)
        os.makedirs(self.mapsDir)
        
        # go to pcraster maps directory (so all pcr.report files will be saved in this directory) 
        os.chdir(self.mapsDir)


    def repair_ini_key_names(self):
        """
        Change key names for initial condition fields. 
        This is needed because Edwin was very stupid as once he changed some key names of initial conditions!  
        """

        # temporal resolution of the model
        self.timeStep = 1.0
        self.timeStepUnit = "day"
        if 'timeStep' in self.globalOptions.keys() and \
           'timeStepUnit'in self.globalOptions.keys():

            if float(self.globalOptions['timeStep']) != 1.0 or \
                     self.globalOptions['timeStepUnit'] != "day":
                logger.error('The model runs only on daily time step. Please check your ini/configuration file')
                self.timeStep     = None
                self.timeStepUnit = None
        
        # adjustment for limitAbstraction (to use only renewable water)
        if 'limitAbstraction' not in self.landSurfaceOptions.keys():
            self.landSurfaceOptions['limitAbstraction'] = False

        # irrigation efficiency map 
        if 'irrigationEfficiency' not in self.landSurfaceOptions.keys():
            logger.warning('The "irrigationEfficiency" map is not defined in the configuration file. This run assumes 100% efficiency.')
            self.landSurfaceOptions['irrigationEfficiency'] = "1.00"
        
        # adjustment for the option 'includeLivestockWaterDemand'
        if 'includeLivestockWaterDemand' not in self.landSurfaceOptions.keys():
            msg  = 'The option "includeLivestockWaterDemand" is not defined in the "landSurfaceOptions" of the configuration file. '
            msg += 'We assume "None" for this option. Livestock water demand is NOT included in the calculation.'
            logger.warning(msg)
            self.landSurfaceOptions['includeLivestockWaterDemand'] = "False"

        # adjustment for the option 'livestockWaterDemandFile'
        if (self.landSurfaceOptions['includeLivestockWaterDemand'] == "False") and ('livestockWaterDemandFile' not in self.landSurfaceOptions.keys()):
            msg  = 'The option "livestockWaterDemandFile" is not defined in the "landSurfaceOptions" of the configuration file. '
            msg += 'We assume "None" for this option. Livestock water demand is NOT included in the calculation.'
            logger.warning(msg)
            self.landSurfaceOptions['livestockWaterDemandFile'] = "None"

        # adjustment for desalinationWater
        if 'desalinationWater' not in self.landSurfaceOptions.keys():
            self.landSurfaceOptions['desalinationWater'] = "None"

        # adjustment for routingOptions
        if 'routingMethod' not in self.routingOptions.keys():
            logger.warning('The "routingMethod" is not defined in the "routingOptions" of the configuration file. "accuTravelTime" is used in this run.')
            iniItems.routingOptions['routingMethod'] = "accuTravelTime"

        # adjustment for option 'limitRegionalAnnualGroundwaterAbstraction'
        if 'pumpingCapacityNC' not in self.groundwaterOptions.keys():
            msg  = 'The "pumpingCapacityNC" (annual groundwater pumping capacity limit netcdf file) '
            msg += 'is not defined in the "groundwaterOptions" of the configuration file. '
            msg += 'We assume no annual pumping limit used in this run. '
            msg += 'It may result too high groundwater abstraction.'
            logger.warning(msg)
            self.groundwaterOptions['pumpingCapacityNC'] = "None"
        
        # adjustment for option 'allocationSegmentsForGroundSurfaceWater'
        if 'allocationSegmentsForGroundSurfaceWater' not in self.landSurfaceOptions.keys():
            msg  = 'The option "allocationSegmentsForGroundSurfaceWater" is not defined in the "groundwaterOptions" of the configuration file. '
            msg += 'We assume "None" for this option. Here, water demand will be satisfied by local source only. '
            logger.warning(msg)
            self.landSurfaceOptions['allocationSegmentsForGroundSurfaceWater'] = "None"
        
        # adjustment for option 'dynamicFloodPlain'
        if 'dynamicFloodPlain' in self.routingOptions.keys():
            msg  = 'The option "dynamicFloodPlain" is not defined in the "routingOptions" of the configuration file. '
            msg += 'We assume "False" for this option. Hence, the flood plain extent is constant for the entire simulation.'
            self.routingOptions['dynamicFloodPlain'] == "False"
        
        # adjustment for initial conditions in the routingOptions
        #
        if 'm2tChannelDischargeLongIni' in self.routingOptions.keys():
            self.routingOptions['m2tDischargeLongIni'] = self.routingOptions['m2tChannelDischargeLongIni']
        #
        if 'waterBodyStorageIni' not in self.routingOptions.keys():
            logger.warning("Note that 'waterBodyStorageIni' is not defined in the ini/configuration file will be calculated from 'channelStorageIni'.")
            self.routingOptions['waterBodyStorageIni'] = "None"
        if self.routingOptions['waterBodyStorageIni'] == "None":
            self.routingOptions['waterBodyStorageIni'] = None
        #
        if 'avgChannelDischargeIni' in self.routingOptions.keys():
            self.routingOptions['avgDischargeLongIni'] = self.routingOptions['avgChannelDischargeIni']
        #
        if 'm2tChannelDischargeIni' in self.routingOptions.keys():
            self.routingOptions['m2tDischargeLongIni'] = self.routingOptions['m2tChannelDischargeIni']
        #
        if 'avgBaseflowIni' in self.routingOptions.keys():
            self.routingOptions['avgBaseflowLongIni'] = self.routingOptions['avgBaseflowIni']

        if 'avgInflowLakeReservIni' in self.routingOptions.keys():
            self.routingOptions['avgLakeReservoirInflowShortIni'] = self.routingOptions['avgInflowLakeReservIni']

        if 'avgOutflowDischargeIni' in self.routingOptions.keys():
            self.routingOptions['avgLakeReservoirOutflowLongIni'] = self.routingOptions['avgOutflowDischargeIni']

        if 'avgDischargeShortIni' not in self.routingOptions.keys():
            logger.warning('The initial condition "avgDischargeShortIni" is not defined. "avgDischargeLongIni" is used in this run.')
            self.routingOptions['avgDischargeShortIni'] = self.routingOptions['avgDischargeLongIni']

        if 'avgSurfaceWaterInputLongIni' in self.routingOptions.keys():
            logger.warning("Note that avgSurfaceWaterInputLongIni is not used and not needed in the ini/configuration file.")
            
        if 'subDischargeIni' not in self.routingOptions.keys() or self.routingOptions['subDischargeIni'] == str(None):
            msg = 'The initial condition "subDischargeIni" is not defined. Either "avgDischargeShortIni" or "avgDischargeLongIni" is used in this run. '
            msg += 'Note that the "subDischargeIni" is only relevant if kinematic wave approaches are used.'
            logger.warning(msg)
            self.routingOptions['subDischargeIni'] = self.routingOptions['avgDischargeShortIni']

        if 'storGroundwaterFossilIni' not in self.groundwaterOptions.keys():
            msg  = 'The initial condition "storGroundwaterFossilIni" is not defined. '
            msg += 'Zero initial condition is assumed here. '
            logger.warning(msg)
            self.groundwaterOptions['storGroundwaterFossilIni'] = "0.0"
            # Note for Edwin: Zero initial condition cannot be used for the run with IWMI project.
             
        if 'avgTotalGroundwaterAbstractionIni' not in self.groundwaterOptions.keys():
            msg  = "The initial condition 'avgTotalGroundwaterAbstractionIni' is not defined, "
            msg += 'Zero initial condition is assumed here. '
            logger.warning(msg)
            self.groundwaterOptions['avgTotalGroundwaterAbstractionIni'] = "0.0"

        if 'avgTotalGroundwaterAllocationLongIni' not in self.groundwaterOptions.keys():
            msg  = "The initial condition 'avgTotalGroundwaterAllocationLongIni' is not defined, "
            msg += 'Zero initial condition is assumed here. '
            logger.warning(msg)
            self.groundwaterOptions['avgTotalGroundwaterAllocationLongIni'] = "0.0"

        if 'avgTotalGroundwaterAllocationShortIni' not in self.groundwaterOptions.keys():
            msg  = "The initial condition 'avgTotalGroundwaterAllocationShortIni' is not defined, "
            msg += 'Zero initial condition is assumed here. '
            logger.warning(msg)
            self.groundwaterOptions['avgTotalGroundwaterAllocationShortIni'] = "0.0"

        if 'avgNonFossilGroundwaterAllocationLongIni' not in self.groundwaterOptions.keys():
            msg  = "The initial condition 'avgNonFossilGroundwaterAllocationLongIni' is not defined, "
            msg += 'Zero initial condition is assumed here. '
            logger.warning(msg)
            self.groundwaterOptions['avgNonFossilGroundwaterAllocationLongIni'] = "0.0"

        if 'avgNonFossilGroundwaterAllocationShortIni' not in self.groundwaterOptions.keys():
            msg  = "The initial condition 'avgNonFossilGroundwaterAllocationShortIni' is not defined, "
            msg += "'avgNonFossilGroundwaterAllocationLongIni' is used here."
            logger.warning(msg)
            self.groundwaterOptions['avgNonFossilGroundwaterAllocationShortIni'] = self.groundwaterOptions['avgNonFossilGroundwaterAllocationLongIni']
        # TODO: repair key names while somebody wants to run 3 layer model but use 2 layer initial conditions (and vice versa). 
