# Container Control Tool
***Based on runc***
## Usage
./containerctl \<command> \<parameters>
## Command
### create 
pull image and create a container

create
-n(\*) <container_name>
-i(\*) <image_name>
-t <image_tag(default=latest)> 
### start
start a stopped container

start
-n(*) <container_name>
### stop
stop a running container

stop
-n(*) <container_name>
### list
list all the containers created and their status
### delete
remove a container

delete
-n(*) <container_name>
