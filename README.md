# Logger
Simple Logger for all docker containers in my server. Created for learning CICD Pipelines with Docker and Github Actions. 


Allows for search and filtering of logs based on containers.


Docker run example:

``` 
docker run \
   -d \
   -v /var/run/docker.sock:/var/run/docker.sock \
   -p 8000:8000 \
   aldn0975/logger:latest
```

Compose:
```
services:
  log-manager:
    image: "aldn0975/logger:latest"
    volumes:
      - //var/run/docker.sock:/var/run/docker.sock:ro  # Mount the socket as Read-Only if you want
    environment:
      - PYTHONUNBUFFERED=1
    ports:
      - "8000:8000"
    restart: always
```

Binds to the docker sock in your docker environment. Runs a simple web app that shows all of the logs from your docker environment.
No database currently so it can show up to 500 lines only from the time that it runs. 

## Current TODO:
~~~
Add simple database
Add Export to file (plaintext, csv, etc)
~~~