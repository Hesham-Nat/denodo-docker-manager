@echo off
if not exist data mkdir data

echo Fetching denodo-platform tags...
call gcloud container images list-tags gcr.io/denodo-container/denodo-platform > data/denodo_docker_images.txt

echo Fetching solution-manager tags...
call gcloud container images list-tags gcr.io/denodo-container/solution-manager > data/sm_docker_images.txt

echo Done.