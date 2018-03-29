PCR-GLOBWB
==========

PCR-GLOBWB (PCRaster Global Water Balance) is a large-scale hydrological model intended for global to regional studies and developed at the Department of Physical Geography, Utrecht University (Netherlands).

contact: Edwin Sutanudjaja (E.H.Sutanudjaja@uu.nl).

Please also see the file README.txt.

Using PCR-GLOBWB deterministic runner from the docker image:
```
docker pull ewatercycle/pcr-globwb_model
docker run -v <path-to-ini-file>:/config.ini -v <root-data-directory>:/data ewatercycle/pcr-globwb_model
```
The inputDir in your ini-file should be called /data. The root-data-directory is the reference path for all relative
paths in the ini-file. 
