# DockertFile for the Massive-PotreeConverter
FROM ewatercycle/pcraster-container:latest
MAINTAINER Gijs van den Oord <g.vandenoord@esciencecenter.nl>
COPY . /opt/
WORKDIR /opt
RUN pip install netCDF4
