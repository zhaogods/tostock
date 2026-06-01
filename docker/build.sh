#!/bin/sh

rm -rf tostock
rsync -av --progress ../../tostock . --exclude .git --exclude .idea --exclude *.md --exclude *.bat --exclude __pycache__ --exclude .gitignore --exclude tostock/cron --exclude tostock/img --exclude tostock/docker --exclude instock/cache --exclude instock/log --exclude instock/test --exclude .env --exclude instock/config/database.json --exclude instock/config/tushare.json
rm -rf cron
cp -r ../../tostock/cron .

DOCKER_NAME=zsswwz/tostock
TAG1=$(date "+%Y%m")
TAG2=latest

echo " docker build -f Dockerfile -t ${DOCKER_NAME} ."
docker build -f Dockerfile -t ${DOCKER_NAME}:${TAG1} -t ${DOCKER_NAME}:${TAG2} .
echo "#################################################################"
echo " docker push ${DOCKER_NAME} "

docker push ${DOCKER_NAME}:${TAG1}
docker push ${DOCKER_NAME}:${TAG2}