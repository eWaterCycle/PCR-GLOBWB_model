#! /usr/bin/env python
from configuration import Configuration
from pcrglobwb import PCRGlobWB
import pcraster as pcr
import numpy as np
from currTimeStep import ModelTime
import sys
import logging
from duplicity.dup_temp import SrcIter

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
        
        self.shape = pcr.pcr2numpy(self.model.landmask, 1e20).shape
        
        logger.info("Shape of maps is %s", str(self.shape))
        
        logger.info("PCRGlobWB Initialized")
        
    def update (self):
        timestep = self.model_time.timeStepPCR
        
        self.model_time.update(timestep + 1)
        
        self.model.read_forcings()
        self.model.update(report_water_balance=True)
        
        
        #numpy = pcr.pcr2numpy(self.model.landSurface.satDegUpp000005, 1e20)
        numpy = pcr.pcr2numpy(self.model.landSurface.satDegUpp000005, np.NaN)
        print numpy.shape
        print numpy
        
        
    
    def update_until (self, time):
        pass
    
    def finalize (self):
        pass
    def run_model (self):
        pass

    def get_var_type (self, long_var_name):
        return 'f32'
    
    def get_var_units (self, long_var_name):
        pass
    
    def get_var_rank (self, long_var_name):
        return 

    def get_value (self, long_var_name):
        
        if (long_var_name == "top_layer_soil_saturation"):
            print pcr.pcr2numpy(self.model.landSurface.satDegUpp000005, np.NaN)
            print "\n"
            print pcr.pcr2numpy(self.model.landSurface.satDegUpp000005, np.NaN).flat
            print "\n"
            return pcr.pcr2numpy(self.model.landSurface.satDegUpp000005, np.NaN)
        else:
            raise Exception("unknown var name" + long_var_name)
    
    
    def get_value_at_indices (self, long_var_name, inds):
        pass
    
    
    def get_satDegUpp000005_from_observation(self):

        # assumption for observation values
        # - this should be replaced by values from the ECV soil moisture value (sattelite data)
        # - uncertainty should be included here
        # - note that the value should be between 0.0 and 1.0
        observed_satDegUpp000005 = pcr.min(1.0,\
                                   pcr.max(0.0,\
                                   pcr.normal(pcr.boolean(1)) + 1.0))
        return observed_satDegUpp000005                           

    def set_satDegUpp000005(self, src):
        mask = np.isnan(src)
        src[mask] = 1e20
        observed_satDegUpp000005 = pcr.numpy2pcr(pcr.Scalar, src, 1e20)

        # ratio between observation and model
        ratio_between_observation_and_model = pcr.ifthenelse(self.model.landSurface.satDegUpp000005> 0.0, 
                                                             observed_satDegUpp000005 / \
                                                             self.model.landSurface.satDegUpp000005, 0.0) 
        
        # updating upper soil states for all lad cover types
        for coverType in self.model.landSurface.coverTypes:
            
            # correcting upper soil state (storUpp000005)
            self.model.landSurface.landCoverObj[coverType].storUpp000005 *= ratio_between_observation_and_model
            
            # if model value = 0.0, storUpp000005 is calculated based on storage capacity (model parameter) and observed saturation degree   
            self.model.landSurface.landCoverObj[coverType].storUpp000005  = pcr.ifthenelse(self.model.landSurface.satDegUpp000005 > 0.0,\
                                                                                           self.model.landSurface.landCoverObj[coverType].storUpp000005,\
                                                                                           observed_satDegUpp000005 * self.model.landSurface.parameters.storCapUpp000005) 
    
    def set_value (self, long_var_name, src):
        
        logger.info("setting value for %s", long_var_name)
        
        logger.info("setting value shape %s", src.shape)
        
        if (long_var_name == "top_layer_soil_saturation"):
            self.set_satDegUpp000005(src)
        else:
            raise Exception("unknown var name" + long_var_name)
            
            
    def set_value_at_indices (self, long_var_name, inds, src):
        pass

    def get_component_name (self):
        pass
    def get_input_var_names (self):
        pass
    
    def get_output_var_names (self):
        
        state = self.model.getAllState();
        
        logger.info(state)
        

    def get_start_time (self):
        pass
    def get_end_time (self):
        pass
    def get_current_time (self):
        pass
    
    def get_grid_shape (self, long_var_name):
        return self.shape
    
    def get_grid_spacing (self, long_var_name):
        pass
    def get_grid_origin (self, long_var_name):
        pass
    
    
    
