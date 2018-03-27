# DockertFile for the Massive-PotreeConverter
FROM ewatercycle/pcraster-container:latest
MAINTAINER Gijs van den Oord <g.vandenoord@esciencecenter.nl>
COPY . /opt/PCR-GLOBWB_model/
WORKDIR /opt
RUN pip install netCDF4
