# DockerFile for PCR-GLOB model. The ini-file should be mounted as config.ini,
# the input data root directory should be mounted as /data
FROM ewatercycle/pcraster-container:latest
MAINTAINER Gijs van den Oord <g.vandenoord@esciencecenter.nl>
COPY . /opt/PCR-GLOBWB_model/
RUN pip install netCDF4 Cython
VOLUME /data
VOLUME /config.ini
ENV PYTHONPATH /usr/local/python/
WORKDIR /opt/PCR-GLOBWB_model/model
RUN python setup.py install
CMD ["python","./deterministic_runner.py","/config.ini","/data"]
