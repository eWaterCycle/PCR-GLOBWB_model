#! /usr/bin/env python
import datetime
import logging
import sys
from imagemean import downsample

import numpy as np
import pcraster as pcr

from bmi import BmiGridType
from bmi import EBmi
from configuration import Configuration
from currTimeStep import ModelTime
from pcrglobwb import PCRGlobWB
from reporting import Reporting
import variable_list

logger = logging.getLogger(__name__)


class BmiPCRGlobWB(EBmi):

    epoch_start_date = datetime.date(1901, 1, 1)

    scalar_variables = ["flood_innundation_depth"]

    # we use the same epoch as pcrglobwb netcdf reporting
    @staticmethod
    def days_since_industry_epoch(model_time):
        return (model_time - BmiPCRGlobWB.epoch_start_date).days

    @staticmethod
    def in_modeltime(days_since_industry_epoch):
        return BmiPCRGlobWB.epoch_start_date + datetime.timedelta(days=days_since_industry_epoch)

    def __init__(self):
        self.configuration = None
        self.model = None
        self.model_time = None
        self.shape = None
        self.reporting = None

    def update_output(self):
        self.output = {}
        if self.model is None:
            return
        submodels = [self.model,
                     self.model.routing,
                     self.model.routing.WaterBodies,
                     self.model.landSurface,
                     self.model.meteo,
                     self.model.groundwater]

        for key in variable_list.netcdf_short_name:
            for submodel in submodels:
                if hasattr(submodel, key):
                    self.output[key] = submodel
                    break

    def calculate_shape(self):
        return pcr.clone().nrRows(), pcr.clone().nrCols()

    # BMI initialize (as a single step)
    def initialize(self, filename):
        self.initialize_config(filename)
        self.initialize_model("<empty>")

    # EBMI initialize (first step of two)
    def initialize_config(self, filename):
        logger.info("PCRGlobWB: initialize_config")
        try:
            self.configuration = Configuration(filename)
            pcr.setclone(self.configuration.cloneMap)

            # set start and end time based on configuration
            self.model_time = ModelTime()
            self.model_time.getStartEndTimeSteps(self.configuration.globalOptions['startTime'],
                                                 self.configuration.globalOptions['endTime'])
            self.model_time.update(0)
            self.shape = self.calculate_shape()
            logger.info("Shape of maps is %s", str(self.shape))
        except:
            import traceback
            traceback.print_exc()
            raise

    # EBMI initialize (second step of two)
    def initialize_model(self, source_directory):
        if self.model is not None:
            # already initialized
            return
        try:
            logger.info("PCRGlobWB: initialize_model, source dir %s is not used" % source_directory)
            initial_state = None
            self.model = PCRGlobWB(self.configuration, self.model_time, initial_state)
            self.reporting = Reporting(self.configuration, self.model, self.model_time)
            logger.info("Shape of maps is %s", str(self.shape))
            logger.info("PCRGlobWB Initialized")
        except:
            import traceback
            traceback.print_exc()
            raise

    def update(self):
        timestep = self.model_time.timeStepPCR
        if self.model is None:
            raise ValueError("Model has not been initialized, unable to start time stepping")
        self.model_time.update(timestep + 1)
        self.model.read_forcings()
        self.model.update(report_water_balance=True)
        if self.reporting is not None:
            self.reporting.report()

    def update_until(self, time):
        while self.get_current_time() + 0.001 < time:
            self.update()

    def update_frac(self, time_frac):
        raise NotImplementedError("pcrglobwb does not support fractional time steps")

    def finalize(self):
        self.configuration = None
        self.model = None
        self.model_time = None
        self.shape = None
        self.reporting = None

    def get_component_name(self):
        return "pcrglobwb"

    def get_input_var_names(self):
        return ["top_layer_soil_saturation"]

    def get_output_var_names(self):
        result = []
        for k in variable_list.netcdf_short_name:
            if hasattr(self.reporting, k):
                result.append(variable_list.netcdf_short_name[k])
        return result

    def get_var_type(self, var_name):
        if var_name == "soil_layer_count":
            return np.int32
        return np.float32

    def get_var_units(self, var_name):
        attribute = [n for n in variable_list.netcdf_short_name if variable_list.netcdf_short_name[n] == var_name][0]
        return variable_list.netcdf_unit[attribute]

    def get_var_rank(self, long_var_name):
        return 1

    def get_var_size(self, long_var_name):
        return self.get_var_itemsize(long_var_name)

    def get_var_itemsize(self, long_var_name):
        return self.get_var_type(long_var_name).itemsize

    def get_var_nbytes(self, long_var_name):
        return np.prod(self.get_grid_shape(long_var_name)) * self.get_var_itemsize(long_var_name)

    def get_start_time(self):
        return self.days_since_industry_epoch(self.model_time.startTime)

    def get_current_time(self):
        return self.days_since_industry_epoch(self.model_time.currTime)

    def get_end_time(self):
        return self.days_since_industry_epoch(self.model_time.endTime)

    def get_time_step(self):
        return 1

    # TODO: Add time zone info?
    def get_time_units(self):
        return "days since " + str(BmiPCRGlobWB.epoch_start_date)

    # TODO: Raises exception when attribute is missing, fix this
    def get_value(self, var_name):
        logger.info("getting value for var %s", var_name)
        attribute = [n for n in variable_list.netcdf_short_name if variable_list.netcdf_short_name[n] == var_name][0]
        pcrdata = getattr(self.reporting, attribute)
        if var_name in BmiPCRGlobWB.scalar_variables:
            return var_name
        remasked = pcr.ifthen(self.model.landmask, pcr.cover(pcrdata, 0.0))
        pcr.report(pcrdata, "value.map")
        pcr.report(remasked, "remasked.map")
        return np.flipud(pcr.pcr2numpy(remasked, np.NaN))

    def get_value_at_indices(self, long_var_name, indices):
        return self.get_value(long_var_name)[indices]

    def set_satDegUpp000005(self, src):
        mask = np.isnan(src)
        src[mask] = 1e20
        observed_satDegUpp000005 = pcr.numpy2pcr(pcr.Scalar, src, 1e20)

        pcr.report(observed_satDegUpp000005, "observed.map")

        constrained_satDegUpp000005 = pcr.min(1.0, pcr.max(0.0, observed_satDegUpp000005))

        pcr.report(constrained_satDegUpp000005, "constrained.map")

        pcr.report(self.model.landSurface.satDegUpp000005, "origmap.map")
        diffmap = constrained_satDegUpp000005 - self.model.landSurface.satDegUpp000005
        pcr.report(diffmap, "diffmap.map")

        # ratio between observation and model
        ratio_between_observation_and_model = pcr.ifthenelse(self.model.landSurface.satDegUpp000005 > 0.0,
                                                             constrained_satDegUpp000005 / \
                                                             self.model.landSurface.satDegUpp000005, 0.0)

        # updating upper soil states for all lad cover types
        for coverType in self.model.landSurface.coverTypes:
            # correcting upper soil state (storUpp000005)
            self.model.landSurface.landCoverObj[coverType].storUpp000005 *= ratio_between_observation_and_model

            # if model value = 0.0, storUpp000005 is calculated based on storage capacity (model parameter) and observed saturation degree   
            self.model.landSurface.landCoverObj[coverType].storUpp000005 = pcr.ifthenelse(
                self.model.landSurface.satDegUpp000005 > 0.0, \
                self.model.landSurface.landCoverObj[coverType].storUpp000005, \
                constrained_satDegUpp000005 * self.model.landSurface.parameters.storCapUpp000005)
            # correct for any scaling issues (value < 0 or > 1 do not make sense
            self.model.landSurface.landCoverObj[coverType].storUpp000005 = pcr.min(1.0, pcr.max(0.0,
                                                                                                self.model.landSurface.landCoverObj[
                                                                                                    coverType].storUpp000005))

    def set_value(self, long_var_name, src):

        if self.model is None or not hasattr(self.model.landSurface, 'satDegUpp000005'):
            logger.info("cannot set value for %s, as model has not run yet.", long_var_name)
            return

        logger.info("setting value for %s", long_var_name)

        # logger.info("dumping state to %s", self.configuration.endStateDir)
        # self.model.dumpStateDir(self.configuration.endStateDir + "/pre/")

        # print "got value to set", src

        # make sure the raster is the right side up
        src = np.flipud(src)

        # print "flipped", src

        # cast to pcraster precision
        src = src.astype(np.float32)

        # print "as float 32", src

        sys.stdout.flush()

        logger.info("setting value shape %s", src.shape)

        if long_var_name == "top_layer_soil_saturation":
            self.set_satDegUpp000005(src)
        else:
            raise Exception("unknown var name" + long_var_name)

        # write state here to facilitate restarting tomorrow
        # logger.info("dumping state to %s", self.configuration.endStateDir)
        # self.model.dumpStateDir(self.configuration.endStateDir + "/post/")

    def set_value_at_indices(self, long_var_name, inds, src):
        raise NotImplementedError

    # TODO: Nonstandard BMI: work with grid ids
    def get_grid_type(self, long_var_name):
        return BmiGridType.UNIFORM

    def get_grid_shape(self, long_var_name):
        return self.shape

    def get_grid_spacing(self, long_var_name):

        cellsize = pcr.clone().cellSize()

        return np.array([cellsize, cellsize])

    def get_grid_origin(self, long_var_name):

        north = pcr.clone().north()
        cellSize = pcr.clone().cellSize()
        nrRows = pcr.clone().nrRows()

        south = north - (cellSize * nrRows)

        west = pcr.clone().west()

        return np.array([south, west])

    def get_grid_x(self, long_var_name):
        raise ValueError

    def get_grid_y(self, long_var_name):
        raise ValueError

    def get_grid_z(self, long_var_name):
        raise ValueError

    def get_grid_connectivity(self, long_var_name):
        raise ValueError

    def get_grid_offset(self, long_var_name):
        raise ValueError

    # EBMI functions

    def set_start_time(self, start_time):
        self.model_time.setStartTime(self.in_modeltime(start_time))

    def set_end_time(self, end_time):
        self.model_time.setEndTime(self.in_modeltime(end_time))

    def get_attribute_names(self):
        raise NotImplementedError

    def get_attribute_value(self, attribute_name):
        raise NotImplementedError

    def set_attribute_value(self, attribute_name, attribute_value):
        raise NotImplementedError

    def save_state(self, destination_directory):
        logger.info("saving state to %s", destination_directory)
        self.model.dumpStateDir(destination_directory)

    def load_state(self, source_directory):
        raise NotImplementedError


