FROM python:3-alpine

RUN \
    apk add --update gettext && \
    apk add --virtual build_deps libintl &&  \
    cp /usr/bin/envsubst /usr/local/bin/envsubst && \
    apk del build_deps

RUN apk --no-cache update && \
    apk --no-cache add ca-certificates sudo bash wget unzip make coreutils curl && \
    update-ca-certificates && \
    rm -rf /var/cache/apk/*

RUN \
    mkdir -p /aws && \
    apk -Uuv add groff less python py-pip && \
    pip install awscli && \
    apk --purge -v del py-pip && \
    rm /var/cache/apk/*

RUN mkdir -p /root/.aws
RUN mkdir -p /deployment
RUN mkdir -p /scripts

WORKDIR /

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY aws_config /root/.aws/config

ADD scripts /scripts

CMD ["python3", "--version"]
