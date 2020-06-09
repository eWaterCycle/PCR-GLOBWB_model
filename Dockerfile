# DockerFile for PCR-GLOB model. The ini-file should be mounted as config.ini,
# the input data root directory should be mounted as /data
FROM ewatercycle/pcraster-container:latest
RUN apt-get update && apt-get upgrade -y
RUN pip install --upgrade pip
RUN pip install --upgrade numpy
RUN pip install netCDF4 Cython
COPY . /opt/PCR-GLOBWB_model/
VOLUME /data
VOLUME /config.ini
ENV PYTHONPATH /usr/local/python/
WORKDIR /opt/PCR-GLOBWB_model/model
RUN python setup.py install
CMD ["python","./deterministic_runner.py","/config.ini","/data"]
