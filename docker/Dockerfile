FROM redsoft-registry.gazprom-neft.local:5000/ubi7/ubi-minimal

WORKDIR /app

USER root

RUN curl -k https://nexus.gazprom-neft.local/repository/local-repo/CA/root-ca-gazprom-neft.pem --output /etc/pki/ca-trust/source/anchors/root-ca-gazprom-neft.crt && \
    curl -k https://nexus.gazprom-neft.local/repository/local-repo/CA/sub-ca.pem --output /etc/pki/ca-trust/source/anchors/sub-ca.crt && \
    update-ca-trust

RUN rm -rf /etc/yum.repos.d/*
COPY ["./docker/repos/*.repo", "/etc/yum.repos.d/"]

RUN microdnf install -y \
    yq \
    git \
    && microdnf clean all

COPY ["./src/git-sync.sh", "./git-sync.sh"]

CMD ["/bin/bash", "./git-sync.sh"]
