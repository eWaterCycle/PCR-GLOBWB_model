#! /usr/bin/env python
from configuration import Configuration
from pcrglobwb import PCRGlobWB
import pcraster as pcr
import numpy as np
from currTimeStep import ModelTime
import sys
import logging
from reporting import Reporting
import math
import datetime as dt

logger = logging.getLogger(__name__)

class BmiGridType (object):
    UNKNOWN = 0
    UNIFORM = 1
    RECTILINEAR = 2
    STRUCTURED = 3
    UNSTRUCTURED = 4

class BMI (object):
    def initialize (self, file):
        pass
    def update (self):
        pass
    def update_until (self, time):
        pass
    def finalize (self):
        pass
    def run_model (self):
        pass

    def get_var_type (self, long_var_name):
        pass
    def get_var_units (self, long_var_name):
        pass
    def get_var_rank (self, long_var_name):
        pass

    def get_value (self, long_var_name):
        pass
    def get_value_at_indices (self, long_var_name, inds):
        pass
    def set_value (self, long_var_name, src):
        pass
    def set_value_at_indices (self, long_var_name, inds, src):
        pass

    def get_component_name (self):
        pass
    def get_input_var_names (self):
        pass
    def get_output_var_names (self):
        pass

    def get_start_time (self):
        pass
    def get_end_time (self):
        pass
    def get_current_time (self):
        pass

class BmiRaster (BMI):
    def get_grid_shape (self, long_var_name):
        pass
    def get_grid_spacing (self, long_var_name):
        pass
    def get_grid_origin (self, long_var_name):
        pass

class BmiRectilinear (BMI):
    def get_grid_shape (self, long_var_name):
        pass
    def get_grid_x (self, long_var_name):
        pass
    def get_grid_y (self, long_var_name):
        pass
    def get_grid_z (self, long_var_name):
        pass

class BmiStructured (BMI):
    def get_grid_shape (self, long_var_name):
        pass
    def get_grid_x (self, long_var_name):
        pass
    def get_grid_y (self, long_var_name):
        pass
    def get_grid_z (self, long_var_name):
        pass

class BmiUnstructured (BMI):
    def get_grid_x (self, long_var_name):
        pass
    def get_grid_y (self, long_var_name):
        pass
    def get_grid_z (self, long_var_name):
        pass
    def get_grid_connectivity (self, long_var_name):
        pass
    def get_grid_offset (self, long_var_name):
        pass

class BmiPCRGlobWB(BmiRaster):
    
    def date_to_mjd(self, date):
        """
        Taken from: https://gist.github.com/jiffyclub/1294443
        
        Convert a date to Julian Day.
        
        Algorithm from 'Practical Astronomy with your Calculator or Spreadsheet', 
            4th ed., Duffet-Smith and Zwart, 2011.
        
        Parameters
        ----------
        year : int
            Year as integer. Years preceding 1 A.D. should be 0 or negative.
            The year before 1 A.D. is 0, 10 B.C. is year -9.
            
        month : int
            Month as integer, Jan = 1, Feb. = 2, etc.
        
        day : float
            Day, may contain fractional part.
        
        Returns
        -------
        jd : float
            Julian Day
            
        Examples
        --------
        Convert 6 a.m., February 17, 1985 to Julian Day
        
        >>> date_to_jd(1985,2,17.25)
        2446113.75
        
        """
        
        year = date.year
        month = date.month
        day = date.day
        
        if month == 1 or month == 2:
            yearp = year - 1
            monthp = month + 12
        else:
            yearp = year
            monthp = month
        
        # this checks where we are in relation to October 15, 1582, the beginning
        # of the Gregorian calendar.
        if ((year < 1582) or
            (year == 1582 and month < 10) or
            (year == 1582 and month == 10 and day < 15)):
            # before start of Gregorian calendar
            B = 0
        else:
            # after start of Gregorian calendar
            A = math.trunc(yearp / 100.)
            B = 2 - A + math.trunc(A / 4.)
            
        if yearp < 0:
            C = math.trunc((365.25 * yearp) - 0.75)
        else:
            C = math.trunc(365.25 * yearp)
            
        D = math.trunc(30.6001 * (monthp + 1))
        
        jd = B + C + D + day + 1720994.5
        
        return jd - 2400000.5
    
    def initialize (self, fileName):
        print "PCRGlobWB Initializing"
    
        self.configuration = Configuration(fileName)
        
        #set start and end time based on configuration
        self.model_time = ModelTime()
        self.model_time.getStartEndTimeSteps(self.configuration.globalOptions['startTime'],
                                      self.configuration.globalOptions['endTime'])
        
        self.model_time.update(0)
        
        initial_state = None
         
        self.model = PCRGlobWB(self.configuration, self.model_time, initial_state)
        
        self.reporting = Reporting(self.configuration, self.model, self.model_time)
        
        self.shape = pcr.pcr2numpy(self.model.landmask, 1e20).shape
        
        logger.info("Shape of maps is %s", str(self.shape))
        
        logger.info("PCRGlobWB Initialized")
        
    def update (self):
        timestep = self.model_time.timeStepPCR
        
        self.model_time.update(timestep + 1)
        
        self.model.read_forcings()
        self.model.update(report_water_balance=True)
        self.reporting.report()
        
