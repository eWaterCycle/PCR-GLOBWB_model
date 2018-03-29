# DockertFile for the Massive-PotreeConverter
FROM ewatercycle/pcraster-container:latest
MAINTAINER Gijs van den Oord <g.vandenoord@esciencecenter.nl>
COPY . /opt/PCR-GLOBWB_model/
RUN pip install netCDF4
VOLUME /data
VOLUME /config.ini
ENV PYTHONPATH /usr/local/python/
WORKDIR /opt/PCR-GLOBWB_model/model
CMD ["python","./deterministic_runner.py","/config.ini"]
