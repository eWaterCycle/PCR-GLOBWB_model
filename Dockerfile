# DockerFile for PCR-GLOB model. The ini-file should be mounted as config.ini,
# the input data root directory should be mounted as /data
FROM ewatercycle/pcraster-container:421

MAINTAINER Gijs van den Oord <g.vandenoord@esciencecenter.nl>

RUN apt-get update -y && apt install -y python3-pip
RUN pip3 install netCDF4 Cython

COPY . /opt/PCR-GLOBWB_model/

VOLUME /data
VOLUME /config.ini

ENV PYTHONPATH /usr/local/python/:/root/pcraster/python
ENV PYTHONIOENCODING UTF-8

WORKDIR /opt/PCR-GLOBWB_model/model

RUN python3 setup.py install

CMD ["python3","./deterministic_runner.py","/config.ini","/data"]