#         #numpy = pcr.pcr2numpy(self.model.landSurface.satDegUpp000005, 1e20)
#         numpy = pcr.pcr2numpy(self.model.landSurface.satDegUpp000005, np.NaN)
#         print numpy.shape
#         print numpy
        
    
    def update_until (self, time):
        while self.get_current_time() + 0.001 < time:
            self.update()
    
    def finalize (self):
        pass
    
    def run_model (self):
        self.update_until(self.get_end_time())

    def get_var_type (self, long_var_name):
        return 'f8'
    
    def get_var_units (self, long_var_name):
        return '1'
    
    def get_var_rank (self, long_var_name):
        return 0

    def get_value (self, long_var_name):
        logger.info("getting value for var %s", long_var_name)
        
        if (long_var_name == "top_layer_soil_saturation"):
            
            if hasattr(self.model.landSurface, 'satDegUpp000005'):
                value = pcr.pcr2numpy(self.model.landSurface.satDegUpp000005, np.NaN)
            else:
                logger.info("model has not run yet, returning empty state for top_layer_soil_saturation")
                value = pcr.pcr2numpy(pcr.scalar(0.0), np.NaN)
            
            #print "getting var", value
            #sys.stdout.flush()
            
            doubles = value.astype(np.float64)
            
            #print "getting var as doubles!!!!", doubles
            
            result = np.flipud(doubles)
            
            #print "getting var as doubles flipped!!!!", result
            #sys.stdout.flush()
            
            return result
        else:
            raise Exception("unknown var name" + long_var_name)
    
    
    def get_value_at_indices (self, long_var_name, inds):
        pass
    
    
#     def get_satDegUpp000005_from_observation(self):
# 
#         # assumption for observation values
#         # - this should be replaced by values from the ECV soil moisture value (sattelite data)
#         # - uncertainty should be included here
#         # - note that the value should be between 0.0 and 1.0
#         observed_satDegUpp000005 = pcr.min(1.0,\
#                                    pcr.max(0.0,\
#                                    pcr.normal(pcr.boolean(1)) + 1.0))
#         return observed_satDegUpp000005                           

    def set_satDegUpp000005(self, src):
        mask = np.isnan(src)
        src[mask] = 1e20
        observed_satDegUpp000005 = pcr.numpy2pcr(pcr.Scalar, src, 1e20)
        
        pcr.report(observed_satDegUpp000005, "observed.map")
        
        constrained_satDegUpp000005 = pcr.min(1.0,pcr.max(0.0,observed_satDegUpp000005))
        
        pcr.report(constrained_satDegUpp000005, "constrained.map")
        
        pcr.report(self.model.landSurface.satDegUpp000005, "origmap.map")
        diffmap = constrained_satDegUpp000005 - self.model.landSurface.satDegUpp000005
        pcr.report(diffmap, "diffmap.map")
        

        # ratio between observation and model
        ratio_between_observation_and_model = pcr.ifthenelse(self.model.landSurface.satDegUpp000005> 0.0, 
                                                             constrained_satDegUpp000005 / \
                                                             self.model.landSurface.satDegUpp000005, 0.0) 
        
        # updating upper soil states for all lad cover types
        for coverType in self.model.landSurface.coverTypes:
            
            # correcting upper soil state (storUpp000005)
            self.model.landSurface.landCoverObj[coverType].storUpp000005 *= ratio_between_observation_and_model
            
            # if model value = 0.0, storUpp000005 is calculated based on storage capacity (model parameter) and observed saturation degree   
            self.model.landSurface.landCoverObj[coverType].storUpp000005  = pcr.ifthenelse(self.model.landSurface.satDegUpp000005 > 0.0,\
                                                                                           self.model.landSurface.landCoverObj[coverType].storUpp000005,\
                                                                                           constrained_satDegUpp000005 * self.model.landSurface.parameters.storCapUpp000005) 
    
    def set_value (self, long_var_name, src):
        
        logger.info("setting value for %s", long_var_name)
        
        logger.info("dumping state to %s", self.configuration.endStateDir)
        self.model.dumpStateDir(self.configuration.endStateDir + "/pre/")

        #print "got value to set", src
        
        #make sure the raster is the right side up
        src = np.flipud(src)
        
        #print "flipped", src
        
        #cast to pcraster precision
        src = src.astype(np.float32)

        #print "as float 32", src
        
        sys.stdout.flush()
        
        logger.info("setting value shape %s", src.shape)
        
        if (long_var_name == "top_layer_soil_saturation"):
            self.set_satDegUpp000005(src)
        else:
            raise Exception("unknown var name" + long_var_name)
        
        #HACK: write state here to facilitate restarting tomorrow
        logger.info("dumping state to %s", self.configuration.endStateDir)
        self.model.dumpStateDir(self.configuration.endStateDir + "/post/")
            
    def set_value_at_indices (self, long_var_name, inds, src):
        pass

    def get_component_name (self):
        return "pcrglobwb"
    
    def get_input_var_names (self):
        return ["top_layer_soil_saturation"]
    
    def get_output_var_names (self):
        return ["top_layer_soil_saturation"]

    def get_start_time (self):
        return self.date_to_mjd(self.model_time.startTime)
        
    def get_end_time (self):
        return self.date_to_mjd(self.model_time.endTime)
    
    def get_current_time (self):
        return self.date_to_mjd(self.model_time.currTime)
    
    def get_grid_shape (self, long_var_name):
        return self.shape
    
    def get_grid_spacing (self, long_var_name):
        
        cellsize = pcr.clone().cellSize()
        
        return np.array([cellsize, cellsize])
    
    def get_grid_origin (self, long_var_name):
        north = pcr.clone().north()
        cellSize = pcr.clone().cellSize()
        nrRows = pcr.clone().nrRows()
        
        south = north - (cellSize * nrRows)
        
        west = pcr.clone().west()
        
        return np.array([south, west])

    
    
    
