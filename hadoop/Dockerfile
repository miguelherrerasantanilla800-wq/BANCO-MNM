FROM apache/hadoop:3.3.6 AS hadoop

FROM python:3.11-slim-bookworm

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends bash openjdk-17-jre-headless procps \
    && groupadd --system --gid 1000 hadoop \
    && useradd --system --uid 1000 --gid hadoop --create-home hadoop \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY --from=hadoop --chown=hadoop:hadoop /opt/hadoop /opt/hadoop
COPY --chown=hadoop:hadoop core-site.xml hdfs-site.xml yarn-site.xml mapred-site.xml /opt/hadoop/etc/hadoop/

RUN mkdir -p /hadoop/dfs/name /hadoop/dfs/data /hadoop/mapred/history /tmp/hadoop-yarn \
    && chown -R hadoop:hadoop /hadoop /tmp/hadoop-yarn /opt/hadoop

ENV HADOOP_HOME=/opt/hadoop \
    HADOOP_CONF_DIR=/opt/hadoop/etc/hadoop \
    HADOOP_COMMON_HOME=/opt/hadoop \
    HADOOP_HDFS_HOME=/opt/hadoop \
    HADOOP_MAPRED_HOME=/opt/hadoop \
    HADOOP_YARN_HOME=/opt/hadoop \
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    JAVA_TOOL_OPTIONS="--add-opens=java.base/java.lang=ALL-UNNAMED" \
    PATH=/opt/hadoop/bin:/opt/hadoop/sbin:/usr/lib/jvm/java-17-openjdk-amd64/bin:$PATH

USER hadoop
WORKDIR /opt/hadoop