class ScaledBmiPCRGlobWB(BmiPCRGlobWB):
    factor = 5

    def set_value(self, long_var_name, scaled_new_value):
        # small value for comparison
        current_value = self.get_value(long_var_name)

        print 'current value after scaling', current_value

        print 'value given by user', scaled_new_value

        diff = scaled_new_value - current_value

        print "diff now", diff

        # scale to model resolution
        big_diff = np.repeat(np.repeat(diff, self.factor, axis=0), self.factor, axis=1)

        big_current_value = BmiPCRGlobWB.get_value(self, long_var_name)

        new_value = big_current_value + big_diff

        # new_value = np.repeat(np.repeat(src, self.factor, axis=0), self.factor, axis=1)

        BmiPCRGlobWB.set_value(self, long_var_name, new_value)

    def calculate_shape(self):
        original = BmiPCRGlobWB.calculate_shape(self)

        logger.info("original shape !!! =" + str(original))

        return np.array([original[0] // self.factor, original[1] // self.factor])

    def get_value(self, long_var_name):
        big_map = BmiPCRGlobWB.get_value(self, long_var_name)

        print "getting value original shape " + str(big_map.shape)
        print "original size " + str(big_map.size)
        print "nans in original " + str(np.count_nonzero(np.isnan(big_map)))

        result = np.zeros(shape=self.get_grid_shape(long_var_name))

        downsample(big_map, result)

        print "getting value new shape " + str(result.shape)
        print "result size " + str(result.size)
        print "nans count in result " + str(np.count_nonzero(np.isnan(result)))

        print "getting value", result
        sys.stdout.flush()

        return result

    def get_grid_spacing(self, long_var_name):
        cellsize = pcr.clone().cellSize()

        return np.array([cellsize * self.factor, cellsize * self.factor])
